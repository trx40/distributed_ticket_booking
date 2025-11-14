import grpc
import sys
sys.path.append('../src/client')

import ticket_booking_pb2
import ticket_booking_pb2_grpc


def check_server(address, name):
    """Check if a server is responding"""
    try:
        channel = grpc.insecure_channel(address, options=[
            ('grpc.keepalive_time_ms', 10000),
            ('grpc.keepalive_timeout_ms', 5000),
        ])
        
        # Try to establish connection
        grpc.channel_ready_future(channel).result(timeout=5)
        channel.close()
        
        print(f"✓ {name} ({address}) - HEALTHY")
        return True
    except Exception as e:
        print(f"✗ {name} ({address}) - UNHEALTHY: {e}")
        return False


def main():
    """Run health checks on all services"""
    print("="*60)
    print(" System Health Check ".center(60))
    print("="*60 + "\n")
    
    servers = [
        ('localhost:50060', 'LLM Server'),
        ('localhost:50051', 'App Server 1'),
        ('localhost:50052', 'App Server 2'),
        ('localhost:50053', 'App Server 3'),
    ]
    
    results = []
    for address, name in servers:
        result = check_server(address, name)
        results.append(result)
    
    print("\n" + "="*60)
    healthy = sum(results)
    total = len(results)
    
    if healthy == total:
        print(f"✓ All services healthy ({healthy}/{total})".center(60))
    else:
        print(f"⚠ Some services unhealthy ({healthy}/{total})".center(60))
    
    print("="*60)
    
    return healthy == total


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
