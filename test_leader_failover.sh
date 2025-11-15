#!/bin/bash
# Test leader failover systematically

echo "=================================================="
echo "  LEADER FAILOVER TEST"
echo "=================================================="

# Cleanup
echo -e "\n[1/8] Cleaning up old processes..."
pkill -9 -f "application_server.py" 2>/dev/null
pkill -9 -f "llm_server.py" 2>/dev/null
sleep 2
rm -f logs/*.log

# Start system
echo -e "\n[2/8] Starting system..."
source venv/bin/activate
./start_system.sh &
SYSTEM_PID=$!

echo "Waiting 20 seconds for full initialization..."
sleep 20

# Check if all started
echo -e "\n[3/8] Checking if all nodes started..."
APP_COUNT=$(ps aux | grep -c "application_server.py" | grep -v grep)
echo "Running application servers: $APP_COUNT/3"

if [ $APP_COUNT -lt 3 ]; then
    echo "✗ Not all servers started! Aborting test."
    exit 1
fi

# Find the leader
echo -e "\n[4/8] Finding the leader..."
LEADER_NODE=""
for i in 1 2 3; do
    if grep -q "Became LEADER" logs/app_server_${i}.log 2>/dev/null; then
        LEADER_NODE="node${i}"
        echo "✓ Leader is: $LEADER_NODE"
        break
    fi
done

if [ -z "$LEADER_NODE" ]; then
    echo "✗ No leader found! Check logs."
    exit 1
fi

# Get the leader's PID
echo -e "\n[5/8] Getting leader PID..."
LEADER_PID=$(ps aux | grep "application_server.py.*${LEADER_NODE}" | grep -v grep | awk '{print $2}')
echo "Leader PID: $LEADER_PID"

if [ -z "$LEADER_PID" ]; then
    echo "✗ Could not find leader PID!"
    exit 1
fi

# Check follower nodes before killing leader
echo -e "\n[6/8] Status before killing leader..."
ps aux | grep "application_server.py" | grep -v grep
echo ""
echo "Follower nodes should be running:"
for i in 1 2 3; do
    if [ "node${i}" != "$LEADER_NODE" ]; then
        PID=$(ps aux | grep "application_server.py.*node${i}" | grep -v grep | awk '{print $2}')
        echo "  node${i}: PID=$PID"
    fi
done

# Kill the leader
echo -e "\n[7/8] KILLING LEADER: $LEADER_NODE (PID: $LEADER_PID)"
kill -9 $LEADER_PID
echo "Leader killed at: $(date)"

# Monitor what happens to followers
echo -e "\n[8/8] Monitoring followers for 15 seconds..."
for i in {15..1}; do
    echo -n "T-${i}: "
    
    # Count remaining nodes
    ALIVE=$(ps aux | grep "application_server.py" | grep -v grep | wc -l)
    echo -n "Alive=$ALIVE "
    
    # Check if any became leader
    for j in 1 2 3; do
        if [ "node${j}" != "$LEADER_NODE" ]; then
            if tail -10 logs/app_server_${j}.log 2>/dev/null | grep -q "Became LEADER"; then
                echo -n "[node${j} is NEW LEADER] "
            fi
        fi
    done
    
    echo ""
    sleep 1
done

echo -e "\n=================================================="
echo "  FINAL STATUS"
echo "=================================================="

SURVIVORS=$(ps aux | grep "application_server.py" | grep -v grep | wc -l)
echo "Surviving nodes: $SURVIVORS/2"

if [ $SURVIVORS -eq 2 ]; then
    echo "✓ Both followers survived!"
    
    # Check if new leader elected
    NEW_LEADER_FOUND=0
    for i in 1 2 3; do
        if [ "node${i}" != "$LEADER_NODE" ]; then
            if tail -20 logs/app_server_${i}.log 2>/dev/null | grep -q "Became LEADER"; then
                echo "✓ New leader elected: node${i}"
                NEW_LEADER_FOUND=1
                break
            fi
        fi
    done
    
    if [ $NEW_LEADER_FOUND -eq 1 ]; then
        echo "✓✓ TEST PASSED - Failover successful!"
    else
        echo "✗ No new leader elected (may need more time)"
    fi
else
    echo "✗✗ TEST FAILED - Followers crashed!"
    echo ""
    echo "Checking logs for crash reason..."
    for i in 1 2 3; do
        if [ "node${i}" != "$LEADER_NODE" ]; then
            echo ""
            echo "=== node${i} last 30 lines ==="
            tail -30 logs/app_server_${i}.log
        fi
    done
fi

echo ""
echo "To see full logs:"
echo "  tail -50 logs/app_server_2.log"
echo "  tail -50 logs/app_server_3.log"
echo ""
echo "=================================================="
