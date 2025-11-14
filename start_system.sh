!/bin/bash
# Script to start all components of the distributed system

echo "=================================================="
echo "  Starting Distributed Ticket Booking System     "
echo "=================================================="

# Function to cleanup on exit
cleanup() {
    echo -e "\n\nShutting down all services..."
    pkill -P $$
    exit 0
}

trap cleanup SIGINT SIGTERM

# Activate virtual environment
source venv/bin/activate

# Start LLM Server (Node 1)
echo -e "\n[Node 1] Starting LLM Server on port 50060..."
cd src/servers
python3 llm_server.py --port 50060 > ../../logs/llm_server.log 2>&1 &
LLM_PID=$!
echo "LLM Server PID: $LLM_PID"
cd ../..

sleep 3

# Start Application Server 1 (Leader) - Node 2
echo -e "\n[Node 2] Starting Application Server 1 (Raft port 50061, App port 50051)..."
cd src/servers
python3 application_server.py \
    --node-id node1 \
    --port 50051 \
    --raft-port 50061 \
    --llm-server localhost:50060 \
    --peers "node1:localhost:50061,node2:localhost:50062,node3:localhost:50063" \
    > ../../logs/app_server_1.log 2>&1 &
APP1_PID=$!
echo "App Server 1 PID: $APP1_PID"
cd ../..

sleep 3

# Start Application Server 2 (Follower) - Node 3
echo -e "\n[Node 3] Starting Application Server 2 (Raft port 50062, App port 50052)..."
cd src/servers
python3 application_server.py \
    --node-id node2 \
    --port 50052 \
    --raft-port 50062 \
    --llm-server localhost:50060 \
    --peers "node1:localhost:50061,node2:localhost:50062,node3:localhost:50063" \
    > ../../logs/app_server_2.log 2>&1 &
APP2_PID=$!
echo "App Server 2 PID: $APP2_PID"
cd ../..

sleep 3

# Start Application Server 3 (Follower) - Node 4
echo -e "\n[Node 4] Starting Application Server 3 (Raft port 50063, App port 50053)..."
cd src/servers
python3 application_server.py \
    --node-id node3 \
    --port 50053 \
    --raft-port 50063 \
    --llm-server localhost:50060 \
    --peers "node1:localhost:50061,node2:localhost:50062,node3:localhost:50063" \
    > ../../logs/app_server_3.log 2>&1 &
APP3_PID=$!
echo "App Server 3 PID: $APP3_PID"
cd ../..

echo -e "\n✓ All servers started!"
echo "=================================================="
echo "  System Status"
echo "=================================================="
echo "LLM Server:       localhost:50060 (PID: $LLM_PID)"
echo "App Server 1:     localhost:50051 (PID: $APP1_PID)"
echo "App Server 2:     localhost:50052 (PID: $APP2_PID)"
echo "App Server 3:     localhost:50053 (PID: $APP3_PID)"
echo "=================================================="
echo ""
echo "Logs are in ./logs/ directory"
echo "Press Ctrl+C to stop all services"
echo ""

# Wait for all background processes
wait
