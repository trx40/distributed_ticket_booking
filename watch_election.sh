#!/bin/bash
# Watch election process in real-time

echo "Watching election process (press Ctrl+C to stop)..."
echo "Monitoring: vote requests, grants, denials, election results"
echo ""

tail -f logs/app_server_*.log | grep --line-buffered -E "election|vote|LEADER|FOLLOWER|CANDIDATE"
