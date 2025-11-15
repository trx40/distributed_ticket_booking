#!/usr/bin/env python3
"""Test if Raft handlers are working"""

import sys
import os
sys.path.insert(0, 'src/raft')

from raft_node import RaftNode
import raft_pb2

def test_request_vote_handler():
    """Test the RequestVote handler directly"""
    print("Testing RequestVote handler...")
    
    # Create a simple Raft node
    peers = {'test_node': 'localhost:50099'}
    node = RaftNode('test_node', peers, 50099)
    
    # Create a RequestVote request
    request = raft_pb2.RequestVoteRequest()
    setattr(request, 'from', 'other_node')
    request.to = 'test_node'
    request.term = 1
    request.last_log_index = -1
    request.last_log_term = 0
    
    print(f"  Request: from=other_node, term=1")
    print(f"  Node state: {node.state.name}, term={node.current_term}")
    
    # Call the handler directly (no gRPC)
    try:
        print("  Calling RequestVote handler...")
        response = node.RequestVote(request, None)
        print(f"  ✓ Handler returned!")
        print(f"  Response: vote_granted={response.vote_granted}, term={response.term}")
        return True
    except Exception as e:
        print(f"  ✗ Handler failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_append_entries_handler():
    """Test the AppendEntries handler directly"""
    print("\nTesting AppendEntries handler...")
    
    # Create a simple Raft node
    peers = {'test_node': 'localhost:50099'}
    node = RaftNode('test_node', peers, 50099)
    
    # Create an AppendEntries request (heartbeat)
    request = raft_pb2.AppendEntriesRequest()
    setattr(request, 'from', 'leader_node')
    request.to = 'test_node'
    request.term = 1
    request.prev_index = -1
    request.prev_term = 0
    request.commit_index = -1
    
    print(f"  Request: from=leader_node, term=1 (heartbeat)")
    print(f"  Node state: {node.state.name}, term={node.current_term}")
    
    # Call the handler directly (no gRPC)
    try:
        print("  Calling AppendEntries handler...")
        response = node.AppendEntries(request, None)
        print(f"  ✓ Handler returned!")
        print(f"  Response: entry_appended={response.entry_appended}, term={response.term}")
        return True
    except Exception as e:
        print(f"  ✗ Handler failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    print("="*60)
    print("Testing Raft Handlers Directly")
    print("="*60)
    print()
    
    test1 = test_request_vote_handler()
    test2 = test_append_entries_handler()
    
    print("\n" + "="*60)
    if test1 and test2:
        print("✓ All handlers work correctly")
        print("\nThe issue must be with gRPC server registration or threading")
    else:
        print("✗ Handlers are broken - need to fix the handler code")
    print("="*60)
