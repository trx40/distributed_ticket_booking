#!/usr/bin/env python3
"""
Improved Client with Leader Caching
Handles leader election and failover gracefully with minimal latency
"""

import grpc
import json
import time
import sys
from datetime import datetime

import ticket_booking_pb2
import ticket_booking_pb2_grpc


class SmartTicketBookingClient:
    """Client with intelligent leader caching and fast failover"""
    
    def __init__(self, server_addresses):
        """
        Initialize client with multiple server addresses
        server_addresses: list of all server addresses
        """
        self.server_addresses = server_addresses
        self.token = None
        self.username = None
        
        # Leader caching mechanism
        self.last_known_leader = None  # Cache the last known leader address
        self.leader_failures = 0  # Track consecutive failures to cached leader
        self.max_leader_failures = 2  # After this many failures, invalidate cache
        
        print(f"[Client] Initialized with {len(server_addresses)} servers")
        print(f"[Client] Servers: {', '.join(server_addresses)}")
        print(f"[Client] Leader caching enabled for fast failover")
    
    def _get_ordered_servers(self):
        """
        Get server list ordered by likelihood of being leader
        Returns list with cached leader first, then others
        """
        if self.last_known_leader and self.leader_failures < self.max_leader_failures:
            # Try cached leader first
            ordered = [self.last_known_leader]
            ordered.extend([s for s in self.server_addresses if s != self.last_known_leader])
            return ordered
        else:
            # No cache or too many failures - try all servers
            return list(self.server_addresses)
    
    def _update_leader_cache(self, address, success=True):
        """
        Update leader cache based on operation result
        address: the server address that was tried
        success: whether the operation succeeded
        """
        if success:
            # Operation succeeded - this is likely the leader
            if self.last_known_leader != address:
                print(f"[Client] Updated leader cache: {address}")
                self.last_known_leader = address
                self.leader_failures = 0
        else:
            # Operation failed
            if self.last_known_leader == address:
                self.leader_failures += 1
                if self.leader_failures >= self.max_leader_failures:
                    print(f"[Client] Invalidating leader cache after {self.leader_failures} failures")
                    self.last_known_leader = None
                    self.leader_failures = 0
    
    def _execute_with_retry(self, operation_func, max_retries=None, is_write=True):
        """
        Execute operation with automatic retry across all nodes
        Uses leader cache for write operations to minimize latency
        
        is_write: if True, uses leader cache and validates leadership
        """
        if max_retries is None:
            max_retries = len(self.server_addresses) * 2
        
        last_error = None
        attempt = 0
        
        while attempt < max_retries:
            # Get server list ordered by leader probability
            ordered_servers = self._get_ordered_servers()
            
            for address in ordered_servers:
                try:
                    # Show which server we're trying (only on first attempt)
                    if attempt == 0 and is_write and address == self.last_known_leader:
                        print(f"[Client] Trying cached leader: {address}")
                    
                    channel = grpc.insecure_channel(address, options=[
                        ('grpc.keepalive_time_ms', 10000),
                        ('grpc.keepalive_timeout_ms', 5000),
                    ])
                    
                    # Quick connection test with short timeout
                    grpc.channel_ready_future(channel).result(timeout=2)
                    
                    stub = ticket_booking_pb2_grpc.TicketBookingServiceStub(channel)
                    
                    # Execute the operation
                    result = operation_func(stub)
                    channel.close()
                    
                    # Success! Update leader cache
                    if is_write:
                        self._update_leader_cache(address, success=True)
                    
                    return result
                    
                except grpc.RpcError as e:
                    error_msg = str(e.details()) if hasattr(e, 'details') else str(e)
                    
                    # Check if it's a "not leader" error
                    if "Not the leader" in error_msg or "not leader" in error_msg.lower():
                        # This server is not the leader
                        if is_write:
                            self._update_leader_cache(address, success=False)
                        last_error = error_msg
                        continue
                    
                    # Other gRPC errors
                    if is_write:
                        self._update_leader_cache(address, success=False)
                    last_error = error_msg
                    continue
                    
                except Exception as e:
                    # Connection failed - server likely down
                    if is_write and address == self.last_known_leader:
                        print(f"[Client] Cached leader {address} unreachable")
                        self._update_leader_cache(address, success=False)
                    last_error = str(e)
                    continue
            
            # If we've tried all servers, wait before retrying
            attempt += 1
            if attempt < max_retries:
                wait_time = min(2, attempt * 0.5)  # Progressive backoff
                print(f"[Client] Retry {attempt}/{max_retries} in {wait_time}s...")
                time.sleep(wait_time)
        
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
            # Login is a read operation - any server can handle it
            response = self._execute_with_retry(_login, 
                                               max_retries=len(self.server_addresses),
                                               is_write=False)
            
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
            response = self._execute_with_retry(_logout, is_write=False)
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
            # Read operation - any server can handle
            response = self._execute_with_retry(_get_movies, is_write=False)
            
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
            # Read operation - any server can handle
            response = self._execute_with_retry(_get_seats, is_write=False)
            
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
        """
        Book movie tickets - WRITE OPERATION
        Uses leader cache for fast response
        """
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
            print("\n[Processing booking...]")
            start_time = time.time()
            
            # This is a WRITE operation - uses leader cache
            response = self._execute_with_retry(_book, 
                                               max_retries=len(self.server_addresses) * 3,
                                               is_write=True)
            
            elapsed = time.time() - start_time
            
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
                print(f"  Response time: {elapsed:.2f}s")
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
        """Cancel a booking - WRITE OPERATION"""
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
            start_time = time.time()
            
            # WRITE operation - uses leader cache
            response = self._execute_with_retry(_cancel, is_write=True)
            
            elapsed = time.time() - start_time
            
            if response.status == "success":
                result = json.loads(response.message)
                print(f"\n{'='*60}")
                print("✓ BOOKING CANCELLED!".center(60))
                print(f"{'='*60}")
                print(f"  Refund Amount: ${result.get('refund_amount', 0):.2f}")
                print(f"  Refund will be processed in 5-7 business days")
                print(f"  Response time: {elapsed:.2f}s")
                print(f"{'='*60}\n")
                return True
            else:
                print(f"\n✗ Cancellation failed: {response.message}")
                return False
        
        except Exception as e:
            print(f"\n✗ Cancellation error: {e}")
            return False
    
    def process_payment(self, booking_id, payment_method='card'):
        """Process payment for a booking - WRITE OPERATION"""
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
            start_time = time.time()
            
            # WRITE operation - uses leader cache
            response = self._execute_with_retry(_payment, is_write=True)
            
            elapsed = time.time() - start_time
            
            if response.status == "success":
                result = json.loads(response.message)
                print(f"\n{'='*60}")
                print("✓ PAYMENT SUCCESSFUL!".center(60))
                print(f"{'='*60}")
                print(f"  Payment ID: {result.get('payment_id')}")
                print(f"  Booking ID: {booking_id}")
                print(f"  Method: {payment_method}")
                print(f"  Response time: {elapsed:.2f}s")
                print(f"{'='*60}\n")
                return True
            else:
                print(f"\n✗ Payment failed: {response.message}")
                return False
        
        except Exception as e:
            print(f"\n✗ Payment error: {e}")
            return False
    
    def get_my_bookings(self):
        """Get user's bookings - READ OPERATION"""
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
            # Read operation - any server can handle
            response = self._execute_with_retry(_get_bookings, is_write=False)
            
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
        """Ask LLM for assistance - READ OPERATION"""
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
            response = self._execute_with_retry(_ask_llm, is_write=False)
            
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
    
    def get_leader_info(self):
        """Display current leader cache status"""
        if self.last_known_leader:
            print(f"\n[Leader Cache] Current: {self.last_known_leader} (failures: {self.leader_failures})")
        else:
            print(f"\n[Leader Cache] No cached leader (will try all servers)")


# All the UI functions remain the same
def print_banner():
    """Print welcome banner"""
    banner = """
    ╔══════════════════════════════════════════════════════════════╗
    ║                                                              ║
    ║        DISTRIBUTED MOVIE TICKET BOOKING SYSTEM               ║
    ║                  with Smart Leader Caching                   ║
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
    print("  6. 🔍 Show Leader Cache Status")
    print("  7. 🚪 Logout")
    print("="*80)


def interactive_menu():
    """Interactive command-line menu"""
    print_banner()
    
    # Always use all three servers
    servers = ['localhost:50051', 'localhost:50052', 'localhost:50053']
    
    print(f"\n✓ Connected to {len(servers)} server(s)")
    print("  Client will automatically cache the leader for fast response")
    print("  After failover, client adapts within 1-2 requests")
    
    client = SmartTicketBookingClient(servers)
    
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
    
    # Main menu loop
    while True:
        try:
            print_menu()
            choice = input("\nEnter your choice (1-7): ").strip()
            
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
                client.get_leader_info()
            
            elif choice == '7':
                confirm = input("\nAre you sure you want to logout? (yes/no): ").strip().lower()
                if confirm == 'yes':
                    client.logout()
                    print("\n" + "="*80)
                    print("Thank you for using our service!".center(80))
                    print("="*80 + "\n")
                    break
            
            else:
                print("\n✗ Invalid choice. Please enter a number between 1 and 7.")
            
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