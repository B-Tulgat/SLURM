#!/bin/bash
# start.sh
# IP address must be changed where LXC-API is running.
NODE=$1
curl -X POST http://10.241.236.211:5000/lxc/control -H "Content-Type: application/json"  -d "{\"action\": \"start\", \"node\": \"$NODE\"}"
scontrol update NodeName="$NODE.c1xacc355.com" State=RESUME
exit 0
