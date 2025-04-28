#!/bin/bash
# Define the host list and user name
USER=user-name
HOSTS=(
  host0 # e.g. "er001.utah.cloudlab.us"
  host1 # e.g. "er002.utah.cloudlab.us"
  host2 # e.g. "er003.utah.cloudlab.us"
  host3 # e.g. "er004.utah.cloudlab.us"
)

NODE0_HOST=$(getent hosts ${HOSTS[0]} | awk '{ print $1 }')
NODE1_HOST=$(getent hosts ${HOSTS[1]} | awk '{ print $1 }')
NODE2_HOST=$(getent hosts ${HOSTS[2]} | awk '{ print $1 }')
NODE3_HOST=$(getent hosts ${HOSTS[3]} | awk '{ print $1 }')

cd ~/bullshark_ansible_auto
ansible-playbook -i inventory setup_nodes.yml -e "user=$USER node0_host=$NODE0_HOST node1_host=$NODE1_HOST node2_host=$NODE2_HOST node3_host=$NODE3_HOST"
python3 ~/bullshark_ansible_auto/logs.py ~/bullshark_ansible_auto/logs
python3 ~/bullshark_ansible_auto/quorums.py ~/bullshark_ansible_auto/logs
