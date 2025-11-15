#!/bin/bash
# Graceful Shutdown Script for Distributed Ticket Booking System

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "=================================================="
echo "  Graceful Shutdown - Distributed Ticket Booking"
echo "=================================================="

# Function to check if a process exists
process_exists() {
    ps -p $1 > /dev/null 2>&1
    return $?
}

# Function to wait for process to stop
wait_for_process() {
    local pid=$1
    local name=$2
    local timeout=10
    local count=0
    
    while process_exists $pid; do
        if [ $count -ge $timeout ]; then
            return 1
        fi
        sleep 1
        count=$((count + 1))
    done
    return 0
}

# Step 1: Find all running processes
echo -e "\n${YELLOW}[1/6]${NC} Identifying running processes..."

LLM_PID=$(pgrep -f "llm_server.py" | head -1)
APP_PIDS=$(pgrep -f "application_server.py")

if [ -z "$LLM_PID" ] && [ -z "$APP_PIDS" ]; then
    echo -e "${GREEN}✓${NC} No processes running - system already stopped"
    exit 0
fi

echo "Found processes:"
if [ ! -z "$LLM_PID" ]; then
    echo -e "  ${BLUE}•${NC} LLM Server (PID: $LLM_PID)"
fi

if [ ! -z "$APP_PIDS" ]; then
    for pid in $APP_PIDS; do
        # Get node ID from process command
        NODE_ID=$(ps -p $pid -o args= | grep -oP 'node-id \K\w+' || echo "unknown")
        echo -e "  ${BLUE}•${NC} Application Server - $NODE_ID (PID: $pid)"
    done
fi

# Step 2: Check for active client connections (optional)
echo -e "\n${YELLOW}[2/6]${NC} Checking for active connections..."

# Count established connections on server ports
CONN_COUNT=$(netstat -an 2>/dev/null | grep -E ':(50051|50052|50053|50060)' | grep ESTABLISHED | wc -l || echo 0)

if [ $CONN_COUNT -gt 0 ]; then
    echo -e "${YELLOW}⚠${NC} Found $CONN_COUNT active connection(s)"
    echo "  Waiting 5 seconds for clients to disconnect..."
    sleep 5
else
    echo -e "${GREEN}✓${NC} No active client connections"
fi

# Step 3: Stop Application Servers gracefully (SIGTERM first)
echo -e "\n${YELLOW}[3/6]${NC} Stopping Application Servers..."

if [ ! -z "$APP_PIDS" ]; then
    for pid in $APP_PIDS; do
        NODE_ID=$(ps -p $pid -o args= | grep -oP 'node-id \K\w+' || echo "unknown")
        
        if process_exists $pid; then
            echo -e "  Stopping $NODE_ID (PID: $pid)..."
            
            # Send SIGTERM (graceful shutdown)
            kill -TERM $pid 2>/dev/null
            
            # Wait for it to stop
            if wait_for_process $pid "$NODE_ID"; then
                echo -e "  ${GREEN}✓${NC} $NODE_ID stopped gracefully"
            else
                echo -e "  ${YELLOW}⚠${NC} $NODE_ID did not stop in time, forcing..."
                kill -9 $pid 2>/dev/null
                sleep 1
                if process_exists $pid; then
                    echo -e "  ${RED}✗${NC} Failed to stop $NODE_ID"
                else
                    echo -e "  ${GREEN}✓${NC} $NODE_ID force stopped"
                fi
            fi
        fi
    done
else
    echo -e "  ${BLUE}•${NC} No Application Servers to stop"
fi

# Step 4: Stop LLM Server gracefully
echo -e "\n${YELLOW}[4/6]${NC} Stopping LLM Server..."

if [ ! -z "$LLM_PID" ] && process_exists $LLM_PID; then
    echo -e "  Stopping LLM Server (PID: $LLM_PID)..."
    
    # Send SIGTERM (graceful shutdown)
    kill -TERM $LLM_PID 2>/dev/null
    
    # Wait for it to stop
    if wait_for_process $LLM_PID "LLM Server"; then
        echo -e "  ${GREEN}✓${NC} LLM Server stopped gracefully"
    else
        echo -e "  ${YELLOW}⚠${NC} LLM Server did not stop in time, forcing..."
        kill -9 $LLM_PID 2>/dev/null
        sleep 1
        if process_exists $LLM_PID; then
            echo -e "  ${RED}✗${NC} Failed to stop LLM Server"
        else
            echo -e "  ${GREEN}✓${NC} LLM Server force stopped"
        fi
    fi
else
    echo -e "  ${BLUE}•${NC} LLM Server not running"
fi

# Step 5: Verify all processes stopped
echo -e "\n${YELLOW}[5/6]${NC} Verifying shutdown..."

sleep 2

REMAINING_PROCS=$(pgrep -f "application_server.py\|llm_server.py" | wc -l)

if [ $REMAINING_PROCS -eq 0 ]; then
    echo -e "${GREEN}✓${NC} All processes stopped successfully"
else
    echo -e "${RED}✗${NC} $REMAINING_PROCS process(es) still running"
    echo "  Attempting force kill..."
    pkill -9 -f "application_server.py"
    pkill -9 -f "llm_server.py"
    sleep 2
    
    REMAINING_PROCS=$(pgrep -f "application_server.py\|llm_server.py" | wc -l)
    if [ $REMAINING_PROCS -eq 0 ]; then
        echo -e "${GREEN}✓${NC} Force kill successful"
    else
        echo -e "${RED}✗${NC} Some processes could not be stopped"
        echo "  You may need to use: sudo killall -9 python3"
    fi
fi

# Step 6: Clean up resources (optional)
echo -e "\n${YELLOW}[6/6]${NC} Cleaning up resources..."

# Check if ports are still in use
PORTS_IN_USE=0
for port in 50051 50052 50053 50060 50061 50062 50063; do
    if netstat -tuln 2>/dev/null | grep -q ":$port " || ss -tuln 2>/dev/null | grep -q ":$port "; then
        echo -e "  ${YELLOW}⚠${NC} Port $port still in use"
        PORTS_IN_USE=1
    fi
done

if [ $PORTS_IN_USE -eq 0 ]; then
    echo -e "${GREEN}✓${NC} All ports released"
else
    echo -e "${YELLOW}⚠${NC} Some ports still in use (they will be released shortly)"
fi

# Archive logs (optional)
read -p "Archive logs before exit? (y/n): " -n 1 -r ARCHIVE
echo

if [[ $ARCHIVE =~ ^[Yy]$ ]]; then
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    ARCHIVE_DIR="logs_archive_${TIMESTAMP}"
    
    mkdir -p "$ARCHIVE_DIR"
    cp logs/*.log "$ARCHIVE_DIR/" 2>/dev/null
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓${NC} Logs archived to: $ARCHIVE_DIR"
    else
        echo -e "${YELLOW}⚠${NC} No logs to archive"
    fi
fi

# Final summary
echo ""
echo "=================================================="
echo "  Shutdown Complete"
echo "=================================================="

FINAL_COUNT=$(pgrep -f "application_server.py\|llm_server.py" | wc -l)

if [ $FINAL_COUNT -eq 0 ]; then
    echo -e "\n${GREEN}✓✓✓ SHUTDOWN SUCCESSFUL ✓✓✓${NC}"
    echo ""
    echo "All services have been stopped gracefully."
    echo ""
    echo "To restart the system:"
    echo "  ${BLUE}./start_system.sh${NC}"
    echo ""
    echo "To check if ports are free:"
    echo "  ${BLUE}netstat -tuln | grep -E ':(5005[123]|5006[0-3])'${NC}"
else
    echo -e "\n${YELLOW}⚠ SHUTDOWN INCOMPLETE ⚠${NC}"
    echo ""
    echo "Some processes may still be running."
    echo "Check with: ps aux | grep -E 'application_server|llm_server'"
    echo ""
    echo "If needed, use force kill:"
    echo "  ${BLUE}pkill -9 -f 'application_server.py'${NC}"
    echo "  ${BLUE}pkill -9 -f 'llm_server.py'${NC}"
fi

echo "=================================================="
