import grpc
import json
import time
import threading
from concurrent.futures import ThreadPoolExecutor

import sys
sys.path.append('../src/client')
import ticket_booking_pb2
import ticket_booking_pb2_grpc


class ConcurrentBookingTest:
    def __init__(self, server_address='localhost:50051'):
        self.server_address = server_address
        self.results = []
        self.lock = threading.Lock()
    
    def login_user(self, username, password):
        """Login and return token"""
        try:
            channel = grpc.insecure_channel(self.server_address)
            stub = ticket_booking_pb2_grpc.TicketBookingServiceStub(channel)
            
            request = ticket_booking_pb2.LoginRequest(
                username=username,
                password=password
            )
            
            response = stub.Login(request)
            channel.close()
            
            if response.status == "success":
                return response.token
            return None
        except Exception as e:
            print(f"Login error: {e}")
            return None
    
    def book_ticket_thread(self, token, movie_id, seats, thread_id):
        """Book ticket in a separate thread"""
        try:
            channel = grpc.insecure_channel(self.server_address)
            stub = ticket_booking_pb2_grpc.TicketBookingServiceStub(channel)
            
            data = json.dumps({
                'movie_id': movie_id,
                'seats': seats
            })
            
            request = ticket_booking_pb2.PostRequest(
                token=token,
                type="book_ticket",
                data=data
            )
            
            start_time = time.time()
            response = stub.Post(request)
            end_time = time.time()
            
            channel.close()
            
            with self.lock:
                self.results.append({
                    'thread_id': thread_id,
                    'status': response.status,
                    'message': response.message,
                    'latency': end_time - start_time
                })
                
                if response.status == "success":
                    print(f"✓ Thread {thread_id}: Booking SUCCESSFUL")
                else:
                    print(f"✗ Thread {thread_id}: Booking FAILED - {response.message}")
        
        except Exception as e:
            print(f"✗ Thread {thread_id}: ERROR - {e}")
    
    def test_concurrent_same_seats(self, num_threads=5):
        """Test multiple threads trying to book same seats"""
        print("\n" + "="*80)
        print("TEST 1: Concurrent Booking of Same Seats")
        print("="*80)
        print(f"Spawning {num_threads} threads trying to book seats [1, 2, 3] simultaneously")
        print("Expected: Only 1 should succeed\n")
        
        self.results = []
        
        # Login users
        tokens = []
        for i in range(num_threads):
            username = f"user{(i % 2) + 1}"
            password = f"password{(i % 2) + 1}"
            token = self.login_user(username, password)
            if token:
                tokens.append(token)
        
        # Start concurrent booking threads
        threads = []
        for i, token in enumerate(tokens):
            thread = threading.Thread(
                target=self.book_ticket_thread,
                args=(token, "movie1", [1, 2, 3], i+1)
            )
            threads.append(thread)
        
        # Start all threads at once
        for thread in threads:
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Analyze results
        successes = [r for r in self.results if r['status'] == 'success']
        failures = [r for r in self.results if r['status'] == 'error']
        
        print(f"\n{'='*80}")
        print("RESULTS:")
        print(f"Total Attempts: {len(self.results)}")
        print(f"Successful: {len(successes)}")
        print(f"Failed: {len(failures)}")
        print(f"Average Latency: {sum(r['latency'] for r in self.results) / len(self.results):.3f}s")
        
        if len(successes) == 1:
            print("\n✓ TEST PASSED: Exactly 1 booking succeeded (no overbooking)")
        else:
            print(f"\n✗ TEST FAILED: {len(successes)} bookings succeeded (overbooking detected!)")
    
    def test_concurrent_different_seats(self, num_threads=5):
        """Test multiple threads booking different seats"""
        print("\n" + "="*80)
        print("TEST 2: Concurrent Booking of Different Seats")
        print("="*80)
        print(f"Spawning {num_threads} threads booking different seats")
        print("Expected: All should succeed\n")
        
        self.results = []
        
        # Login users
        tokens = []
        for i in range(num_threads):
            username = f"user{(i % 2) + 1}"
            password = f"password{(i % 2) + 1}"
            token = self.login_user(username, password)
            if token:
                tokens.append(token)
        
        # Start concurrent booking threads with different seats
        threads = []
        for i, token in enumerate(tokens):
            # Each thread books different seats
            seats = [10 + i*3, 11 + i*3, 12 + i*3]
            thread = threading.Thread(
                target=self.book_ticket_thread,
                args=(token, "movie1", seats, i+1)
            )
            threads.append(thread)
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Analyze results
        successes = [r for r in self.results if r['status'] == 'success']
        failures = [r for r in self.results if r['status'] == 'error']
        
        print(f"\n{'='*80}")
        print("RESULTS:")
        print(f"Total Attempts: {len(self.results)}")
        print(f"Successful: {len(successes)}")
        print(f"Failed: {len(failures)}")
        
        if len(successes) == num_threads:
            print("\n✓ TEST PASSED: All bookings succeeded")
        else:
            print(f"\n✗ TEST FAILED: Only {len(successes)}/{num_threads} succeeded")
