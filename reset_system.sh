#!/bin/bash
# Reset system state - kills servers and clears logs
# This ensures a completely fresh start with empty state

echo "=================================================="
echo "  Resetting Distributed Ticket Booking System"
echo "=================================================="

echo -e "\n[1/4] Stopping all servers..."
pkill -f "application_server.py" 2>/dev/null
pkill -f "llm_server.py" 2>/dev/null
sleep 2

# Check if processes are really stopped
if pgrep -f "application_server.py\|llm_server.py" > /dev/null; then
    echo "  Force killing remaining processes..."
    pkill -9 -f "application_server.py" 2>/dev/null
    pkill -9 -f "llm_server.py" 2>/dev/null
    sleep 1
fi

echo "  ✓ All servers stopped"

echo -e "\n[2/4] Clearing logs..."
rm -f logs/*.log
mkdir -p logs
echo "  ✓ Logs cleared"

echo -e "\n[3/4] Clearing any persistent data..."
# Remove any state files if they exist
rm -f *.db 2>/dev/null
rm -f *.state 2>/dev/null
rm -f src/servers/*.db 2>/dev/null
rm -f src/raft/*.db 2>/dev/null
echo "  ✓ State files cleared"

echo -e "\n[4/4] Verifying clean state..."
# Check no Python processes related to our system
REMAINING=$(pgrep -f "application_server.py\|llm_server.py" | wc -l)
if [ $REMAINING -eq 0 ]; then
    echo "  ✓ No processes running"
else
    echo "  ⚠️  Warning: $REMAINING process(es) still running"
fi

echo ""
echo "="*50
echo "✓ RESET COMPLETE - System is now clean"
echo "="*50
echo ""
echo "State machine will reinitialize with fresh data on next start."
echo ""
echo "Next steps:"
echo "  1. Start system: ./start_system.sh"
echo "  2. Wait 15 seconds for initialization"
echo "  3. Check state: python3 check_state.py"
echo "  4. Run test: python3 quick_test.py"
echo ""
echo "=================================================="
