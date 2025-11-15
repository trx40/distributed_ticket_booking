#!/bin/bash
# Find the exact cause of the crash

echo "=================================================="
echo "  Finding Exact Crash Cause"
echo "=================================================="

# Function to extract last error from log
get_last_error() {
    local logfile=$1
    echo ""
    echo "Last error in $logfile:"
    echo "----------------------------------------"
    
    # Get last traceback
    if grep -q "Traceback" "$logfile" 2>/dev/null; then
        grep -A 20 "Traceback" "$logfile" | tail -25
    elif grep -qi "error" "$logfile" 2>/dev/null; then
        grep -i "error" "$logfile" | tail -10
    else
        echo "(No errors found)"
    fi
    echo "----------------------------------------"
}

# Check all logs
for i in 1 2 3; do
    if [ -f "logs/app_server_${i}.log" ]; then
        get_last_error "logs/app_server_${i}.log"
    fi
done

# Common crash patterns
echo ""
echo "=================================================="
echo "  Analyzing Crash Patterns"
echo "=================================================="

echo ""
echo "[1] Checking for deadlock indicators..."
if grep -qi "lock.*timeout\|deadlock" logs/*.log 2>/dev/null; then
    echo "✗ DEADLOCK DETECTED"
    grep -i "lock.*timeout\|deadlock" logs/*.log
else
    echo "✓ No deadlock patterns"
fi

echo ""
echo "[2] Checking for thread errors..."
if grep -qi "thread.*error\|threading" logs/*.log 2>/dev/null; then
    echo "✗ THREAD ERRORS DETECTED"
    grep -i "thread.*error" logs/*.log | head -10
else
    echo "✓ No thread errors"
fi

echo ""
echo "[3] Checking for RPC failures..."
RPC_COUNT=$(grep -ci "rpc.*error\|rpc.*failed" logs/*.log 2>/dev/null || echo 0)
if [ $RPC_COUNT -gt 50 ]; then
    echo "✗ EXCESSIVE RPC FAILURES ($RPC_COUNT)"
    echo "Sample:"
    grep -i "rpc.*error\|rpc.*failed" logs/*.log | head -5
else
    echo "✓ RPC failures: $RPC_COUNT (normal during leader kill)"
fi

echo ""
echo "[4] Checking for lock acquisition issues..."
if grep -qi "acquire.*failed\|cannot acquire lock" logs/*.log 2>/dev/null; then
    echo "✗ LOCK ACQUISITION FAILURES"
    grep -i "acquire.*failed\|cannot acquire lock" logs/*.log
else
    echo "✓ No lock acquisition issues"
fi

echo ""
echo "[5] Checking for exception in critical sections..."
if grep -qi "exception.*election\|exception.*heartbeat" logs/*.log 2>/dev/null; then
    echo "✗ EXCEPTIONS IN CRITICAL CODE"
    grep -B 2 -A 5 "exception.*election\|exception.*heartbeat" logs/*.log
else
    echo "✓ No exceptions in critical sections"
fi

echo ""
echo "[6] Checking process exit status..."
for i in 1 2 3; do
    if [ -f "logs/app_server_${i}.log" ]; then
        if tail -5 "logs/app_server_${i}.log" | grep -qi "shutting down\|stopped"; then
            echo "  Node $i: Clean shutdown"
        else
            echo "  Node $i: Abnormal termination (crashed)"
            echo "    Last lines:"
            tail -3 "logs/app_server_${i}.log" | sed 's/^/      /'
        fi
    fi
done

# Specific known issues
echo ""
echo "=================================================="
echo "  Known Issue Detection"
echo "=================================================="

echo ""
echo "[Issue 1] Lock held during RPC call:"
if grep -q "RequestVote.*timeout\|AppendEntries.*timeout" logs/*.log 2>/dev/null; then
    echo "✗ LIKELY CAUSE: Locks held during RPC calls"
    echo "  This causes deadlocks when peer nodes are unreachable"
    echo "  FIX: Use the Ultra-Robust Raft implementation"
else
    echo "✓ No evidence of this issue"
fi

echo ""
echo "[Issue 2] Unhandled RPC exceptions:"
if grep -q "Traceback.*stub\|Traceback.*RequestVote\|Traceback.*AppendEntries" logs/*.log 2>/dev/null; then
    echo "✗ LIKELY CAUSE: Unhandled RPC exceptions"
    echo "  RPC calls to dead leader throw exceptions"
    echo "  FIX: Wrap all RPC calls in try-except blocks"
else
    echo "✓ No evidence of this issue"
fi

echo ""
echo "[Issue 3] Threading issues:"
if grep -q "Thread.*died\|Thread.*exception" logs/*.log 2>/dev/null; then
    echo "✗ LIKELY CAUSE: Thread crashes"
    echo "  Background threads dying without recovery"
    grep "Thread.*died\|Thread.*exception" logs/*.log
else
    echo "✓ No evidence of this issue"
fi

echo ""
echo "[Issue 4] State machine errors:"
if grep -qi "state machine.*error\|apply.*error" logs/*.log 2>/dev/null; then
    echo "✗ State machine errors detected"
    grep -i "state machine.*error\|apply.*error" logs/*.log
else
    echo "✓ No state machine errors"
fi

# Recommendation
echo ""
echo "=================================================="
echo "  Diagnosis Summary"
echo "=================================================="

DEADLOCK=$(grep -ci "deadlock\|lock.*timeout" logs/*.log 2>/dev/null || echo 0)
EXCEPTIONS=$(grep -ci "exception\|error" logs/*.log 2>/dev/null || echo 0)
RPC_ERRORS=$(grep -ci "rpc.*error" logs/*.log 2>/dev/null || echo 0)

echo ""
echo "Statistics:"
echo "  Deadlock indicators: $DEADLOCK"
echo "  Total exceptions: $EXCEPTIONS"
echo "  RPC errors: $RPC_ERRORS"
echo ""

if [ $DEADLOCK -gt 0 ]; then
    echo "PRIMARY ISSUE: Deadlock"
    echo ""
    echo "The code is holding locks while making RPC calls."
    echo "When a node is killed, RPCs to it hang, causing deadlock."
    echo ""
    echo "SOLUTION:"
    echo "  1. Replace src/raft/raft_node.py with Ultra-Robust version"
    echo "  2. Key fix: Release locks BEFORE making RPC calls"
    echo "  3. Use daemon threads for parallel operations"
    echo ""
elif [ $EXCEPTIONS -gt 100 ]; then
    echo "PRIMARY ISSUE: Unhandled exceptions"
    echo ""
    echo "RPC calls are failing but exceptions aren't caught."
    echo ""
    echo "SOLUTION:"
    echo "  1. Add try-except around ALL RPC calls"
    echo "  2. Handle grpc.RpcError specifically"
    echo "  3. Don't crash on UNAVAILABLE status (normal during failures)"
    echo ""
else
    echo "UNCLEAR - Manual inspection needed"
    echo ""
    echo "Check the full logs:"
    echo "  tail -100 logs/app_server_1.log"
    echo "  tail -100 logs/app_server_2.log"
    echo "  tail -100 logs/app_server_3.log"
    echo ""
fi

echo "=================================================="
