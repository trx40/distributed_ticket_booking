#!/usr/bin/env python3
"""Test ports at TCP level"""

import socket
import time

def test_tcp_connection(host, port):
    """Test if we can make a TCP connection"""
    print(f"\nTesting TCP connection to {host}:{port}...")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex((host, port))
        sock.close()
        
        if result == 0:
            print(f"  ✓ TCP connection successful")
            return True
        else:
            print(f"  ✗ TCP connection failed: error code {result}")
            return False
    except Exception as e:
        print(f"  ✗ Exception: {e}")
        return False

def test_grpc_channel(address):
    """Test gRPC channel without making RPC"""
    import grpc
    print(f"\nTesting gRPC channel to {address}...")
    try:
        channel = grpc.insecure_channel(address, options=[
            ('grpc.enable_http_proxy', 0),
        ])
        # Just try to connect, don't make RPC
        future = grpc.channel_ready_future(channel)
        future.result(timeout=3)
        print(f"  ✓ gRPC channel ready")
        channel.close()
        return True
    except Exception as e:
        print(f"  ✗ gRPC channel failed: {e}")
        return False

def main():
    ports = [
        ('node1', 'localhost', 50061),
        ('node2', 'localhost', 50062),
        ('node3', 'localhost', 50063),
    ]
    
    print("="*60)
    print("Testing Port Connectivity (No gRPC RPC)")
    print("="*60)
    
    for name, host, port in ports:
        print(f"\n{'='*60}")
        print(f"{name} - {host}:{port}")
        print('='*60)
        
        # Test TCP
        tcp_ok = test_tcp_connection(host, port)
        
        # Test gRPC channel
        if tcp_ok:
            grpc_ok = test_grpc_channel(f'{host}:{port}')
        
        time.sleep(0.5)
    
    print("\n" + "="*60)
    print("If TCP works but gRPC channel fails, it's a gRPC issue")
    print("If TCP fails, the port isn't listening properly")
    print("="*60)

if __name__ == '__main__':
    main()
