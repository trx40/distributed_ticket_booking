import grpc
import time
import random
import threading
import json
from concurrent import futures
from enum import Enum

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
        self.heartbeat_interval = 2.0
        
        # State machine
        self.state_machine = StateMachine()
        
        # Threading
        self.lock = threading.Lock()
        self.running = True
        
        # Start background threads
        self.election_thread = threading.Thread(target=self._election_timer, daemon=True)
        self.heartbeat_thread = threading.Thread(target=self._heartbeat_timer, daemon=True)
        
        print(f"[{self.node_id}] Initialized as FOLLOWER")
    
    def start(self):
        self.election_thread.start()
        self.heartbeat_thread.start()
        
        server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
        raft_pb2_grpc.add_RaftServiceServicer_to_server(self, server)
        server.add_insecure_port(f'[::]:{self.port}')
        server.start()
        print(f"[{self.node_id}] Raft node started on port {self.port}")
        
        try:
            server.wait_for_termination()
        except KeyboardInterrupt:
            self.running = False
            server.stop(0)
    
    def _election_timer(self):
        while self.running:
            time.sleep(0.5)
            
            with self.lock:
                if self.state == NodeState.LEADER:
                    continue
                
                elapsed = time.time() - self.last_heartbeat
                if elapsed > self.election_timeout:
                    print(f"[{self.node_id}] Election timeout, starting election")
                    self._start_election()
    
    def _start_election(self):
        self.state = NodeState.CANDIDATE
        self.current_term += 1
        self.voted_for = self.node_id
        self.last_heartbeat = time.time()
        self.election_timeout = random.uniform(5.0, 10.0)
        
        term = self.current_term
        last_log_index = len(self.log) - 1
        last_log_term = self.log[-1].term if self.log else 0
        
        print(f"[{self.node_id}] Starting election for term {term}")
        
        votes = 1  # Vote for self
        
        for peer_id, peer_addr in self.peers.items():
            if peer_id == self.node_id:
                continue
            
            try:
                channel = grpc.insecure_channel(peer_addr)
                stub = raft_pb2_grpc.RaftServiceStub(channel)
                
                request = raft_pb2.RequestVoteRequest(
                    from_=self.node_id,
                    to=peer_id,
                    term=term,
                    last_log_index=last_log_index,
                    last_log_term=last_log_term
                )
                
                response = stub.RequestVote(request, timeout=2.0)
                
                with self.lock:
                    if response.term > self.current_term:
                        self._step_down(response.term)
                        return
                    
                    if response.vote_granted:
                        votes += 1
                        print(f"[{self.node_id}] Received vote from {peer_id}")
                
                channel.close()
            except Exception as e:
                print(f"[{self.node_id}] Failed to request vote from {peer_id}: {e}")
        
        with self.lock:
            if self.state == NodeState.CANDIDATE and votes > len(self.peers) // 2:
                self._become_leader()
    
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
        while self.running:
            time.sleep(self.heartbeat_interval)
            
            with self.lock:
                if self.state == NodeState.LEADER:
                    self._send_heartbeats()
    
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
                
                request = raft_pb2.AppendEntriesRequest(
                    from_=self.node_id,
                    to=peer_id,
                    term=self.current_term,
                    prev_index=prev_index,
                    prev_term=prev_term,
                    commit_index=self.commit_index,
                    entries=entries
                )
                
                response = stub.AppendEntries(request, timeout=2.0)
                
                with self.lock:
                    if response.term > self.current_term:
                        self._step_down(response.term)
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
        with self.lock:
            if request.term > self.current_term:
                self._step_down(request.term)
            
            vote_granted = False
            
            if request.term == self.current_term:
                if self.voted_for is None or self.voted_for == request.from_:
                    last_log_index = len(self.log) - 1
                    last_log_term = self.log[-1].term if self.log else 0
                    
                    if (request.last_log_term > last_log_term or 
                        (request.last_log_term == last_log_term and 
                         request.last_log_index >= last_log_index)):
                        vote_granted = True
                        self.voted_for = request.from_
                        self.last_heartbeat = time.time()
            
            return raft_pb2.RequestVoteReply(
                from_=self.node_id,
                to=request.from_,
                term=self.current_term,
                vote_granted=vote_granted
            )
    
    def AppendEntries(self, request, context):
        with self.lock:
            if request.term > self.current_term:
                self._step_down(request.term)
            
            self.last_heartbeat = time.time()
            entry_appended = False
            match_index = -1
            
            if request.term == self.current_term:
                if self.state != NodeState.FOLLOWER:
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
            
            return raft_pb2.AppendEntriesReply(
                from_=self.node_id,
                to=request.from_,
                term=self.current_term,
                entry_appended=entry_appended,
                match_index=match_index
            )
    
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
            
            print(f"[{self.node_id}] Command submitted to log index {len(self.log) - 1}")
            
            # Wait for replication (simplified)
            time.sleep(1.0)
            
            # Update commit index
            match_indices = [len(self.log) - 1] + list(self.match_index.values())
            match_indices.sort()
            majority_index = match_indices[len(match_indices) // 2]
            
            if majority_index > self.commit_index and self.log[majority_index].term == self.current_term:
                self.commit_index = majority_index
                self._apply_committed_entries()
            
            return {'status': 'success', 'message': 'Command committed'}
    
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
