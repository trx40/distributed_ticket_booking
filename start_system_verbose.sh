#!/bin/bash
# Start system with verbose logging

echo "=================================================="
echo "  Starting System with Verbose Logging"
echo "=================================================="

# Cleanup function
cleanup() {
    echo -e "\n\nShutting down all services..."
    pkill -f application_server.py
    pkill -f llm_server.py
    sleep 2
    exit 0
}

trap cleanup SIGINT SIGTERM

# Kill any existing processes
echo "Cleaning up old processes..."
pkill -f application_server.py 2>/dev/null
pkill -f llm_server.py 2>/dev/null
sleep 2

# Create logs directory
mkdir -p logs
rm -f logs/*.log

# Activate virtual environment
source venv/bin/activate

# Start LLM Server
echo -e "\n[1/4] Starting LLM Server..."
cd src/servers
python3 -u llm_server.py --port 50060 >> ../../logs/llm_server.log 2>&1 &
LLM_PID=$!
echo "  Started with PID: $LLM_PID"
cd ../..

sleep 3
echo "  Checking if LLM server started..."
if ps -p $LLM_PID > /dev/null; then
    echo "  ✓ LLM Server is running"
    tail -5 logs/llm_server.log | sed 's/^/    /'
else
    echo "  ✗ LLM Server failed to start!"
    echo "  Log contents:"
    cat logs/llm_server.log | sed 's/^/    /'
    exit 1
fi

# Start App Server 1
echo -e "\n[2/4] Starting Application Server 1..."
cd src/servers
python3 -u application_server.py \
    --node-id node1 \
    --port 50051 \
    --raft-port 50061 \
    --llm-server localhost:50060 \
    --peers "node1:localhost:50061,node2:localhost:50062,node3:localhost:50063" \
    >> ../../logs/app_server_1.log 2>&1 &
APP1_PID=$!
echo "  Started with PID: $APP1_PID"
cd ../..

sleep 3
echo "  Checking if App Server 1 started..."
if ps -p $APP1_PID > /dev/null; then
    echo "  ✓ App Server 1 is running"
    tail -10 logs/app_server_1.log | sed 's/^/    /'
else
    echo "  ✗ App Server 1 failed to start!"
    echo "  Log contents:"
    cat logs/app_server_1.log | sed 's/^/    /'
    exit 1
fi

# Start App Server 2
echo -e "\n[3/4] Starting Application Server 2..."
cd src/servers
python3 -u application_server.py \
    --node-id node2 \
    --port 50052 \
    --raft-port 50062 \
    --llm-server localhost:50060 \
    --peers "node1:localhost:50061,node2:localhost:50062,node3:localhost:50063" \
    >> ../../logs/app_server_2.log 2>&1 &
APP2_PID=$!
echo "  Started with PID: $APP2_PID"
cd ../..

sleep 3
echo "  Checking if App Server 2 started..."
if ps -p $APP2_PID > /dev/null; then
    echo "  ✓ App Server 2 is running"
    tail -10 logs/app_server_2.log | sed 's/^/    /'
else
    echo "  ✗ App Server 2 failed to start!"
    echo "  Log contents:"
    cat logs/app_server_2.log | sed 's/^/    /'
    exit 1
fi

# Start App Server 3
echo -e "\n[4/4] Starting Application Server 3..."
cd src/servers
python3 -u application_server.py \
    --node-id node3 \
    --port 50053 \
    --raft-port 50063 \
    --llm-server localhost:50060 \
    --peers "node1:localhost:50061,node2:localhost:50062,node3:localhost:50063" \
    >> ../../logs/app_server_3.log 2>&1 &
APP3_PID=$!
echo "  Started with PID: $APP3_PID"
cd ../..

sleep 3
echo "  Checking if App Server 3 started..."
if ps -p $APP3_PID > /dev/null; then
    echo "  ✓ App Server 3 is running"
    tail -10 logs/app_server_3.log | sed 's/^/    /'
else
    echo "  ✗ App Server 3 failed to start!"
    echo "  Log contents:"
    cat logs/app_server_3.log | sed 's/^/    /'
    exit 1
fi

echo -e "\n=================================================="
echo "  All Servers Started"
echo "=================================================="
echo "LLM Server:       localhost:50060 (PID: $LLM_PID)"
echo "App Server 1:     localhost:50051 (PID: $APP1_PID)"
echo "App Server 2:     localhost:50052 (PID: $APP2_PID)"
echo "App Server 3:     localhost:50053 (PID: $APP3_PID)"
echo "=================================================="
echo ""
echo "Waiting for Raft consensus (15 seconds)..."
sleep 15

echo -e "\nChecking Raft status..."
for i in 1 2 3; do
    echo "  App Server $i:"
    tail -5 logs/app_server_${i}.log | grep -i "leader\|follower\|candidate" | sed 's/^/    /' || echo "    (No Raft status found)"
done

echo -e "\nTo monitor logs:"
echo "  tail -f logs/app_server_1.log"
echo ""
echo "Press Ctrl+C to stop all services"
echo ""

# Wait for processes
wait
