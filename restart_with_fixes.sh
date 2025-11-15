#!/bin/bash
# Complete restart with all fixes

echo "=================================================="
echo "  Restarting with Raft Fixes"
echo "=================================================="

# Stop everything
echo -e "\n[1/4] Stopping all servers..."
pkill -f application_server.py
pkill -f llm_server.py
sleep 3

# Clean logs
rm -f logs/*.log
mkdir -p logs

# Activate venv
source venv/bin/activate

echo -e "\n[2/4] Starting LLM Server..."
cd src/servers
python3 -u llm_server.py --port 50060 > ../../logs/llm_server.log 2>&1 &
LLM_PID=$!
cd ../..
sleep 3

if ! ps -p $LLM_PID > /dev/null; then
    echo "  ✗ LLM Server failed!"
    cat logs/llm_server.log
    exit 1
fi
echo "  ✓ LLM Server started (PID: $LLM_PID)"

echo -e "\n[3/4] Starting Application Servers..."

# Server 1
cd src/servers
python3 -u application_server.py \
    --node-id node1 --port 50051 --raft-port 50061 \
    --llm-server localhost:50060 \
    --peers "node1:localhost:50061,node2:localhost:50062,node3:localhost:50063" \
    > ../../logs/app_server_1.log 2>&1 &
APP1_PID=$!
cd ../..
echo "  Started node1 (PID: $APP1_PID)"
sleep 2

# Server 2
cd src/servers
python3 -u application_server.py \
    --node-id node2 --port 50052 --raft-port 50062 \
    --llm-server localhost:50060 \
    --peers "node1:localhost:50061,node2:localhost:50062,node3:localhost:50063" \
    > ../../logs/app_server_2.log 2>&1 &
APP2_PID=$!
cd ../..
echo "  Started node2 (PID: $APP2_PID)"
sleep 2

# Server 3
cd src/servers
python3 -u application_server.py \
    --node-id node3 --port 50053 --raft-port 50063 \
    --llm-server localhost:50060 \
    --peers "node1:localhost:50061,node2:localhost:50062,node3:localhost:50063" \
    > ../../logs/app_server_3.log 2>&1 &
APP3_PID=$!
cd ../..
echo "  Started node3 (PID: $APP3_PID)"

echo -e "\n[4/4] Waiting for initialization (10 seconds)..."
sleep 10

echo -e "\nChecking if servers are running..."
for pid in $APP1_PID $APP2_PID $APP3_PID; do
    if ps -p $pid > /dev/null; then
        echo "  ✓ Process $pid is running"
    else
        echo "  ✗ Process $pid died!"
    fi
done

echo -e "\nChecking Raft status..."
grep -h "Raft node started\|LEADER\|FOLLOWER\|Testing Raft" logs/app_server_*.log | tail -20

echo -e "\n=================================================="
echo "Testing Raft connectivity..."
echo "=================================================="
chmod +x test_raft_ports.py
python3 test_raft_ports.py

echo -e "\n=================================================="
echo "To monitor:"
echo "  tail -f logs/app_server_1.log"
echo "  ./check_all_logs.sh"
echo "=================================================="
