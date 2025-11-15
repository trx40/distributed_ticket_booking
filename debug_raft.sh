#!/bin/bash
# Debug script to check what's actually happening

echo "=========================================="
echo "  Raft Debug Information"
echo "=========================================="

echo -e "\n[1] Checking if servers are running..."
ps aux | grep -E "application_server|llm_server" | grep -v grep

echo -e "\n[2] Checking ports..."
netstat -tuln 2>/dev/null | grep -E ":(50051|50052|50053|50060|50061|50062|50063)" || ss -tuln 2>/dev/null | grep -E ":(50051|50052|50053|50060|50061|50062|50063)"

echo -e "\n[3] Checking log files exist..."
ls -lh logs/

echo -e "\n[4] App Server 1 - Full log:"
if [ -f "logs/app_server_1.log" ]; then
    cat logs/app_server_1.log
else
    echo "  Log file not found!"
fi

echo -e "\n[5] App Server 1 - Last 30 lines:"
if [ -f "logs/app_server_1.log" ]; then
    tail -n 30 logs/app_server_1.log
fi

echo -e "\n[6] Checking for Python errors in logs..."
for log in logs/*.log; do
    if [ -f "$log" ]; then
        echo "=== $log ==="
        grep -i "error\|traceback\|exception" "$log" | head -20
    fi
done

echo -e "\n[7] Testing direct Python import..."
cd src/servers
python3 << 'EOF'
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../raft'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../utils'))

try:
    print("Testing imports...")
    import ticket_booking_pb2
    print("✓ ticket_booking_pb2")
    
    import raft_pb2
    print("✓ raft_pb2")
    
    from raft_node import RaftNode
    print("✓ RaftNode")
    
    from auth import AuthManager
    print("✓ AuthManager")
    
    print("\nAll imports successful!")
except Exception as e:
    print(f"\n✗ Import failed: {e}")
    import traceback
    traceback.print_exc()
EOF
cd ../..
