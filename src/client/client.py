#!/usr/bin/env python3
"""
Fixed Client with automatic retry across all nodes
Handles leader election and failover gracefully
"""

import grpc
import json
import time
import sys
from datetime import datetime

import ticket_booking_pb2
import ticket_booking_pb2_grpc


class TicketBookingClient:
    """Client with intelligent multi-node retry"""
    
    def __init__(self, server_addresses):
        """
        Initialize client with multiple server addresses
        server_addresses: list of all server addresses
        """
        self.server_addresses = server_addresses
        self.token = None
        self.username = None
        print(f"[Client] Initialized with {len(server_addresses)} servers")
        print(f"[Client] Servers: {', '.join(server_addresses)}")
    
    def _execute_with_retry(self, operation_func, max_retries=None):
        """
        Execute operation with automatic retry across all nodes
        For write operations, this ensures we find the leader
        """
        if max_retries is None:
            max_retries = len(self.server_addresses) * 2  # Try each server twice
        
        last_error = None
        
        for attempt in range(max_retries):
            # Try each server
            for address in self.server_addresses:
                try:
                    channel = grpc.insecure_channel(address, options=[
                        ('grpc.keepalive_time_ms', 10000),
                        ('grpc.keepalive_timeout_ms', 5000),
                    ])
                    
                    # Test connection
                    grpc.channel_ready_future(channel).result(timeout=3)
                    
                    stub = ticket_booking_pb2_grpc.TicketBookingServiceStub(channel)
                    
                    # Execute the operation
                    result = operation_func(stub)
                    channel.close()
                    
                    # Success!
                    return result
                    
                except grpc.RpcError as e:
                    error_msg = str(e.details()) if hasattr(e, 'details') else str(e)
                    
                    # If it's a "not leader" error, try next server
                    if "Not the leader" in error_msg or "not leader" in error_msg.lower():
                        print(f"[Client] {address} is not leader, trying next server...")
                        last_error = error_msg
                        continue
                    
                    # Other errors - try next server
                    print(f"[Client] Error from {address}: {error_msg}")
                    last_error = error_msg
                    continue
                    
                except Exception as e:
                    print(f"[Client] Connection failed to {address}: {e}")
                    last_error = str(e)
                    continue
            
            # If we've tried all servers and no success, wait a bit before retrying
            if attempt < max_retries - 1:
                print(f"[Client] Retry {attempt + 1}/{max_retries} - waiting 2 seconds...")
                time.sleep(2)
        
        # All retries exhausted
        raise Exception(f"All servers unavailable after {max_retries} attempts. Last error: {last_error}")
    
    def login(self, username, password):
        """Login to the system"""
        def _login(stub):
            request = ticket_booking_pb2.LoginRequest(
                username=username,
                password=password
            )
            return stub.Login(request, timeout=5.0)
        
        try:
            response = self._execute_with_retry(_login, max_retries=len(self.server_addresses))
            
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
        
        def _logout(stub):
            request = ticket_booking_pb2.LogoutRequest(token=self.token)
            return stub.Logout(request, timeout=5.0)
        
        try:
            response = self._execute_with_retry(_logout)
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
        
        def _get_movies(stub):
            request = ticket_booking_pb2.GetRequest(
                token=self.token,
                type="movie_list",
                params=""
            )
            return stub.Get(request, timeout=5.0)
        
        try:
            response = self._execute_with_retry(_get_movies)
            
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
        
        def _get_seats(stub):
            params = json.dumps({'movie_id': movie_id})
            request = ticket_booking_pb2.GetRequest(
                token=self.token,
                type="available_seats",
                params=params
            )
            return stub.Get(request, timeout=5.0)
        
        try:
            response = self._execute_with_retry(_get_seats)
            
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
        """Book movie tickets - with automatic leader finding"""
        if not self.token:
            print("\n✗ Please login first")
            return None
        
        def _book(stub):
            data = json.dumps({
                'movie_id': movie_id,
                'seats': seats
            })
            
            request = ticket_booking_pb2.PostRequest(
                token=self.token,
                type="book_ticket",
                data=data
            )
            
            return stub.Post(request, timeout=15.0)
        
        try:
            print("\n[Processing booking - finding leader...]")
            response = self._execute_with_retry(_book, max_retries=len(self.server_addresses) * 3)
            
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
            print("This might indicate no leader is available. Please wait for leader election to complete.")
            return None
    
    def cancel_booking(self, booking_id):
        """Cancel a booking"""
        if not self.token:
            print("\n✗ Please login first")
            return False
        
        def _cancel(stub):
            data = json.dumps({'booking_id': booking_id})
            request = ticket_booking_pb2.PostRequest(
                token=self.token,
                type="cancel_booking",
                data=data
            )
            return stub.Post(request, timeout=10.0)
        
        try:
            print("\n[Processing cancellation...]")
            response = self._execute_with_retry(_cancel)
            
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
        
        def _payment(stub):
            data = json.dumps({
                'booking_id': booking_id,
                'payment_method': payment_method
            })
            request = ticket_booking_pb2.PostRequest(
                token=self.token,
                type="payment",
                data=data
            )
            return stub.Post(request, timeout=10.0)
        
        try:
            print("\n[Processing payment...]")
            response = self._execute_with_retry(_payment)
            
            if response.status == "success":
                result = json.loads(response.message)
                print(f"\n{'='*60}")
                print("✓ PAYMENT SUCCESSFUL!".center(60))
                print(f"{'='*60}")
                print(f"  Payment ID: {result.get('payment_id')}")
                print(f"  Booking ID: {booking_id}")
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
        
        def _get_bookings(stub):
            request = ticket_booking_pb2.GetRequest(
                token=self.token,
                type="my_bookings",
                params=""
            )
            return stub.Get(request, timeout=5.0)
        
        try:
            response = self._execute_with_retry(_get_bookings)
            
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
        
        def _ask_llm(stub):
            request = ticket_booking_pb2.LLMRequest(
                token=self.token,
                query=query,
                context="Customer support query"
            )
            return stub.GetLLMAssistance(request, timeout=30.0)
        
        try:
            print("\n[Consulting AI assistant...]")
            response = self._execute_with_retry(_ask_llm)
            
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


# Rest of the client code (print_banner, print_menu, interactive_menu, main) remains the same
# Just copy from the original client.py starting from line ~490

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
    
    # Always use all three servers
    servers = ['localhost:50051', 'localhost:50052', 'localhost:50053']
    
    print(f"\n✓ Connected to {len(servers)} server(s)")
    print("  Client will automatically find the leader for write operations")
    
    client = TicketBookingClient(servers)
    
    # Login loop
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
    
    # Main menu loop - same as original
    while True:
        try:
            print_menu()
            choice = input("\nEnter your choice (1-6): ").strip()
            
            if choice == '1':
                print("\n[Loading movies...]")
                movies = client.get_movies()
                client.display_movies(movies)
            
            elif choice == '2':
                print("\n[Loading movies...]")
                movies = client.get_movies()
                
                if not movies:
                    print("\n✗ No movies available")
                    continue
                
                client.display_movies(movies)
                
                movie_id = input("\nEnter Movie ID (or 'back' to return): ").strip()
                if movie_id.lower() == 'back':
                    continue
                
                if not any(m['id'] == movie_id for m in movies):
                    print(f"\n✗ Invalid movie ID: {movie_id}")
                    continue
                
                print(f"\n[Loading available seats for {movie_id}...]")
                seats = client.get_available_seats(movie_id)
                
                if not seats:
                    print(f"\n✗ No seats available for {movie_id}")
                    continue
                
                print(f"\nAvailable seats ({len(seats)} total):")
                if len(seats) > 30:
                    print(f"  {', '.join(map(str, seats[:30]))}... (and {len(seats)-30} more)")
                else:
                    print(f"  {', '.join(map(str, seats))}")
                
                seat_input = input("\nEnter seat numbers (comma-separated, e.g., 1,2,3): ").strip()
                
                try:
                    selected_seats = [int(s.strip()) for s in seat_input.split(',')]
                    
                    invalid_seats = [s for s in selected_seats if s not in seats]
                    if invalid_seats:
                        print(f"\n✗ Invalid or unavailable seats: {', '.join(map(str, invalid_seats))}")
                        continue
                    
                    result = client.book_ticket(movie_id, selected_seats)
                    
                    if result:
                        process_pay = input("\nProcess payment now? (y/n): ").strip().lower()
                        if process_pay == 'y':
                            payment_method = input("Payment method (card/upi/wallet) [card]: ").strip() or 'card'
                            client.process_payment(result['booking_id'], payment_method)
                
                except ValueError:
                    print("\n✗ Invalid seat numbers. Please enter numbers separated by commas.")
            
            elif choice == '3':
                print("\n[Loading your bookings...]")
                bookings = client.get_my_bookings()
                client.display_bookings(bookings)
            
            elif choice == '4':
                print("\n[Loading your bookings...]")
                bookings = client.get_my_bookings()
                
                if not bookings:
                    print("\n✗ You have no bookings to cancel")
                    continue
                
                client.display_bookings(bookings)
                
                booking_id = input("\nEnter Booking ID to cancel (or 'back' to return): ").strip()
                if booking_id.lower() == 'back':
                    continue
                
                confirm = input(f"\nAre you sure you want to cancel booking {booking_id}? (yes/no): ").strip().lower()
                if confirm == 'yes':
                    client.cancel_booking(booking_id)
            
            elif choice == '5':
                print("\n" + "="*80)
                print("AI ASSISTANT".center(80))
                print("="*80)
                print("\nExamples:")
                print("  • How do I book tickets?")
                print("  • How do I cancel my booking?")
                print("  • What payment methods do you accept?")
                print()
                
                query = input("Your question (or 'back' to return): ").strip()
                if query.lower() != 'back' and query:
                    client.ask_llm(query)
            
            elif choice == '6':
                confirm = input("\nAre you sure you want to logout? (yes/no): ").strip().lower()
                if confirm == 'yes':
                    client.logout()
                    print("\n" + "="*80)
                    print("Thank you for using our service!".center(80))
                    print("="*80 + "\n")
                    break
            
            else:
                print("\n✗ Invalid choice. Please enter a number between 1 and 6.")
            
            input("\nPress Enter to continue...")
        
        except KeyboardInterrupt:
            print("\n\n[Interrupted by user]")
            client.logout()
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"\n✗ An error occurred: {e}")


def main():
    """Main entry point"""
    try:
        interactive_menu()
    except Exception as e:
        print(f"\n✗ Fatal error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()