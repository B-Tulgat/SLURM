from flask import Flask, request, jsonify
import os



app = Flask(__name__)

# Helper function to execute lxc commands securely
def execute_lxc_command(action, node_name, timeout=60):
    # Ensure node name contains only alphanumeric characters
    if not node_name.isalnum():
        raise ValueError("Invalid node name")

    # Ensure the action is either 'start' or 'stop'
    if action not in ['start', 'stop']:
        raise ValueError("Invalid action. Allowed actions are 'start' or 'stop'.")


    # Construct the lxc command
    command = f"timeout {timeout}s sudo lxc {action} {node_name}"

    # Execute the command using os.system()
    exit_code = os.system(command)

    # Check for errors based on exit code
    if exit_code != 0:
        raise Exception(f"Command failed with exit code {exit_code}")

    return f"Node {node_name} {action}ed successfully"


# API route to control LXC nodes (start/stop)
@app.route('/lxc/control', methods=['POST'])
def control_lxc():
    action = request.json.get('action')
    node_name = request.json.get('node')

    print(f"action: {action}, node: {node_name}")

    if not action or not node_name:
        return jsonify({"error": "Action and Node name are required"}), 400

    try:
        output = execute_lxc_command(action, node_name)
        return jsonify({"message": f"Node {node_name} {action}ed", "output": output}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
