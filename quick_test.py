#!/usr/bin/env python3
"""Quick test to see if the system works - FIXED VERSION"""

import grpc
import json
import sys
import time

sys.path.append('src/client')
import ticket_booking_pb2
import ticket_booking_pb2_grpc

def test_simple_booking():
    """Test booking flow with dynamic seat selection"""
    print("Testing simple booking system...\n")
    
    try:
        # Connect
        print("[1/6] Connecting to server...")
        channel = grpc.insecure_channel('localhost:50051')
        grpc.channel_ready_future(channel).result(timeout=5)
        stub = ticket_booking_pb2_grpc.TicketBookingServiceStub(channel)
        print("  ✓ Connected to localhost:50051")
        
        # Login
        print("\n[2/6] Logging in...")
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
        print("\n[3/6] Getting movies...")
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
        
        # Get available seats to pick unused ones
        print("\n[4/6] Getting available seats for movie1...")
        params = json.dumps({'movie_id': 'movie1'})
        get_req = ticket_booking_pb2.GetRequest(
            token=token,
            type="available_seats",
            params=params
        )
        get_resp = stub.Get(get_req, timeout=5.0)
        
        if get_resp.status != "success" or not get_resp.items:
            print(f"  ✗ Failed to get available seats")
            return False
        
        seat_data = json.loads(get_resp.items[0].data)
        available_seats = seat_data['available_seats']
        
        if len(available_seats) < 3:
            print(f"  ✗ Not enough seats available (only {len(available_seats)} left)")
            return False
        
        # Pick first 3 available seats
        seats_to_book = available_seats[:3]
        print(f"  ✓ Will book seats: {seats_to_book}")
        
        # Book ticket
        print("\n[5/6] Booking tickets...")
        data = json.dumps({
            'movie_id': 'movie1',
            'seats': seats_to_book
        })
        
        post_req = ticket_booking_pb2.PostRequest(
            token=token,
            type="book_ticket",
            data=data
        )
        
        print("  [Processing booking via Raft consensus...]")
        post_resp = stub.Post(post_req, timeout=10.0)
        
        if post_resp.status != "success":
            print(f"  ✗ Booking failed: {post_resp.message}")
            return False
        
        result = json.loads(post_resp.message)
        print(f"  ✓ Booking successful!")
        print(f"     Booking ID: {result.get('booking_id')}")
        print(f"     Seats: {result['details']['seats']}")
        print(f"     Price: ${result['details']['price']:.2f}")
        
        # Verify booking
        print("\n[6/6] Verifying booking...")
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
        
        # Verify our booking is in the list
        found_booking = False
        for item in get_resp.items:
            booking = json.loads(item.data)
            if booking['booking_id'] == result['booking_id']:
                found_booking = True
                print(f"     ✓ Confirmed: {booking['booking_id']} - {booking['movie_title']}")
                break
        
        if not found_booking:
            print(f"  ✗ Booking not found in list!")
            return False
        
        channel.close()
        
        print("\n" + "="*60)
        print("✓ ALL TESTS PASSED!")
        print("="*60)
        print("\nSystem is working correctly:")
        print("  ✓ Authentication working")
        print("  ✓ gRPC communication working")
        print("  ✓ Raft consensus working")
        print("  ✓ State machine working")
        print("  ✓ Booking persistence working")
        return True
        
    except grpc.RpcError as e:
        print(f"\n✗ gRPC Error: {e.code()}: {e.details()}")
        return False
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    print("="*60)
    print("QUICK SYSTEM TEST".center(60))
    print("="*60)
    print("\nThis test will:")
    print("  1. Connect to the leader server")
    print("  2. Login as a test user")
    print("  3. Get available movies")
    print("  4. Find available seats dynamically")
    print("  5. Book 3 tickets via Raft consensus")
    print("  6. Verify the booking was saved")
    print("\n" + "="*60 + "\n")
    
    time.sleep(1)
    
    success = test_simple_booking()
    
    if not success:
        print("\n" + "="*60)
        print("TROUBLESHOOTING".center(60))
        print("="*60)
        print("\n1. Is the system running?")
        print("   Check: ps aux | grep 'application_server\\|llm_server'")
        print("\n2. Are the ports open?")
        print("   Check: netstat -tuln | grep 5005")
        print("\n3. Check logs for errors:")
        print("   tail -f logs/app_server_1.log")
        print("\n4. Reset and restart:")
        print("   ./reset_system.sh")
        print("   ./start_system.sh")
        print("="*60)
    
    sys.exit(0 if success else 1)
