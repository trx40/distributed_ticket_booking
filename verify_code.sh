#!/bin/bash
# Verify the code has the fixes

echo "Checking if fixes are applied..."
echo ""

echo "[1] Checking raft_node.py for setattr fix..."
if grep -q "setattr(request, 'from', self.node_id)" src/raft/raft_node.py; then
    echo "  ✓ Has setattr fix in RequestVote"
else
    echo "  ✗ Missing setattr fix!"
fi

if grep -q "setattr(reply, 'from', self.node_id)" src/raft/raft_node.py; then
    echo "  ✓ Has setattr fix in responses"
else
    echo "  ✗ Missing setattr fix in responses!"
fi

echo ""
echo "[2] Checking for try-except in handlers..."
if grep -q "except Exception as e:" src/raft/raft_node.py | head -1; then
    echo "  ✓ Has error handling in handlers"
else
    echo "  ✗ Missing error handling!"
fi

echo ""
echo "[3] Checking RequestVote handler signature..."
grep -A 2 "def RequestVote" src/raft/raft_node.py | head -3

echo ""
echo "[4] Checking if server.wait_for_termination is removed..."
if grep -q "server.wait_for_termination()" src/raft/raft_node.py; then
    echo "  ✗ Still has blocking wait_for_termination!"
else
    echo "  ✓ Blocking call removed"
fi

echo ""
echo "[5] Showing first 50 lines of RequestVote handler..."
grep -A 50 "def RequestVote" src/raft/raft_node.py | head -50
