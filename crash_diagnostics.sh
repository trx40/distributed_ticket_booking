#!/bin/bash
# Comprehensive crash diagnostics

echo "=================================================="
echo "  CRASH DIAGNOSTICS"
echo "=================================================="

echo -e "\n[1] Checking if any processes are running..."
ps aux | grep -E "application_server|llm_server" | grep -v grep

echo -e "\n[2] Checking all log files for last 50 lines..."
for i in 1 2 3; do
    echo -e "\n=== APP SERVER $i (last 50 lines) ==="
    if [ -f "logs/app_server_${i}.log" ]; then
        tail -50 "logs/app_server_${i}.log"
    else
        echo "  (No log file)"
    fi
done

echo -e "\n=== LLM SERVER (last 30 lines) ==="
if [ -f "logs/llm_server.log" ]; then
    tail -30 logs/llm_server.log
else
    echo "  (No log file)"
fi

echo -e "\n[3] Looking for Python tracebacks..."
for log in logs/app_server_*.log; do
    if [ -f "$log" ]; then
        echo -e "\n=== $log ==="
        grep -A 15 "Traceback" "$log" | tail -20
    fi
done

echo -e "\n[4] Looking for specific error patterns..."
echo "Errors mentioning 'import':"
grep -i "import.*error\|modulenotfound\|cannot import" logs/app_server_*.log 2>/dev/null | head -10

echo -e "\nErrors mentioning 'grpc':"
grep -i "grpc.*error" logs/app_server_*.log 2>/dev/null | head -10

echo -e "\nErrors mentioning 'raft':"
grep -i "raft.*error" logs/app_server_*.log 2>/dev/null | head -10

echo -e "\n[5] Checking ports..."
echo "Ports that should be listening: 50051-50053, 50060-50063"
netstat -tuln 2>/dev/null | grep -E ":(5005[123]|5006[0-3])" || ss -tuln | grep -E ":(5005[123]|5006[0-3])"

echo -e "\n[6] Testing if Python can import raft_node..."
cd src/raft
python3 -c "
import sys
sys.path.insert(0, '..')
try:
    from raft_node import RaftNode
    print('✓ raft_node imports successfully')
except Exception as e:
    print(f'✗ Import failed: {e}')
    import traceback
    traceback.print_exc()
" 2>&1
cd ../..

echo -e "\n=================================================="
echo "  DIAGNOSIS COMPLETE"
echo "=================================================="
