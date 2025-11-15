#!/bin/bash
# Compare what's different between the nodes

echo "=========================================="
echo "  Comparing Node Logs"
echo "=========================================="

for i in 1 2 3; do
    echo -e "\n=== NODE $i ==="
    echo "Last 20 lines:"
    tail -20 logs/app_server_${i}.log 2>/dev/null || echo "  (No log)"
    
    echo -e "\nRaft messages:"
    grep "Raft node started\|RequestVote\|AppendEntries\|ERROR" logs/app_server_${i}.log 2>/dev/null | tail -10 || echo "  (None)"
done

echo -e "\n=========================================="
echo "  Process Status"
echo "=========================================="
ps aux | grep -E "application_server.*node" | grep -v grep

echo -e "\n=========================================="
echo "  Port Status"
echo "=========================================="
netstat -tuln 2>/dev/null | grep -E "5006[123]" || ss -tuln | grep -E "5006[123]"
