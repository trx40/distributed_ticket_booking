#!/bin/bash
# Emergency recovery - fix the crashing system

echo "=================================================="
echo "  EMERGENCY RECOVERY - Fix Crashing Nodes"
echo "=================================================="

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Step 1: Nuclear option - kill everything
echo -e "\n${YELLOW}[1/8]${NC} Force killing all processes..."
pkill -9 -f "python.*application_server"
pkill -9 -f "python.*llm_server"
pkill -9 python3  # Last resort
sleep 3

# Verify nothing running
REMAINING=$(pgrep -f "application_server\|llm_server" | wc -l)
if [ $REMAINING -gt 0 ]; then
    echo -e "${RED}✗ Processes still running, trying sudo...${NC}"
    sudo killall -9 python3 2>/dev/null
    sleep 2
fi

REMAINING=$(pgrep -f "application_server\|llm_server" | wc -l)
if [ $REMAINING -eq 0 ]; then
    echo -e "${GREEN}✓ All processes stopped${NC}"
else
    echo -e "${RED}✗ Cannot kill processes - reboot may be required${NC}"
    exit 1
fi

# Step 2: Clear everything
echo -e "\n${YELLOW}[2/8]${NC} Clearing logs and state..."
rm -rf logs/*.log
rm -rf logs/*.pid
rm -rf *.db
rm -rf *.state
mkdir -p logs
echo -e "${GREEN}✓ Logs cleared${NC}"

# Step 3: Verify files exist
echo -e "\n${YELLOW}[3/8]${NC} Verifying source files..."
MISSING=0

if [ ! -f "src/raft/raft_node.py" ]; then
    echo -e "${RED}✗ Missing src/raft/raft_node.py${NC}"
    MISSING=1
fi

if [ ! -f "src/servers/application_server.py" ]; then
    echo -e "${RED}✗ Missing src/servers/application_server.py${NC}"
    MISSING=1
fi

if [ ! -f "src/servers/llm_server.py" ]; then
    echo -e "${RED}✗ Missing src/servers/llm_server.py${NC}"
    MISSING=1
fi

if [ $MISSING -eq 1 ]; then
    echo -e "${RED}Cannot continue - missing source files${NC}"
    exit 1
fi

echo -e "${GREEN}✓ All source files present${NC}"

# Step 4: Check for syntax errors
echo -e "\n${YELLOW}[4/8]${NC} Checking for Python syntax errors..."
source venv/bin/activate

python3 -m py_compile src/raft/raft_node.py 2>&1 | grep -i error
if [ $? -eq 0 ]; then
    echo -e "${RED}✗ Syntax errors in raft_node.py${NC}"
    exit 1
fi

python3 -m py_compile src/servers/application_server.py 2>&1 | grep -i error
if [ $? -eq 0 ]; then
    echo -e "${RED}✗ Syntax errors in application_server.py${NC}"
    exit 1
fi

echo -e "${GREEN}✓ No syntax errors${NC}"

# Step 5: Test imports
echo -e "\n${YELLOW}[5/8]${NC} Testing imports..."
cd src/raft
python3 -c "import raft_node; print('OK')" 2>&1 | grep -q OK
if [ $? -ne 0 ]; then
    echo -e "${RED}✗ Cannot import raft_node${NC}"
    cd ../..
    exit 1
fi
cd ../..

echo -e "${GREEN}✓ Imports working${NC}"

# Step 6: Check port availability
echo -e "\n${YELLOW}[6/8]${NC} Checking ports..."
for port in 50051 50052 50053 50060 50061 50062 50063; do
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo -e "${RED}✗ Port $port is in use${NC}"
        lsof -i :$port
        exit 1
    fi
done
echo -e "${GREEN}✓ All ports available${NC}"

# Step 7: Start with verbose logging
echo -e "\n${YELLOW}[7/8]${NC} Starting system with verbose logging..."

# Start LLM server
echo "  Starting LLM server..."
cd src/servers
python3 -u llm_server.py --port 50060 > ../../logs/llm_server.log 2>&1 &
LLM_PID=$!
cd ../..
sleep 3

# Check if LLM started
if ! ps -p $LLM_PID > /dev/null; then
    echo -e "${RED}✗ LLM server failed to start${NC}"
    echo "Log:"
    cat logs/llm_server.log
    exit 1
fi
echo -e "${GREEN}✓ LLM server started (PID: $LLM_PID)${NC}"

# Start app server 1
echo "  Starting app server 1..."
cd src/servers
python3 -u application_server.py \
    --node-id node1 \
    --port 50051 \
    --raft-port 50061 \
    --llm-server localhost:50060 \
    --peers "node1:localhost:50061,node2:localhost:50062,node3:localhost:50063" \
    > ../../logs/app_server_1.log 2>&1 &
APP1_PID=$!
cd ../..
sleep 3

if ! ps -p $APP1_PID > /dev/null; then
    echo -e "${RED}✗ App server 1 failed${NC}"
    echo "Log:"
    tail -50 logs/app_server_1.log
    exit 1
fi
echo -e "${GREEN}✓ App server 1 started (PID: $APP1_PID)${NC}"

# Start app server 2
echo "  Starting app server 2..."
cd src/servers
python3 -u application_server.py \
    --node-id node2 \
    --port 50052 \
    --raft-port 50062 \
    --llm-server localhost:50060 \
    --peers "node1:localhost:50061,node2:localhost:50062,node3:localhost:50063" \
    > ../../logs/app_server_2.log 2>&1 &
APP2_PID=$!
cd ../..
sleep 3

if ! ps -p $APP2_PID > /dev/null; then
    echo -e "${RED}✗ App server 2 failed${NC}"
    echo "Log:"
    tail -50 logs/app_server_2.log
    exit 1
fi
echo -e "${GREEN}✓ App server 2 started (PID: $APP2_PID)${NC}"

# Start app server 3
echo "  Starting app server 3..."
cd src/servers
python3 -u application_server.py \
    --node-id node3 \
    --port 50053 \
    --raft-port 50063 \
    --llm-server localhost:50060 \
    --peers "node1:localhost:50061,node2:localhost:50062,node3:localhost:50063" \
    > ../../logs/app_server_3.log 2>&1 &
APP3_PID=$!
cd ../..
sleep 3

if ! ps -p $APP3_PID > /dev/null; then
    echo -e "${RED}✗ App server 3 failed${NC}"
    echo "Log:"
    tail -50 logs/app_server_3.log
    exit 1
fi
echo -e "${GREEN}✓ App server 3 started (PID: $APP3_PID)${NC}"

# Step 8: Monitor startup
echo -e "\n${YELLOW}[8/8]${NC} Monitoring startup (15 seconds)..."
for i in {15..1}; do
    echo -n "$i... "
    sleep 1
    
    # Check if any crashed
    for pid in $APP1_PID $APP2_PID $APP3_PID; do
        if ! ps -p $pid > /dev/null; then
            echo -e "\n${RED}✗ Process $pid crashed during startup${NC}"
            exit 1
        fi
    done
done
echo ""

echo -e "${GREEN}✓ All servers still running${NC}"

# Final checks
echo ""
echo "=================================================="
echo "  System Status"
echo "=================================================="

echo ""
echo "Processes:"
ps aux | grep -E "application_server|llm_server" | grep -v grep | awk '{print "  "$2" "$11" "$12" "$13}'

echo ""
echo "Ports:"
netstat -tuln 2>/dev/null | grep -E ":(5005[123]|5006[0-3])" | awk '{print "  "$4}' | sort -u || \
ss -tuln | grep -E ":(5005[123]|5006[0-3])" | awk '{print "  "$5}' | sort -u

echo ""
echo "Checking for leader election..."
sleep 5
LEADER=$(grep "Became LEADER" logs/app_server_*.log 2>/dev/null | tail -1)
if [ ! -z "$LEADER" ]; then
    echo -e "${GREEN}✓ Leader elected:${NC}"
    echo "  $LEADER"
else
    echo -e "${YELLOW}⚠ No leader yet (may need more time)${NC}"
fi

echo ""
echo "=================================================="
echo "  Recovery Complete"
echo "=================================================="
echo ""
echo "System is running. Next steps:"
echo ""
echo "1. Test basic operation:"
echo "   ${BLUE}python3 quick_test.py${NC}"
echo ""
echo "2. Monitor logs:"
echo "   ${BLUE}tail -f logs/app_server_1.log${NC}"
echo ""
echo "3. Test failover:"
echo "   ${BLUE}# Find leader${NC}"
echo "   ${BLUE}grep 'Became LEADER' logs/app_server_*.log${NC}"
echo "   ${BLUE}# Kill it (e.g., if node1 is leader)${NC}"
echo "   ${BLUE}pkill -f 'application_server.py.*node1'${NC}"
echo "   ${BLUE}# Wait 10 seconds${NC}"
echo "   ${BLUE}sleep 10${NC}"
echo "   ${BLUE}# Check remaining nodes${NC}"
echo "   ${BLUE}ps aux | grep application_server | grep -v grep${NC}"
echo "   ${BLUE}# Should show 2 processes still running${NC}"
echo ""
echo "If nodes still crash, the issue is in the code."
echo "Replace src/raft/raft_node.py with the 'Ultra-Robust' version."
echo ""
echo "PIDs:"
echo "  LLM: $LLM_PID"
echo "  Node1: $APP1_PID"
echo "  Node2: $APP2_PID"
echo "  Node3: $APP3_PID"
echo ""
echo "=================================================="
