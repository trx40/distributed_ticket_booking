#!/bin/bash
# Monitor script to watch logs in real-time

echo "Monitoring system logs..."
echo "Press Ctrl+C to exit"
echo ""

# Use multitail if available, otherwise fall back to tail
if command -v multitail &> /dev/null; then
    multitail \
        -l "tail -f logs/llm_server.log" \
        -l "tail -f logs/app_server_1.log" \
        -l "tail -f logs/app_server_2.log" \
        -l "tail -f logs/app_server_3.log"
else
    # Fallback: use regular tail
    tail -f logs/*.log
fi
