#!/bin/bash
# Script to start a client

echo "Starting Movie Ticket Booking Client..."
source venv/bin/activate

cd src/client
python3 client.py

cd ../..
