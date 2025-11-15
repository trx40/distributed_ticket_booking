#!/bin/bash
# Quick diagnostic script

echo "=========================================="
echo "  System Diagnostic"
echo "=========================================="

# Check if servers are running
echo -e "\n[1] Checking running processes..."
if pgrep -f "llm_server.py" > /dev/null; then
    echo "  ✓ LLM Server is running"
else
    echo "  ✗ LLM Server is NOT running"
fi

for i in 1 2 3; do
    if pgrep -f "application_server.py.*node$i" > /dev/null; then
        echo "  ✓ App Server $i is running"
    else
        echo "  ✗ App Server $i is NOT running"
    fi
done

# Check ports
echo -e "\n[2] Checking ports..."
for port in 50051 50052 50053 50060 50061 50062 50063; do
    if netstat -tuln 2>/dev/null | grep -q ":$port "; then
        echo "  ✓ Port $port is listening"
    else
        if ss -tuln 2>/dev/null | grep -q ":$port "; then
            echo "  ✓ Port $port is listening"
        else
            echo "  ✗ Port $port is NOT listening"
        fi
    fi
done

# Check recent logs
echo -e "\n[3] Recent log entries..."
if [ -f "logs/llm_server.log" ]; then
    echo "  LLM Server (last 3 lines):"
    tail -n 3 logs/llm_server.log | sed 's/^/    /'
fi

if [ -f "logs/app_server_1.log" ]; then
    echo "  App Server 1 (last 3 lines):"
    tail -n 3 logs/app_server_1.log | sed 's/^/    /'
fi

# Check for errors
echo -e "\n[4] Checking for errors..."
for log in logs/*.log; do
    if [ -f "$log" ]; then
        ERROR_COUNT=$(grep -ci "error\|exception\|traceback" "$log" 2>/dev/null || echo "0")
        if [ "$ERROR_COUNT" -gt 0 ]; then
            echo "  ⚠ $log has $ERROR_COUNT error(s)"
        fi
    fi
done

echo ""
echo "To view full logs:"
echo "  tail -f logs/llm_server.log"
echo "  tail -f logs/app_server_1.log"
echo ""
