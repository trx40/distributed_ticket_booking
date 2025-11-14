#!/bin/bash
# Cleanup script to reset the system

echo "Cleaning up Distributed Ticket Booking System..."

# Kill all running processes
pkill -f application_server.py
pkill -f llm_server.py
pkill -f client.py

# Clean logs
rm -f logs/*.log

# Clean generated files
rm -rf generated/*
rm -rf src/**/*_pb2.py
rm -rf src/**/*_pb2_grpc.py
rm -rf src/**/__pycache__

# Clean Python cache
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find . -type f -name "*.pyc" -delete

echo "✓ Cleanup complete"

