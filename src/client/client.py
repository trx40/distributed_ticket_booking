import grpc
import json
import time
import sys
from datetime import datetime

# Import generated protobuf files
import ticket_booking_pb2
import ticket_booking_pb2_grpc


class TicketBookingClient:
    """Client for Movie Ticket Booking System"""
    
    def __init__(self, server_addresses):
        """
        Initialize client with multiple server addresses for fault tolerance
        server_addresses: list of server addresses ['localhost:50051', 'localhost:50052']
        """
        self.server_addresses = server_addresses
        self.current_server_idx = 0
        self.token = None
        self.username = None
        print(f"[Client] Initialized with {len(server_addresses)} servers")
    
    def _get_stub(self):
        """Get gRPC stub with automatic failover"""
        max_retries = len(self.server_addresses)
        
        for attempt in range(max_retries):
            try:
                address = self.server_addresses[self.current_server_idx]
                channel = grpc.insecure_channel(address, options=[
                    ('grpc.keepalive_time_ms', 10000),
                    ('grpc.keepalive_timeout_ms', 5000),
                ])
                
                # Test connection
                grpc.channel_ready_future(channel).result(timeout=5)
                
                stub = ticket_booking_pb2_grpc.TicketBookingServiceStub(channel)
                return stub, channel
                
            except Exception as e:
                print(f"[Client] Failed to connect to {address}: {e}")
                self.current_server_idx = (self.current_server_idx + 1) % len(self.server_addresses)
                
                if attempt < max_retries - 1:
                    print(f"[Client] Trying next server...")
                    time.sleep(1)
        
        raise Exception("All servers unavailable. Please check if the system is running.")
    
    def login(self, username, password):
        """Login to the system"""
        try:
            stub, channel = self._get_stub()
            
            request = ticket_booking_pb2.LoginRequest(
                username=username,
                password=password
            )
            
            response = stub.Login(request)
            channel.close()
            
            if response.status == "success":
                self.token = response.token
                self.username = username
                print(f"\n✓ Login successful! Welcome, {username}")
                return True
            else:
                print(f"\n✗ Login failed: {response.message}")
                return False
        
        except Exception as e:
            print(f"\n✗ Login error: {e}")
            return False
    
    def logout(self):
        """Logout from the system"""
        if not self.token:
            print("Not logged in")
            return
        
        try:
            stub, channel = self._get_stub()
            
            request = ticket_booking_pb2.LogoutRequest(token=self.token)
            response = stub.Logout(request)
            channel.close()
            
            print(f"\n✓ {response.message}")
            self.token = None
            self.username = None
            return True
        
        except Exception as e:
            print(f"\n✗ Logout error: {e}")
            return False
    
    def get_movies(self):
        """Get list of available movies"""
        if not self.token:
            print("\n✗ Please login first")
            return []
        
        try:
            stub, channel = self._get_stub()
            
            request = ticket_booking_pb2.GetRequest(
                token=self.token,
                type="movie_list",
                params=""
            )
            
            response = stub.Get(request)
            channel.close()
            
            if response.status == "success":
                movies = []
                for item in response.items:
                    movie = json.loads(item.data)
                    movies.append(movie)
                return movies
            else:
                print(f"\n✗ Error: {response.message}")
                return []
        
        except Exception as e:
            print(f"\n✗ Error getting movies: {e}")
            return []
    
    def get_available_seats(self, movie_id):
        """Get available seats for a movie"""
        if not self.token:
            print("\n✗ Please login first")
            return []
        
        try:
            stub, channel = self._get_stub()
            
            params = json.dumps({'movie_id': movie_id})
            request = ticket_booking_pb2.GetRequest(
                token=self.token,
                type="available_seats",
                params=params
            )
            
            response = stub.Get(request)
            channel.close()
            
            if response.status == "success" and response.items:
                data = json.loads(response.items[0].data)
                return data.get('available_seats', [])
            else:
                print(f"\n✗ Error: {response.message}")
                return []
        
        except Exception as e:
            print(f"\n✗ Error getting seats: {e}")
            return []
    
    def book_ticket(self, movie_id, seats):
        """Book movie tickets"""
        if not self.token:
            print("\n✗ Please login first")
            return None
        
        try:
            stub, channel = self._get_stub()
            
            data = json.dumps({
                'movie_id': movie_id,
                'seats': seats
            })
            
            request = ticket_booking_pb2.PostRequest(
                token=self.token,
                type="book_ticket",
                data=data
            )
            
            print("\n[Processing booking...]")
            response = stub.Post(request, timeout=30.0)
            channel.close()
            
            if response.status == "success":
                result = json.loads(response.message)
                print(f"\n{'='*60}")
                print("✓ BOOKING SUCCESSFUL!".center(60))
                print(f"{'='*60}")
                print(f"  Booking ID: {result.get('booking_id')}")
                print(f"  Movie: {result['details']['movie_title']}")
                print(f"  Seats: {', '.join(map(str, result['details']['seats']))}")
                print(f"  Total Price: ${result['details']['price']:.2f}")
                print(f"  Status: {result['details']['status']}")
                print(f"  Booked at: {result['details']['timestamp']}")
                print(f"{'='*60}\n")
                return result
            else:
                print(f"\n✗ Booking failed: {response.message}")
                return None
        
        except Exception as e:
            print(f"\n✗ Booking error: {e}")
            return None
    
    def cancel_booking(self, booking_id):
        """Cancel a booking"""
        if not self.token:
            print("\n✗ Please login first")
            return False
        
        try:
            stub, channel = self._get_stub()
            
            data = json.dumps({'booking_id': booking_id})
            
            request = ticket_booking_pb2.PostRequest(
                token=self.token,
                type="cancel_booking",
                data=data
            )
            
            print("\n[Processing cancellation...]")
            response = stub.Post(request)
            channel.close()
            
            if response.status == "success":
                result = json.loads(response.message)
                print(f"\n{'='*60}")
                print("✓ BOOKING CANCELLED!".center(60))
                print(f"{'='*60}")
                print(f"  Refund Amount: ${result.get('refund_amount', 0):.2f}")
                print(f"  Refund will be processed in 5-7 business days")
                print(f"{'='*60}\n")
                return True
            else:
                print(f"\n✗ Cancellation failed: {response.message}")
                return False
        
        except Exception as e:
            print(f"\n✗ Cancellation error: {e}")
            return False
    
    def process_payment(self, booking_id, payment_method='card'):
        """Process payment for a booking"""
        if not self.token:
            print("\n✗ Please login first")
            return False
        
        try:
            stub, channel = self._get_stub()
            
            data = json.dumps({
                'booking_id': booking_id,
                'payment_method': payment_method
            })
            
            request = ticket_booking_pb2.PostRequest(
                token=self.token,
                type="payment",
                data=data
            )
            
            print("\n[Processing payment...]")
            response = stub.Post(request)
            channel.close()
            
            if response.status == "success":
                result = json.loads(response.message)
                print(f"\n{'='*60}")
                print("✓ PAYMENT SUCCESSFUL!".center(60))
                print(f"{'='*60}")
                print(f"  Payment ID: {result.get('payment_id')}")
                print(f"  Booking ID: {booking_id}")
                print(f"  Amount: Processed")
                print(f"  Method: {payment_method}")
                print(f"{'='*60}\n")
                return True
            else:
                print(f"\n✗ Payment failed: {response.message}")
                return False
        
        except Exception as e:
            print(f"\n✗ Payment error: {e}")
            return False
    
    def get_my_bookings(self):
        """Get user's bookings"""
        if not self.token:
            print("\n✗ Please login first")
            return []
        
        try:
            stub, channel = self._get_stub()
            
            request = ticket_booking_pb2.GetRequest(
                token=self.token,
                type="my_bookings",
                params=""
            )
            
            response = stub.Get(request)
            channel.close()
            
            if response.status == "success":
                bookings = []
                for item in response.items:
                    booking = json.loads(item.data)
                    bookings.append(booking)
                return bookings
            else:
                print(f"\n✗ Error: {response.message}")
                return []
        
        except Exception as e:
            print(f"\n✗ Error getting bookings: {e}")
            return []
    
    def ask_llm(self, query):
        """Ask LLM for assistance"""
        if not self.token:
            print("\n✗ Please login first")
            return
        
        try:
            stub, channel = self._get_stub()
            
            request = ticket_booking_pb2.LLMRequest(
                token=self.token,
                query=query,
                context="Customer support query"
            )
            
            print("\n[Consulting AI assistant...]")
            response = stub.GetLLMAssistance(request, timeout=30.0)
            channel.close()
            
            if response.status == "success":
                print(f"\n{'='*60}")
                print("🤖 AI ASSISTANT".center(60))
                print(f"{'='*60}")
                print(f"\nQ: {query}")
                print(f"\nA: {response.answer}")
                print(f"\n{'='*60}\n")
            else:
                print(f"\n✗ Error: {response.answer}")
        
        except Exception as e:
            print(f"\n✗ LLM error: {e}")
            print("The AI assistant may be unavailable. Please try again.")
    
    def display_movies(self, movies):
        """Display movies in a formatted way"""
        if not movies:
            print("\nNo movies available")
            return
        
        print("\n" + "="*80)
        print("AVAILABLE MOVIES".center(80))
        print("="*80)
        
        for i, movie in enumerate(movies, 1):
            print(f"\n[{i}] Movie ID: {movie['id']}")
            print(f"    Title: {movie['title']}")
            print(f"    Showtime: {movie['showtime']}")
            print(f"    Price: ${movie['price']:.2f} per ticket")
            print(f"    Available: {movie['available_seats']} of {movie['total_seats']} seats")
            print("-"*80)
        
        print()
    
    def display_bookings(self, bookings):
        """Display bookings in a formatted way"""
        if not bookings:
            print("\n" + "="*80)
            print("No bookings found".center(80))
            print("="*80 + "\n")
            return
        
        print("\n" + "="*80)
        print("YOUR BOOKINGS".center(80))
        print("="*80)
        
        for i, booking in enumerate(bookings, 1):
            status_symbol = "✓" if booking['status'] == 'confirmed' else "✗"
            print(f"\n[{i}] {status_symbol} Booking ID: {booking['booking_id']}")
            print(f"    Movie: {booking['movie_title']}")
            print(f"    Seats: {', '.join(map(str, booking['seats']))}")
            print(f"    Price: ${booking['price']:.2f}")
            print(f"    Status: {booking['status'].upper()}")
            print(f"    Booked on: {booking['timestamp']}")
            print("-"*80)
        
        print()


def print_banner():
    """Print welcome banner"""
    banner = """
    ╔══════════════════════════════════════════════════════════════╗
    ║                                                              ║
    ║        DISTRIBUTED MOVIE TICKET BOOKING SYSTEM               ║
    ║                                                              ║
    ║          🎬 Book Your Favorite Movies Today! 🎬              ║
    ║                                                              ║
    ╚══════════════════════════════════════════════════════════════╝
    """
    print(banner)


def print_menu():
    """Print main menu"""
    print("\n" + "="*80)
    print("MAIN MENU".center(80))
    print("="*80)
    print("  1. 🎬 View Movies")
    print("  2. 🎫 Book Tickets")
    print("  3. 📋 View My Bookings")
    print("  4. ❌ Cancel Booking")
    print("  5. 🤖 Ask AI Assistant")
    print("  6. 🚪 Logout")
    print("="*80)


def interactive_menu():
    """Interactive command-line menu"""
    print_banner()
    
    # Get server addresses
    print("\n📡 Server Configuration")
    print("-" * 60)
    servers_input = input("Enter server addresses (comma-separated)\n[Default: localhost:50051,localhost:50052,localhost:50053]: ").strip()
    
    if not servers_input:
        servers = ['localhost:50051', 'localhost:50052', 'localhost:50053']
    else:
        servers = [s.strip() for s in servers_input.split(',')]
    
    print(f"\n✓ Configured with {len(servers)} server(s)")
    
    client = TicketBookingClient(servers)
    
    # Login
    max_attempts = 3
    attempts = 0
    
    while not client.token and attempts < max_attempts:
        print("\n" + "="*80)
        print("LOGIN".center(80))
        print("="*80)
        print("\nDefault users:")
        print("  • user1 / password1")
        print("  • user2 / password2")
        print("  • admin / admin123")
        print()
        
        username = input("Username (or 'quit' to exit): ").strip()
        if username.lower() == 'quit':
            print("\nGoodbye!")
            return
        
        password = input("Password: ").strip()
        
        if client.login(username, password):
            break
        
        attempts += 1
        if attempts < max_attempts:
            print(f"\n{max_attempts - attempts} attempt(s) remaining")
    
    if not client.token:
        print("\n✗ Maximum login attempts exceeded. Goodbye!")
        return
    
    # Main menu loop
    while True:
        try:
            print_menu()
            choice = input("\nEnter your choice (1-6): ").strip()
            
            if choice == '1':
                # View Movies
                print("\n[Loading movies...]")
                movies = client.get_movies()
                client.display_movies(movies)
            
            elif choice == '2':
                # Book Tickets
                print("\n[Loading movies...]")
                movies = client.get_movies()
                
                if not movies:
                    print("\n✗ No movies available")
                    continue
                
                client.display_movies(movies)
                
                movie_id = input("\nEnter Movie ID (or 'back' to return): ").strip()
                if movie_id.lower() == 'back':
                    continue
                
                # Check if movie exists
                if not any(m['id'] == movie_id for m in movies):
                    print(f"\n✗ Invalid movie ID: {movie_id}")
                    continue
                
                # Get available seats
                print(f"\n[Loading available seats for {movie_id}...]")
                seats = client.get_available_seats(movie_id)
                
                if not seats:
                    print(f"\n✗ No seats available for {movie_id}")
                    continue
                
                print(f"\nAvailable seats ({len(seats)} total):")
                # Show first 30 seats
                if len(seats) > 30:
                    print(f"  {', '.join(map(str, seats[:30]))}... (and {len(seats)-30} more)")
                else:
                    print(f"  {', '.join(map(str, seats))}")
                
                seat_input = input("\nEnter seat numbers (comma-separated, e.g., 1,2,3): ").strip()
                
                try:
                    selected_seats = [int(s.strip()) for s in seat_input.split(',')]
                    
                    # Validate seats
                    invalid_seats = [s for s in selected_seats if s not in seats]
                    if invalid_seats:
                        print(f"\n✗ Invalid or unavailable seats: {', '.join(map(str, invalid_seats))}")
                        continue
                    
                    # Book tickets
                    result = client.book_ticket(movie_id, selected_seats)
                    
                    if result:
                        # Optionally process payment
                        process_pay = input("\nProcess payment now? (y/n): ").strip().lower()
                        if process_pay == 'y':
                            payment_method = input("Payment method (card/upi/wallet) [card]: ").strip() or 'card'
                            client.process_payment(result['booking_id'], payment_method)
                
                except ValueError:
                    print("\n✗ Invalid seat numbers. Please enter numbers separated by commas.")
            
            elif choice == '3':
                # View My Bookings
                print("\n[Loading your bookings...]")
                bookings = client.get_my_bookings()
                client.display_bookings(bookings)
            
            elif choice == '4':
                # Cancel Booking
                print("\n[Loading your bookings...]")
                bookings = client.get_my_bookings()
                
                if not bookings:
                    print("\n✗ You have no bookings to cancel")
                    continue
                
                client.display_bookings(bookings)
                
                booking_id = input("\nEnter Booking ID to cancel (or 'back' to return): ").strip()
                if booking_id.lower() == 'back':
                    continue
                
                # Confirm cancellation
                confirm = input(f"\nAre you sure you want to cancel booking {booking_id}? (yes/no): ").strip().lower()
                if confirm == 'yes':
                    client.cancel_booking(booking_id)
            
            elif choice == '5':
                # Ask AI Assistant
                print("\n" + "="*80)
                print("AI ASSISTANT".center(80))
                print("="*80)
                print("\nExamples:")
                print("  • How do I book tickets?")
                print("  • How do I cancel my booking?")
                print("  • What payment methods do you accept?")
                print("  • What movies are available?")
                print()
                
                query = input("Your question (or 'back' to return): ").strip()
                if query.lower() != 'back' and query:
                    client.ask_llm(query)
            
            elif choice == '6':
                # Logout
                confirm = input("\nAre you sure you want to logout? (yes/no): ").strip().lower()
                if confirm == 'yes':
                    client.logout()
                    print("\n" + "="*80)
                    print("Thank you for using our service!".center(80))
                    print("="*80 + "\n")
                    break
            
            else:
                print("\n✗ Invalid choice. Please enter a number between 1 and 6.")
            
            # Pause before showing menu again
            input("\nPress Enter to continue...")
        
        except KeyboardInterrupt:
            print("\n\n[Interrupted by user]")
            client.logout()
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"\n✗ An error occurred: {e}")
            print("Please try again or contact support.")


def main():
    """Main entry point"""
    try:
        interactive_menu()
    except Exception as e:
        print(f"\n✗ Fatal error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()