#!/usr/bin/env python3
"""Check which server is the Raft leader"""

import grpc
import sys

sys.path.append('src/client')
import ticket_booking_pb2
import ticket_booking_pb2_grpc

def check_server(address):
    """Try to book on a server to see if it's leader"""
    try:
        channel = grpc.insecure_channel(address, options=[
            ('grpc.keepalive_time_ms', 10000),
        ])
        grpc.channel_ready_future(channel).result(timeout=2)
        
        stub = ticket_booking_pb2_grpc.TicketBookingServiceStub(channel)
        
        # Try to login
        request = ticket_booking_pb2.LoginRequest(
            username="user1",
            password="password1"
        )
        response = stub.Login(request, timeout=5.0)
        
        if response.status == "success":
            print(f"✓ {address} - Accepting connections")
            channel.close()
            return True
        else:
            print(f"✗ {address} - Login failed")
            channel.close()
            return False
            
    except Exception as e:
        print(f"✗ {address} - Connection failed: {e}")
        return False

def main():
    print("Checking server availability...\n")
    
    servers = [
        ('Server 1', 'localhost:50051'),
        ('Server 2', 'localhost:50052'),
        ('Server 3', 'localhost:50053'),
    ]
    
    available = []
    for name, address in servers:
        if check_server(address):
            available.append((name, address))
    
    print(f"\n{len(available)}/{len(servers)} servers are available")
    
    if available:
        print("\nTry connecting to:")
        for name, address in available:
            print(f"  {name}: {address}")
    else:
        print("\n⚠ No servers are available!")
        print("Make sure the system is running: ./start_system.sh")

if __name__ == '__main__':
    main()
