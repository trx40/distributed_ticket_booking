#!/bin/bash
# Check all server logs

echo "=========================================="
echo "  Checking All Server Logs"
echo "=========================================="

for i in 1 2 3; do
    echo -e "\n=== APP SERVER $i ==="
    if [ -f "logs/app_server_${i}.log" ]; then
        cat "logs/app_server_${i}.log"
    else
        echo "  (No log file)"
    fi
    echo ""
done

echo "=== Checking for Raft activity ==="
grep -h "election\|vote\|LEADER\|FOLLOWER\|CANDIDATE" logs/app_server_*.log 2>/dev/null | sort

echo ""
echo "=== Checking for errors ==="
grep -h -i "error\|exception\|failed\|traceback" logs/app_server_*.log 2>/dev/null | head -20
