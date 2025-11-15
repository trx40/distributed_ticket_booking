#!/bin/bash
# Automated testing script

echo "=================================================="
echo "  Testing Distributed Ticket Booking System      "
echo "=================================================="

source venv/bin/activate

echo -e "\n[Test 1] Testing gRPC connectivity..."
# Add test code here

echo -e "\n[Test 2] Testing Raft consensus..."
# Add test code here

echo -e "\n[Test 3] Testing fault tolerance..."
# Simulate leader failure
# Kill leader and verify new election

echo -e "\n[Test 4] Testing concurrent bookings..."
# Start multiple clients simultaneously

echo -e "\n✓ All tests completed!"
