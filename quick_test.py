#!/usr/bin/env python3
"""Quick test to see if the simple server works"""

import grpc
import json
import sys
import time

sys.path.append('src/client')
import ticket_booking_pb2
import ticket_booking_pb2_grpc

def test_simple_booking():
    """Test booking flow"""
    print("Testing simple booking system...\n")
    
    try:
        # Connect
        print("[1/5] Connecting to server...")
        channel = grpc.insecure_channel('localhost:50051')
        grpc.channel_ready_future(channel).result(timeout=5)
        stub = ticket_booking_pb2_grpc.TicketBookingServiceStub(channel)
        print("  ✓ Connected to localhost:50051")
        
        # Login
        print("\n[2/5] Logging in...")
        login_req = ticket_booking_pb2.LoginRequest(
            username="user1",
            password="password1"
        )
        login_resp = stub.Login(login_req, timeout=5.0)
        
        if login_resp.status != "success":
            print(f"  ✗ Login failed: {login_resp.message}")
            return False
        
        token = login_resp.token
        print(f"  ✓ Logged in successfully")
        
        # Get movies
        print("\n[3/5] Getting movies...")
        get_req = ticket_booking_pb2.GetRequest(
            token=token,
            type="movie_list",
            params=""
        )
        get_resp = stub.Get(get_req, timeout=5.0)
        
        if get_resp.status != "success":
            print(f"  ✗ Failed to get movies: {get_resp.message}")
            return False
        
        print(f"  ✓ Found {len(get_resp.items)} movies")
        for item in get_resp.items[:3]:
            movie = json.loads(item.data)
            print(f"     - {movie['title']}: {movie['available_seats']} seats available")
        
        # Book ticket
        print("\n[4/5] Booking tickets...")
        data = json.dumps({
            'movie_id': 'movie1',
            'seats': [50, 51, 52]
        })
        
        post_req = ticket_booking_pb2.PostRequest(
            token=token,
            type="book_ticket",
            data=data
        )
        
        post_resp = stub.Post(post_req, timeout=10.0)
        
        if post_resp.status != "success":
            print(f"  ✗ Booking failed: {post_resp.message}")
            return False
        
        result = json.loads(post_resp.message)
        print(f"  ✓ Booking successful!")
        print(f"     Booking ID: {result['booking_id']}")
        print(f"     Seats: {result['details']['seats']}")
        print(f"     Price: ${result['details']['price']}")
        
        # Verify booking
        print("\n[5/5] Verifying booking...")
        get_req = ticket_booking_pb2.GetRequest(
            token=token,
            type="my_bookings",
            params=""
        )
        get_resp = stub.Get(get_req, timeout=5.0)
        
        if get_resp.status != "success":
            print(f"  ✗ Failed to get bookings: {get_resp.message}")
            return False
        
        print(f"  ✓ Found {len(get_resp.items)} booking(s)")
        
        channel.close()
        
        print("\n" + "="*60)
        print("✓ ALL TESTS PASSED!")
        print("="*60)
        return True
        
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = test_simple_booking()
    sys.exit(0 if success else 1)
