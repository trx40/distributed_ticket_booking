#!/bin/bash
# Diagnose why nodes crash when leader is killed

echo "=================================================="
echo "  Node Crash Diagnosis Tool"
echo "=================================================="

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Function to check node health
check_node_health() {
    local node_num=$1
    local log_file="logs/app_server_${node_num}.log"
    
    echo -e "\n${YELLOW}[Node ${node_num}]${NC}"
    
    # Check if process is running
    if pgrep -f "application_server.py.*node${node_num}" > /dev/null; then
        echo -e "  Process: ${GREEN}RUNNING${NC}"
    else
        echo -e "  Process: ${RED}STOPPED${NC}"
    fi
    
    # Check for errors in log
    if [ -f "$log_file" ]; then
        local error_count=$(grep -i "error\|exception\|traceback" "$log_file" | wc -l)
        if [ $error_count -gt 0 ]; then
            echo -e "  Errors: ${RED}${error_count} found${NC}"
            echo "  Last 5 errors:"
            grep -i "error\|exception" "$log_file" | tail -5 | sed 's/^/    /'
        else
            echo -e "  Errors: ${GREEN}None${NC}"
        fi
        
        # Check last state
        local last_state=$(grep "LEADER\|FOLLOWER\|CANDIDATE" "$log_file" | tail -1)
        if [ ! -z "$last_state" ]; then
            echo "  Last state: $last_state"
        fi
        
        # Check for lock issues
        local lock_count=$(grep -i "lock\|deadlock\|timeout" "$log_file" | wc -l)
        if [ $lock_count -gt 0 ]; then
            echo -e "  ${YELLOW}Warning: $lock_count lock-related messages${NC}"
        fi
        
        # Check for RPC failures
        local rpc_fail=$(grep -i "rpc.*fail\|unavailable\|connection" "$log_file" | tail -3)
        if [ ! -z "$rpc_fail" ]; then
            echo "  Recent RPC issues:"
            echo "$rpc_fail" | sed 's/^/    /'
        fi
    else
        echo -e "  Log: ${RED}NOT FOUND${NC}"
    fi
}

# Main diagnosis
echo -e "\n${YELLOW}Step 1: Current System State${NC}"
echo "================================"

# Check all nodes
for i in 1 2 3; do
    check_node_health $i
done

# Check for common issues
echo -e "\n${YELLOW}Step 2: Common Issue Detection${NC}"
echo "================================"

# Issue 1: All nodes trying to be leader
echo -e "\n[Checking for split-brain...]"
leader_count=$(grep "Became LEADER" logs/app_server_*.log 2>/dev/null | wc -l)
if [ $leader_count -gt 1 ]; then
    echo -e "  ${RED}WARNING: Multiple leaders detected!${NC}"
    grep "Became LEADER" logs/app_server_*.log
else
    echo -e "  ${GREEN}OK: Single leader${NC}"
fi

# Issue 2: Nodes can't reach each other
echo -e "\n[Checking for network issues...]"
unreachable=$(grep -i "failed to.*vote\|failed to.*append" logs/app_server_*.log 2>/dev/null | wc -l)
if [ $unreachable -gt 10 ]; then
    echo -e "  ${RED}WARNING: High number of unreachable peers ($unreachable)${NC}"
else
    echo -e "  ${GREEN}OK: Peers reachable${NC}"
fi

# Issue 3: Thread deadlocks
echo -e "\n[Checking for deadlocks...]"
if grep -qi "deadlock" logs/app_server_*.log 2>/dev/null; then
    echo -e "  ${RED}WARNING: Deadlock detected!${NC}"
    grep -i "deadlock" logs/app_server_*.log
else
    echo -e "  ${GREEN}OK: No deadlocks${NC}"
fi

# Issue 4: Election storms
echo -e "\n[Checking for election storms...]"
election_count=$(grep "Starting election" logs/app_server_*.log 2>/dev/null | wc -l)
if [ $election_count -gt 20 ]; then
    echo -e "  ${RED}WARNING: Too many elections ($election_count)${NC}"
    echo "  This suggests nodes are constantly timing out"
else
    echo -e "  ${GREEN}OK: Normal election count${NC}"
fi

# Step 3: Test leader kill scenario
echo -e "\n${YELLOW}Step 3: Testing Leader Kill Scenario${NC}"
echo "================================"

# Find current leader
current_leader=$(grep "Became LEADER" logs/app_server_*.log 2>/dev/null | tail -1 | grep -o "app_server_[0-9]" | grep -o "[0-9]")

if [ -z "$current_leader" ]; then
    echo -e "${RED}No leader found. System may not be running properly.${NC}"
    echo ""
    echo "Try:"
    echo "  1. Stop all: pkill -9 -f application_server"
    echo "  2. Clear logs: rm -f logs/*.log"
    echo "  3. Start fresh: ./start_system.sh"
    echo "  4. Wait 15 seconds"
    echo "  5. Run this diagnosis again"
    exit 1
fi

echo "Current leader: node${current_leader}"
echo ""
echo "To test failover manually:"
echo "  1. Run: pkill -f 'application_server.py.*node${current_leader}'"
echo "  2. Wait 10 seconds"
echo "  3. Run this script again to see if new leader elected"
echo ""

# Step 4: Provide recommendations
echo -e "\n${YELLOW}Step 4: Recommendations${NC}"
echo "================================"

running_nodes=$(pgrep -f "application_server.py" | wc -l)
echo "Running nodes: $running_nodes/3"

if [ $running_nodes -lt 2 ]; then
    echo -e "\n${RED}CRITICAL: Less than 2 nodes running!${NC}"
    echo "Raft requires at least 2 nodes to function."
    echo "Action: Restart all nodes"
elif [ $running_nodes -eq 2 ]; then
    echo -e "\n${YELLOW}WARNING: Only 2 nodes running${NC}"
    echo "System is working but has no redundancy."
    echo "If another node fails, system will halt."
else
    echo -e "\n${GREEN}Good: All 3 nodes running${NC}"
fi

# Check Python exceptions
echo -e "\n[Checking for Python exceptions...]"
if grep -qi "traceback" logs/app_server_*.log 2>/dev/null; then
    echo -e "${RED}Python exceptions found in logs:${NC}"
    for i in 1 2 3; do
        if grep -qi "traceback" logs/app_server_${i}.log 2>/dev/null; then
            echo -e "\nNode $i last exception:"
            grep -A 10 "Traceback" logs/app_server_${i}.log | tail -15 | sed 's/^/  /'
        fi
    done
else
    echo -e "${GREEN}No Python exceptions found${NC}"
fi

# Step 5: Solution
echo -e "\n${YELLOW}Step 5: Quick Fix${NC}"
echo "================================"

echo ""
echo "If nodes are crashing when leader is killed:"
echo ""
echo "1. Update raft_node.py with the fixed version"
echo "   - Better error handling"
echo "   - No deadlocks"
echo "   - Proper thread management"
echo ""
echo "2. Restart system cleanly:"
echo "   pkill -9 -f application_server.py"
echo "   pkill -9 -f llm_server.py"
echo "   rm -f logs/*.log"
echo "   ./start_system.sh"
echo "   sleep 15"
echo ""
echo "3. Test failover:"
echo "   python3 test_failover.py"
echo ""

echo "=================================================="
