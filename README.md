# Bullshark Ansible Automation

Automated deployment and testing of Bullshark consensus protocol using Ansible on CloudLab infrastructure.

## Prerequisites

1. CloudLab Account and Project Setup
   - Create an account on [CloudLab](https://www.cloudlab.us/)
   - Join or create a project
   - Upload your SSH public key to CloudLab profile settings

2. System Requirements
   - Python >= 3.8.0
   - Ansible >= 2.9.0
   - SSH client
   
   Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Setup Instructions

1. Update SSH Key on CloudLab
   ```bash
   # Generate a new SSH key if you don't have one
   ssh-keygen -t rsa -b 4096 -C "your_email@example.com"
   
   # Copy your public key
   cat ~/.ssh/id_rsa.pub
   ```
   - Go to your CloudLab profile
   - Add the public key to your SSH keys

2. Clone the Repository
   ```bash
   git clone https://github.com/soxziw/bullshark_ansible_auto.git
   cd bullshark_ansible_auto
   ```

3. Configure Connection
   - Edit `distributedTest.sh` file with your CloudLab node information:
     ```bash
     USER=your-username
     HOSTS=(
       er001.utah.cloudlab.us  # Your first CloudLab node
       er002.utah.cloudlab.us  # Your second CloudLab node
       er003.utah.cloudlab.us  # Your third CloudLab node
       er004.utah.cloudlab.us  # Your fourth CloudLab node
     )
     ```

## Usage

1. Run the Distributed Test
   ```bash
   ./distributedTest.sh
   ```

2. View Results
   - Check `results.txt` for benchmark results
   - Logs are stored in the `logs/` directory
   - Use `logs.py` to analyze the results:
     ```bash
     python3 logs.py logs/
     ```

3. Custom Quorum Analysis
   ```bash
   python3 quorums.py logs/
   ```

## File Structure

- `distributedTest.sh`: Main script for running distributed tests
- `setup_nodes.yml`: Ansible playbook for node configuration
- `inventory`: Ansible inventory file
- `logs.py`: Log analysis script
- `quorums.py`: Quorum configuration analysis
- `logs/`: Directory containing test logs
- `results.txt`: Test results output

## Environment Variables

- `NODE0_HOST` to `NODE3_HOST`: CloudLab node hostnames
- `USER`: CloudLab username
- `benchmark_running_time`: Test duration (default: 10)

## Troubleshooting

1. SSH Connection Issues
   - Verify your SSH key is properly added to CloudLab
   - Check node accessibility: `ssh username@nodename.cloudlab.us`

2. Ansible Errors
   - Verify inventory file format
   - Check node connectivity: `ansible all -i inventory -m ping`