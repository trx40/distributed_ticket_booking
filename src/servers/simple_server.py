#!/usr/bin/env python3
"""
Simplified application server WITHOUT Raft - for testing
This bypasses Raft consensus and directly applies commands to state machine
"""

import grpc
import json
import sys
import os
import time
from concurrent import futures

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
from state_machine import StateMachine

class SimpleApplicationServer(ticket_booking_pb2_grpc.TicketBookingServiceServicer,
                              ticket_booking_pb2_grpc.InternalServiceServicer):
    
    def __init__(self, port, llm_server_address):
        self.port = port
        self.llm_server_address = llm_server_address
        
        # Initialize authentication manager
        self.auth_manager = AuthManager()
        
        # Initialize state machine directly (no Raft)
        self.state_machine = StateMachine()
        
        print(f"[SimpleServer] Initialized on port {port}")
        print(f"[SimpleServer] LLM server: {llm_server_address}")
        print(f"[SimpleServer] Running in SINGLE-SERVER mode (no Raft)")
    
    def Login(self, request, context):
        """Authenticate user and return session token"""
        print(f"[SimpleServer] Login attempt: {request.username}")
        
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
        print(f"[SimpleServer] Logout request")
        self.auth_manager.logout(request.token)
        
        return ticket_booking_pb2.StatusResponse(
            status="success",
            message="Logged out successfully"
        )
    
    def Post(self, request, context):
        """Handle POST operations (book, cancel, payment)"""
        print(f"[SimpleServer] POST request: {request.type}")
        
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
            
            # Apply directly to state machine (no Raft)
            command_json = json.dumps(command)
            print(f"[SimpleServer] Applying command: {command.get('operation')}")
            result = self.state_machine.apply_command(command_json)
            
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
            print(f"[SimpleServer] POST error: {e}")
            import traceback
            traceback.print_exc()
            return ticket_booking_pb2.StatusResponse(
                status="error",
                message=str(e)
            )
    
    def Get(self, request, context):
        """Handle GET operations (query data)"""
        print(f"[SimpleServer] GET request: {request.type}")
        
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
                movies = self.state_machine.get_movies()
                for movie in movies:
                    items.append(ticket_booking_pb2.DataItem(
                        id=movie['id'],
                        data=json.dumps(movie)
                    ))
            
            elif request.type == "available_seats":
                params = json.loads(request.params) if request.params else {}
                movie_id = params.get('movie_id')
                seats = self.state_machine.get_available_seats(movie_id)
                items.append(ticket_booking_pb2.DataItem(
                    id=movie_id,
                    data=json.dumps({'available_seats': seats})
                ))
            
            elif request.type == "my_bookings":
                bookings = self.state_machine.get_user_bookings(username)
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
            print(f"[SimpleServer] GET error: {e}")
            import traceback
            traceback.print_exc()
            return ticket_booking_pb2.GetResponse(
                status="error",
                items=[],
                message=str(e)
            )
    
    def GetLLMAssistance(self, request, context):
        """Get AI assistance from LLM server"""
        print(f"[SimpleServer] LLM request: {request.query[:50]}...")
        
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
            
            # Add context
            movies = self.state_machine.get_movies()
            bookings = self.state_machine.get_user_bookings(username)
            context_info = f"User: {username}\nAvailable Movies: {len(movies)}\nUser's Bookings: {len(bookings)}"
            full_context = f"{request.context}\n\n{context_info}"
            
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
            print(f"[SimpleServer] LLM error: {e}")
            return ticket_booking_pb2.LLMResponse(
                status="error",
                answer=f"LLM service unavailable: {str(e)}"
            )
    
    def ProcessBusinessRequest(self, request, context):
        """Handle internal business logic requests"""
        return ticket_booking_pb2.BusinessResponse(
            status="success",
            result=json.dumps({"processed": True})
        )
    
    def SyncState(self, request, context):
        """Synchronize state between servers"""
        current_state = self.state_machine.get_state()
        return ticket_booking_pb2.StateResponse(
            status="success",
            data=json.dumps(current_state)
        )
    
    def start(self):
        """Start the application server"""
        server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
        
        # Add servicers
        ticket_booking_pb2_grpc.add_TicketBookingServiceServicer_to_server(self, server)
        ticket_booking_pb2_grpc.add_InternalServiceServicer_to_server(self, server)
        
        server.add_insecure_port(f'[::]:{self.port}')
        server.start()
        
        print(f"[SimpleServer] Server started on port {self.port}")
        print(f"[SimpleServer] Ready to accept connections!")
        print("-" * 60)
        
        try:
            server.wait_for_termination()
        except KeyboardInterrupt:
            print(f"\n[SimpleServer] Shutting down...")
            server.stop(0)


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Simple Movie Ticket Booking Server (No Raft)')
    parser.add_argument('--port', type=int, default=50051, help='Application server port')
    parser.add_argument('--llm-server', default='localhost:50060', help='LLM server address')
    
    args = parser.parse_args()
    
    server = SimpleApplicationServer(
        port=args.port,
        llm_server_address=args.llm_server
    )
    
    server.start()


if __name__ == '__main__':
    main()
