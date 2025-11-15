#!/usr/bin/env python3
"""Test if Raft ports are accessible"""

import grpc
import sys
import time

sys.path.append('src/raft')
import raft_pb2
import raft_pb2_grpc

def test_raft_port(address, node_name):
    """Test if we can connect to a Raft port"""
    print(f"\nTesting {node_name} at {address}...")
    
    try:
        # Try to connect
        channel = grpc.insecure_channel(address)
        grpc.channel_ready_future(channel).result(timeout=5)
        print(f"  ✓ Connection established")
        
        # Try to make an RPC call
        stub = raft_pb2_grpc.RaftServiceStub(channel)
        
        # Create a test RequestVote
        request = raft_pb2.RequestVoteRequest()
        setattr(request, 'from', 'test')
        request.to = node_name
        request.term = 0
        request.last_log_index = -1
        request.last_log_term = 0
        
        print(f"  Sending test RequestVote...")
        response = stub.RequestVote(request, timeout=5.0)
        print(f"  ✓ Got response: vote_granted={response.vote_granted}, term={response.term}")
        
        channel.close()
        return True
        
    except grpc.FutureTimeoutError:
        print(f"  ✗ Connection timeout")
        return False
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False

def main():
    print("="*60)
    print("Testing Raft Port Connectivity")
    print("="*60)
    
    raft_ports = [
        ('node1', 'localhost:50061'),
        ('node2', 'localhost:50062'),
        ('node3', 'localhost:50063'),
    ]
    
    results = []
    for node_name, address in raft_ports:
        result = test_raft_port(address, node_name)
        results.append(result)
    
    print("\n" + "="*60)
    working = sum(results)
    print(f"Result: {working}/{len(results)} Raft nodes are accessible")
    print("="*60)
    
    if working == 0:
        print("\n⚠ No Raft nodes are responding!")
        print("This means the Raft gRPC servers aren't starting properly.")
        print("\nCheck:")
        print("  1. Are the ports listening? netstat -tuln | grep 5006")
        print("  2. Check logs: tail -f logs/app_server_*.log")
    
    return working == len(results)

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
