#!/usr/bin/env python3
"""Check current system state - see which seats are available"""

import grpc
import json
import sys

sys.path.append('src/client')
import ticket_booking_pb2
import ticket_booking_pb2_grpc

def check_state():
    """Check current system state"""
    print("="*70)
    print("CURRENT SYSTEM STATE".center(70))
    print("="*70)
    
    try:
        # Connect
        print("\nConnecting to server...")
        channel = grpc.insecure_channel('localhost:50051')
        grpc.channel_ready_future(channel).result(timeout=5)
        stub = ticket_booking_pb2_grpc.TicketBookingServiceStub(channel)
        print("✓ Connected\n")
        
        # Login
        login_req = ticket_booking_pb2.LoginRequest(
            username="user1",
            password="password1"
        )
        login_resp = stub.Login(login_req, timeout=5.0)
        
        if login_resp.status != "success":
            print(f"✗ Login failed: {login_resp.message}")
            return False
        
        token = login_resp.token
        
        # Get movies and their available seats
        print("MOVIES AND SEAT AVAILABILITY:")
        print("-"*70)
        
        get_req = ticket_booking_pb2.GetRequest(
            token=token,
            type="movie_list",
            params=""
        )
        get_resp = stub.Get(get_req, timeout=5.0)
        
        if get_resp.status != "success":
            print(f"✗ Failed to get movies")
            return False
        
        for item in get_resp.items:
            movie = json.loads(item.data)
            print(f"\n📽️  {movie['title']} (ID: {movie['id']})")
            print(f"   Total Seats: {movie['total_seats']}")
            print(f"   Available: {movie['available_seats']}")
            print(f"   Booked: {movie['total_seats'] - movie['available_seats']}")
            print(f"   Price: ${movie['price']}")
            print(f"   Showtime: {movie['showtime']}")
            
            # Get detailed available seat numbers
            params = json.dumps({'movie_id': movie['id']})
            seat_req = ticket_booking_pb2.GetRequest(
                token=token,
                type="available_seats",
                params=params
            )
            seat_resp = stub.Get(seat_req, timeout=5.0)
            
            if seat_resp.status == "success" and seat_resp.items:
                seat_data = json.loads(seat_resp.items[0].data)
                available = seat_data['available_seats']
                
                if len(available) > 0:
                    if len(available) <= 20:
                        print(f"   Available seats: {available}")
                    else:
                        print(f"   Available seats: {available[:10]}... (showing first 10 of {len(available)})")
                        print(f"   First available: {available[0]}")
                        print(f"   Last available: {available[-1]}")
                else:
                    print(f"   ⚠️  NO SEATS AVAILABLE!")
        
        # Get all bookings
        print("\n" + "="*70)
        print("ALL BOOKINGS:")
        print("-"*70)
        
        booking_req = ticket_booking_pb2.GetRequest(
            token=token,
            type="my_bookings",
            params=""
        )
        booking_resp = stub.Get(booking_req, timeout=5.0)
        
        if booking_resp.status == "success":
            if len(booking_resp.items) == 0:
                print("\n✓ No bookings found (system is clean)")
            else:
                print(f"\nFound {len(booking_resp.items)} booking(s):\n")
                for item in booking_resp.items:
                    booking = json.loads(item.data)
                    print(f"🎫 {booking['booking_id']}")
                    print(f"   Movie: {booking['movie_title']}")
                    print(f"   Seats: {booking['seats']}")
                    print(f"   Price: ${booking['price']}")
                    print(f"   Status: {booking['status']}")
                    print(f"   Time: {booking['timestamp']}")
                    print()
        
        channel.close()
        
        print("="*70)
        print("\nDiagnosis:")
        
        # Check movie1 specifically
        movie1_available = None
        for item in get_resp.items:
            movie = json.loads(item.data)
            if movie['id'] == 'movie1':
                movie1_available = movie['available_seats']
                break
        
        if movie1_available == 0:
            print("⚠️  WARNING: Movie1 has NO available seats!")
            print("\nSolution:")
            print("  1. Stop all servers: pkill -f 'application_server\\|llm_server'")
            print("  2. Wait 2 seconds: sleep 2")
            print("  3. Restart: ./start_system.sh")
            print("  4. Wait 15 seconds: sleep 15")
            print("  5. Test: python3 quick_test.py")
        elif movie1_available < 10:
            print(f"⚠️  Movie1 is almost full (only {movie1_available} seats left)")
        else:
            print(f"✓ Movie1 has {movie1_available} seats available")
        
        return True
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    check_state()
