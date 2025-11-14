import grpc
import time
import subprocess
import signal
import os

class RaftConsensusTest:
    def __init__(self):
        self.server_pids = {}
    
    def start_server(self, node_id, app_port, raft_port):
        """Start an application server"""
        cmd = [
            'python3', 'src/servers/application_server.py',
            '--node-id', node_id,
            '--port', str(app_port),
            '--raft-port', str(raft_port),
            '--llm-server', 'localhost:50060',
            '--peers', 'node1:localhost:50061,node2:localhost:50062,node3:localhost:50063'
        ]
        
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.server_pids[node_id] = proc.pid
        print(f"Started {node_id} (PID: {proc.pid})")
        return proc
    
    def kill_server(self, node_id):
        """Kill a server process"""
        if node_id in self.server_pids:
            pid = self.server_pids[node_id]
            try:
                os.kill(pid, signal.SIGTERM)
                print(f"Killed {node_id} (PID: {pid})")
                del self.server_pids[node_id]
                return True
            except:
                return False
        return False
    
    def check_leader(self, port):
        """Check if a server is the leader"""
        # This would require adding a status RPC to the proto
        # For now, we'll check logs
        pass
    
    def test_leader_election(self):
        """Test leader election"""
        print("\n" + "="*80)
        print("TEST: Leader Election")
        print("="*80)
        
        print("\n1. Starting 3 servers...")
        servers = [
            self.start_server('node1', 50051, 50061),
            self.start_server('node2', 50052, 50062),
            self.start_server('node3', 50053, 50063)
        ]
        
        print("\n2. Waiting for initial leader election (10 seconds)...")
        time.sleep(10)
        
        print("\n3. Killing leader (node1)...")
        self.kill_server('node1')
        
        print("\n4. Waiting for new leader election (10 seconds)...")
        time.sleep(10)
        
        print("\n5. Check logs to verify new leader was elected")
        print("   Expected: node2 or node3 became leader within 10 seconds")
        
        # Cleanup
        self.kill_server('node2')
        self.kill_server('node3')
        
        print("\n✓ TEST COMPLETED: Check logs/app_server_*.log for verification")
    
    def test_log_replication(self):
        """Test log replication across nodes"""
        print("\n" + "="*80)
        print("TEST: Log Replication")
        print("="*80)
        
        print("\nThis test requires:")
        print("1. Start all servers")
        print("2. Make a booking on one server")
        print("3. Query bookings from different server")
        print("4. Verify same booking appears")
        
        print("\nExpected: Booking appears on all servers (consistency)")
