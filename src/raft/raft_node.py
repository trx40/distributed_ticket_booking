import grpc
import time
import random
import threading
import json
import sys
import os
from concurrent import futures
from enum import Enum

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import raft_pb2
import raft_pb2_grpc

# Import state machine from same directory
from state_machine import StateMachine

class NodeState(Enum):
    FOLLOWER = 1
    CANDIDATE = 2
    LEADER = 3

class RaftNode(raft_pb2_grpc.RaftServiceServicer):
    def __init__(self, node_id, peers, port):
        self.node_id = node_id
        self.peers = peers  # {node_id: address}
        self.port = port
        
        # Raft state
        self.state = NodeState.FOLLOWER
        self.current_term = 0
        self.voted_for = None
        self.log = []  # List of log entries
        self.commit_index = -1
        self.last_applied = -1
        
        # Leader state
        self.next_index = {}
        self.match_index = {}
        
        # Timing
        self.last_heartbeat = time.time()
        self.election_timeout = random.uniform(5.0, 10.0)
        self.heartbeat_interval = 1.0  # Faster heartbeats for better responsiveness
        
        # State machine
        self.state_machine = StateMachine()
        
        # Threading - use RLock to allow reentrant locking
        self.lock = threading.RLock()
        self.running = True
        
        # Delay starting background threads
        self.election_thread = threading.Thread(target=self._election_timer, daemon=True)
        self.heartbeat_thread = threading.Thread(target=self._heartbeat_timer, daemon=True)
        
        print(f"[{self.node_id}] Initialized as FOLLOWER", flush=True)
    
    def start(self):
        """Start Raft node - non-blocking version for use in daemon thread"""
        # Start gRPC server first
        self.server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
        raft_pb2_grpc.add_RaftServiceServicer_to_server(self, self.server)
        self.server.add_insecure_port(f'[::]:{self.port}')
        self.server.start()
        print(f"[{self.node_id}] Raft gRPC server started on port {self.port}", flush=True)
        
        # Give the server a moment to start accepting connections
        time.sleep(0.5)
        
        # NOW start the background threads
        self.election_thread.start()
        self.heartbeat_thread.start()
        print(f"[{self.node_id}] Raft background threads started", flush=True)
        
        # Don't block - let the thread continue
        # The server will keep running in the background
    
    def stop(self):
        """Stop the Raft node"""
        self.running = False
        if hasattr(self, 'server'):
            self.server.stop(0)
    
    def _election_timer(self):
        # Wait before starting election monitoring to let server initialize
        time.sleep(2.0)
        print(f"[{self.node_id}] Election timer started", flush=True)
        
        while self.running:
            time.sleep(0.5)
            
            # Use timeout to avoid blocking forever
            acquired = self.lock.acquire(timeout=1.0)
            if not acquired:
                print(f"[{self.node_id}] Election timer: couldn't acquire lock", flush=True)
                continue
            
            try:
                if self.state == NodeState.LEADER:
                    continue
                
                elapsed = time.time() - self.last_heartbeat
                if elapsed > self.election_timeout:
                    print(f"[{self.node_id}] Election timeout, starting election", flush=True)
                    self._start_election()
            finally:
                self.lock.release()
    
    def _start_election(self):
        # This is called while holding the lock already
        self.state = NodeState.CANDIDATE
        self.current_term += 1
        self.voted_for = self.node_id
        self.last_heartbeat = time.time()
        self.election_timeout = random.uniform(5.0, 10.0)
        
        term = self.current_term
        last_log_index = len(self.log) - 1
        last_log_term = self.log[-1].term if self.log else 0
        
        print(f"[{self.node_id}] Starting election for term {term}", flush=True)
        
        votes = 1  # Vote for self
        peers_to_contact = [(pid, paddr) for pid, paddr in self.peers.items() if pid != self.node_id]
        
        # Release lock while making RPC calls to other nodes
        self.lock.release()
        
        try:
            for peer_id, peer_addr in peers_to_contact:
                try:
                    print(f"[{self.node_id}] Requesting vote from {peer_id} at {peer_addr}", flush=True)
                    channel = grpc.insecure_channel(peer_addr)
                    stub = raft_pb2_grpc.RaftServiceStub(channel)
                    
                    # Create request - 'from' is a keyword so we use setattr
                    request = raft_pb2.RequestVoteRequest()
                    setattr(request, 'from', self.node_id)
                    request.to = peer_id
                    request.term = term
                    request.last_log_index = last_log_index
                    request.last_log_term = last_log_term
                    
                    response = stub.RequestVote(request, timeout=2.0)
                    
                    # Re-acquire lock to check state
                    if not self.lock.acquire(timeout=1.0):
                        print(f"[{self.node_id}] Couldn't reacquire lock in election", flush=True)
                        channel.close()
                        return
                    
                    try:
                        if response.term > self.current_term:
                            print(f"[{self.node_id}] Higher term {response.term} from {peer_id}, stepping down", flush=True)
                            self._step_down(response.term)
                            channel.close()
                            return
                        
                        if response.vote_granted:
                            votes += 1
                            print(f"[{self.node_id}] Received vote from {peer_id} (total: {votes})", flush=True)
                        else:
                            print(f"[{self.node_id}] Vote denied by {peer_id}", flush=True)
                    finally:
                        self.lock.release()
                    
                    channel.close()
                except Exception as e:
                    print(f"[{self.node_id}] Failed to request vote from {peer_id}: {e}", flush=True)
            
            # Re-acquire lock for final vote count
            if not self.lock.acquire(timeout=1.0):
                print(f"[{self.node_id}] Couldn't reacquire lock for final vote count", flush=True)
                return
            
            try:
                majority = (len(self.peers) + 1) // 2 + 1
                print(f"[{self.node_id}] Election complete: {votes} votes, need {majority} for majority", flush=True)
                
                if self.state == NodeState.CANDIDATE and votes >= majority:
                    self._become_leader()
                else:
                    print(f"[{self.node_id}] Election failed, not enough votes", flush=True)
            finally:
                pass  # Lock will be released by caller
        
        except Exception as e:
            print(f"[{self.node_id}] Election error: {e}", flush=True)
            # Try to reacquire lock before returning
            try:
                self.lock.acquire(timeout=0.5)
            except:
                pass
    
    def _become_leader(self):
        print(f"[{self.node_id}] Became LEADER for term {self.current_term}")
        self.state = NodeState.LEADER
        
        # Initialize leader state
        for peer_id in self.peers:
            if peer_id != self.node_id:
                self.next_index[peer_id] = len(self.log)
                self.match_index[peer_id] = -1
    
    def _step_down(self, term):
        print(f"[{self.node_id}] Stepping down to FOLLOWER (term {term})")
        self.state = NodeState.FOLLOWER
        self.current_term = term
        self.voted_for = None
    
    def _heartbeat_timer(self):
        # Wait before starting heartbeats
        time.sleep(2.0)
        print(f"[{self.node_id}] Heartbeat timer started", flush=True)
        
        while self.running:
            time.sleep(self.heartbeat_interval)
            
            # Use timeout to avoid blocking forever
            acquired = self.lock.acquire(timeout=1.0)
            if not acquired:
                continue
            
            try:
                if self.state == NodeState.LEADER:
                    self._send_heartbeats()
            finally:
                self.lock.release()
    
    def _send_heartbeats(self):
        for peer_id, peer_addr in self.peers.items():
            if peer_id == self.node_id:
                continue
            
            try:
                channel = grpc.insecure_channel(peer_addr)
                stub = raft_pb2_grpc.RaftServiceStub(channel)
                
                next_idx = self.next_index.get(peer_id, len(self.log))
                prev_index = next_idx - 1
                prev_term = self.log[prev_index].term if prev_index >= 0 else 0
                
                entries = []
                if next_idx < len(self.log):
                    entries = [raft_pb2.LogEntry(
                        term=entry.term,
                        command=entry.command
                    ) for entry in self.log[next_idx:]]
                
                # Create request - 'from' is a keyword so we use setattr
                request = raft_pb2.AppendEntriesRequest()
                setattr(request, 'from', self.node_id)
                request.to = peer_id
                request.term = self.current_term
                request.prev_index = prev_index
                request.prev_term = prev_term
                request.commit_index = self.commit_index
                request.entries.extend(entries)
                
                response = stub.AppendEntries(request, timeout=2.0)
                
                with self.lock:
                    if response.term > self.current_term:
                        self._step_down(response.term)
                        channel.close()
                        return
                    
                    if response.entry_appended:
                        self.match_index[peer_id] = response.match_index
                        self.next_index[peer_id] = response.match_index + 1
                    else:
                        self.next_index[peer_id] = max(0, self.next_index[peer_id] - 1)
                
                channel.close()
            except Exception as e:
                pass  # Silently handle heartbeat failures
    
    def RequestVote(self, request, context):
        """Handle RequestVote RPC - MUST NOT DEADLOCK"""
        try:
            # Get 'from' field using getattr to handle reserved keyword
            from_node = getattr(request, 'from')
            
            print(f"[{self.node_id}] Received RequestVote from {from_node} for term {request.term}", flush=True)
            
            with self.lock:
                if request.term > self.current_term:
                    self._step_down(request.term)
                
                vote_granted = False
                
                if request.term == self.current_term:
                    if self.voted_for is None or self.voted_for == from_node:
                        last_log_index = len(self.log) - 1
                        last_log_term = self.log[-1].term if self.log else 0
                        
                        if (request.last_log_term > last_log_term or 
                            (request.last_log_term == last_log_term and 
                             request.last_log_index >= last_log_index)):
                            vote_granted = True
                            self.voted_for = from_node
                            self.last_heartbeat = time.time()
                            print(f"[{self.node_id}] Granted vote to {from_node} for term {request.term}", flush=True)
                        else:
                            print(f"[{self.node_id}] Denied vote to {from_node} - log not up to date", flush=True)
                    else:
                        print(f"[{self.node_id}] Denied vote to {from_node} - already voted for {self.voted_for}", flush=True)
                else:
                    print(f"[{self.node_id}] Denied vote to {from_node} - term mismatch ({request.term} vs {self.current_term})", flush=True)
                
                current_term = self.current_term
            
            # Create response OUTSIDE the lock
            reply = raft_pb2.RequestVoteReply()
            setattr(reply, 'from', self.node_id)
            reply.to = from_node
            reply.term = current_term
            reply.vote_granted = vote_granted
            
            print(f"[{self.node_id}] Sending RequestVote response to {from_node}: granted={vote_granted}", flush=True)
            return reply
            
        except Exception as e:
            print(f"[{self.node_id}] ERROR in RequestVote: {e}", flush=True)
            import traceback
            traceback.print_exc()
            raise
    
    def AppendEntries(self, request, context):
        with self.lock:
            # Get 'from' field using getattr to handle reserved keyword
            from_node = getattr(request, 'from')
            
            if request.term > self.current_term:
                self._step_down(request.term)
            
            self.last_heartbeat = time.time()
            entry_appended = False
            match_index = -1
            
            if request.term == self.current_term:
                if self.state != NodeState.FOLLOWER:
                    print(f"[{self.node_id}] Converting to FOLLOWER (received AppendEntries from {from_node})", flush=True)
                    self.state = NodeState.FOLLOWER
                
                # Log consistency check
                if request.prev_index == -1 or (
                    request.prev_index < len(self.log) and
                    self.log[request.prev_index].term == request.prev_term
                ):
                    entry_appended = True
                    
                    # Append new entries
                    if request.entries:
                        insert_idx = request.prev_index + 1
                        for i, entry in enumerate(request.entries):
                            idx = insert_idx + i
                            if idx < len(self.log):
                                self.log[idx] = type('LogEntry', (), {
                                    'term': entry.term,
                                    'command': entry.command
                                })()
                            else:
                                self.log.append(type('LogEntry', (), {
                                    'term': entry.term,
                                    'command': entry.command
                                })())
                        
                        match_index = insert_idx + len(request.entries) - 1
                    else:
                        match_index = request.prev_index
                    
                    # Update commit index
                    if request.commit_index > self.commit_index:
                        self.commit_index = min(request.commit_index, len(self.log) - 1)
                        self._apply_committed_entries()
            
            # Create response using setattr for 'from' field
            reply = raft_pb2.AppendEntriesReply()
            setattr(reply, 'from', self.node_id)
            reply.to = from_node
            reply.term = self.current_term
            reply.entry_appended = entry_appended
            reply.match_index = match_index
            
            return reply
    
    def _apply_committed_entries(self):
        while self.last_applied < self.commit_index:
            self.last_applied += 1
            entry = self.log[self.last_applied]
            result = self.state_machine.apply_command(entry.command)
            print(f"[{self.node_id}] Applied log entry {self.last_applied}: {result}")
    
    def submit_command(self, command):
        with self.lock:
            if self.state != NodeState.LEADER:
                return {'status': 'error', 'message': 'Not leader'}
            
            # Append to log
            log_entry = type('LogEntry', (), {
                'term': self.current_term,
                'command': command
            })()
            self.log.append(log_entry)
            log_index = len(self.log) - 1
            
            print(f"[{self.node_id}] Command submitted to log index {log_index}")
        
        # Trigger immediate heartbeat to replicate
        self._send_heartbeats()
        
        # Wait for replication with timeout
        max_wait = 5.0  # 5 seconds max
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            with self.lock:
                # Check if we're still leader
                if self.state != NodeState.LEADER:
                    return {'status': 'error', 'message': 'Lost leadership'}
                
                # Check if command is replicated to majority
                match_indices = [log_index] + [self.match_index.get(p, -1) for p in self.peers if p != self.node_id]
                match_indices.sort()
                majority_index = match_indices[len(match_indices) // 2]
                
                if majority_index >= log_index:
                    # Command replicated to majority
                    if self.commit_index < log_index:
                        self.commit_index = log_index
                        self._apply_committed_entries()
                    
                    print(f"[{self.node_id}] Command committed at index {log_index}")
                    return {'status': 'success', 'message': 'Command committed'}
            
            time.sleep(0.1)
        
        print(f"[{self.node_id}] Command replication timeout at index {log_index}")
        return {'status': 'error', 'message': 'Replication timeout'}
    
    def is_leader(self):
        with self.lock:
            return self.state == NodeState.LEADER
    
    def get_leader_info(self):
        with self.lock:
            return {
                'is_leader': self.state == NodeState.LEADER,
                'term': self.current_term,
                'state': self.state.name
            }