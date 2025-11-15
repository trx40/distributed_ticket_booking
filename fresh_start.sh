#!/bin/bash
# Fresh start script - ensures completely clean system

echo "=================================================="
echo "  FRESH START - Distributed Ticket Booking"
echo "=================================================="

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "\n${YELLOW}[1/7]${NC} Stopping all servers..."
pkill -9 -f "application_server.py" 2>/dev/null
pkill -9 -f "llm_server.py" 2>/dev/null
sleep 3

# Verify stopped
REMAINING=$(pgrep -f "application_server.py\|llm_server.py" | wc -l)
if [ $REMAINING -eq 0 ]; then
    echo -e "  ${GREEN}✓${NC} All servers stopped"
else
    echo -e "  ${RED}✗${NC} Warning: $REMAINING process(es) still running"
    echo "  Trying harder..."
    sudo killall -9 python3 2>/dev/null
    sleep 2
fi

echo -e "\n${YELLOW}[2/7]${NC} Clearing logs..."
rm -rf logs/*.log
mkdir -p logs
echo -e "  ${GREEN}✓${NC} Logs cleared"

echo -e "\n${YELLOW}[3/7]${NC} Clearing any state files..."
find . -name "*.db" -delete 2>/dev/null
find . -name "*.state" -delete 2>/dev/null
find . -name "*.pkl" -delete 2>/dev/null
echo -e "  ${GREEN}✓${NC} State files cleared"

echo -e "\n${YELLOW}[4/7]${NC} Starting system..."
./start_system.sh > /tmp/startup.log 2>&1 &
STARTUP_PID=$!

echo "  Waiting for startup (this takes about 20 seconds)..."
for i in {1..20}; do
    echo -n "."
    sleep 1
done
echo ""

echo -e "\n${YELLOW}[5/7]${NC} Checking server status..."
sleep 2

# Check LLM server
if pgrep -f "llm_server.py" > /dev/null; then
    echo -e "  ${GREEN}✓${NC} LLM Server running"
else
    echo -e "  ${RED}✗${NC} LLM Server not running"
fi

# Check app servers
APP_COUNT=$(pgrep -f "application_server.py" | wc -l)
if [ $APP_COUNT -eq 3 ]; then
    echo -e "  ${GREEN}✓${NC} All 3 Application Servers running"
else
    echo -e "  ${YELLOW}⚠${NC} Only $APP_COUNT/3 Application Servers running"
fi

echo -e "\n${YELLOW}[6/7]${NC} Waiting for Raft consensus..."
sleep 5

# Check for leader
if grep -q "Became LEADER" logs/app_server_*.log 2>/dev/null; then
    LEADER=$(grep "Became LEADER" logs/app_server_*.log 2>/dev/null | tail -1 | cut -d']' -f1 | cut -d'[' -f2)
    echo -e "  ${GREEN}✓${NC} Leader elected: $LEADER"
else
    echo -e "  ${YELLOW}⚠${NC} No leader elected yet (may need more time)"
fi

echo -e "\n${YELLOW}[7/7]${NC} Verifying system state..."

# Run state check
if [ -f "check_state.py" ]; then
    python3 check_state.py > /tmp/state_check.log 2>&1
    
    # Check if state is clean
    if grep -q "No bookings found" /tmp/state_check.log; then
        echo -e "  ${GREEN}✓${NC} System state is clean (no bookings)"
    else
        BOOKING_COUNT=$(grep -c "booking_id" /tmp/state_check.log)
        echo -e "  ${YELLOW}⚠${NC} Found $BOOKING_COUNT booking(s) - state may not be clean"
    fi
    
    # Check available seats
    MOVIE1_SEATS=$(grep "movie1" /tmp/state_check.log | grep -oP "Available: \K\d+")
    if [ ! -z "$MOVIE1_SEATS" ]; then
        if [ $MOVIE1_SEATS -eq 100 ]; then
            echo -e "  ${GREEN}✓${NC} Movie1 has all 100 seats available"
        else
            echo -e "  ${YELLOW}⚠${NC} Movie1 has only $MOVIE1_SEATS/100 seats available"
        fi
    fi
else
    echo -e "  ${YELLOW}⚠${NC} check_state.py not found, skipping state verification"
fi

echo ""
echo "=================================================="
echo -e "${GREEN}✓ FRESH START COMPLETE${NC}"
echo "=================================================="
echo ""
echo "System Status:"
ps aux | grep -E "application_server|llm_server" | grep -v grep | awk '{print "  - "$11" "$12" "$13" (PID: "$2")"}'
echo ""
echo "Next Steps:"
echo "  1. Check state:  python3 check_state.py"
echo "  2. Run test:     python3 quick_test.py"
echo "  3. Start client: ./start_client.sh"
echo ""
echo "Logs available in: logs/"
echo "  - tail -f logs/app_server_1.log"
echo "  - tail -f logs/llm_server.log"
echo ""
echo "=================================================="
