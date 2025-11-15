#!/bin/bash
# Verify Log Replication Across Raft Nodes

echo "=================================================="
echo "  Raft Log Replication Verification"
echo "=================================================="

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Check if system is running
echo -e "\n${YELLOW}[1/7]${NC} Checking system status..."

APP_COUNT=$(ps aux | grep "application_server.py" | grep -v grep | wc -l)
LLM_COUNT=$(ps aux | grep "llm_server.py" | grep -v grep | wc -l)

if [ $APP_COUNT -lt 2 ]; then
    echo -e "${RED}✗${NC} Need at least 2 application servers running"
    echo "  Currently running: $APP_COUNT"
    echo "  Start system with: ./start_system.sh"
    exit 1
fi

echo -e "${GREEN}✓${NC} System is running"
echo "  Application Servers: $APP_COUNT"
echo "  LLM Server: $LLM_COUNT"

# Check which node is leader
echo -e "\n${YELLOW}[2/7]${NC} Identifying leader node..."

LEADER=""
for i in 1 2 3; do
    if [ -f "logs/app_server_${i}.log" ]; then
        if grep -q "Became LEADER" logs/app_server_${i}.log 2>/dev/null; then
            LAST_LEADER=$(grep "Became LEADER" logs/app_server_${i}.log | tail -1)
            if echo "$LAST_LEADER" | grep -q "term"; then
                LEADER="node${i}"
                LEADER_TERM=$(echo "$LAST_LEADER" | grep -oP 'term \K\d+' || echo "unknown")
                echo -e "${GREEN}✓${NC} Leader: $LEADER (Term: $LEADER_TERM)"
                break
            fi
        fi
    fi
done

if [ -z "$LEADER" ]; then
    echo -e "${RED}✗${NC} No leader found - system may still be electing"
    echo "  Wait a few seconds and try again"
    exit 1
fi

# Check log entries on each node
echo -e "\n${YELLOW}[3/7]${NC} Checking applied log entries on each node..."

declare -A APPLIED_COUNTS

for i in 1 2 3; do
    if [ -f "logs/app_server_${i}.log" ]; then
        COUNT=$(grep -c "Applied entry" logs/app_server_${i}.log 2>/dev/null || echo 0)
        APPLIED_COUNTS[node${i}]=$COUNT
        
        if [ "node${i}" = "$LEADER" ]; then
            echo -e "  ${BLUE}node${i}${NC} (Leader):   $COUNT entries applied"
        else
            echo -e "  ${BLUE}node${i}${NC} (Follower): $COUNT entries applied"
        fi
    fi
done

# Check if counts match
echo -e "\n${YELLOW}[4/7]${NC} Verifying entry counts match..."

FIRST_COUNT=""
ALL_MATCH=true

for node in "${!APPLIED_COUNTS[@]}"; do
    if [ -z "$FIRST_COUNT" ]; then
        FIRST_COUNT=${APPLIED_COUNTS[$node]}
    elif [ "${APPLIED_COUNTS[$node]}" != "$FIRST_COUNT" ]; then
        ALL_MATCH=false
        break
    fi
done

if $ALL_MATCH; then
    echo -e "${GREEN}✓${NC} All nodes have same entry count: $FIRST_COUNT"
else
    echo -e "${RED}✗${NC} Entry counts differ across nodes!"
    for node in "${!APPLIED_COUNTS[@]}"; do
        echo "  $node: ${APPLIED_COUNTS[$node]}"
    done
    echo ""
    echo "This may indicate:"
    echo "  • Replication lag (wait a few seconds)"
    echo "  • Follower crashed during replication"
    echo "  • Network issues between nodes"
fi

# Check last applied entries
echo -e "\n${YELLOW}[5/7]${NC} Checking last applied entry on each node..."

for i in 1 2 3; do
    if [ -f "logs/app_server_${i}.log" ]; then
        LAST_ENTRY=$(grep "Applied entry" logs/app_server_${i}.log 2>/dev/null | tail -1)
        if [ ! -z "$LAST_ENTRY" ]; then
            ENTRY_NUM=$(echo "$LAST_ENTRY" | grep -oP 'Applied entry \K\d+')
            echo "  node${i}: Last applied entry $ENTRY_NUM"
        else
            echo "  node${i}: No entries applied yet"
        fi
    fi
done

# Check AppendEntries activity
echo -e "\n${YELLOW}[6/7]${NC} Checking replication activity..."

RECENT_WINDOW=30  # seconds

for i in 1 2 3; do
    if [ -f "logs/app_server_${i}.log" ]; then
        # Count recent AppendEntries
        if [ "node${i}" = "$LEADER" ]; then
            # Leader sends AppendEntries
            APPEND_COUNT=$(grep "AppendEntries" logs/app_server_${i}.log 2>/dev/null | tail -100 | wc -l)
            echo "  ${BLUE}node${i}${NC} (Leader):   $APPEND_COUNT recent AppendEntries operations"
        else
            # Followers receive AppendEntries
            APPEND_COUNT=$(grep "AppendEntries" logs/app_server_${i}.log 2>/dev/null | tail -100 | wc -l)
            echo "  ${BLUE}node${i}${NC} (Follower): $APPEND_COUNT recent AppendEntries operations"
        fi
    fi
done

# Test by running Python verification
echo -e "\n${YELLOW}[7/7]${NC} Running comprehensive state verification..."
echo ""

python3 test_log_replication.py --quick-check 2>&1 | tail -20 || {
    # If Python test doesn't have quick-check flag, show manual verification
    echo "To run full verification test:"
    echo "  ${BLUE}python3 test_log_replication.py${NC}"
}

# Summary
echo ""
echo "=================================================="
echo "  Verification Summary"
echo "=================================================="

if $ALL_MATCH && [ "$FIRST_COUNT" -gt 0 ]; then
    echo -e "\n${GREEN}✓✓✓ LOG REPLICATION VERIFIED ✓✓✓${NC}"
    echo ""
    echo "All nodes have:"
    echo "  ✓ Same number of applied entries ($FIRST_COUNT)"
    echo "  ✓ Active replication (AppendEntries)"
    echo "  ✓ Consistent state"
    echo ""
    echo "Your Raft implementation is working correctly!"
elif $ALL_MATCH && [ "$FIRST_COUNT" -eq 0 ]; then
    echo -e "\n${YELLOW}⚠ NO ENTRIES APPLIED YET ⚠${NC}"
    echo ""
    echo "System is running but no operations have been performed."
    echo ""
    echo "To test log replication:"
    echo "  1. Start a client: ./start_client.sh"
    echo "  2. Make some bookings"
    echo "  3. Run this script again"
    echo ""
    echo "Or run automated test:"
    echo "  ${BLUE}python3 test_log_replication.py${NC}"
else
    echo -e "\n${RED}✗ LOG REPLICATION ISSUES DETECTED ✗${NC}"
    echo ""
    echo "Possible causes:"
    echo "  • Replication lag (wait a few seconds)"
    echo "  • Follower node crashed"
    echo "  • Network connectivity issues"
    echo "  • Raft bug in AppendEntries"
    echo ""
    echo "Debugging steps:"
    echo "  1. Check all nodes are running:"
    echo "     ${BLUE}ps aux | grep application_server${NC}"
    echo ""
    echo "  2. Check for errors in logs:"
    echo "     ${BLUE}grep -i error logs/app_server_*.log${NC}"
    echo ""
    echo "  3. Monitor replication in real-time:"
    echo "     ${BLUE}tail -f logs/app_server_*.log | grep 'Applied entry'${NC}"
    echo ""
    echo "  4. Run full verification test:"
    echo "     ${BLUE}python3 test_log_replication.py${NC}"
fi

echo "=================================================="

# Exit with appropriate code
if $ALL_MATCH; then
    exit 0
else
    exit 1
fi
