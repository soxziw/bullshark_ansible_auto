import re
import os
import sys
from collections import Counter

def count_quorum_authorities(log_dir):
    primary_logs = ['primary-0.log', 'primary-1.log', 'primary-2.log', 'primary-3.log']
    
    # Pattern to match quorum authority lines
    pattern = r'\[.*DEBUG primary::aggregators\] Quorum \[(.*)\]'
    
    for log_file in primary_logs:
        log_file_path = os.path.join(log_dir, log_file)
        
        # Counter to track occurrences of each authority
        authority_counter = Counter()
        total_quorum_count = 0
        
        # Check if file exists
        if not os.path.exists(log_file_path):
            print(f"Warning: Log file not found at {log_file_path}")
            continue
        
        try:
            with open(log_file_path, 'r') as file:
                for line in file:
                    match = re.search(pattern, line)
                    if match:
                        total_quorum_count += 1
                        # Extract authorities from the matched line
                        authorities_text = match.group(1)
                        # Extract each authority's public key
                        authority_matches = re.findall(r'\(([^,]+)', authorities_text)
                        for authority in authority_matches:
                            authority_counter[authority] += 1
            
            print(f"\n----- {log_file} Statistics -----")
            print(f"Total quorum occurrences: {total_quorum_count}")
            print("\nAuthority occurrence counts:")
            for authority, count in authority_counter.items():
                print(f"{authority}: {count}")
            
        except Exception as e:
            print(f"Error processing log file {log_file}: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        count_quorum_authorities(sys.argv[1])
    else:
        count_quorum_authorities()
