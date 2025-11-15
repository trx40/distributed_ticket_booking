#!/bin/bash
# Check what the debug nodes are saying

echo "Checking debug node outputs..."
echo ""
echo "Did you see these messages in the terminals?"
echo ""
echo "Terminal 1 (node1) should show:"
echo "  [node1] Starting debug Raft node on port 50061..."
echo "  [node1] Server started and listening on port 50061"
echo "  [node1] >>> RequestVote called from test"
echo "  [node1] <<< RequestVote returning granted=True"
echo ""
echo "Terminal 2 (node2) should show:"
echo "  [node2] Starting debug Raft node on port 50062..."
echo "  [node2] Server started and listening on port 50062"
echo "  [node2] >>> RequestVote called from test  <-- THIS SHOULD APPEAR!"
echo ""
echo "Terminal 3 (node3) should show:"
echo "  [node3] Starting debug Raft node on port 50063..."
echo "  [node3] Server started and listening on port 50063"
echo "  [node3] >>> RequestVote called from test  <-- THIS SHOULD APPEAR!"
echo ""
echo "If nodes 2 and 3 DON'T show '>>> RequestVote called', then the"
echo "RPC is not reaching the handler at all!"
echo ""
echo "Checking if servers are even running..."
ps aux | grep debug_raft_node | grep -v grep

echo ""
echo "Checking ports..."
netstat -tuln 2>/dev/null | grep -E "5006[123]" || ss -tuln | grep -E "5006[123]"

echo ""
echo "Testing direct connection to ports..."
for port in 50061 50062 50063; do
    echo -n "Port $port: "
    timeout 2 bash -c "echo test | nc localhost $port" 2>&1 && echo "✓ Accepting connections" || echo "✗ No response"
done
