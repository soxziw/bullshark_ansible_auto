#!/bin/bash
# Define the host list and user name
USER="Eirik"
HOSTS=(
  "er013.utah.cloudlab.us"
  "c220g1-030625.wisc.cloudlab.us"
  "clnode067.clemson.cloudlab.us"
  "pc489.emulab.net"
  "pc80.cloudlab.umass.edu"
  "er059.utah.cloudlab.us"
  "c220g1-030621.wisc.cloudlab.us"
  "clnode058.clemson.cloudlab.us"
  "pc437.emulab.net"
  "pc96.cloudlab.umass.edu"
)

NODE0_HOST=$(getent hosts ${HOSTS[0]} | awk '{ print $1 }')
NODE1_HOST=$(getent hosts ${HOSTS[1]} | awk '{ print $1 }')
NODE2_HOST=$(getent hosts ${HOSTS[2]} | awk '{ print $1 }')
NODE3_HOST=$(getent hosts ${HOSTS[3]} | awk '{ print $1 }')
NODE4_HOST=$(getent hosts ${HOSTS[4]} | awk '{ print $1 }')
NODE5_HOST=$(getent hosts ${HOSTS[5]} | awk '{ print $1 }')
NODE6_HOST=$(getent hosts ${HOSTS[6]} | awk '{ print $1 }')
NODE7_HOST=$(getent hosts ${HOSTS[7]} | awk '{ print $1 }')
NODE8_HOST=$(getent hosts ${HOSTS[8]} | awk '{ print $1 }')
NODE9_HOST=$(getent hosts ${HOSTS[9]} | awk '{ print $1 }')

# Check if the first argument is "setup" and only run setup if it is
if [ "$1" == "setup" ]; then
    echo "Running setup only..."
    ansible-playbook -i inventory setup_nodes.yml -e "user=$USER node0_host=$NODE0_HOST node1_host=$NODE1_HOST node2_host=$NODE2_HOST node3_host=$NODE3_HOST node4_host=$NODE4_HOST node5_host=$NODE5_HOST node6_host=$NODE6_HOST node7_host=$NODE7_HOST node8_host=$NODE8_HOST node9_host=$NODE9_HOST" -f 10
    exit 0
fi

# If no argument or argument is not "setup", continue with the full script
TEST_CASE='bullshark'
FAULT_SIZES=('')
TX_RATES_PER_AUTHORITY=(5100 5200 5300 5400 5500 5600 5700 5800 5900)
# TX_RATES_PER_AUTHORITY=(5100 5200 5300 5400 5500 5600 5700 5800 5900)
# TX_RATES_PER_AUTHORITY=(7000 7500)
# TX_RATES_PER_AUTHORITY=(10000 10250 10500 10750 11000 11250 11500 11750 12000)

# Run tests for each transaction rate
for FAULT_SIZE in "${FAULT_SIZES[@]}"; do
  for TX_RATE_PER_AUTHORITY in "${TX_RATES_PER_AUTHORITY[@]}"; do
      echo "Running test with transaction rate: $TX_RATE_PER_AUTHORITY per authority"
      
      # Calculate total transaction rate (rate per authority * number of authorities)
      TOTAL_TX_RATE=$((TX_RATE_PER_AUTHORITY * 10))
      
      # Create a directory for this specific test
      mkdir -p ~/bullshark_ansible_auto/logs/${TEST_CASE}_${FAULT_SIZES}_${TOTAL_TX_RATE}
      
      if [ "$FAULT_SIZE" == "f1" ]; then
        # For f1 fault, exclude node9
        ansible-playbook -i inventory run_nodes.yml -e "user=$USER transaction_rate=$TX_RATE_PER_AUTHORITY fault_size=$FAULT_SIZE node0_host=$NODE0_HOST node1_host=$NODE1_HOST node2_host=$NODE2_HOST node3_host=$NODE3_HOST node4_host=$NODE4_HOST node5_host=$NODE5_HOST node6_host=$NODE6_HOST node7_host=$NODE7_HOST node8_host=$NODE8_HOST node9_host=$NODE9_HOST" -f 10 --limit 'all:!node9'
        python3 ~/bullshark_ansible_auto/logs.py --dir ~/bullshark_ansible_auto/logs --faults 1 --test_case ${TEST_CASE}_${FAULT_SIZES}
      elif [ "$FAULT_SIZE" == "f3" ]; then
        # For f3 fault, exclude node7, node8, node9
        ansible-playbook -i inventory run_nodes.yml -e "user=$USER transaction_rate=$TX_RATE_PER_AUTHORITY fault_size=$FAULT_SIZE node0_host=$NODE0_HOST node1_host=$NODE1_HOST node2_host=$NODE2_HOST node3_host=$NODE3_HOST node4_host=$NODE4_HOST node5_host=$NODE5_HOST node6_host=$NODE6_HOST node7_host=$NODE7_HOST node8_host=$NODE8_HOST node9_host=$NODE9_HOST" -f 10 --limit 'all:!node7:!node8:!node9'
        python3 ~/bullshark_ansible_auto/logs.py --dir ~/bullshark_ansible_auto/logs --faults 3 --test_case ${TEST_CASE}_${FAULT_SIZES}
      else
        # For no fault, use all nodes
        ansible-playbook -i inventory run_nodes.yml -e "user=$USER transaction_rate=$TX_RATE_PER_AUTHORITY fault_size=$FAULT_SIZE node0_host=$NODE0_HOST node1_host=$NODE1_HOST node2_host=$NODE2_HOST node3_host=$NODE3_HOST node4_host=$NODE4_HOST node5_host=$NODE5_HOST node6_host=$NODE6_HOST node7_host=$NODE7_HOST node8_host=$NODE8_HOST node9_host=$NODE9_HOST" -f 10
        python3 ~/bullshark_ansible_auto/logs.py --dir ~/bullshark_ansible_auto/logs --faults 0 --test_case ${TEST_CASE}
      fi
      
      # Move logs to the rate-specific directory
      mv ~/bullshark_ansible_auto/logs/*.log ~/bullshark_ansible_auto/logs/${TEST_CASE}_${FAULT_SIZES}_${TOTAL_TX_RATE}/
      
      # Process logs for this rate
      
      # Wait for 10 seconds before starting the next test
      echo "Waiting 10 seconds before starting the next test..."
      sleep 10s
  done
done

python3 ~/bullshark_ansible_auto/logs.py --plot
