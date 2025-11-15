#!/bin/bash
# Test if application server can start at all

echo "Testing application_server.py directly..."
echo ""

source venv/bin/activate

cd src/servers

echo "Running application server with verbose output..."
echo "=================================================="

python3 -u application_server.py \
    --node-id test_node \
    --port 50099 \
    --raft-port 50098 \
    --llm-server localhost:50060 \
    --peers "test_node:localhost:50098" 2>&1 | head -50

echo ""
echo "=================================================="
echo "If you see errors above, that's the problem!"
echo "If it hangs, press Ctrl+C and the server is working"

cd ../..
