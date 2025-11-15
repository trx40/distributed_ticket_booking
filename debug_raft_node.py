#!/usr/bin/env python3
"""
Debug version of Raft node with extensive logging
"""

import grpc
import sys
import time
from concurrent import futures

sys.path.insert(0, 'src/raft')
import raft_pb2
import raft_pb2_grpc

class DebugRaftServicer(raft_pb2_grpc.RaftServiceServicer):
    def __init__(self, node_id):
        self.node_id = node_id
        print(f"[{node_id}] Servicer created", flush=True)
    
    def RequestVote(self, request, context):
        from_node = getattr(request, 'from')
        print(f"[{self.node_id}] >>> RequestVote called from {from_node}", flush=True)
        print(f"[{self.node_id}]     term={request.term}", flush=True)
        
        # Just return a simple response
        reply = raft_pb2.RequestVoteReply()
        setattr(reply, 'from', self.node_id)
        reply.to = from_node
        reply.term = 1
        reply.vote_granted = True
        
        print(f"[{self.node_id}] <<< RequestVote returning granted=True", flush=True)
        return reply
    
    def AppendEntries(self, request, context):
        from_node = getattr(request, 'from')
        print(f"[{self.node_id}] >>> AppendEntries called from {from_node}", flush=True)
        
        reply = raft_pb2.AppendEntriesReply()
        setattr(reply, 'from', self.node_id)
        reply.to = from_node
        reply.term = 1
        reply.entry_appended = True
        reply.match_index = -1
        
        print(f"[{self.node_id}] <<< AppendEntries returning", flush=True)
        return reply

def start_debug_node(node_id, port):
    """Start a minimal Raft node for debugging"""
    print(f"[{node_id}] Starting debug Raft node on port {port}...", flush=True)
    
    servicer = DebugRaftServicer(node_id)
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    raft_pb2_grpc.add_RaftServiceServicer_to_server(servicer, server)
    
    # Try binding to IPv4 explicitly
    try:
        server.add_insecure_port(f'0.0.0.0:{port}')
        print(f"[{node_id}] Bound to 0.0.0.0:{port}", flush=True)
    except Exception as e:
        print(f"[{node_id}] Failed to bind to 0.0.0.0:{port}: {e}", flush=True)
        print(f"[{node_id}] Trying [::]:{port}...", flush=True)
        server.add_insecure_port(f'[::]:{port}')
    
    server.start()
    
    print(f"[{node_id}] Server started and listening on port {port}", flush=True)
    print(f"[{node_id}] Ready to accept requests", flush=True)
    print(f"[{node_id}] Press Ctrl+C to stop", flush=True)
    
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        print(f"\n[{node_id}] Shutting down...", flush=True)
        server.stop(0)

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument('--node-id', required=True)
    parser.add_argument('--port', type=int, required=True)
    args = parser.parse_args()
    
    start_debug_node(args.node_id, args.port)
