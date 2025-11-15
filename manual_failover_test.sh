#!/bin/bash
# Manual failover test - kills ONLY the leader

echo "=================================================="
echo "  MANUAL LEADER FAILOVER TEST"
echo "=================================================="

# Clean start
echo -e "\n[1/6] Clean restart..."
pkill -9 -f "application_server.py"
pkill -9 -f "llm_server.py"
sleep 2
rm -f logs/*.log

echo "Starting system..."
./start_system.sh > /tmp/system_start.log 2>&1 &
sleep 20

# Check status
echo -e "\n[2/6] Checking initial status..."
ps aux | grep "application_server.py" | grep -v grep
APP_COUNT=$(ps aux | grep "application_server.py" | grep -v grep | wc -l)
echo "Running servers: $APP_COUNT"

if [ $APP_COUNT -ne 3 ]; then
    echo "ERROR: Not all servers started!"
    exit 1
fi

# Find leader
echo -e "\n[3/6] Finding leader..."
for i in 1 2 3; do
    if grep -q "Became LEADER" logs/app_server_${i}.log 2>/dev/null; then
        LEADER="node${i}"
        echo "Leader: $LEADER"
        break
    fi
done

if [ -z "$LEADER" ]; then
    echo "ERROR: No leader found!"
    exit 1
fi

# Show detailed process info
echo -e "\n[4/6] Process details BEFORE kill..."
ps aux | grep "application_server.py" | grep -v grep | while read line; do
    PID=$(echo $line | awk '{print $2}')
    NODE=$(echo $line | grep -oP 'node\d')
    echo "  $NODE: PID=$PID"
done

# Kill ONLY the leader using pkill with full match
echo -e "\n[5/6] Killing leader: $LEADER"
pkill -9 -f "application_server.py.*--node-id ${LEADER} "
echo "Leader killed at: $(date +%T)"

# Monitor for 15 seconds
echo -e "\n[6/6] Monitoring (15 seconds)..."
for i in {15..1}; do
    ALIVE=$(ps aux | grep "application_server.py" | grep -v grep | wc -l)
    echo -n "T-$i: $ALIVE processes alive"
    
    # Check for new leader
    for j in 1 2 3; do
        if [ "node${j}" != "$LEADER" ]; then
            if tail -5 logs/app_server_${j}.log 2>/dev/null | grep -q "Became LEADER"; then
                echo -n " [node${j} elected!]"
            fi
        fi
    done
    echo ""
    sleep 1
done

# Final status
echo -e "\n=================================================="
echo "  FINAL STATUS"
echo "=================================================="

SURVIVORS=$(ps aux | grep "application_server.py" | grep -v grep | wc -l)
echo "Surviving processes: $SURVIVORS (expected: 2)"

if [ $SURVIVORS -eq 2 ]; then
    echo "✓ Followers survived!"
    
    ps aux | grep "application_server.py" | grep -v grep | while read line; do
        PID=$(echo $line | awk '{print $2}')
        NODE=$(echo $line | grep -oP 'node\d')
        echo "  Survivor: $NODE (PID=$PID)"
    done
    
    echo ""
    echo "Checking for new leader..."
    NEW_LEADER_FOUND=0
    for i in 1 2 3; do
        if [ "node${i}" != "$LEADER" ]; then
            if grep -q "Became LEADER" logs/app_server_${i}.log; then
                LAST_LEADER=$(grep "Became LEADER" logs/app_server_${i}.log | tail -1)
                echo "✓ New leader: node${i}"
                echo "  $LAST_LEADER"
                NEW_LEADER_FOUND=1
            fi
        fi
    done
    
    if [ $NEW_LEADER_FOUND -eq 0 ]; then
        echo "⚠ No new leader elected yet (may need more time)"
        echo ""
        echo "Recent activity on survivors:"
        for i in 1 2 3; do
            if [ "node${i}" != "$LEADER" ]; then
                echo "  === node${i} last 10 lines ==="
                tail -10 logs/app_server_${i}.log
            fi
        done
    fi
    
elif [ $SURVIVORS -eq 0 ]; then
    echo "✗✗ ALL processes died (including followers)!"
    echo ""
    echo "Last logs from followers:"
    for i in 1 2 3; do
        if [ "node${i}" != "$LEADER" ]; then
            echo ""
            echo "=== node${i} full log ==="
            cat logs/app_server_${i}.log
        fi
    done
else
    echo "✗ Unexpected number of survivors!"
    ps aux | grep "application_server.py" | grep -v grep
fi

echo ""
echo "=================================================="
