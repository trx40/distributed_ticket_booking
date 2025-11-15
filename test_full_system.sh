#!/bin/bash
# Complete system test

echo "=================================================="
echo "  Full System Test"
echo "=================================================="

echo -e "\n[1/5] Checking if all servers are running..."
ps aux | grep -E "application_server|llm_server" | grep -v grep
echo ""

echo -e "\n[2/5] Checking Raft connectivity..."
python3 test_raft_ports.py

echo -e "\n[3/5] Waiting for leader election (10 seconds)..."
sleep 10

echo -e "\n[4/5] Checking which node is leader..."
echo "Checking logs for LEADER status..."
grep -h "Became LEADER\|LEADER for term" logs/app_server_*.log | tail -5

echo -e "\n[5/5] Testing client connection and booking..."
echo ""
echo "Running quick booking test..."
python3 quick_test.py

echo ""
echo "=================================================="
echo "  Test Complete!"
echo "=================================================="
echo ""
echo "If the booking test passed, you can now:"
echo "  1. Start the interactive client: ./start_client.sh"
echo "  2. Test concurrent bookings: python3 test_concurrent_bookings.py"
echo "  3. Monitor logs: tail -f logs/app_server_*.log"
echo ""
