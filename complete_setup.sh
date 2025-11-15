#!/bin/bash
# Complete setup and sanity check script

echo "=================================================="
echo "  Complete Setup & Sanity Check"
echo "=================================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print status
print_status() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✓${NC} $2"
    else
        echo -e "${RED}✗${NC} $2"
        return 1
    fi
}

# 1. Check Python
echo -e "\n[1/10] Checking Python..."
python3 --version > /dev/null 2>&1
print_status $? "Python 3 installed"

# 2. Create directory structure
echo -e "\n[2/10] Creating directory structure..."
mkdir -p protos src/raft src/servers src/client src/utils generated logs
print_status $? "Directories created"

# 3. Setup virtual environment
echo -e "\n[3/10] Setting up virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
print_status $? "Virtual environment activated"

# 4. Install dependencies
echo -e "\n[4/10] Installing Python packages..."
pip install -q --upgrade pip
pip install -q grpcio==1.60.0 grpcio-tools==1.60.0 protobuf==4.25.1
pip install -q transformers==4.36.0 torch==2.1.0 --index-url https://download.pytorch.org/whl/cpu
pip install -q sentence-transformers==2.2.2 pyjwt==2.8.0 cryptography==41.0.7 python-dotenv==1.0.0
print_status $? "Dependencies installed"

# 5. Generate protobuf files
echo -e "\n[5/10] Generating protobuf files..."
python3 -m grpc_tools.protoc \
    -I./protos \
    --python_out=./generated \
    --grpc_python_out=./generated \
    ./protos/ticket_booking.proto \
    ./protos/raft.proto \
    ./protos/llm_service.proto 2>&1 | grep -v "WARNING"
print_status ${PIPESTATUS[0]} "Protobuf files generated"

# 6. Copy generated files
echo -e "\n[6/10] Copying generated files..."
cp generated/*.py src/raft/ 2>/dev/null
cp generated/*.py src/servers/ 2>/dev/null
cp generated/*.py src/client/ 2>/dev/null
print_status $? "Generated files copied"

# 7. Fix imports in generated files
echo -e "\n[7/10] Fixing imports..."
for file in src/client/*_pb2_grpc.py src/servers/*_pb2_grpc.py src/raft/*_pb2_grpc.py; do
    if [ -f "$file" ]; then
        sed -i 's/from \. import \(.*\)_pb2/import \1_pb2/' "$file"
    fi
done
print_status $? "Imports fixed"

# 8. Create __init__.py files
echo -e "\n[8/10] Creating package files..."
touch src/__init__.py
touch src/client/__init__.py
touch src/servers/__init__.py
touch src/raft/__init__.py
touch src/utils/__init__.py
print_status $? "Package files created"

# 9. Verify critical files exist
echo -e "\n[9/10] Verifying files..."
MISSING=0

check_file() {
    if [ ! -f "$1" ]; then
        echo -e "  ${RED}✗${NC} Missing: $1"
        MISSING=1
    else
        echo -e "  ${GREEN}✓${NC} Found: $1"
    fi
}

echo "  Protobuf files:"
check_file "src/client/ticket_booking_pb2.py"
check_file "src/client/ticket_booking_pb2_grpc.py"
check_file "src/servers/ticket_booking_pb2.py"
check_file "src/servers/ticket_booking_pb2_grpc.py"
check_file "src/servers/llm_service_pb2.py"
check_file "src/servers/llm_service_pb2_grpc.py"
check_file "src/raft/raft_pb2.py"
check_file "src/raft/raft_pb2_grpc.py"

echo "  Source files:"
check_file "src/client/client.py"
check_file "src/servers/application_server.py"
check_file "src/servers/llm_server.py"
check_file "src/raft/raft_node.py"
check_file "src/raft/state_machine.py"
check_file "src/utils/auth.py"

echo "  Proto definitions:"
check_file "protos/ticket_booking.proto"
check_file "protos/raft.proto"
check_file "protos/llm_service.proto"

if [ $MISSING -eq 0 ]; then
    print_status 0 "All required files present"
else
    print_status 1 "Some files are missing"
fi

# 10. Test imports
echo -e "\n[10/10] Testing Python imports..."
python3 << 'EOF'
import sys
import os
sys.path.insert(0, 'src/servers')
sys.path.insert(0, 'src/raft')
sys.path.insert(0, 'src/utils')

errors = []

try:
    import ticket_booking_pb2
    import ticket_booking_pb2_grpc
    print("  ✓ ticket_booking protobuf imports OK")
except Exception as e:
    print(f"  ✗ ticket_booking protobuf error: {e}")
    errors.append(str(e))

try:
    import llm_service_pb2
    import llm_service_pb2_grpc
    print("  ✓ llm_service protobuf imports OK")
except Exception as e:
    print(f"  ✗ llm_service protobuf error: {e}")
    errors.append(str(e))

try:
    import raft_pb2
    import raft_pb2_grpc
    print("  ✓ raft protobuf imports OK")
except Exception as e:
    print(f"  ✗ raft protobuf error: {e}")
    errors.append(str(e))

try:
    from state_machine import StateMachine
    print("  ✓ state_machine import OK")
except Exception as e:
    print(f"  ✗ state_machine error: {e}")
    errors.append(str(e))

try:
    from auth import AuthManager
    print("  ✓ auth import OK")
except Exception as e:
    print(f"  ✗ auth error: {e}")
    errors.append(str(e))

sys.exit(0 if len(errors) == 0 else 1)
EOF

IMPORT_STATUS=$?
print_status $IMPORT_STATUS "Python imports working"

# Make scripts executable
chmod +x start_system.sh start_client.sh fix_imports.sh 2>/dev/null

# Summary
echo ""
echo "=================================================="
echo "  Setup Complete!"
echo "=================================================="
if [ $MISSING -eq 0 ] && [ $IMPORT_STATUS -eq 0 ]; then
    echo -e "${GREEN}✓ System is ready to run${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Start system: ./start_system.sh"
    echo "  2. In new terminal: ./start_client.sh"
    echo ""
    echo "Troubleshooting:"
    echo "  - Check logs: tail -f logs/*.log"
    echo "  - Stop system: pkill -f 'application_server\\|llm_server'"
else
    echo -e "${YELLOW}⚠ Setup completed with warnings${NC}"
    echo "Please review errors above"
fi
echo "=================================================="
