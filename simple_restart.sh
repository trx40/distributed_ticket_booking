#!/bin/bash
# Quick restart with verification

pkill -f application_server.py
pkill -f llm_server.py
sleep 2

rm -f logs/*.log
source venv/bin/activate

# Start LLM
cd src/servers
python3 -u llm_server.py --port 50060 > ../../logs/llm_server.log 2>&1 &
cd ../..
sleep 3

# Start just ONE app server first to test
echo "Starting node1 only for testing..."
cd src/servers
python3 -u application_server.py \
    --node-id node1 --port 50051 --raft-port 50061 \
    --llm-server localhost:50060 \
    --peers "node1:localhost:50061,node2:localhost:50062,node3:localhost:50063" \
    > ../../logs/app_server_1.log 2>&1 &
APP1_PID=$!
cd ../..

sleep 5

echo "Checking node1..."
if ps -p $APP1_PID > /dev/null; then
    echo "✓ Node1 is running"
    tail -20 logs/app_server_1.log
else
    echo "✗ Node1 died"
    cat logs/app_server_1.log
    exit 1
fi

echo ""
echo "Testing node1 Raft port..."
python3 test_raft_ports.py

echo ""
echo "If node1 works, press Enter to start nodes 2 and 3..."
read

# Start node 2
cd src/servers
python3 -u application_server.py \
    --node-id node2 --port 50052 --raft-port 50062 \
    --llm-server localhost:50060 \
    --peers "node1:localhost:50061,node2:localhost:50062,node3:localhost:50063" \
    > ../../logs/app_server_2.log 2>&1 &
cd ../..
sleep 3

# Start node 3
cd src/servers
python3 -u application_server.py \
    --node-id node3 --port 50053 --raft-port 50063 \
    --llm-server localhost:50060 \
    --peers "node1:localhost:50061,node2:localhost:50062,node3:localhost:50063" \
    > ../../logs/app_server_3.log 2>&1 &
cd ../..
sleep 5

echo ""
echo "Testing all nodes..."
python3 test_raft_ports.py

echo ""
echo "Watching for leader election..."
tail -f logs/app_server_*.log | grep -E "LEADER|election|vote"
