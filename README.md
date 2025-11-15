# Distributed Movie Ticket Booking System

A fault-tolerant distributed movie ticket booking system implementing the Raft consensus protocol with gRPC communication and LLM-powered customer support.

## 🎯 Project Overview

This system implements a distributed ticket booking platform with:
- **Raft Consensus**: Ensures strong consistency across multiple nodes
- **gRPC Communication**: High-performance RPC framework for inter-service communication
- **LLM Integration**: AI-powered customer support chatbot using DistilGPT2
- **Fault Tolerance**: Automatic leader election and recovery from node failures
- **Concurrency Control**: Prevents overbooking with distributed locks

## 🏗️ Architecture

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │ gRPC
       ▼
┌─────────────────────────────────────────┐
│     Application Servers (3 nodes)       │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐  │
│  │  Node1  │ │  Node2  │ │  Node3  │  │
│  │ LEADER  │ │FOLLOWER │ │FOLLOWER │  │
│  └────┬────┘ └────┬────┘ └────┬────┘  │
│       └───────Raft Consensus────┘       │
└────────────────┬────────────────────────┘
                 │ gRPC
                 ▼
          ┌─────────────┐
          │ LLM Server  │
          │ (DistilGPT2)│
          └─────────────┘
```

## 📋 Prerequisites

- Python 3.9+
- pip
- Virtual environment support
- 4GB RAM minimum (for LLM model)
- Linux/macOS (tested on Ubuntu)

## 🚀 Quick Start

### 1. Setup

```bash
# Clone the repository
git clone <repository-url>
cd distributed_ticket_booking

# Run complete setup
chmod +x complete_setup.sh
./complete_setup.sh
```

This will:
- Create directory structure
- Set up Python virtual environment
- Install all dependencies
- Generate gRPC protobuf files
- Fix import paths

### 2. Start the System

```bash
# Start all servers (LLM + 3 Raft nodes)
chmod +x start_system.sh
./start_system.sh
```

**Wait 10-15 seconds** for:
- LLM model to load
- Raft leader election to complete
- System initialization

### 3. Start a Client

In a **new terminal**:

```bash
source venv/bin/activate
./start_client.sh
```

## 📝 Usage Guide

### Login Credentials

Default users:
- `user1` / `password1`
- `user2` / `password2`
- `admin` / `admin123`

### Client Menu Options

1. **🎬 View Movies** - See available movies with pricing and seats
2. **🎫 Book Tickets** - Book seats for a movie
3. **📋 View My Bookings** - See your booking history
4. **❌ Cancel Booking** - Cancel a booking (refund processed)
5. **🤖 Ask AI Assistant** - Get help from the LLM chatbot
6. **🚪 Logout** - End your session

### Booking Flow

```bash
# 1. Login
Username: user1
Password: password1

# 2. View Movies
> Select option 1

# 3. Book Tickets
> Select option 2
> Enter Movie ID: movie1
> Enter seat numbers: 50,51,52

# 4. Process Payment
> Process payment now? y
> Payment method: card
```

## 🔧 System Components

### Application Servers (Ports: 50051, 50052, 50053)
- Handle client requests
- Implement Raft consensus
- Manage ticket booking state
- Communicate with LLM server

### Raft Nodes (Ports: 50061, 50062, 50063)
- Leader election
- Log replication
- Failure detection
- State machine consistency

### LLM Server (Port: 50060)
- Customer support chatbot
- FAQ responses
- Context-aware assistance

## 🧪 Testing

### Run All Tests

```bash
# Concurrent booking test (prevent overbooking)
python3 test_concurrent_bookings.py

# Raft consensus test
python3 test_raft_consensus.py

# Quick functionality test
python3 quick_test.py
```

### Health Check

```bash
# Check server status
./diagnose.sh

# Check which node is leader
python3 check_leader.py

# Monitor logs
tail -f logs/app_server_1.log
```

### Test Scenarios

**Test 1: Concurrent Booking Prevention**
```bash
# Multiple clients try to book same seats simultaneously
# Expected: Only 1 succeeds (no overbooking)
python3 test_concurrent_bookings.py
```

**Test 2: Leader Failure & Re-election**
```bash
# 1. Start system
./start_system.sh

# 2. Check leader
grep "LEADER" logs/app_server_*.log

# 3. Kill leader process
pkill -f "application_server.py.*node1"

# 4. Verify new leader elected (within 10 seconds)
grep "LEADER" logs/app_server_*.log
```

## 📊 Monitoring

### View Logs

```bash
# All logs
./check_all_logs.sh

# Specific server
tail -f logs/app_server_1.log
tail -f logs/llm_server.log

# Monitor Raft activity
grep -h "LEADER\|FOLLOWER\|election" logs/app_server_*.log
```

### Check System Status

```bash
# Process status
ps aux | grep -E "application_server|llm_server"

# Port status
netstat -tuln | grep -E "5005[123]|5006[0123]"

# Health check
python3 scripts/health_check.py
```

## 🛠️ Configuration

Edit `.env` file for configuration:

```bash
# Server Ports
APP_SERVER_1_PORT=50051
APP_SERVER_2_PORT=50052
APP_SERVER_3_PORT=50053
LLM_SERVER_PORT=50060

# Raft Ports
RAFT_PORT_1=50061
RAFT_PORT_2=50062
RAFT_PORT_3=50063

# Raft Timing (seconds)
ELECTION_TIMEOUT_MIN=5.0
ELECTION_TIMEOUT_MAX=10.0
HEARTBEAT_INTERVAL=2.0

# Authentication
JWT_SECRET_KEY=dcdf397aeeef9d64d95b97ecb0691aaf
TOKEN_EXPIRY_HOURS=24

# LLM Settings
LLM_MODEL=distilgpt2
LLM_MAX_LENGTH=200
LLM_TEMPERATURE=0.7
```

## 🐛 Troubleshooting

### System Won't Start

```bash
# Check if ports are in use
netstat -tuln | grep -E "5005[123]|5006"

# Kill existing processes
pkill -f "application_server.py"
pkill -f "llm_server.py"

# Clean logs and restart
rm -f logs/*.log
./start_system.sh
```

### Raft Not Electing Leader

```bash
# Check Raft connectivity
python3 test_raft_ports.py

# Verify all nodes started
ps aux | grep application_server

# Check logs for errors
grep -i "error\|exception" logs/app_server_*.log
```

### Client Connection Failed

```bash
# Check if servers are running
./diagnose.sh

# Verify leader exists
python3 check_leader.py

# Try connecting to specific server
# Edit client.py to use: ['localhost:50051']
```

### LLM Not Responding

```bash
# Check LLM server status
tail -f logs/llm_server.log

# Verify model loaded
grep "Model loaded" logs/llm_server.log

# Restart LLM server only
pkill -f llm_server.py
cd src/servers
python3 llm_server.py --port 50060 > ../../logs/llm_server.log 2>&1 &
```

## 📁 Project Structure

```
distributed_ticket_booking/
├── protos/                     # Protocol buffer definitions
│   ├── ticket_booking.proto    # Main service API
│   ├── raft.proto              # Raft consensus protocol
│   └── llm_service.proto       # LLM service API
├── src/
│   ├── client/                 # Client implementation
│   │   ├── client.py           # Interactive CLI client
│   │   └── *_pb2*.py           # Generated protobuf files
│   ├── servers/                # Server implementations
│   │   ├── application_server.py  # Main app server with Raft
│   │   ├── llm_server.py       # LLM inference server
│   │   └── *_pb2*.py           # Generated protobuf files
│   ├── raft/                   # Raft consensus implementation
│   │   ├── raft_node.py        # Raft algorithm core
│   │   ├── state_machine.py   # Application state machine
│   │   └── *_pb2*.py           # Generated protobuf files
│   └── utils/                  # Utility modules
│       └── auth.py             # JWT authentication
├── logs/                       # Server logs
├── .env                        # Configuration file
├── requirements.txt            # Python dependencies
├── start_system.sh             # Start all servers
├── start_client.sh             # Start client
├── complete_setup.sh           # Complete setup script
└── README.md                   # This file
```

## 🔍 Key Features Demonstrated

### 1. Raft Consensus
- ✅ Leader election
- ✅ Log replication
- ✅ Failure detection and recovery
- ✅ Strong consistency guarantees

### 2. gRPC Communication
- ✅ Client-Server RPC
- ✅ Server-Server internal RPC
- ✅ Protobuf message serialization
- ✅ Efficient binary protocol

### 3. LLM Integration
- ✅ Domain-specific responses
- ✅ Rule-based FAQ system
- ✅ Context-aware assistance
- ✅ CPU-optimized inference

### 4. Distributed Features
- ✅ Concurrency control
- ✅ Overbooking prevention
- ✅ Automatic failover
- ✅ State replication

## 📚 Assignment Requirements Checklist

- ✅ gRPC communication for all inter-service messaging
- ✅ Raft consensus for distributed consistency
- ✅ Leader election mechanism
- ✅ Log replication across nodes
- ✅ Failure detection and recovery
- ✅ Real-time seat reservation with concurrency control
- ✅ Overbooking prevention
- ✅ Payment processing (mock)
- ✅ Booking state replication using Raft
- ✅ Fault tolerance on leader/follower failure
- ✅ LLM customer support chatbot
- ✅ 4-5 node system (1 LLM + 3 App servers)
- ✅ Python implementation
- ✅ Proper authentication (JWT tokens)

## 🎥 Demo Scenarios

### Scenario 1: Normal Operation
1. Start system
2. Login as user1
3. View available movies
4. Book tickets for movie1, seats [50,51,52]
5. View booking confirmation
6. Ask LLM: "How do I cancel my booking?"

### Scenario 2: Concurrent Booking
1. Start 5 clients simultaneously
2. All try to book same seats [1,2,3]
3. Only 1 succeeds (others get "seats unavailable")
4. Demonstrates race condition prevention

### Scenario 3: Leader Failure
1. System running with node1 as leader
2. Kill node1 process
3. Within 10 seconds, node2 or node3 becomes new leader
4. System continues accepting requests
5. Demonstrates fault tolerance

## 📖 References

- [Raft Consensus Paper](https://raft.github.io/raft.pdf) - "In Search of an Understandable Consensus Algorithm"
- [gRPC Documentation](https://grpc.io/docs/)
- [Protocol Buffers](https://developers.google.com/protocol-buffers)

## 👥 Team Information

- Team Size: 3 members (as per assignment requirements)
- Project: Distributed Movie Ticket Booking System (Option A)
- Course: Advanced Operating Systems (CS G623)
- Semester: First Semester 2025-26

## 📧 Support

For issues or questions:
1. Check logs: `tail -f logs/*.log`
2. Run diagnostics: `./diagnose.sh`
3. Check health: `python3 scripts/health_check.py`
4. Review troubleshooting section above

## ⚠️ Important Notes

1. **First Run**: Initial LLM model download takes 1-2 minutes
2. **Ports**: Ensure ports 50051-50053 and 50060-50063 are free
3. **Memory**: LLM requires ~2GB RAM
4. **Timing**: Allow 10-15 seconds for system initialization
5. **Leader Election**: First election takes 5-10 seconds

## 🎓 Learning Outcomes

This project demonstrates:
- Distributed consensus algorithms (Raft)
- RPC communication (gRPC)
- Fault-tolerant system design
- Concurrent programming
- State machine replication
- LLM integration in distributed systems

---

**Status**: ✅ Fully Functional | **Last Updated**: November 2025 | **Version**: 1.0.0