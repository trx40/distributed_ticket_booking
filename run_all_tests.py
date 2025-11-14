import sys

def main():
    print("="*80)
    print(" DISTRIBUTED TICKET BOOKING SYSTEM - TEST SUITE".center(80))
    print("="*80)
    
    print("\nIMPORTANT: Make sure the system is running (./start_system.sh)")
    input("Press Enter when ready to start tests...")
    
    # Test 1: Concurrent Bookings
    print("\n\n" + "="*80)
    print(" RUNNING TEST SUITE 1: CONCURRENT BOOKINGS ".center(80))
    print("="*80)
    
    test = ConcurrentBookingTest()
    test.test_concurrent_same_seats(num_threads=5)
    time.sleep(2)
    test.test_concurrent_different_seats(num_threads=5)
    
    print("\n\n" + "="*80)
    print(" TEST SUITE 1 COMPLETED ".center(80))
    print("="*80)
    
    input("\nPress Enter to continue to Raft tests...")
    
    # Test 2: Raft Consensus
    print("\n\n" + "="*80)
    print(" RUNNING TEST SUITE 2: RAFT CONSENSUS ".center(80))
    print("="*80)
    
    print("\nNote: Raft tests require stopping and starting servers")
    print("This will interrupt the current system")
    proceed = input("Continue? (y/n): ")
    
    if proceed.lower() == 'y':
        raft_test = RaftConsensusTest()
        raft_test.test_leader_election()
    
    print("\n\n" + "="*80)
    print(" ALL TESTS COMPLETED ".center(80))
    print("="*80)


if __name__ == '__main__':
    from test_concurrent_bookings import ConcurrentBookingTest
    from test_raft_consensus import RaftConsensusTest
    import time
    
    main()
