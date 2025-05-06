# Copyright(C) Facebook, Inc. and its affiliates.
from datetime import datetime
from glob import glob
from multiprocessing import Pool
from os.path import join
from re import findall, search
from statistics import mean
import re
import os
import sys
from collections import Counter, defaultdict

import argparse
import matplotlib.pyplot as plt
import numpy as np

log_dir = ""
test_case = ""

class ParseError(Exception):
    pass


class LogParser:
    def __init__(self, clients, primaries, workers, faults=0):
        inputs = [clients, primaries, workers]
        assert all(isinstance(x, list) for x in inputs)
        assert all(isinstance(x, str) for y in inputs for x in y)
        assert all(x for x in inputs)

        self.faults = faults
        if isinstance(faults, int):
            self.committee_size = len(primaries) + int(faults)
            self.workers =  len(workers) // len(primaries)
        else:
            self.committee_size = '?'
            self.workers = '?'

        # Parse the clients logs.
        try:
            with Pool() as p:
                results = p.map(self._parse_clients, clients)
        except (ValueError, IndexError, AttributeError) as e:
            raise ParseError(f'Failed to parse clients\' logs: {e}')
        self.size, self.rate, self.start, misses, self.sent_samples \
            = zip(*results)
        self.misses = sum(misses)

        # Parse the primaries logs.
        try:
            with Pool() as p:
                results = p.map(self._parse_primaries, primaries)
        except (ValueError, IndexError, AttributeError) as e:
            raise ParseError(f'Failed to parse nodes\' logs: {e}')
        proposals, commits, self.configs, primary_ips = zip(*results)
        self.proposals = self._merge_results([x.items() for x in proposals])
        self.commits = self._merge_results([x.items() for x in commits])

        # Parse the workers logs.
        try:
            with Pool() as p:
                results = p.map(self._parse_workers, workers)
        except (ValueError, IndexError, AttributeError) as e:
            raise ParseError(f'Failed to parse workers\' logs: {e}')
        sizes, self.received_samples, workers_ips = zip(*results)
        self.sizes = {
            k: v for x in sizes for k, v in x.items() if k in self.commits
        }

        # Determine whether the primary and the workers are collocated.
        self.collocate = set(primary_ips) == set(workers_ips)

        # Check whether clients missed their target rate.
        if self.misses != 0:
            print(
                f'Clients missed their target rate {self.misses:,} time(s)'
            )

    def _merge_results(self, input):
        # Keep the earliest timestamp.
        merged = {}
        for x in input:
            for k, v in x:
                if not k in merged or merged[k] > v:
                    merged[k] = v
        return merged

    def _parse_clients(self, log):
        if search(r'Error', log) is not None:
            raise ParseError('Client(s) panicked')

        size = int(search(r'Transactions size: (\d+)', log).group(1))
        rate = int(search(r'Transactions rate: (\d+)', log).group(1))

        tmp = search(r'\[(.*Z) .* Start ', log).group(1)
        start = self._to_posix(tmp)

        misses = len(findall(r'rate too high', log))

        tmp = findall(r'\[(.*Z) .* sample transaction (\d+)', log)
        samples = {int(s): self._to_posix(t) for t, s in tmp}

        return size, rate, start, misses, samples

    def _parse_primaries(self, log):
        if search(r'(?:panicked|Error)', log) is not None:
            raise ParseError('Primary(s) panicked')

        tmp = findall(r'\[(.*Z) .* Created B\d+\([^ ]+\) -> ([^ ]+=)', log)
        tmp = [(d, self._to_posix(t)) for t, d in tmp]
        proposals = self._merge_results([tmp])

        tmp = findall(r'\[(.*Z) .* Committed B\d+\([^ ]+\) -> ([^ ]+=)', log)
        tmp = [(d, self._to_posix(t)) for t, d in tmp]
        commits = self._merge_results([tmp])

        configs = {
            'header_size': int(
                search(r'Header size .* (\d+)', log).group(1)
            ),
            'max_header_delay': int(
                search(r'Max header delay .* (\d+)', log).group(1)
            ),
            'gc_depth': int(
                search(r'Garbage collection depth .* (\d+)', log).group(1)
            ),
            'sync_retry_delay': int(
                search(r'Sync retry delay .* (\d+)', log).group(1)
            ),
            'sync_retry_nodes': int(
                search(r'Sync retry nodes .* (\d+)', log).group(1)
            ),
            'batch_size': int(
                search(r'Batch size .* (\d+)', log).group(1)
            ),
            'max_batch_delay': int(
                search(r'Max batch delay .* (\d+)', log).group(1)
            ),
        }

        ip = search(r'booted on (\d+.\d+.\d+.\d+)', log).group(1)
        
        return proposals, commits, configs, ip

    def _parse_workers(self, log):
        if search(r'(?:panic|Error)', log) is not None:
            raise ParseError('Worker(s) panicked')

        tmp = findall(r'Batch ([^ ]+) contains (\d+) B', log)
        sizes = {d: int(s) for d, s in tmp}

        tmp = findall(r'Batch ([^ ]+) contains sample tx (\d+)', log)
        samples = {int(s): d for d, s in tmp}

        ip = search(r'booted on (\d+.\d+.\d+.\d+)', log).group(1)

        return sizes, samples, ip

    def _to_posix(self, string):
        x = datetime.fromisoformat(string.replace('Z', '+00:00'))
        return datetime.timestamp(x)

    def _consensus_throughput(self):
        if not self.commits:
            return 0, 0, 0
        start, end = min(self.proposals.values()), max(self.commits.values())
        duration = end - start
        bytes = sum(self.sizes.values())
        bps = bytes / duration
        tps = bps / self.size[0]
        return tps, bps, duration

    def _consensus_latency(self):
        latency = [c - self.proposals[d] for d, c in self.commits.items()]
        return mean(latency) if latency else 0

    def _end_to_end_throughput(self):
        if not self.commits:
            return 0, 0, 0
        start, end = min(self.start), max(self.commits.values())
        duration = end - start
        bytes = sum(self.sizes.values())
        bps = bytes / duration
        tps = bps / self.size[0]
        return tps, bps, duration

    def _end_to_end_latency(self):
        latency = []
        for sent, received in zip(self.sent_samples, self.received_samples):
            for tx_id, batch_id in received.items():
                if batch_id in self.commits:
                    assert tx_id in sent  # We receive txs that we sent.
                    start = sent[tx_id]
                    end = self.commits[batch_id]
                    latency += [end-start]
        return mean(latency) if latency else 0

    def _count_quorum_authorities(self):
        # Get all primary log files from the directory
        primary_logs = [f for f in os.listdir(log_dir) if f.startswith('primary-') and f.endswith('.log')]
        
        # Pattern to match quorum authority lines
        pattern = r'\[.*DEBUG primary::aggregators\] Quorum \[(.*)\]'
        
        # Global counter to track occurrences of each authority across all primaries
        global_authority_counter = Counter()
        global_quorum_count = 0
        
        for log_file in primary_logs:
            log_file_path = os.path.join(log_dir, log_file)
            
            # Check if file exists
            if not os.path.exists(log_file_path):
                print(f"Warning: Log file not found at {log_file_path}")
                continue
            
            try:
                with open(log_file_path, 'r') as file:
                    for line in file:
                        match = re.search(pattern, line)
                        if match:
                            global_quorum_count += 1
                            # Extract authorities from the matched line
                            authorities_text = match.group(1)
                            # Extract each authority's public key
                            authority_matches = re.findall(r'\(([^,]+)', authorities_text)
                            for authority in authority_matches:
                                global_authority_counter[authority] += 1
                    
            except Exception as e:
                print(f"Error processing log file {log_file}: {e}")
        
        # Ensure the counter has exactly committee_size - faults entries
        expected_authorities = self.committee_size - self.faults
        if len(global_authority_counter) < expected_authorities:
            # Fill missing authorities with 0 occurrences
            for i in range(len(global_authority_counter), expected_authorities):
                # Use a placeholder key for missing authorities
                global_authority_counter[f"MissingAuthority{i}"] = 0
            
        # Calculate normalized standard deviation for global counts
        normalized_std_dev = 0
        if global_authority_counter and global_quorum_count > 0:
            counts = list(global_authority_counter.values())
            # Normalize counts by dividing by total quorum count
            normalized_counts = [count / global_quorum_count for count in counts]
            # Calculate mean of normalized counts
            mean_normalized = sum(normalized_counts) / len(normalized_counts)
            # Calculate standard deviation
            normalized_std_dev = (sum((x - mean_normalized) ** 2 for x in normalized_counts) / len(normalized_counts)) ** 0.5
        return global_authority_counter, normalized_std_dev

    def result(self, save_plot_data=False):
        header_size = self.configs[0]['header_size']
        max_header_delay = self.configs[0]['max_header_delay']
        gc_depth = self.configs[0]['gc_depth']
        sync_retry_delay = self.configs[0]['sync_retry_delay']
        sync_retry_nodes = self.configs[0]['sync_retry_nodes']
        batch_size = self.configs[0]['batch_size']
        max_batch_delay = self.configs[0]['max_batch_delay']

        consensus_latency = self._consensus_latency() * 1_000
        consensus_tps, consensus_bps, _ = self._consensus_throughput()
        end_to_end_tps, end_to_end_bps, duration = self._end_to_end_throughput()
        end_to_end_latency = self._end_to_end_latency() * 1_000
        
        global_authority_counter, normalized_std_dev = self._count_quorum_authorities()
        
        if save_plot_data:
            with open('plot.txt', 'a') as f:
                f.write(f"{test_case},{self.faults},{sum(self.rate) / 1000},{end_to_end_tps / 1000},{end_to_end_latency / 1000},{normalized_std_dev}\n")

        return (
            '\n'
            '-----------------------------------------\n'
            ' SUMMARY:\n'
            '-----------------------------------------\n'
            ' + CONFIG:\n'
            f' Faults: {self.faults} node(s)\n'
            f' Committee size: {self.committee_size} node(s)\n'
            f' Worker(s) per node: {self.workers} worker(s)\n'
            f' Collocate primary and workers: {self.collocate}\n'
            f' Input rate: {sum(self.rate):,} tx/s\n'
            f' Transaction size: {self.size[0]:,} B\n'
            f' Execution time: {round(duration):,} s\n'
            '\n'
            f' Header size: {header_size:,} B\n'
            f' Max header delay: {max_header_delay:,} ms\n'
            f' GC depth: {gc_depth:,} round(s)\n'
            f' Sync retry delay: {sync_retry_delay:,} ms\n'
            f' Sync retry nodes: {sync_retry_nodes:,} node(s)\n'
            f' batch size: {batch_size:,} B\n'
            f' Max batch delay: {max_batch_delay:,} ms\n'
            '\n'
            ' + RESULTS:\n'
            f' Consensus TPS: {round(consensus_tps):,} tx/s\n'
            f' Consensus BPS: {round(consensus_bps):,} B/s\n'
            f' Consensus latency: {round(consensus_latency):,} ms\n'
            '\n'
            f' End-to-end TPS: {round(end_to_end_tps):,} tx/s\n'
            f' End-to-end BPS: {round(end_to_end_bps):,} B/s\n'
            f' End-to-end latency: {round(end_to_end_latency):,} ms\n'
            '\n'
            ' + QUORUM STATISTICS:\n'
            ' Authority occurrences in quorums:\n'
            + ''.join([f'   {auth}: {count}\n' for auth, count in global_authority_counter.items()])
            + f'\n Normalized standard deviation: {normalized_std_dev:.6f}\n'
            '-----------------------------------------\n'
        )

    def print(self, filename):
        assert isinstance(filename, str)
        with open(filename, 'a') as f:
            f.write(self.result(True))

    @classmethod
    def process(cls, directory, faults=0):
        assert isinstance(directory, str)

        clients = []
        for filename in sorted(glob(join(directory, 'client-*.log'))):
            with open(filename, 'r') as f:
                clients += [f.read()]
        primaries = []
        for filename in sorted(glob(join(directory, 'primary-*.log'))):
            with open(filename, 'r') as f:
                primaries += [f.read()]
        workers = []
        for filename in sorted(glob(join(directory, 'worker-*.log'))):
            with open(filename, 'r') as f:
                workers += [f.read()]

        return cls(clients, primaries, workers, faults=faults)


if __name__ == '__main__':
    """Parse logs and print results."""
    parser = argparse.ArgumentParser(description='Parse logs and print results.')
    parser.add_argument(
        '--plot', action='store_true', help='Plot the results'
    )
    parser.add_argument(
        '--dir', type=str, default='', help='Directory containing the logs.'
    )
    parser.add_argument(
        '--faults', type=int, default=0, help='Number of faults to tolerate.'
    )
    parser.add_argument(
        '--test_case', type=str, default='', help='Test case'
    )
    parser.add_argument(
        '--output', type=str, default='results.txt', help='Output file.'
    )
    args = parser.parse_args()
    
    if args.dir != '':
        log_dir = args.dir
        test_case = args.test_case
        
        try:
            results = LogParser.process(args.dir, faults=args.faults)
            print(results.result())
            results.print(args.output)            
        except ParseError as e:
            print(f'Failed to parse logs: {e}')
            exit(1)
    
    if args.plot:
        # Read all data from plot.txt
        with open(f'plot.txt', 'r') as f:
            lines = f.readlines()
        
        # key: (test_case_name, faults, throughput), value: list of (latency, normalized_std_dev)
        grouped = defaultdict(list)
        for line in lines:
            data = line.strip().split(',')
            if len(data) >= 6:
                test_case_name = data[0]
                faults = int(data[1])
                throughput = float(data[3])
                latency = float(data[4])
                normalized_std_dev = float(data[5])
                grouped[(test_case_name, faults, throughput)].append((latency, normalized_std_dev))

        # 按 test_case_name 分组，便于画图
        test_case_groups = defaultdict(list)
        for (test_case_name, faults, throughput), values in grouped.items():
            latencies = [v[0] for v in values]
            std_devs = [v[1] for v in values]
            test_case_groups[test_case_name].append({
                'faults': faults,
                'throughput': throughput,
                'latencies': latencies,
                'latency_mean': np.mean(latencies),
                'latency_std': np.std(latencies) if len(latencies) > 1 else 0,
                'std_devs': std_devs,
                'std_mean': np.mean(std_devs),
                'std_std': np.std(std_devs) if len(std_devs) > 1 else 0,
            })

        # Sort each test case by throughput
        for test_case_name in test_case_groups:
            test_case_groups[test_case_name].sort(key=lambda x: x['throughput'])

        # Define markers and colors for different test cases
        markers = ['o', 's', '^', 'D', 'v', '<', '>', 'p', '*', 'h', 'H', '+', 'x', 'd']
        colors = ['b', 'g', 'r', 'c', 'm', 'y', 'k', 'tab:orange', 'tab:purple', 'tab:brown', 'tab:pink', 'tab:olive', 'tab:cyan']

        # Plot 1: Throughput vs Latency (with error bars)
        plt.figure(figsize=(10, 6))
        for i, (test_case_name, data_points) in enumerate(test_case_groups.items()):
            marker_idx = i % len(markers)
            color_idx = i % len(colors)
            throughputs = [d['throughput'] for d in data_points]
            latency_means = [d['latency_mean'] for d in data_points]
            latency_stds = [d['latency_std'] for d in data_points]
            plt.errorbar(throughputs, latency_means, yerr=latency_stds, fmt=markers[marker_idx]+'-', color=colors[color_idx], elinewidth=1.5, capsize=5, label=f'Test: {test_case_name}')
        plt.xlabel('Throughput (tx/s)')
        plt.ylabel('Latency (s)')
        plt.title('Throughput vs Latency')
        plt.grid(True)
        plt.legend()
        plt.gca().xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'{int(x)}k'))
        plt.savefig(f'throughput_latency.png')

        # Plot 2: Throughput vs Normalized Standard Deviation (with error bars)
        plt.figure(figsize=(10, 6))
        for i, (test_case_name, data_points) in enumerate(test_case_groups.items()):
            marker_idx = i % len(markers)
            color_idx = i % len(colors)
            throughputs = [d['throughput'] for d in data_points]
            std_means = [d['std_mean'] for d in data_points]
            std_stds = [d['std_std'] for d in data_points]
            plt.errorbar(throughputs, std_means, yerr=std_stds, fmt=markers[marker_idx]+'-', color=colors[color_idx], elinewidth=1.5, capsize=5, label=f'Test: {test_case_name}')
        plt.xlabel('Throughput (tx/s)')
        plt.ylabel('Normalized Standard Deviation')
        plt.title('Throughput vs Quorum Distribution Fairness')
        plt.grid(True)
        plt.legend()
        plt.ylim(0, 1)
        plt.gca().xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'{int(x)}k'))
        plt.savefig(f'throughput_fairness.png')
