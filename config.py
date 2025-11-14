import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Application configuration"""
    
    # Server Ports
    LLM_SERVER_PORT = int(os.getenv('LLM_SERVER_PORT', 50060))
    APP_SERVER_1_PORT = int(os.getenv('APP_SERVER_1_PORT', 50051))
    APP_SERVER_2_PORT = int(os.getenv('APP_SERVER_2_PORT', 50052))
    APP_SERVER_3_PORT = int(os.getenv('APP_SERVER_3_PORT', 50053))
    
    # Raft Ports
    RAFT_PORT_1 = int(os.getenv('RAFT_PORT_1', 50061))
    RAFT_PORT_2 = int(os.getenv('RAFT_PORT_2', 50062))
    RAFT_PORT_3 = int(os.getenv('RAFT_PORT_3', 50063))
    
    # Raft Configuration
    ELECTION_TIMEOUT_MIN = float(os.getenv('ELECTION_TIMEOUT_MIN', 5.0))
    ELECTION_TIMEOUT_MAX = float(os.getenv('ELECTION_TIMEOUT_MAX', 10.0))
    HEARTBEAT_INTERVAL = float(os.getenv('HEARTBEAT_INTERVAL', 2.0))
    
    # Authentication
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'your-secret-key-change-in-production')
    TOKEN_EXPIRY_HOURS = int(os.getenv('TOKEN_EXPIRY_HOURS', 24))
    
    # LLM Configuration
    LLM_MODEL = os.getenv('LLM_MODEL', 'distilgpt2')
    LLM_MAX_LENGTH = int(os.getenv('LLM_MAX_LENGTH', 200))
    LLM_TEMPERATURE = float(os.getenv('LLM_TEMPERATURE', 0.7))
    
    @classmethod
    def get_peer_config(cls):
        """Get peer configuration for Raft"""
        return {
            'node1': f'localhost:{cls.RAFT_PORT_1}',
            'node2': f'localhost:{cls.RAFT_PORT_2}',
            'node3': f'localhost:{cls.RAFT_PORT_3}'
        }
