import jwt
import time
from datetime import datetime, timedelta

SECRET_KEY = "your-secret-key-change-in-production"

class AuthManager:
    def __init__(self):
        self.users = {
            "user1": "password1",
            "user2": "password2",
            "admin": "admin123"
        }
        self.active_tokens = set()
    
    def authenticate(self, username, password):
        if username in self.users and self.users[username] == password:
            token = jwt.encode({
                'username': username,
                'exp': datetime.utcnow() + timedelta(hours=24)
            }, SECRET_KEY, algorithm='HS256')
            self.active_tokens.add(token)
            return True, token
        return False, None
    
    def validate_token(self, token):
        if token not in self.active_tokens:
            return False, None
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
            return True, payload['username']
        except jwt.ExpiredSignatureError:
            self.active_tokens.discard(token)
            return False, None
        except jwt.InvalidTokenError:
            return False, None
    
    def logout(self, token):
        self.active_tokens.discard(token)
        return True
