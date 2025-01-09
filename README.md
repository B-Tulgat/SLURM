
# HPC Documentation Overview
## Building Blocks

The HPC have the following stack, detoned by firstly the specific tool used and secondly by the type of  function it serves. 
Such as: "Django : REST API".

- **Django** : REST API
- **FreeIPA** : Identity and Access Management
    - **Kerberos** : Authentication
    - **LDAP** : Identity Data Storage
    - **SSSD** : Accessing Identity Data
    - **DNS** : Hostname Distribution
- **LXD Canonical** : Container and VM manager
   - **CephFS** : Storage Platform
    - **Cloud-Init** : Container/VM Setup Automization
    - **LXC** : Containerization
- **SLURM** : Workload Manager
    - **MariaDB** : Account and Accounting Database
    - **MUNGE** : Authentication Service

---
Below are stacks that have not been explored thoroughly therefore must be clearly seperated from above.
- **Jupyter Labs** : HPC Notebook Access
- ??? : Virtual Desktops
- ??? : Modules (Specific Python/R packages)

**Note**: Idented stacks are by design or have been widely used together. Meaning they are bundled/integrated quiet well together.

Powered by SLURM we have Auto-Scaling utilizing SLURM power-saving and elastic computing to provision nodes triggering node creation and deletion jobs. The effectiveness have been claimed by Dr. Ole Holm Nielsen in Techinical University of Denmark (https://slurm.schedmd.com/SLUG23/DTU-SLUG23.pdf). 


## Features

- Elastic and AutoScaling Node Provisioning
- Single Sign On
- Node Configuration Automization
- HPC Notebook Access

There are similiar stack that was developed by the same professor in TUD: https://slurm-web.com/, https://wiki.fysik.dtu.dk/Niflheim_system/SLURM/

## FreeIPA

FreeIPA is the source of truth for hostnames and corresponding addresses. This is needed because both accessing nodes and workload managing of SLURM utilizes hostnames for identifying nodes. Once a node is enrolled to FreeIPA server that hostname is propogated to all of FreeIPA clients which is all of HPC Cluster.

FreeIPA servers **require** NTP (chronyd) for synchronization and security reasons. Furthermore, most FreeIPA support and conversations  take place in RHEL distrobutions therefore it is preferable to install FreeIPA server on **RHEL distrobution** (Rocky 8,9) and Environment which supports NTP naturally which is **VM**.

Decision is then made to install FreeIPA server on **Rocky 8 VM**.

## Server Installation and Configuration

Install prerequisites
```bash
sudo dnf update -y
sudo dnf install -y ipa-server ipa-server-dns bind-dyndb-ldap
```

Setup hostname. This hostname is for FreeIPA server to be identified by region name "example.com" will be what you will use as your region throughout the naming scheme of your hostnames thus by extension your NodeNames of SLURM.

```bash
sudo hostnamectl set-hostname ipa-server.amon.com
```

Generally

```bash
sudo hostnamectl set-hostname <name of the server>.<region with the .com or .com>
```

Afterwhich you install FreeIPA manaully using
```bash
sudo ipa-server-install
```

- Domain name (e.g amon.com)
- Real name (e.g amon.COM) capitalization is important here
- IPA server hostname (the FQDN you set previously)
- Directory manager password
- DNS configuration: YES

After this you should be able to go into the PAM web-interface. Try going to `https://ipa-server.amon.com/ipa/ui/` or equivalent hostname you have setup.

Afterwhich configure /etc/resolv.conf
```bash
search amon.com # or different domain name accordingly
nameserver 10.10.1.168 # the address of the node you have installed the server
```

**Note**: If the web interface should appear on the HOST-OS rather than inside the environment you setup you should add the node hostname and address to /etc/hosts of HOST-OS (e.g. echo 10.10.1.168 ipa-server.amon.com > /etc/hosts)

If for some reason the FreeIPA client or the FreeIPA server is not resolving hostnames there is a high probability some other Network Manager is present or as likely some firewall is in effect.

## Client Installation and Configuration

We use Cloud-Init file for Auto-Enrolling Nodes to FreeIPA server as clients. In LXD Canonical we use "Profiles" to implement Cloud-Init.

For **RHEL** distrobutions we have:
```bash
#cloud-config
write_files:
  - path: /root/setup-ipa-client.sh
    permissions: '0755'
    content: |
      #!/bin/bash

      # Update /etc/hosts with IPA server
      echo "10.10.1.168 ipa-server.amon.com ipa-server" >> /etc/hosts
      hostnamectl set-hostname "$(hostname).amon.com"
      A=$(hostname -I)
      echo "$A  $(hostname)" >> /etc/hosts

      # Set IPA variables
      IPA_SERVER="ipa-server.amon.com"
      IPA_REALM="AMON.COM"
      IPA_DOMAIN="amon.com"

      # Configure Kerberos settings
      cat << EOF > /etc/krb5.conf
      [libdefaults]
          default_realm = $IPA_REALM
          dns_lookup_realm = false
          dns_lookup_kdc = false

      [realms]
          $IPA_REALM = {
              kdc = $IPA_SERVER
              admin_server = $IPA_SERVER
          }

      [domain_realm]
          .$IPA_DOMAIN = $IPA_REALM
          $IPA_DOMAIN = $IPA_REALM
      EOF

      # Install FreeIPA client
      yum install -y ipa-client

      # Configure DNS resolver
      rm -f /etc/resolv.conf
      echo -e "nameserver 10.10.1.168\nsearch amon.com" > /etc/resolv.conf

      # Run the FreeIPA client installer
      ipa-client-install --domain="$IPA_DOMAIN" \
        --principal=admin \
        --password="qweasdrf" \
        --server="$IPA_SERVER" \
        --realm="$IPA_REALM" \
        --no-ntp \
        --unattended

runcmd:
  - yum update -y
  - setenforce 0
  - /root/setup-ipa-client.sh
  - setenforce 1
```

**Note**: Important that REALM, DOMAIN and IPA server names should be changed accordingly.

For Debian (specifically for Ubuntu 24.04):
```bash
#cloud-config
write_files:
  - path: /root/setup-ipa-client.sh
    permissions: '0755'
    content: |
      #!/bin/bash

      echo "10.10.1.168 ipa-server.amon.com ipa-server" >> /etc/hosts

      if [[ "$(hostname)" != *".amon.com" ]]; then
         hostnamectl set-hostname "$(hostname).amon.com"
      fi

      A=$(hostname -I)
      echo "$A  $(hostname)" >> /etc/hosts
      IPA_SERVER="ipa-server.amon.com"
      IPA_REALM="AMON.COM"
      IPA_DOMAIN="amon.com"

      debconf-set-selections <<< "krb5-config krb5-config/default_realm string $IPA_REALM"
      debconf-set-selections <<< "krb5-config krb5-config/kerberos_servers string $IPA_SERVER"
      debconf-set-selections <<< "krb5-config krb5-config/admin_server string $IPA_SERVER"
      debconf-set-selections <<< "krb5-config krb5-config/realms string $IPA_REALM"
      debconf-set-selections <<< "krb5-config krb5-config/dns_lookup_realm boolean false"
      debconf-set-selections <<< "krb5-config krb5-config/dns_lookup_kdc boolean false"

      apt-get install -y freeipa-client

      rm -f /etc/resolv.conf
      echo -e "nameserver 10.10.1.168\nsearch amon.com" > /etc/resolv.conf

      ipa-client-install --domain="$IPA_DOMAIN" \
        --principal=admin \
        --password="qweasdrf" \
        --server="$IPA_SERVER" \
        --realm="$IPA_REALM" \
        --no-ntp \
        --unattended
runcmd:
  - apt update -y
  - /root/setup-ipa-client.sh
```

## Installation check

After you booted a node with above Cloud-Init. Then if you go to FreeIPA web-interface and go to hosts you should see that hostname listed on hosts tab. Furthermore, once you create users those users should propogate throughout the FreeIPA Cluster. Use Kerberos
```bash
kinit admin
```
after entering credential you should be able to `ssh` onto client nodes.

```bash
ssh admin@node1
```

Same goes for any user you may create inside FreeIPA server via the IPA.


# LXD Canonical

LXD Canonical is Container and VM Manager. The biggest reason to use LXD canonical is for LXC containers. LXC containers use namespaces and Cgroup for efficient resource management and has faster boot up time than VM setups. Within LXD Canonical there are ways to implement Cloud-Init via Profiles, Network devices, CephFS storage platform. Across nodes that have been created by LXD we use FreeIPA to connect, authenticate and access them. FreeIPA also takes care of hostnames whereas LXD does not naturally solve, not to mention across multiple LXD Clusters.

### CephFS

Currently left blank.

### LXD/LXC Containers and VM setup

As of now, we have the current setup.
| #  |  Name |  Distribution |  Environment | 
|---|---|---|---|
|  1 |  Database (MariaDB for slurmdbd) |   Ubuntu 24.04 |  Container |   
|  2 |  FreeIPA server  | Rocky 8  |  VM |   
|  3 |  SLURM Primary Controller | Ubuntu 24.04  | Container   |  
|  4 |  SLURM Secondary Controller (BackUp) | Ubuntu 24.04   | Container  | 
|  5 | SLURM Worker Node(s)  |  Ubuntu 24.04  |  Container  | 

Controller, FreeIPA server, Database nodes are manually setup as documented here. Worker nodes must auto-Enroll, auto-setup therefore Cloud-Init is utilized.

### Cloud-Init
The following is cloud-init file for SLURM worker nodes. Every worker node has to
1. Auto Enroll to FreeIPA
2. Share munge.key secret to authenticate itself as worker node
3. Running SLURM Daemon (slurmd) and shared config file **slurm.conf**

```bash
#cloud-config
write_files:
  - path: /root/setup-ipa-client.sh
    permissions: '0755'
    content: |
      #!/bin/bash

      echo "10.10.1.168 ipa-server.amon.com ipa-server" >> /etc/hosts

      if [[ "$(hostname)" != *".amon.com" ]]; then
         hostnamectl set-hostname "$(hostname).amon.com"
      fi

      A=$(hostname -I)
      echo "$A  $(hostname)" >> /etc/hosts
      IPA_SERVER="ipa-server.amon.com"
      IPA_REALM="AMON.COM"
      IPA_DOMAIN="amon.com"

      debconf-set-selections <<< "krb5-config krb5-config/default_realm string $IPA_REALM"
      debconf-set-selections <<< "krb5-config krb5-config/kerberos_servers string $IPA_SERVER"
      debconf-set-selections <<< "krb5-config krb5-config/admin_server string $IPA_SERVER"
      debconf-set-selections <<< "krb5-config krb5-config/realms string $IPA_REALM"
      debconf-set-selections <<< "krb5-config krb5-config/dns_lookup_realm boolean false"
      debconf-set-selections <<< "krb5-config krb5-config/dns_lookup_kdc boolean false"

      apt-get install -y freeipa-client

      rm -f /etc/resolv.conf
      echo -e "nameserver 10.10.1.168\nsearch amon.com" > /etc/resolv.conf

      ipa-client-install --domain="$IPA_DOMAIN" \
        --principal=admin \
        --password="qweasdrf" \
        --server="$IPA_SERVER" \
        --realm="$IPA_REALM" \
        --no-ntp \
        --unattended
runcmd:
  - apt update -y
  - echo "------------------- Start Munge ---------------------"
  - apt install munge -y
  - apt install libmunge2 -y
  - apt install libmunge-dev -y
  - echo "--------Decoding munge.key secret from base64--------"
  - echo "Uo+fZsKZIFWqHRBT7KaXiyjyWk0KYpaO2hO5rtXDOFD4zhduPCsMvpzFmsg+otkGRGLm49wTvmKLHcNIS7NCKZbWlRd27ZT72eHYiWofhaB0C7RGUho8HbyoNswKLv/Boiy6aBbWge6nBHVM+iOBk1oKANFQ3Dqv4VJzBuL+Pe4=" | base64 -d | sudo tee /etc/munge/munge.key > /dev/null
  - chown -R munge:munge /etc/munge/ /var/log/munge/ /var/lib/munge/ /run/munge/
  - chmod 0700 /etc/munge/ /var/log/munge/ /var/lib/munge/
  - chmod 0755 /run/munge/
  - chmod 0700 /etc/munge/munge.key
  - chown -R munge:munge /etc/munge/munge.key
  - systemctl enable munge
  - systemctl restart munge
  - echo "-------------------Munge Done ---------------------"
  - systemctl status munge
  - echo "-------------------Start SLURM --------------------"
  - echo "10.10.1.151 controller" | sudo tee -a /etc/hosts > /dev/null
  - apt install -y libpmix-dev
  - apt install -y slurm-wlm
  - echo "---------------Getting Slurm conf file -----------"
  - git clone https://github.com/B-Tulgat/SLURM.git
  - cp ./SLURM/slurm.conf /etc/slurm/slurm.conf
  - rm -rf ./SLURM
  - systemctl enable slurmd
  - systemctl restart slurmd
  - systemctl status slurmd
  - echo "---------------FreeIPA Auto Enroll -----------"
  - /root/setup-ipa-client.sh
```

**Note**: Change controller IP address, FreeIPA server hostname and region accordingly.

## SLURM

SLURM is the Workload Manager of the HPC server. It allows for multiple users to share computational resources efficiently. SLURM is developed to be used in SaaS. Therefore it has built in functionalities and compatibilities when using it as a Workload Manager for HPC service; including compatibility with various cloud providers such as Azure, AWS, GCP etc. 

SLURM defines **computational nodes** via `NodeName` i.e. their hostnames and **instance type** via `PartitionName`. Users can submit a job for number of nodes with specific sets of specs which is predefined in the `PartitionName`.

For Example: In the `/ect/slurm/slurm.conf` you can define `PartitionName`: **partition_gpu** and **partition_cpu** where you allocate GPUs to the **partition_gpu** and allocate CPUs to the **partition_cpu**. A user knowing their computation does not need GPU for their computation can leave the resource free for the next person to submit a job.

Notable SLURM Configuration Files:

- `/etc/slurm/slurm.conf` 
    The primary configuration file for SLURM. We have `ControlMachine` : Controller Node, `NodeName` : Lists the compute nodes, `PartitionName` : Defines type of computation node.
- `/etc/slurm/slurmdbd.conf`
    SLURM Database Daemon where it stores SLURM username/HPC username and accounts. SLURM has built in accounting report features where it tracks duration and use of computation nodes, job monitoring and statistics. It is reccomended to use **MariaDB** for this Database and for it to be remote to the `ControlMachine`.
- `/etc/slurm/gres.conf`
    Used to configure Generic Resrouces (GRES) such as GPUs corresponding to particular `PartitionName` the SLURM defined (e.g **partition_gpu**)

**Note**: Config files are defined inside the Controller Node i.e. `ControlMachine`.

### Installation

Official documentation: https://slurm.schedmd.com/quickstart_admin.html
Suplementary: https://wiki.fysik.dtu.dk/Niflheim_system/Slurm_installation/

Where you follow this Installation is what will be your ControlMachine/Controller Node.

1. Install Munge and distribute munge.key
2. Configure **slurmctld**, **slurmd**
3. Configure MariaDB followed by **slurmdbd**












