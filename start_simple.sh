#!/bin/bash
# Start simple single-server system (no Raft)

echo "=================================================="
echo "  Starting Simple Ticket Booking System"
echo "  (Single server mode - no Raft consensus)"
echo "=================================================="

# Cleanup
cleanup() {
    echo -e "\n\nShutting down services..."
    pkill -P $$
    exit 0
}

trap cleanup SIGINT SIGTERM

# Create logs directory
mkdir -p logs

# Activate virtual environment
if [ -d "venv" ]; then
    source venv/bin/activate
else
    echo "ERROR: Virtual environment not found. Run ./complete_setup.sh first"
    exit 1
fi

# Start LLM Server
echo -e "\n[1/2] Starting LLM Server on port 50060..."
cd src/servers
python3 llm_server.py --port 50060 > ../../logs/llm_server.log 2>&1 &
LLM_PID=$!
echo "  ✓ LLM Server started (PID: $LLM_PID)"
cd ../..

echo "  Waiting for LLM Server to initialize..."
sleep 5

# Start Simple Application Server
echo -e "\n[2/2] Starting Application Server on port 50051..."
cd src/servers
python3 simple_server.py --port 50051 --llm-server localhost:50060 > ../../logs/app_server.log 2>&1 &
APP_PID=$!
echo "  ✓ Application Server started (PID: $APP_PID)"
cd ../..

sleep 3

echo -e "\n✓ System started successfully!"
echo ""
echo "=================================================="
echo "  System Status"
echo "=================================================="
echo "LLM Server:       localhost:50060 (PID: $LLM_PID)"
echo "App Server:       localhost:50051 (PID: $APP_PID)"
echo "=================================================="
echo ""
echo "System is ready!"
echo ""
echo "To start client: ./start_client.sh"
echo "To view logs:    tail -f logs/app_server.log"
echo "Press Ctrl+C to stop"
echo ""

# Wait for all background processes
wait
