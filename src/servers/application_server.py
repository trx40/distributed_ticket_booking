#!/usr/bin/env python3
"""Application Server with Raft Consensus - FIXED VERSION"""

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

# Add paths for imports
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../raft'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../utils'))

# Import generated protobuf files
import ticket_booking_pb2
import ticket_booking_pb2_grpc
import llm_service_pb2
import llm_service_pb2_grpc

# Import custom modules
from auth import AuthManager
from raft_node import RaftNode

class ApplicationServer(ticket_booking_pb2_grpc.TicketBookingServiceServicer,
                       ticket_booking_pb2_grpc.InternalServiceServicer):
    
    def __init__(self, node_id, port, raft_port, peers, peer_app_ports, llm_server_address):
        self.node_id = node_id
        self.port = port
        self.raft_port = raft_port
        self.llm_server_address = llm_server_address
        self.peer_app_ports = peer_app_ports  # {node_id: app_port}
        
        print(f"[AppServer-{node_id}] Initializing...", flush=True)
        
        # Initialize authentication manager
        self.auth_manager = AuthManager()
        print(f"[AppServer-{node_id}] Auth manager initialized", flush=True)
        
        # Initialize Raft node
        self.raft_node = RaftNode(node_id, peers, raft_port)
        print(f"[AppServer-{node_id}] Raft node created", flush=True)
        
        # Start Raft node
        self.raft_node.start()
        print(f"[AppServer-{node_id}] Raft node started", flush=True)
        
        print(f"[AppServer-{node_id}] Initialized on port {port}", flush=True)
        print(f"[AppServer-{node_id}] Raft node on port {raft_port}", flush=True)
        print(f"[AppServer-{node_id}] LLM server: {llm_server_address}", flush=True)
    
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
        """Handle POST operations with automatic leader forwarding"""
        print(f"[AppServer-{self.node_id}] POST request: {request.type}")
        
        # Validate token
        valid, username = self.auth_manager.validate_token(request.token)
        if not valid:
            return ticket_booking_pb2.StatusResponse(
                status="error",
                message="Invalid or expired token"
            )
        
        # If not leader, forward to leader
        if not self.raft_node.is_leader():
            print(f"[AppServer-{self.node_id}] Not leader, attempting to forward request")
            return self._forward_to_leader(request, username)
        
        # Process as leader
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
            import traceback
            traceback.print_exc()
            return ticket_booking_pb2.StatusResponse(
                status="error",
                message=str(e)
            )
    
    def _forward_to_leader(self, request, username):
        """Forward write request to leader"""
        # Try each peer to find the leader
        for peer_id, app_port in self.peer_app_ports.items():
            if peer_id == self.node_id:
                continue
            
            try:
                print(f"[AppServer-{self.node_id}] Trying to forward to {peer_id} at localhost:{app_port}")
                channel = grpc.insecure_channel(f'localhost:{app_port}')
                stub = ticket_booking_pb2_grpc.TicketBookingServiceStub(channel)
                
                # Forward the request
                response = stub.Post(request, timeout=10.0)
                channel.close()
                
                # If we get a success or a legitimate error (not "not leader"), return it
                if response.status == "success" or "Not the leader" not in response.message:
                    print(f"[AppServer-{self.node_id}] Successfully forwarded to {peer_id}")
                    return response
                
            except Exception as e:
                print(f"[AppServer-{self.node_id}] Failed to forward to {peer_id}: {e}")
                continue
        
        # No leader found
        return ticket_booking_pb2.StatusResponse(
            status="error",
            message="No leader available. System is electing a new leader. Please try again in a few seconds."
        )
    
    def Get(self, request, context):
        """Handle GET operations - can be served by any node"""
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
            channel = grpc.insecure_channel(self.llm_server_address)
            stub = llm_service_pb2_grpc.LLMServiceStub(channel)
            
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
    
    def ProcessBusinessRequest(self, request, context):
        """Handle internal business logic requests"""
        print(f"[AppServer-{self.node_id}] Internal business request: {request.request_id}")
        
        try:
            payload = json.loads(request.payload)
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
    
    def _submit_to_raft(self, command):
        """Submit command to Raft consensus - FIXED VERSION"""
        if not self.raft_node.is_leader():
            return {
                'status': 'error',
                'message': 'Not the leader. Please retry - request will be forwarded.'
            }
        
        command_json = json.dumps(command)
        print(f"[AppServer-{self.node_id}] Submitting command to Raft: {command.get('operation')}")
        
        # Submit and wait for result
        result = self.raft_node.submit_command(command_json)
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
        
        ticket_booking_pb2_grpc.add_TicketBookingServiceServicer_to_server(self, server)
        ticket_booking_pb2_grpc.add_InternalServiceServicer_to_server(self, server)
        
        server.add_insecure_port(f'[::]:{self.port}')
        server.start()
        
        print(f"[AppServer-{self.node_id}] Server started on port {self.port}")
        print(f"[AppServer-{self.node_id}] Waiting for Raft initialization...")
        
        time.sleep(5)
        
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
    
    # Parse peers for Raft
    peers = {}
    for peer_info in args.peers.split(','):
        parts = peer_info.split(':')
        if len(parts) == 3:
            peer_id, host, port = parts
            peers[peer_id] = f"{host}:{port}"
    
    # Parse peer application ports for forwarding
    peer_app_ports = {
        'node1': 50051,
        'node2': 50052,
        'node3': 50053
    }
    
    server = ApplicationServer(
        node_id=args.node_id,
        port=args.port,
        raft_port=args.raft_port,
        peers=peers,
        peer_app_ports=peer_app_ports,
        llm_server_address=args.llm_server
    )
    
    server.start()


if __name__ == '__main__':
    main()