#!/usr/bin/env python3
"""
Ultra-Robust Raft Implementation
Key principle: NEVER hold locks during I/O operations
"""

import grpc
import time
import random
import threading
import json
import sys
import os
from concurrent import futures
from enum import Enum
from queue import Queue, Empty

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import raft_pb2
import raft_pb2_grpc
from state_machine import StateMachine

class NodeState(Enum):
    FOLLOWER = 1
    CANDIDATE = 2
    LEADER = 3


class RaftNode(raft_pb2_grpc.RaftServiceServicer):
    def __init__(self, node_id, peers, port):
        self.node_id = node_id
        self.peers = peers
        self.port = port
        
        # Raft persistent state
        self.current_term = 0
        self.voted_for = None
        self.log = []
        
        # Raft volatile state
        self.commit_index = -1
        self.last_applied = -1
        self.state = NodeState.FOLLOWER
        
        # Leader volatile state
        self.next_index = {}
        self.match_index = {}
        
        # Timing
        self.last_heartbeat_time = time.time()
        self.election_timeout = random.uniform(5.0, 10.0)
        self.heartbeat_interval = 1.0
        
        # State machine
        self.state_machine = StateMachine()
        
        # Simple lock - only for updating state variables
        self.lock = threading.Lock()
        
        # Command queue for clients
        self.pending_commands = Queue()
        
        # Control flag
        self.running = True
        
        print(f"[{self.node_id}] Raft node initialized", flush=True)
    
    def start(self):
        """Start the Raft node"""
        # Start gRPC server
        self.server = grpc.server(
            futures.ThreadPoolExecutor(max_workers=20),
            options=[
                ('grpc.max_send_message_length', 50 * 1024 * 1024),
                ('grpc.max_receive_message_length', 50 * 1024 * 1024),
                ('grpc.so_reuseport', 1),
                ('grpc.keepalive_time_ms', 10000),
                ('grpc.keepalive_timeout_ms', 5000),
            ]
        )
        raft_pb2_grpc.add_RaftServiceServicer_to_server(self, self.server)
        self.server.add_insecure_port(f'[::]:{self.port}')
        self.server.start()
        
        print(f"[{self.node_id}] gRPC server started on port {self.port}", flush=True)
        
        # Start background threads
        threading.Thread(target=self._election_loop, daemon=True, name=f"{self.node_id}-election").start()
        threading.Thread(target=self._heartbeat_loop, daemon=True, name=f"{self.node_id}-heartbeat").start()
        threading.Thread(target=self._apply_loop, daemon=True, name=f"{self.node_id}-apply").start()
        
        print(f"[{self.node_id}] Background threads started", flush=True)
        time.sleep(0.5)
    
    def stop(self):
        """Stop the node"""
        self.running = False
        if hasattr(self, 'server'):
            self.server.stop(grace=0)
    
    # ==================== BACKGROUND LOOPS ====================
    
    def _election_loop(self):
        """Monitor election timeout and trigger elections"""
        time.sleep(2.0)  # Initial delay
        print(f"[{self.node_id}] Election loop started", flush=True)
        
        while self.running:
            try:
                time.sleep(0.5)
                
                # Read state without holding lock for long
                with self.lock:
                    current_state = self.state
                    last_hb = self.last_heartbeat_time
                    timeout = self.election_timeout
                
                # Check timeout only if not leader
                if current_state != NodeState.LEADER:
                    if time.time() - last_hb > timeout:
                        # Trigger election WITHOUT holding lock
                        self._start_election()
                        
            except Exception as e:
                print(f"[{self.node_id}] Election loop error: {e}", flush=True)
                time.sleep(1)
    
    def _heartbeat_loop(self):
        """Send heartbeats if leader"""
        time.sleep(2.0)
        print(f"[{self.node_id}] Heartbeat loop started", flush=True)
        
        while self.running:
            try:
                time.sleep(self.heartbeat_interval)
                
                # Check if leader without holding lock
                with self.lock:
                    is_leader = (self.state == NodeState.LEADER)
                
                if is_leader:
                    # Send heartbeats WITHOUT holding lock
                    self._send_heartbeats()
                    
            except Exception as e:
                print(f"[{self.node_id}] Heartbeat loop error: {e}", flush=True)
                time.sleep(1)
    
    def _apply_loop(self):
        """Apply committed entries to state machine"""
        time.sleep(2.0)
        print(f"[{self.node_id}] Apply loop started", flush=True)
        
        while self.running:
            try:
                time.sleep(0.1)
                
                with self.lock:
                    # Check if there are entries to apply
                    if self.last_applied < self.commit_index:
                        self.last_applied += 1
                        idx = self.last_applied
                        
                        # Get entry to apply
                        if idx < len(self.log):
                            entry = self.log[idx]
                            command = entry['command']
                        else:
                            continue
                
                # Apply to state machine WITHOUT holding lock
                try:
                    result = self.state_machine.apply_command(command)
                    
                    # Store result
                    with self.lock:
                        if idx < len(self.log):
                            self.log[idx]['result'] = result
                    
                    print(f"[{self.node_id}] Applied entry {idx}", flush=True)
                except Exception as e:
                    print(f"[{self.node_id}] Error applying entry {idx}: {e}", flush=True)
                    
            except Exception as e:
                print(f"[{self.node_id}] Apply loop error: {e}", flush=True)
                time.sleep(1)
    
    # ==================== ELECTION LOGIC ====================
    
    def _start_election(self):
        """Start election - NO LOCKS HELD DURING RPC"""
        try:
            # Transition to candidate
            with self.lock:
                self.state = NodeState.CANDIDATE
                self.current_term += 1
                self.voted_for = self.node_id
                self.last_heartbeat_time = time.time()
                self.election_timeout = random.uniform(5.0, 10.0)
                
                term = self.current_term
                last_idx = len(self.log) - 1
                last_term = self.log[-1]['term'] if self.log else 0
            
            print(f"[{self.node_id}] Starting election for term {term}", flush=True)
            
            # Vote for self
            votes = 1
            votes_lock = threading.Lock()
            
            # Request votes from all peers IN PARALLEL
            def request_vote_worker(peer_id, peer_addr):
                """Worker thread to request vote from one peer"""
                try:
                    channel = grpc.insecure_channel(
                        peer_addr,
                        options=[
                            ('grpc.max_connection_idle_ms', 5000),
                        ]
                    )
                    stub = raft_pb2_grpc.RaftServiceStub(channel)
                    
                    request = raft_pb2.RequestVoteRequest()
                    setattr(request, 'from', self.node_id)
                    request.to = peer_id
                    request.term = term
                    request.last_log_index = last_idx
                    request.last_log_term = last_term
                    
                    # Make RPC with timeout
                    response = stub.RequestVote(request, timeout=2.0)
                    
                    # Process response
                    if response.vote_granted:
                        with votes_lock:
                            nonlocal votes
                            votes += 1
                        print(f"[{self.node_id}] Got vote from {peer_id}", flush=True)
                    
                    # Check for higher term
                    if response.term > term:
                        with self.lock:
                            if response.term > self.current_term:
                                self._step_down_unsafe(response.term)
                    
                    channel.close()
                    
                except grpc.RpcError as e:
                    # Node unavailable - this is NORMAL during failures
                    pass
                except Exception as e:
                    print(f"[{self.node_id}] Vote request error from {peer_id}: {e}", flush=True)
            
            # Launch all vote requests in parallel
            threads = []
            for peer_id, peer_addr in self.peers.items():
                if peer_id != self.node_id:
                    t = threading.Thread(
                        target=request_vote_worker,
                        args=(peer_id, peer_addr),
                        daemon=True
                    )
                    t.start()
                    threads.append(t)
            
            # Wait for all threads with timeout
            for t in threads:
                t.join(timeout=3.0)
            
            # Check election result
            majority = (len(self.peers) // 2) + 1
            
            print(f"[{self.node_id}] Election result: {votes}/{len(self.peers)} votes (need {majority})", flush=True)
            
            with self.lock:
                # Only become leader if still candidate and won
                if self.state == NodeState.CANDIDATE and votes >= majority:
                    self._become_leader_unsafe()
                    
        except Exception as e:
            print(f"[{self.node_id}] Election error: {e}", flush=True)
            import traceback
            traceback.print_exc()
    
    def _become_leader_unsafe(self):
        """Become leader - MUST BE CALLED WITH LOCK HELD"""
        print(f"[{self.node_id}] Became LEADER for term {self.current_term}", flush=True)
        self.state = NodeState.LEADER
        
        # Initialize leader state
        for peer_id in self.peers:
            if peer_id != self.node_id:
                self.next_index[peer_id] = len(self.log)
                self.match_index[peer_id] = -1
    
    def _step_down_unsafe(self, term):
        """Step down to follower - MUST BE CALLED WITH LOCK HELD"""
        if term > self.current_term:
            print(f"[{self.node_id}] Stepping down to term {term}", flush=True)
            self.current_term = term
            self.voted_for = None
            self.state = NodeState.FOLLOWER
            self.last_heartbeat_time = time.time()
    
    # ==================== HEARTBEAT LOGIC ====================
    
    def _send_heartbeats(self):
        """Send heartbeats to all followers - NO LOCKS HELD DURING RPC"""
        # Get current state
        with self.lock:
            if self.state != NodeState.LEADER:
                return
            term = self.current_term
            commit_idx = self.commit_index
        
        # Send to all peers in parallel
        def heartbeat_worker(peer_id, peer_addr):
            """Send AppendEntries to one peer"""
            try:
                # Get data for this peer
                with self.lock:
                    if self.state != NodeState.LEADER:
                        return
                    
                    next_idx = self.next_index.get(peer_id, len(self.log))
                    prev_idx = next_idx - 1
                    prev_term = self.log[prev_idx]['term'] if prev_idx >= 0 else 0
                    
                    # Get entries to send
                    entries_to_send = []
                    if next_idx < len(self.log):
                        entries_to_send = self.log[next_idx:]
                
                # Make RPC WITHOUT lock
                channel = grpc.insecure_channel(
                    peer_addr,
                    options=[('grpc.max_connection_idle_ms', 5000)]
                )
                stub = raft_pb2_grpc.RaftServiceStub(channel)
                
                request = raft_pb2.AppendEntriesRequest()
                setattr(request, 'from', self.node_id)
                request.to = peer_id
                request.term = term
                request.prev_index = prev_idx
                request.prev_term = prev_term
                request.commit_index = commit_idx
                
                # Add entries
                for entry in entries_to_send:
                    log_entry = raft_pb2.LogEntry()
                    log_entry.term = entry['term']
                    log_entry.command = entry['command']
                    request.entries.append(log_entry)
                
                response = stub.AppendEntries(request, timeout=1.5)
                
                # Process response
                with self.lock:
                    if self.state != NodeState.LEADER:
                        channel.close()
                        return
                    
                    if response.term > self.current_term:
                        self._step_down_unsafe(response.term)
                        channel.close()
                        return
                    
                    if response.entry_appended:
                        self.match_index[peer_id] = response.match_index
                        self.next_index[peer_id] = response.match_index + 1
                        self._update_commit_index_unsafe()
                    else:
                        # Decrement on failure
                        self.next_index[peer_id] = max(0, self.next_index[peer_id] - 1)
                
                channel.close()
                
            except grpc.RpcError:
                # Peer unavailable - normal during failures
                pass
            except Exception as e:
                print(f"[{self.node_id}] Heartbeat error to {peer_id}: {e}", flush=True)
        
        # Launch all heartbeats in parallel
        for peer_id, peer_addr in self.peers.items():
            if peer_id != self.node_id:
                threading.Thread(
                    target=heartbeat_worker,
                    args=(peer_id, peer_addr),
                    daemon=True
                ).start()
    
    def _update_commit_index_unsafe(self):
        """Update commit index - MUST BE CALLED WITH LOCK HELD"""
        if self.state != NodeState.LEADER:
            return
        
        # Get match indices
        match_indices = [len(self.log) - 1]
        for peer_id in self.peers:
            if peer_id != self.node_id:
                match_indices.append(self.match_index.get(peer_id, -1))
        
        # Find majority
        match_indices.sort()
        majority_idx = match_indices[len(match_indices) // 2]
        
        # Update commit index if higher and from current term
        if majority_idx > self.commit_index:
            if majority_idx < len(self.log) and self.log[majority_idx]['term'] == self.current_term:
                self.commit_index = majority_idx
    
    # ==================== RPC HANDLERS ====================
    
    def RequestVote(self, request, context):
        """Handle RequestVote RPC"""
        try:
            with self.lock:
                from_node = getattr(request, 'from')
                
                # Update term if higher
                if request.term > self.current_term:
                    self._step_down_unsafe(request.term)
                
                vote_granted = False
                
                # Grant vote if eligible
                if request.term == self.current_term:
                    if self.voted_for is None or self.voted_for == from_node:
                        # Check log up-to-date
                        last_idx = len(self.log) - 1
                        last_term = self.log[-1]['term'] if self.log else 0
                        
                        log_ok = (request.last_log_term > last_term or
                                 (request.last_log_term == last_term and 
                                  request.last_log_index >= last_idx))
                        
                        if log_ok:
                            vote_granted = True
                            self.voted_for = from_node
                            self.last_heartbeat_time = time.time()
                
                reply = raft_pb2.RequestVoteReply()
                setattr(reply, 'from', self.node_id)
                reply.to = from_node
                reply.term = self.current_term
                reply.vote_granted = vote_granted
                
                return reply
                
        except Exception as e:
            print(f"[{self.node_id}] RequestVote error: {e}", flush=True)
            reply = raft_pb2.RequestVoteReply()
            setattr(reply, 'from', self.node_id)
            reply.to = getattr(request, 'from', 'unknown')
            reply.term = self.current_term
            reply.vote_granted = False
            return reply
    
    def AppendEntries(self, request, context):
        """Handle AppendEntries RPC"""
        try:
            with self.lock:
                from_node = getattr(request, 'from')
                
                # Update term if higher
                if request.term > self.current_term:
                    self._step_down_unsafe(request.term)
                
                # Reset election timer
                self.last_heartbeat_time = time.time()
                
                entry_appended = False
                match_idx = -1
                
                # Process if term matches
                if request.term == self.current_term:
                    # Become follower if candidate
                    if self.state != NodeState.FOLLOWER:
                        self.state = NodeState.FOLLOWER
                    
                    # Check log consistency
                    log_ok = (request.prev_index == -1 or
                             (request.prev_index < len(self.log) and
                              self.log[request.prev_index]['term'] == request.prev_term))
                    
                    if log_ok:
                        entry_appended = True
                        
                        # Append entries
                        if request.entries:
                            insert_idx = request.prev_index + 1
                            
                            for i, entry in enumerate(request.entries):
                                idx = insert_idx + i
                                new_entry = {
                                    'term': entry.term,
                                    'command': entry.command,
                                    'result': None
                                }
                                
                                if idx < len(self.log):
                                    if self.log[idx]['term'] != entry.term:
                                        self.log = self.log[:idx]
                                        self.log.append(new_entry)
                                else:
                                    self.log.append(new_entry)
                            
                            match_idx = insert_idx + len(request.entries) - 1
                        else:
                            match_idx = request.prev_index
                        
                        # Update commit index
                        if request.commit_index > self.commit_index:
                            self.commit_index = min(request.commit_index, len(self.log) - 1)
                
                reply = raft_pb2.AppendEntriesReply()
                setattr(reply, 'from', self.node_id)
                reply.to = from_node
                reply.term = self.current_term
                reply.entry_appended = entry_appended
                reply.match_index = match_idx
                
                return reply
                
        except Exception as e:
            print(f"[{self.node_id}] AppendEntries error: {e}", flush=True)
            reply = raft_pb2.AppendEntriesReply()
            setattr(reply, 'from', self.node_id)
            reply.to = getattr(request, 'from', 'unknown')
            reply.term = self.current_term
            reply.entry_appended = False
            reply.match_index = -1
            return reply
    
    # ==================== CLIENT API ====================
    
    def submit_command(self, command):
        """Submit command - SIMPLIFIED VERSION"""
        # Quick check if leader
        with self.lock:
            if self.state != NodeState.LEADER:
                return {'status': 'error', 'message': 'Not leader'}
            
            # Append to log
            entry = {
                'term': self.current_term,
                'command': command,
                'result': None
            }
            self.log.append(entry)
            log_idx = len(self.log) - 1
        
        # Trigger replication
        self._send_heartbeats()
        
        # Wait for commit
        timeout = 10.0
        start = time.time()
        
        while time.time() - start < timeout:
            with self.lock:
                if self.state != NodeState.LEADER:
                    return {'status': 'error', 'message': 'Lost leadership'}
                
                if self.commit_index >= log_idx:
                    result = self.log[log_idx].get('result')
                    if result:
                        return result
            
            time.sleep(0.05)
        
        return {'status': 'error', 'message': 'Timeout'}
    
    def is_leader(self):
        """Check if leader"""
        with self.lock:
            return self.state == NodeState.LEADER
    
    def get_leader_info(self):
        """Get info"""
        with self.lock:
            return {
                'is_leader': self.state == NodeState.LEADER,
                'term': self.current_term,
                'state': self.state.name
            }