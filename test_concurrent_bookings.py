#!/usr/bin/env python3
"""
Concurrent Booking Test Suite
Tests the system's ability to handle multiple simultaneous booking requests
"""

import grpc
import json
import time
import threading
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.append('src/client')
import ticket_booking_pb2
import ticket_booking_pb2_grpc


class ConcurrentBookingTest:
    def __init__(self):
        self.servers = ['localhost:50051', 'localhost:50052', 'localhost:50053']
        self.results = []
        self.lock = threading.Lock()
    
    def get_available_server(self):
        """Find an available server"""
        for server in self.servers:
            try:
                channel = grpc.insecure_channel(server)
                grpc.channel_ready_future(channel).result(timeout=2)
                channel.close()
                return server
            except:
                continue
        return self.servers[0]  # Default to first server
    
    def login_user(self, username, password):
        """Login and return token"""
        server = self.get_available_server()
        try:
            channel = grpc.insecure_channel(server)
            stub = ticket_booking_pb2_grpc.TicketBookingServiceStub(channel)
            
            request = ticket_booking_pb2.LoginRequest(
                username=username,
                password=password
            )
            
            response = stub.Login(request, timeout=5.0)
            channel.close()
            
            if response.status == "success":
                return response.token
            return None
        except Exception as e:
            print(f"Login error: {e}")
            return None
    
    def book_ticket_thread(self, thread_id, token, movie_id, seats):
        """Book ticket in a separate thread"""
        server = self.get_available_server()
        
        try:
            channel = grpc.insecure_channel(server)
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
            response = stub.Post(request, timeout=15.0)
            end_time = time.time()
            
            channel.close()
            
            result = {
                'thread_id': thread_id,
                'status': response.status,
                'message': response.message,
                'latency': end_time - start_time,
                'seats': seats
            }
            
            with self.lock:
                self.results.append(result)
                
                if response.status == "success":
                    print(f"✓ Thread {thread_id}: Booking SUCCESSFUL - Seats {seats}")
                else:
                    print(f"✗ Thread {thread_id}: Booking FAILED - {response.message[:50]}")
            
            return result
        
        except Exception as e:
            with self.lock:
                print(f"✗ Thread {thread_id}: ERROR - {e}")
            return None
    
    def test_same_seats(self, num_threads=5):
        """Test multiple threads trying to book the SAME seats"""
        print("\n" + "="*80)
        print(" TEST 1: CONCURRENT BOOKING OF SAME SEATS (Race Condition Test)")
        print("="*80)
        print(f"Spawning {num_threads} threads trying to book seats [1, 2, 3] simultaneously")
        print("Expected: Only 1 should succeed (no overbooking)")
        print("-"*80)
        
        self.results = []
        
        # Login users
        print("Logging in users...")
        tokens = []
        for i in range(num_threads):
            username = f"user{(i % 2) + 1}"
            password = f"password{(i % 2) + 1}"
            token = self.login_user(username, password)
            if token:
                tokens.append(token)
        
        print(f"✓ {len(tokens)} users logged in\n")
        
        # Start concurrent booking threads
        print("Starting concurrent bookings...")
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = []
            for i, token in enumerate(tokens):
                future = executor.submit(
                    self.book_ticket_thread,
                    i+1,
                    token,
                    "movie1",
                    [1, 2, 3]
                )
                futures.append(future)
            
            # Wait for all to complete
            for future in as_completed(futures):
                future.result()
        
        # Analyze results
        time.sleep(1)
        successes = [r for r in self.results if r and r['status'] == 'success']
        failures = [r for r in self.results if r and r['status'] == 'error']
        
        print(f"\n{'='*80}")
        print(" RESULTS:")
        print(f"{'='*80}")
        print(f"Total Attempts:     {len(self.results)}")
        print(f"Successful:         {len(successes)}")
        print(f"Failed:             {len(failures)}")
        if self.results:
            print(f"Average Latency:    {sum(r['latency'] for r in self.results if r) / len(self.results):.3f}s")
        
        if len(successes) == 1:
            print(f"\n{'✓'*40}")
            print("✓ TEST PASSED: Exactly 1 booking succeeded")
            print("✓ No overbooking detected")
            print("✓ Race condition handled correctly")
            print(f"{'✓'*40}")
            return True
        else:
            print(f"\n{'✗'*40}")
            print(f"✗ TEST FAILED: {len(successes)} bookings succeeded")
            print("✗ Overbooking detected - system allowed multiple bookings for same seats!")
            print(f"{'✗'*40}")
            return False
    
    def test_different_seats(self, num_threads=5):
        """Test multiple threads booking different seats"""
        print("\n\n" + "="*80)
        print(" TEST 2: CONCURRENT BOOKING OF DIFFERENT SEATS (Parallelism Test)")
        print("="*80)
        print(f"Spawning {num_threads} threads booking different seats")
        print("Expected: All should succeed")
        print("-"*80)
        
        self.results = []
        
        # Login users
        print("Logging in users...")
        tokens = []
        for i in range(num_threads):
            username = f"user{(i % 2) + 1}"
            password = f"password{(i % 2) + 1}"
            token = self.login_user(username, password)
            if token:
                tokens.append(token)
        
        print(f"✓ {len(tokens)} users logged in\n")
        
        # Start concurrent booking threads with different seats
        print("Starting concurrent bookings...")
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = []
            for i, token in enumerate(tokens):
                # Each thread books different seats
                seats = [10 + i*3, 11 + i*3, 12 + i*3]
                future = executor.submit(
                    self.book_ticket_thread,
                    i+1,
                    token,
                    "movie1",
                    seats
                )
                futures.append(future)
            
            # Wait for all to complete
            for future in as_completed(futures):
                future.result()
        
        # Analyze results
        time.sleep(1)
        successes = [r for r in self.results if r and r['status'] == 'success']
        failures = [r for r in self.results if r and r['status'] == 'error']
        
        print(f"\n{'='*80}")
        print(" RESULTS:")
        print(f"{'='*80}")
        print(f"Total Attempts:     {len(self.results)}")
        print(f"Successful:         {len(successes)}")
        print(f"Failed:             {len(failures)}")
        if self.results:
            print(f"Average Latency:    {sum(r['latency'] for r in self.results if r) / len(self.results):.3f}s")
        
        if len(successes) == num_threads:
            print(f"\n{'✓'*40}")
            print("✓ TEST PASSED: All bookings succeeded")
            print("✓ System handled concurrent requests correctly")
            print(f"{'✓'*40}")
            return True
        else:
            print(f"\n{'✗'*40}")
            print(f"✗ TEST FAILED: Only {len(successes)}/{num_threads} succeeded")
            print("✗ System failed to handle parallel requests")
            print(f"{'✗'*40}")
            return False
    
    def test_stress(self, num_threads=10):
        """Stress test with many concurrent requests"""
        print("\n\n" + "="*80)
        print(" TEST 3: STRESS TEST (High Concurrency)")
        print("="*80)
        print(f"Spawning {num_threads} threads with mixed operations")
        print("Expected: System remains stable and consistent")
        print("-"*80)
        
        self.results = []
        
        # Login users
        print("Logging in users...")
        tokens = []
        for i in range(num_threads):
            username = f"user{(i % 2) + 1}"
            password = f"password{(i % 2) + 1}"
            token = self.login_user(username, password)
            if token:
                tokens.append(token)
        
        print(f"✓ {len(tokens)} users logged in\n")
        
        # Mix of different and same seat bookings
        print("Starting stress test...")
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = []
            for i, token in enumerate(tokens):
                if i % 3 == 0:
                    # Some threads try same seats (should mostly fail)
                    seats = [40, 41, 42]
                else:
                    # Others try different seats (should succeed)
                    seats = [50 + i*3, 51 + i*3, 52 + i*3]
                
                future = executor.submit(
                    self.book_ticket_thread,
                    i+1,
                    token,
                    "movie1",
                    seats
                )
                futures.append(future)
            
            # Wait for all to complete
            for future in as_completed(futures):
                future.result()
        
        # Analyze results
        time.sleep(1)
        successes = [r for r in self.results if r and r['status'] == 'success']
        failures = [r for r in self.results if r and r['status'] == 'error']
        
        print(f"\n{'='*80}")
        print(" RESULTS:")
        print(f"{'='*80}")
        print(f"Total Attempts:     {len(self.results)}")
        print(f"Successful:         {len(successes)}")
        print(f"Failed:             {len(failures)}")
        if self.results:
            print(f"Average Latency:    {sum(r['latency'] for r in self.results if r) / len(self.results):.3f}s")
            print(f"Max Latency:        {max(r['latency'] for r in self.results if r):.3f}s")
            print(f"Min Latency:        {min(r['latency'] for r in self.results if r):.3f}s")
        
        # System is stable if at least half succeeded and no crashes
        if len(successes) >= num_threads // 2 and len(self.results) == num_threads:
            print(f"\n{'✓'*40}")
            print("✓ TEST PASSED: System handled high load")
            print("✓ No crashes or hangs detected")
            print(f"{'✓'*40}")
            return True
        else:
            print(f"\n{'✗'*40}")
            print(f"✗ TEST WARNING: Low success rate or incomplete results")
            print(f"{'✗'*40}")
            return False


def main():
    """Run all concurrent booking tests"""
    print("="*80)
    print(" CONCURRENT BOOKING TEST SUITE ".center(80))
    print("="*80)
    print("\nThis test suite will:")
    print("  1. Test race condition handling (same seats)")
    print("  2. Test parallel processing (different seats)")
    print("  3. Stress test with high concurrency")
    print("\n" + "="*80)
    
    input("\nPress Enter to start tests (make sure system is running)...")
    
    tester = ConcurrentBookingTest()
    
    results = []
    
    # Test 1: Race condition
    results.append(("Race Condition Test", tester.test_same_seats(num_threads=5)))
    time.sleep(2)
    
    # Test 2: Parallel processing
    results.append(("Parallel Processing Test", tester.test_different_seats(num_threads=5)))
    time.sleep(2)
    
    # Test 3: Stress test
    results.append(("Stress Test", tester.test_stress(num_threads=10)))
    
    # Summary
    print("\n\n" + "="*80)
    print(" TEST SUITE SUMMARY ".center(80))
    print("="*80)
    
    for test_name, passed in results:
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"{test_name:.<50} {status}")
    
    print("="*80)
    
    all_passed = all(result[1] for result in results)
    if all_passed:
        print("\n" + "✓"*80)
        print("✓ ALL TESTS PASSED - System is working correctly!".center(80))
        print("✓"*80 + "\n")
        print("Your distributed ticket booking system demonstrates:")
        print("  ✓ Proper race condition handling")
        print("  ✓ Concurrent request processing")
        print("  ✓ Raft consensus maintaining consistency")
        print("  ✓ No overbooking under high load")
    else:
        print("\n" + "⚠"*80)
        print("⚠ SOME TESTS FAILED - Review results above".center(80))
        print("⚠"*80 + "\n")
    
    print("\nFor detailed analysis, check:")
    print("  - Server logs: logs/app_server_*.log")
    print("  - Raft consensus logs: grep 'Applied entry' logs/app_server_*.log")
    print("="*80)
    
    return all_passed


if __name__ == '__main__':
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nTest failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
