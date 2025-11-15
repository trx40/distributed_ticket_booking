#!/bin/bash
# Patch script to fix timeout issues

echo "Patching timeout issues..."

# 1. Update client timeouts
if [ -f "src/client/client.py" ]; then
    sed -i 's/timeout=30\.0/timeout=60.0/g' src/client/client.py
    echo "✓ Updated client timeouts to 60 seconds"
fi

# 2. Update Raft heartbeat interval
if [ -f "src/raft/raft_node.py" ]; then
    sed -i 's/self\.heartbeat_interval = 2\.0/self.heartbeat_interval = 1.0/' src/raft/raft_node.py
    echo "✓ Updated Raft heartbeat interval to 1 second"
fi

echo ""
echo "Patches applied! Restart the system for changes to take effect:"
echo "  pkill -f 'application_server\\|llm_server'"
echo "  ./start_system.sh"
