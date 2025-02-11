#!/bin/bash

#strigger --set --node --idle --offset=3600 --program=./sus.sh

for node in "$@"; do
        scontrol update NodeName="$node" State=DOWN Reason="Idle for too long"
done

echo "$@" > /tmp/sets.txt
