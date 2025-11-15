#!/usr/bin/env python3
"""
Test Log Replication Across Raft Nodes

This test verifies that:
1. All nodes have the same committed entries
2. Leader properly replicates logs to followers
3. State machines across all nodes are consistent
"""

import grpc
import json
import time
import sys
from collections import defaultdict

sys.path.append('src/client')
import ticket_booking_pb2
import ticket_booking_pb2_grpc


class LogReplicationTest:
    def __init__(self):
        self.servers = {
            'node1': 'localhost:50051',
            'node2': 'localhost:50052',
            'node3': 'localhost:50053'
        }
        self.tokens = {}
    
    def login_to_server(self, server_address, username, password):
        """Login to a specific server"""
        try:
            channel = grpc.insecure_channel(server_address)
            grpc.channel_ready_future(channel).result(timeout=3)
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
            print(f"  ✗ Login failed to {server_address}: {e}")
            return None
    
    def book_on_leader(self, movie_id, seats):
        """Make a booking (will automatically go to leader)"""
        # Try each server until we find the leader
        for node_name, server_address in self.servers.items():
            try:
                token = self.tokens.get(node_name)
                if not token:
                    token = self.login_to_server(server_address, "user1", "password1")
                    if not token:
                        continue
                    self.tokens[node_name] = token
                
                channel = grpc.insecure_channel(server_address)
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
                
                response = stub.Post(request, timeout=15.0)
                channel.close()
                
                if response.status == "success":
                    result = json.loads(response.message)
                    return True, result, node_name
                elif "Not the leader" in response.message or "No leader" in response.message:
                    continue
                else:
                    return False, response.message, node_name
                    
            except Exception as e:
                continue
        
        return False, "Could not find leader", None
    
    def query_bookings_from_node(self, node_name, server_address):
        """Query all bookings from a specific node"""
        try:
            token = self.tokens.get(node_name)
            if not token:
                token = self.login_to_server(server_address, "user1", "password1")
                if not token:
                    return None, "Login failed"
                self.tokens[node_name] = token
            
            channel = grpc.insecure_channel(server_address)
            stub = ticket_booking_pb2_grpc.TicketBookingServiceStub(channel)
            
            request = ticket_booking_pb2.GetRequest(
                token=token,
                type="my_bookings",
                params=""
            )
            
            response = stub.Get(request, timeout=5.0)
            channel.close()
            
            if response.status == "success":
                bookings = []
                for item in response.items:
                    booking = json.loads(item.data)
                    bookings.append(booking)
                return bookings, None
            else:
                return None, response.message
                
        except Exception as e:
            return None, str(e)
    
    def query_movie_state_from_node(self, node_name, server_address, movie_id):
        """Query movie state from a specific node"""
        try:
            token = self.tokens.get(node_name)
            if not token:
                token = self.login_to_server(server_address, "user1", "password1")
                if not token:
                    return None, "Login failed"
                self.tokens[node_name] = token
            
            channel = grpc.insecure_channel(server_address)
            stub = ticket_booking_pb2_grpc.TicketBookingServiceStub(channel)
            
            params = json.dumps({'movie_id': movie_id})
            request = ticket_booking_pb2.GetRequest(
                token=token,
                type="available_seats",
                params=params
            )
            
            response = stub.Get(request, timeout=5.0)
            channel.close()
            
            if response.status == "success" and response.items:
                seat_data = json.loads(response.items[0].data)
                return seat_data['available_seats'], None
            else:
                return None, response.message
                
        except Exception as e:
            return None, str(e)
    
    def test_log_replication(self):
        """Main test: Verify log replication across all nodes"""
        print("\n" + "="*80)
        print(" LOG REPLICATION TEST ".center(80))
        print("="*80)
        print("\nThis test verifies that Raft properly replicates logs across all nodes")
        print("Expected: All nodes should have identical state after operations")
        print("-"*80)
        
        # Step 1: Make several bookings
        print("\n[STEP 1] Making bookings on leader...")
        bookings_made = []
        
        for i in range(3):
            seats = [70 + i*3, 71 + i*3, 72 + i*3]
            success, result, leader = self.book_on_leader("movie1", seats)
            
            if success:
                print(f"  ✓ Booking {i+1}: Seats {seats} - {result['booking_id']} (via {leader})")
                bookings_made.append(result['booking_id'])
                time.sleep(1)  # Give time for replication
            else:
                print(f"  ✗ Booking {i+1} failed: {result}")
        
        if len(bookings_made) == 0:
            print("\n✗ Could not make any bookings! Test cannot continue.")
            return False
        
        print(f"\n✓ Made {len(bookings_made)} bookings")
        print(f"  Booking IDs: {bookings_made}")
        
        # Step 2: Wait for replication to complete
        print("\n[STEP 2] Waiting for log replication (5 seconds)...")
        time.sleep(5)
        
        # Step 3: Query state from all nodes
        print("\n[STEP 3] Querying booking state from all nodes...")
        print("-"*80)
        
        node_bookings = {}
        node_errors = {}
        
        for node_name, server_address in self.servers.items():
            print(f"\n{node_name} ({server_address}):")
            bookings, error = self.query_bookings_from_node(node_name, server_address)
            
            if error:
                print(f"  ✗ Error: {error}")
                node_errors[node_name] = error
            elif bookings is not None:
                node_bookings[node_name] = bookings
                print(f"  ✓ Retrieved {len(bookings)} bookings")
                
                # Show booking IDs
                booking_ids = [b['booking_id'] for b in bookings]
                print(f"  Booking IDs: {booking_ids}")
            else:
                print(f"  ✗ No response")
                node_errors[node_name] = "No response"
        
        # Step 4: Verify consistency
        print("\n[STEP 4] Verifying consistency across nodes...")
        print("-"*80)
        
        if len(node_bookings) < 2:
            print(f"\n✗ TEST FAILED: Could only query {len(node_bookings)} node(s)")
            print("  Need at least 2 nodes for consistency check")
            return False
        
        # Compare booking counts
        booking_counts = {node: len(bookings) for node, bookings in node_bookings.items()}
        print(f"\nBooking counts per node:")
        for node, count in booking_counts.items():
            print(f"  {node}: {count} bookings")
        
        # Check if all nodes have same count
        unique_counts = set(booking_counts.values())
        if len(unique_counts) > 1:
            print(f"\n✗ INCONSISTENCY DETECTED: Different booking counts!")
            print(f"  Counts: {booking_counts}")
            return False
        
        # Compare actual booking IDs
        print(f"\nComparing booking IDs across nodes:")
        booking_id_sets = {
            node: set(b['booking_id'] for b in bookings)
            for node, bookings in node_bookings.items()
        }
        
        all_same = True
        reference_node = list(booking_id_sets.keys())[0]
        reference_ids = booking_id_sets[reference_node]
        
        for node, ids in booking_id_sets.items():
            if node == reference_node:
                continue
            
            if ids == reference_ids:
                print(f"  ✓ {node} matches {reference_node}")
            else:
                print(f"  ✗ {node} differs from {reference_node}")
                missing = reference_ids - ids
                extra = ids - reference_ids
                if missing:
                    print(f"    Missing: {missing}")
                if extra:
                    print(f"    Extra: {extra}")
                all_same = False
        
        # Step 5: Verify state machine consistency (available seats)
        print("\n[STEP 5] Verifying state machine consistency...")
        print("-"*80)
        print("\nChecking movie1 available seats on each node:")
        
        node_seats = {}
        for node_name, server_address in self.servers.items():
            seats, error = self.query_movie_state_from_node(node_name, server_address, "movie1")
            
            if error:
                print(f"  {node_name}: Error - {error}")
            else:
                node_seats[node_name] = set(seats) if seats else set()
                print(f"  {node_name}: {len(node_seats[node_name])} available seats")
        
        # Compare seat availability
        if len(node_seats) >= 2:
            reference_node = list(node_seats.keys())[0]
            reference_seats = node_seats[reference_node]
            
            seats_consistent = True
            for node, seats in node_seats.items():
                if node == reference_node:
                    continue
                
                if seats == reference_seats:
                    print(f"  ✓ {node} seat availability matches {reference_node}")
                else:
                    print(f"  ✗ {node} seat availability differs from {reference_node}")
                    diff_count = len(reference_seats.symmetric_difference(seats))
                    print(f"    Difference: {diff_count} seats")
                    seats_consistent = False
        
        # Final verdict
        print("\n" + "="*80)
        print(" TEST RESULTS ".center(80))
        print("="*80)
        
        if all_same and seats_consistent:
            print("\n" + "✓"*80)
            print("✓ TEST PASSED: Log replication is working correctly!".center(80))
            print("✓"*80)
            print("\nAll nodes have:")
            print("  ✓ Identical booking records")
            print("  ✓ Consistent state machine state")
            print("  ✓ Same available seat counts")
            print("\nRaft consensus is properly replicating logs across the cluster!")
            return True
        else:
            print("\n" + "✗"*80)
            print("✗ TEST FAILED: Inconsistency detected!".center(80))
            print("✗"*80)
            
            if not all_same:
                print("\n  Problem: Booking records differ across nodes")
                print("  This indicates log replication issues")
            
            if not seats_consistent:
                print("\n  Problem: State machine states differ across nodes")
                print("  This indicates apply mechanism issues")
            
            print("\nCheck:")
            print("  - Raft logs: grep 'Applied entry' logs/app_server_*.log")
            print("  - Replication: grep 'AppendEntries' logs/app_server_*.log")
            print("  - Commit index: grep 'commit_index' logs/app_server_*.log")
            
            return False


def main():
    """Run log replication test"""
    print("="*80)
    print(" RAFT LOG REPLICATION TEST ".center(80))
    print("="*80)
    print("\nThis test will:")
    print("  1. Make several bookings through the leader")
    print("  2. Wait for replication to complete")
    print("  3. Query state from all nodes")
    print("  4. Verify all nodes have identical state")
    print("\n" + "="*80)
    
    input("\nPress Enter to start test (ensure system is running)...")
    
    tester = LogReplicationTest()
    success = tester.test_log_replication()
    
    print("\n" + "="*80)
    
    if success:
        print("\n✓ Your Raft implementation correctly replicates logs!")
        print("\nThis demonstrates:")
        print("  • Leader properly sends AppendEntries to followers")
        print("  • Followers correctly append and commit entries")
        print("  • State machines stay synchronized")
        print("  • Strong consistency is maintained")
    else:
        print("\n⚠ Log replication needs attention")
        print("\nDebugging tips:")
        print("  1. Check if all nodes are running")
        print("  2. Verify leader is sending heartbeats")
        print("  3. Check logs for replication errors")
        print("  4. Ensure commit_index is being updated")
    
    print("="*80)
    
    return success


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
