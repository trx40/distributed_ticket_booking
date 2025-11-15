#!/usr/bin/env python3
"""Application Server with Raft Consensus"""

import grpc
import json
import sys
import os
import time
import threading
from concurrent import futures

# Force unbuffered output
sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', buffering=1)
sys.stderr = os.fdopen(sys.stderr.fileno(), 'w', buffering=1)

print(f"[DEBUG] Application server starting...", flush=True)
print(f"[DEBUG] Python path: {sys.path}", flush=True)

# Add paths for imports
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../raft'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../utils'))

print(f"[DEBUG] Importing protobuf modules...", flush=True)

# Import generated protobuf files
import ticket_booking_pb2
import ticket_booking_pb2_grpc
import llm_service_pb2
import llm_service_pb2_grpc

print(f"[DEBUG] Importing custom modules...", flush=True)

# Import custom modules
from auth import AuthManager
from raft_node import RaftNode

print(f"[DEBUG] All imports successful!", flush=True)

class ApplicationServer(ticket_booking_pb2_grpc.TicketBookingServiceServicer,
                       ticket_booking_pb2_grpc.InternalServiceServicer):
    
    def __init__(self, node_id, port, raft_port, peers, llm_server_address):
        self.node_id = node_id
        self.port = port
        self.raft_port = raft_port
        self.llm_server_address = llm_server_address
        
        print(f"[AppServer-{node_id}] Initializing...", flush=True)
        
        # Initialize authentication manager
        self.auth_manager = AuthManager()
        print(f"[AppServer-{node_id}] Auth manager initialized", flush=True)
        
        # Initialize Raft node
        self.raft_node = RaftNode(node_id, peers, raft_port)
        print(f"[AppServer-{node_id}] Raft node created", flush=True)
        
        # Start Raft node directly (not in separate thread)
        self.raft_node.start()
        print(f"[AppServer-{node_id}] Raft node started", flush=True)
        
        print(f"[AppServer-{node_id}] Initialized on port {port}", flush=True)
        print(f"[AppServer-{node_id}] Raft node on port {raft_port}", flush=True)
        print(f"[AppServer-{node_id}] LLM server: {llm_server_address}", flush=True)
    
    # ========================================================================
    # Client-facing RPC Methods
    # ========================================================================
    
    def Login(self, request, context):
        """Authenticate user and return session token"""
        print(f"[AppServer-{self.node_id}] Login attempt: {request.username}")
        
        success, token = self.auth_manager.authenticate(request.username, request.password)
        
        if success:
            return ticket_booking_pb2.LoginResponse(
                status="success",
                token=token,
                message="Login successful"
            )
        else:
            return ticket_booking_pb2.LoginResponse(
                status="error",
                token="",
                message="Invalid credentials"
            )
    
    def Logout(self, request, context):
        """End user session"""
        print(f"[AppServer-{self.node_id}] Logout request")
        
        self.auth_manager.logout(request.token)
        
        return ticket_booking_pb2.StatusResponse(
            status="success",
            message="Logged out successfully"
        )
    
    def Post(self, request, context):
        """Handle POST operations (book, cancel, payment)"""
        print(f"[AppServer-{self.node_id}] POST request: {request.type}")
        
        # Validate token
        valid, username = self.auth_manager.validate_token(request.token)
        if not valid:
            return ticket_booking_pb2.StatusResponse(
                status="error",
                message="Invalid or expired token"
            )
        
        try:
            data = json.loads(request.data)
            data['username'] = username
            
            # Prepare command based on type
            if request.type == "book_ticket":
                command = {
                    'operation': 'book_ticket',
                    'movie_id': data.get('movie_id'),
                    'seats': data.get('seats', []),
                    'username': username
                }
            elif request.type == "cancel_booking":
                command = {
                    'operation': 'cancel_booking',
                    'booking_id': data.get('booking_id'),
                    'username': username
                }
            elif request.type == "payment":
                command = {
                    'operation': 'process_payment',
                    'booking_id': data.get('booking_id'),
                    'payment_method': data.get('payment_method', 'card')
                }
            else:
                return ticket_booking_pb2.StatusResponse(
                    status="error",
                    message="Unknown operation type"
                )
            
            # Submit to Raft for consensus
            result = self._submit_to_raft(command)
            
            if result['status'] == 'success':
                return ticket_booking_pb2.StatusResponse(
                    status="success",
                    message=json.dumps(result)
                )
            else:
                return ticket_booking_pb2.StatusResponse(
                    status="error",
                    message=result.get('message', 'Operation failed')
                )
        
        except Exception as e:
            print(f"[AppServer-{self.node_id}] POST error: {e}")
            return ticket_booking_pb2.StatusResponse(
                status="error",
                message=str(e)
            )
    
    def Get(self, request, context):
        """Handle GET operations (query data)"""
        print(f"[AppServer-{self.node_id}] GET request: {request.type}")
        
        # Validate token
        valid, username = self.auth_manager.validate_token(request.token)
        if not valid:
            return ticket_booking_pb2.GetResponse(
                status="error",
                items=[],
                message="Invalid or expired token"
            )
        
        try:
            items = []
            
            if request.type == "movie_list":
                movies = self.raft_node.state_machine.get_movies()
                for movie in movies:
                    items.append(ticket_booking_pb2.DataItem(
                        id=movie['id'],
                        data=json.dumps(movie)
                    ))
            
            elif request.type == "available_seats":
                params = json.loads(request.params) if request.params else {}
                movie_id = params.get('movie_id')
                seats = self.raft_node.state_machine.get_available_seats(movie_id)
                items.append(ticket_booking_pb2.DataItem(
                    id=movie_id,
                    data=json.dumps({'available_seats': seats})
                ))
            
            elif request.type == "my_bookings":
                bookings = self.raft_node.state_machine.get_user_bookings(username)
                for booking in bookings:
                    items.append(ticket_booking_pb2.DataItem(
                        id=booking['booking_id'],
                        data=json.dumps(booking)
                    ))
            
            else:
                return ticket_booking_pb2.GetResponse(
                    status="error",
                    items=[],
                    message="Unknown query type"
                )
            
            return ticket_booking_pb2.GetResponse(
                status="success",
                items=items,
                message="Query successful"
            )
        
        except Exception as e:
            print(f"[AppServer-{self.node_id}] GET error: {e}")
            return ticket_booking_pb2.GetResponse(
                status="error",
                items=[],
                message=str(e)
            )
    
    def GetLLMAssistance(self, request, context):
        """Get AI assistance from LLM server"""
        print(f"[AppServer-{self.node_id}] LLM request: {request.query[:50]}...")
        
        # Validate token
        valid, username = self.auth_manager.validate_token(request.token)
        if not valid:
            return ticket_booking_pb2.LLMResponse(
                status="error",
                answer="Please login first"
            )
        
        try:
            # Connect to LLM server
            channel = grpc.insecure_channel(self.llm_server_address)
            stub = llm_service_pb2_grpc.LLMServiceStub(channel)
            
            # Add context about current state
            context_info = self._build_context(username)
            full_context = f"{request.context}\n\nCurrent System State:\n{context_info}"
            
            llm_request = llm_service_pb2.LLMQuery(
                request_id=f"req_{int(time.time())}",
                query=request.query,
                context=full_context
            )
            
            response = stub.GetLLMAnswer(llm_request, timeout=30.0)
            channel.close()
            
            return ticket_booking_pb2.LLMResponse(
                status="success",
                answer=response.answer
            )
        
        except Exception as e:
            print(f"[AppServer-{self.node_id}] LLM error: {e}")
            return ticket_booking_pb2.LLMResponse(
                status="error",
                answer=f"LLM service unavailable: {str(e)}"
            )
    
    # ========================================================================
    # Internal RPC Methods (Server-to-Server)
    # ========================================================================
    
    def ProcessBusinessRequest(self, request, context):
        """Handle internal business logic requests"""
        print(f"[AppServer-{self.node_id}] Internal business request: {request.request_id}")
        
        try:
            payload = json.loads(request.payload)
            # Process business logic here
            
            return ticket_booking_pb2.BusinessResponse(
                status="success",
                result=json.dumps({"processed": True})
            )
        except Exception as e:
            return ticket_booking_pb2.BusinessResponse(
                status="error",
                result=str(e)
            )
    
    def SyncState(self, request, context):
        """Synchronize state between servers"""
        print(f"[AppServer-{self.node_id}] State sync request")
        
        try:
            current_state = self.raft_node.state_machine.get_state()
            
            return ticket_booking_pb2.StateResponse(
                status="success",
                data=json.dumps(current_state)
            )
        except Exception as e:
            return ticket_booking_pb2.StateResponse(
                status="error",
                data=str(e)
            )
    
    # ========================================================================
    # Helper Methods
    # ========================================================================
    
    def _submit_to_raft(self, command):
        """Submit command to Raft consensus"""
        # Check if this node is leader
        if not self.raft_node.is_leader():
            # Wait a bit for leader election to complete
            max_wait = 3.0
            start = time.time()
            while time.time() - start < max_wait:
                if self.raft_node.is_leader():
                    break
                time.sleep(0.5)
            
            if not self.raft_node.is_leader():
                return {
                    'status': 'error',
                    'message': 'Not the leader. This server cannot process writes. Please try another server.'
                }
        
        # Submit command
        command_json = json.dumps(command)
        print(f"[AppServer-{self.node_id}] Submitting command to Raft: {command.get('operation')}")
        
        result = self.raft_node.submit_command(command_json)
        
        if result['status'] == 'success':
            # Command committed, get result from state machine
            print(f"[AppServer-{self.node_id}] Command committed, applying to state machine")
            state_result = self.raft_node.state_machine.apply_command(command_json)
            return state_result
        else:
            print(f"[AppServer-{self.node_id}] Command failed: {result.get('message')}")
            return result
    
    def _build_context(self, username):
        """Build context information for LLM"""
        try:
            movies = self.raft_node.state_machine.get_movies()
            bookings = self.raft_node.state_machine.get_user_bookings(username)
            
            context = f"User: {username}\n"
            context += f"Available Movies: {len(movies)}\n"
            context += f"User's Bookings: {len(bookings)}\n"
            
            return context
        except:
            return "No context available"
    
    def start(self):
        """Start the application server"""
        server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
        
        # Add servicers
        ticket_booking_pb2_grpc.add_TicketBookingServiceServicer_to_server(self, server)
        ticket_booking_pb2_grpc.add_InternalServiceServicer_to_server(self, server)
        
        server.add_insecure_port(f'[::]:{self.port}')
        server.start()
        
        print(f"[AppServer-{self.node_id}] Server started on port {self.port}")
        print(f"[AppServer-{self.node_id}] Waiting for Raft initialization...")
        
        # Wait for Raft to stabilize
        time.sleep(5)
        
        # Display status
        info = self.raft_node.get_leader_info()
        print(f"[AppServer-{self.node_id}] Raft Status: {info['state']} (Term: {info['term']})")
        
        try:
            server.wait_for_termination()
        except KeyboardInterrupt:
            print(f"\n[AppServer-{self.node_id}] Shutting down...")
            server.stop(0)


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Movie Ticket Booking Application Server')
    parser.add_argument('--node-id', required=True, help='Node identifier')
    parser.add_argument('--port', type=int, required=True, help='Application server port')
    parser.add_argument('--raft-port', type=int, required=True, help='Raft port')
    parser.add_argument('--llm-server', required=True, help='LLM server address')
    parser.add_argument('--peers', required=True, help='Peer nodes (format: id1:host1:port1,id2:host2:port2)')
    
    args = parser.parse_args()
    
    # Parse peers
    peers = {}
    for peer_info in args.peers.split(','):
        parts = peer_info.split(':')
        if len(parts) == 3:
            peer_id, host, port = parts
            peers[peer_id] = f"{host}:{port}"
    
    # Create and start server
    server = ApplicationServer(
        node_id=args.node_id,
        port=args.port,
        raft_port=args.raft_port,
        peers=peers,
        llm_server_address=args.llm_server
    )
    
    server.start()


if __name__ == '__main__':
    main()