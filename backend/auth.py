import jwt
import datetime
from functools import wraps
from flask import request, jsonify

SECRET_KEY = "splitright-super-secret-key-change-in-production"

def generate_token(user_id):
    """
    Generate a JWT token for the user that lasts 30 days.
    """
    payload = {
        'exp': datetime.datetime.utcnow() + datetime.timedelta(days=30),
        'iat': datetime.datetime.utcnow(),
        'sub': user_id
    }
    return jwt.encode(payload, SECRET_KEY, algorithm='HS256')

def decode_token(token):
    """
    Decode a JWT token and return the user ID.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        return payload['sub']
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None

def token_required(f):
    """
    Decorator to protect API endpoints.
    Requires a valid JWT token in the Authorization header: Bearer <token>.
    Passes the user_id as the first argument to the decorated function.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            if auth_header.startswith('Bearer '):
                token = auth_header.split(" ")[1]
        
        if not token:
            return jsonify({'message': 'Authorization token is missing!'}), 401
        
        user_id = decode_token(token)
        if not user_id:
            return jsonify({'message': 'Token is invalid or expired!'}), 401
            
        return f(user_id, *args, **kwargs)
    
    return decorated
