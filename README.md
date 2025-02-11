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

Powered by SLURM we have Auto-Scaling utilizing SLURM Triggers and Custom Python Scripts for node creations and deletions.

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

**Disclaimer**: To propogate the same `munge.key` across the cluster I have implemented the same base64 encode throughout the node creation. This is for demonstration purpose only, do not use it for production. See munge installation.

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
3. Configure remote database followed by **slurmdbd**
#### Munge Installation 
Part of **munge installation** is already in cloud-init. Only difference is you leave munge.key as is. Newer versions of munge automatically generate munge.key for you as opposed to the older versions where you needed to generate the munge.key, now you do not have to.

```bash
# Install Munge
sudo apt install munge -y
sudo apt install libmunge2 -y
sudo apt install libmunge-dev -y
# Chown munge with munge user
sudo chown -R munge:munge /etc/munge/ /var/log/munge/ /var/lib/munge/ /run/munge/
sudo chmod 0700 /etc/munge/ /var/log/munge/ /var/lib/munge/
sudo chmod 0755 /run/munge/
sudo chmod 0700 /etc/munge/munge.key
sudo chown -R munge:munge /etc/munge/munge.key
sudo systemctl enable munge
sudo systemctl restart munge
```

**Important note**: In the cloud-init configuration there is a base64 encode placeholder of `munge.key`, do not use it for production as it is not safe to do so!

`munge.key` must be the same across the cluster. There are multiple ways to achieve this. The naive approach is what I have implemented with base64 encode however exposing secrets in raw text in the cloud-init is not secure. It is heavily recommended to use more secure method.

#### Configure slurmctld, slurmd

`slurmctld` and `slurmd` are the controller and SLURM daemon which serves as the heartbeat of the SLURM cluster. `slurmctld` is only installed in the `controller`, it handles commands such as `sinfo` to show specification of the SLURM cluster and `scontrol` to update, down nodes as well as job handling. `slurmd` however is installed to all worker nodes, it continuily checks the status of each worker nodes if they are available/idle, cannot be reached or busy. Essentially a user will submit job via `slurmctld` and that submission will be handled and balanced by SLURM via `slurmd` checking availability. It is note worthy that direct access to `controller` is unsafe, therefore a dedicated `login-node` is desirable that sends request to the `controller` that triggers a job submission.

**Note**: `slurmctld` and `slurmd` as well as but not as strongly `slurmdbd` must all have the same version. It is not well documented that what version works with another. Thus you should try to be as strict with your versions as possible in order to avoid extra work. Sometimes installation does not go smoothly and that is part of the challenge. I heavily reccomend: https://wiki.fysik.dtu.dk/Niflheim_system/Slurm_installation/ and the official installation guide on https://slurm.schedmd.com/

Here is what worked for me:

Check the versions after installing. If you are installing them from a repository they should work together. The next best thing to do would be installing it from source after compiling it to `.deb` files or `.rpm` for RHEL distros respectively.
```bash
sudo apt install slurmctld slurmd -y
slurmctld --version
slurmd --version
```

Installation should create a system user named `slurm`:
```bash
id slurm
```

Create required directories and set ownership.
```bash
sudo mkdir -p /var/spool/slurmctld
sudo mkdir -p /var/spool/slurmd
sudo mkdir -p /var/log/slurm
sudo chown -R slurm: /var/spool/slurmctld
sudo chown -R slurm: /var/spool/slurmd
sudo chown -R slurm: /var/log/slurm
sudo chmod 755 /var/spool/slurmctld
sudo chmod 755 /var/spool/slurmd
sudo chmod 755 /var/log/slurm
```

Check `slurmctld`
```bash
sudo systemctl enable slurmctld
sudo systemctl start slurmctld
sudo systemctl status slurmctld
```

Check `slurmd`
```bash
sudo systemctl enable slurmd
sudo systemctl start slurmd
sudo systemctl status slurmd
```

Replace the `/etc/slurm/slurm.conf` to what suits your setup. You can use the `slurm.conf` on this repository for reference. Or use the configuration tool from the official site (https://slurm.schedmd.com/configurator.html) . If you use custom `slurm.conf` change the corresponding `slurm.conf` for the `cloud.init` file. SLURM configuration file **must be the same across the SLURM cluster, controller and worker node should share the same** `slurm.conf`.

#### Configure remote database followed by slurmdbd

For SLURM installtion a remote database is preffered.
1. Install MariaDB on a seperate node to `controller`.
2. Configure slurmdbd on the `controller`


**On a remote node, seperate from controller node.**

Install MariaDB prefferably 10.6 or newer.
```bash
sudo apt install mariadb-server
sudo systemctl enable --now mariadb
```

Enter MariaDB:
```bash
mysql -u root -p
```

Create a database and user for SLURM accounting (replace `somepassword` after `IDENTIFIED BY`):
```sql
CREATE DATABASE slurm_acct_db;
GRANT ALL PRIVILEGES ON slurm_acct_db.* TO `slurm`@`localhost` IDENTIFIED BY 'somepassword';
FLUSH PRIVILEGES;
```

Optimize MariaDB settings by adding the following to `/etc/mysql/mariadb.conf.d/50-server.conf`
```
[mysqld]
innodb_buffer_pool_size = 256M
innodb_lock_wait_timeout = 50
```

**On a controller node**
Assuming the remote database is in `10.10.1.150` (change the address of the remote database accordingly).

Check if you have connection to the remote database and you can login as ``` `slurm`@`localhost` ```.
```bash
mariadb -u slurm -p -h 10.10.1.150 slurm_acct_db
```

After verifying you can connect to the remote database as the user you have created. Install the slurmdbd on the `controller`.

```bash
sudo apt install slurmdbd
sudo systemctl status slurmdbd
```

Set correct permissions and files:
```bash
sudo chmod 600 /etc/slurm/slurmdbd.conf
sudo chown slurm: /etc/slurm/slurmdbd.conf
sudo mkdir -p /var/run/slurm
sudo chown -R slurm: /var/run/slurm
sudo touch  /var/run/slurmdbd.pid
sudo chown -R slurm:  /var/run/slurmdbd.pid
```

Replace the `/etc/slurm/slurmdbd.conf` to what suits your setup. You can use the `slurmdbd.conf` on this repository for reference. Change the `StorageHost` to the corresponding remote database address as well as `StoragePass`,`StorageUser` for password and user respectively that you have created.

Start and verify slurmdbd
```bash
sudo systemctl start slurmdbd
sudo systemctl enable slurmdbd
sudo systemctl status slurmdbd
```

## Node Provisioning Based on SLURM Workload.
For the purpose of horizontal scaling and power-saving we would like to shut-down idle worker nodes and rescale the server once the workload increases. SLURM has their Power-Saving guide (https://slurm.schedmd.com/power_save.html) and SLURM Elastic Computing built into SLURM. However from **my personal experience** SLURM Elastic Computing and Power-Saving does not work on LXC Containers and VMs. In order to have Auto-Scaling on HPC powered by SLURM, I worked around it with custom python scripts and SLURM triggers.

### Delist Idle Nodes from the HPC

Creates SLURM Trigger that updates node status to `DOWN` if they have been idle for more than 3600 seconds, meaning they have been on stand-by for more than 60 minutes.
```bash
strigger --set --node --idle --offset=3600 --program=./sus.sh
```

Future works will include that we not only `DOWN` a node but completely free resources from the HPC.

### Enlist Nodes to HPC

`ENROLLER.py` runs on `controller` node that polls for job submission. If the HPC can produce required nodes with specified specs with `Partition`, it starts nodes so that the job could run.
Nodes are started by running `start.sh` script that sends request to `LXC-API`.
- `LXC-API.py` is run on a user on a machine that runs the LXD Canonical that has permission to run command `lxc` without `sudo` so that `lxc start node1` runs without the machine raising privilege error.

## Testing the setup.

Now we test simple SLURM setup on our hpc.
```bash
sinfo
```
should produce all nodes from `node1.amon.com` to `node3.amon.com` from `debug` partition as well as `node4.amon.com` and `node5.amon.com` from `double` on STATE `Idle`.

#### srun
```bash
srun hostname -n 5
```
Should produce
```
node1.amon.com
node2.amon.com
node3.amon.com
node4.amon.com
node5.amon.com
```
In different orders each time.

#### sbatch
Create a script `job.sh`
```bash
#!/bin/bash
#SBATCH --job-name=test_job          # Job name
#SBATCH --output=/tmp/slurm_%j.out   # Standard output log file
#SBATCH --error=/tmp/slurm_%j.err    # Standard error log file
#SBATCH --time=00:02:00              # Max time limit (2 minutes)
#SBATCH --ntasks=1                   # Number of tasks
#SBATCH --cpus-per-task=1            # CPUs per task

sleep 60
echo "This is $(hostname)" > /tmp/slurm_job_output_${SLURM_JOB_ID}.txt
```

And finally run
```bash
sbatch job.sh
```

Should produce text file on `/tmp/` as specified on `job.sh` on a node that is running the job. You can check which node is running your job by eximining node states by running `sinfo`.

Since you have already setup FreeIPA. You can use `kinit admin` and then `ssh admin@nodeX.amon.com` on the running node to see if the expected file is produced.

### Node provisioning

- First start the `LXC-API` on the LXD hosting machine.
- Reconfigure `start.sh` script so that the `LXC-API` address mathces.
- Run the `ENROLLER.py` on the `controller`.
- `DOWN` every node by on the SLURM cluster for testing. Run command `scontrol update NodeName=all State=DOWN`
- Start spawning jobs that request partitions `debug` and `double` accordingly.

Jobs for `debug` partition:
`sbatch --partition=debug job.sh`

Jobs for `double` partition:
`sbatch --partition=double job.sh`

Check the `ENROLLER.py` output as well check `squeue` for job submission queue. You can check if the expected results are being generated by `ssh`-ing into respective worker nodes.

## Future Works

- Integrating FreeIPA credentials with SLURM Accoutning
- Dedicated Login-Node for job submission
- Node Provisioning further works.
- HPC Notebook Access
- CephFS for HPC File System for LXD Cluster
```
