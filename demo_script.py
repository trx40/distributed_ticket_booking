import grpc
import json
import time
import ticket_booking_pb2
import ticket_booking_pb2_grpc


def print_section(title):
    print("\n" + "="*80)
    print(f" {title} ".center(80))
    print("="*80 + "\n")


def demo():
    """Run automated demo"""
    
    print_section("DISTRIBUTED MOVIE TICKET BOOKING SYSTEM - DEMO")
    
    # Connect to server
    channel = grpc.insecure_channel('localhost:50051')
    stub = ticket_booking_pb2_grpc.TicketBookingServiceStub(channel)
    
    print_section("1. USER LOGIN")
    login_req = ticket_booking_pb2.LoginRequest(
        username="user1",
        password="password1"
    )
    login_resp = stub.Login(login_req)
    print(f"Status: {login_resp.status}")
    print(f"Message: {login_resp.message}")
    token = login_resp.token
    
    time.sleep(2)
    
    print_section("2. VIEW AVAILABLE MOVIES")
    get_req = ticket_booking_pb2.GetRequest(
        token=token,
        type="movie_list",
        params=""
    )
    get_resp = stub.Get(get_req)
    
    for item in get_resp.items:
        movie = json.loads(item.data)
        print(f"ID: {movie['id']}")
        print(f"Title: {movie['title']}")
        print(f"Available: {movie['available_seats']}/{movie['total_seats']} seats")
        print(f"Price: ${movie['price']}")
        print(f"Showtime: {movie['showtime']}")
        print("-" * 80)
    
    time.sleep(2)
    
    print_section("3. CHECK AVAILABLE SEATS")
    params = json.dumps({'movie_id': 'movie1'})
    get_req = ticket_booking_pb2.GetRequest(
        token=token,
        type="available_seats",
        params=params
    )
    get_resp = stub.Get(get_req)
    
    if get_resp.items:
        data = json.loads(get_resp.items[0].data)
        seats = data['available_seats']
        print(f"Available seats: {seats[:20]}... (showing first 20)")
    
    time.sleep(2)
    
    print_section("4. BOOK TICKETS")
    data = json.dumps({
        'movie_id': 'movie1',
        'seats': [50, 51, 52]
    })
    post_req = ticket_booking_pb2.PostRequest(
        token=token,
        type="book_ticket",
        data=data
    )
    post_resp = stub.Post(post_req)
    print(f"Status: {post_resp.status}")
    
    if post_resp.status == "success":
        result = json.loads(post_resp.message)
        print(f"Booking ID: {result['booking_id']}")
        print(f"Movie: {result['details']['movie_title']}")
        print(f"Seats: {result['details']['seats']}")
        print(f"Total: ${result['details']['price']}")
        booking_id = result['booking_id']
    
    time.sleep(2)
    
    print_section("5. VIEW MY BOOKINGS")
    get_req = ticket_booking_pb2.GetRequest(
        token=token,
        type="my_bookings",
        params=""
    )
    get_resp = stub.Get(get_req)
    
    for item in get_resp.items:
        booking = json.loads(item.data)
        print(f"Booking ID: {booking['booking_id']}")
        print(f"Movie: {booking['movie_title']}")
        print(f"Seats: {booking['seats']}")
        print(f"Status: {booking['status']}")
        print("-" * 80)
    
    time.sleep(2)
    
    print_section("6. ASK LLM ASSISTANT")
    llm_req = ticket_booking_pb2.LLMRequest(
        token=token,
        query="How do I cancel my booking?",
        context="User wants to cancel"
    )
    llm_resp = stub.GetLLMAssistance(llm_req, timeout=30.0)
    print(f"Question: How do I cancel my booking?")
    print(f"Answer: {llm_resp.answer}")
    
    time.sleep(2)
    
    print_section("7. LOGOUT")
    logout_req = ticket_booking_pb2.LogoutRequest(token=token)
    logout_resp = stub.Logout(logout_req)
    print(f"Status: {logout_resp.status}")
    print(f"Message: {logout_resp.message}")
    
    channel.close()
    
    print_section("DEMO COMPLETED")
    print("\nAll features demonstrated successfully!")


if __name__ == '__main__':
    import sys
    sys.path.append('src/client')
    
    print("Starting demo in 3 seconds...")
    time.sleep(3)
    
    try:
        demo()
    except Exception as e:
        print(f"\nError during demo: {e}")
        print("Make sure the system is running: ./start_system.sh")
