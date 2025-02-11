import subprocess

def run_command(cmd, default=""):
    try:
        return subprocess.check_output(cmd, shell=True, text=True).strip()
    except subprocess.CalledProcessError:
        return default

def get_pending_jobs():
    """Fetch pending jobs from squeue."""
    pending_jobs = []
    output = run_command("squeue -t PENDING --format='%i %P' --noheader")
    for line in output.splitlines():
        job_id, partition = line.split()
        pending_jobs.append({"id": job_id, "partition": partition})
    print(pending_jobs)
    return pending_jobs

def get_job_requirements(job_id):
    """Fetch job requirements using scontrol."""
    job_details = run_command(f"scontrol show job {job_id}")
    # Parse required nodes and CPUs from job details
    required_nodes = int(next(line.split("=")[1].split("-")[0]
                          for line in job_details.splitlines()
                          if line.strip().startswith("NumNodes")))
    print(f"required nodes: {required_nodes}")

    node_details = run_command(f"scontrol show nodes | grep \"State=IDLE+CLOUD \"")
    idle_nodes = 0
    for line in node_details.splitlines():
        idle_nodes += 1

    print(f"idle nodes: {idle_nodes}")

    return required_nodes, idle_nodes

def main():
    # Fetch pending jobs
    pending_jobs = get_pending_jobs()
    for job in pending_jobs:
        job_id = job["id"]
        partition = job["partition"]

        # Get job requirements
        required_nodes, idle_nodes = get_job_requirements(job_id)

        payload = f"scontrol show nodes | awk '/NodeName=/ {{node=$1}} /State=DOWN/ {{state=$1}} /Partitions={partition}/ {{partition=$1}} {{if(node && state && partition) {{print node, state, partition; node=\"\"; state=\"\"; partition=\"\"}}}}'"

        output = run_command(payload)
        payload2 = f"scontrol show nodes | awk '/NodeName=/ {{node=$1}} /State=.*NOT_RESPONDING/ {{state=$1}} /Partitions={partition}/ {{partition=$1}} {{if(node && state && partition) {{print node, state, partition; node=\"\"; state=\"\"; partition=\"\"}}}}'"
        output2 = run_command(payload2)
        nodes_to_resume = []

        if len(output.splitlines()) + len(output2.splitlines()) < required_nodes - idle_nodes:
            print("Not enough nodes for this job")
        else:
            for line in output2.splitlines() + output.splitlines():
                if len(nodes_to_resume) >= required_nodes - idle_nodes:
                    break
                node_name = line.split("NodeName=")[1].split()[0]
                nodes_to_resume.append(node_name)

            print(f"nodes_to_resume: {nodes_to_resume}")

            for node in nodes_to_resume:
                run_command(f"./start.sh {node.split('.')[0]}")


if __name__ == "__main__":
    main()
