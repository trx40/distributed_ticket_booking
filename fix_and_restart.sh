#!/bin/bash
# Fix Raft issues and restart system

echo "=================================================="
echo "  Fixing Raft and Restarting System"
echo "=================================================="

# Stop everything
echo -e "\n[1/3] Stopping all servers..."
pkill -f application_server.py
pkill -f llm_server.py
sleep 2
echo "  ✓ Servers stopped"

# Make sure the fixed raft_node.py is in place
echo -e "\n[2/3] Verifying fixes..."
if [ -f "src/raft/raft_node.py" ]; then
    # Check if the file has the setattr fix
    if grep -q "setattr(request, 'from'" src/raft/raft_node.py; then
        echo "  ✓ raft_node.py has the 'from' field fix"
    else
        echo "  ✗ raft_node.py needs to be updated with the fixed version"
        echo "  Please replace src/raft/raft_node.py with the fixed version"
        exit 1
    fi
else
    echo "  ✗ src/raft/raft_node.py not found!"
    exit 1
fi

# Start system
echo -e "\n[3/3] Starting system..."
chmod +x start_system_verbose.sh
./start_system_verbose.sh
