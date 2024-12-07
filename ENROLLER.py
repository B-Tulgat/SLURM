import subprocess

# Total logical nodes in the partition
TOTAL_PARTITION_NODES = 10

def run_command(cmd):
    """Run a shell command and return the output."""
    return subprocess.check_output(cmd, shell=True, text=True).strip()

def get_pending_jobs():
    """Fetch pending jobs from squeue."""
    pending_jobs = []
    output = run_command("squeue -t PENDING --format='%i %P' --noheader")
    for line in output.splitlines():
        job_id, partition = line.split()
        pending_jobs.append({"id": job_id, "partition": partition})
    return pending_jobs

def get_job_requirements(job_id):
    """Fetch job requirements using scontrol."""
    job_details = run_command(f"scontrol show job {job_id}")
    # Parse required nodes and CPUs from job details
    required_nodes = int(next(line.split("=")[1] for line in job_details.split() if line.startswith("NumNodes")))
    return required_nodes

def get_partition_info(partition):
    """Fetch partition node states."""
    output = run_command(f"scontrol show nodes | grep PartitionName={partition}")
    idle_nodes = 0
    computation_nodes = 0

    for line in output.splitlines():
        if "State=IDLE" in line:
            idle_nodes += 1
        elif "State=ALLOCATED" in line or "State=MIXED" in line:
            computation_nodes += 1

    return idle_nodes, computation_nodes

def resume_nodes(partition, required_nodes):
    """Resume nodes in the specified partition."""
    output = run_command(f"scontrol show nodes | grep PartitionName={partition} | grep State=DOWN")
    nodes_to_resume = []

    for line in output.splitlines():
        if len(nodes_to_resume) >= required_nodes:
            break
        node_name = line.split("NodeName=")[1].split()[0]
        nodes_to_resume.append(node_name)

    for node in nodes_to_resume:
        print(f"Resuming node: {node}")
        run_command(f"scontrol update NodeName={node} State=RESUME")

def main():
    # Fetch pending jobs
    pending_jobs = get_pending_jobs()
    for job in pending_jobs[0]:
        job_id = job["id"]
        partition = job["partition"]
        print(job)
        print(job["partition"])
        print(job["id"])

        # Get job requirements
        required_nodes = get_job_requirements(job_id)

        # Get partition information
        idle_nodes, computation_nodes = get_partition_info(partition)

        # Check if there are enough resources to enroll nodes
        if TOTAL_PARTITION_NODES - computation_nodes >= required_nodes - idle_nodes:
            print(f"Enrolling nodes for job {job_id} in partition {partition}")
            nodes_to_resume = required_nodes - idle_nodes
            resume_nodes(partition, nodes_to_resume)
        else:
            print(f"Insufficient resources to enroll nodes for job {job_id}")

if __name__ == "__main__":
    main()
