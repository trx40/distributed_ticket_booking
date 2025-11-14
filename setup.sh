#!/bin/bash
# ============================================================================
# FILE: setup.sh
# ============================================================================
# Complete setup script for Distributed Movie Ticket Booking System

echo "=================================================="
echo "  Distributed Movie Ticket Booking System Setup  "
echo "=================================================="

# Check Python version
echo -e "\n[1/6] Checking Python version..."
python3 --version
if [ $? -ne 0 ]; then
    echo "ERROR: Python 3 is not installed"
    exit 1
fi

# Create project structure
echo -e "\n[2/6] Creating project structure..."
mkdir -p protos src/raft src/servers src/client src/utils generated

# Install system dependencies
echo -e "\n[3/6] Installing system dependencies..."
sudo apt-get update
sudo apt-get install -y python3-pip python3-venv

# Create and activate virtual environment
echo -e "\n[4/6] Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
echo -e "\n[5/6] Installing Python packages..."
pip install --upgrade pip
pip install grpcio==1.60.0
pip install grpcio-tools==1.60.0
pip install protobuf==4.25.1
pip install transformers==4.36.0
pip install torch==2.1.0 --index-url https://download.pytorch.org/whl/cpu
pip install sentence-transformers==2.2.2
pip install pyjwt==2.8.0
pip install cryptography==41.0.7
pip install python-dotenv==1.0.0

# Generate gRPC code from proto files
echo -e "\n[6/6] Generating gRPC code..."
python3 -m grpc_tools.protoc \
    -I./protos \
    --python_out=./generated \
    --grpc_python_out=./generated \
    ./protos/ticket_booking.proto \
    ./protos/raft.proto \
    ./protos/llm_service.proto

# Fix imports in generated files
echo "Fixing imports in generated files..."
cd generated
for file in *_pb2_grpc.py; do
    sed -i 's/import \(.*\)_pb2/from . import \1_pb2/' "$file"
done
cd ..

# Copy generated files to source directories
cp generated/*.py src/raft/
cp generated/*.py src/servers/
cp generated/*.py src/client/

echo -e "\n✓ Setup complete!"
echo "To activate the environment, run: source venv/bin/activate"
