import jwt
import functools
from flask import request, jsonify
from config import Config
from models import get_user_by_id, get_staff_by_id

def generate_token(payload):
    return jwt.encode(payload, Config.SECRET_KEY, algorithm='HS256')

def decode_token(token):
    return jwt.decode(token, Config.SECRET_KEY, algorithms=['HS256'])

def citizen_required(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        if not token:
            return jsonify({'error': 'No token provided'}), 401
        try:
            payload = decode_token(token)
            user    = get_user_by_id(payload['user_id'])
            if not user:
                return jsonify({'error': 'User not found'}), 401
            request.current_user = user
        except Exception:
            return jsonify({'error': 'Invalid or expired token'}), 401
        return f(*args, **kwargs)
    return decorated

def staff_required(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        if not token:
            return jsonify({'error': 'No token provided'}), 401
        try:
            payload = decode_token(token)
            staff   = get_staff_by_id(payload['staff_id'])
            if not staff:
                return jsonify({'error': 'Staff not found'}), 401
            request.current_staff = staff
        except Exception:
            return jsonify({'error': 'Invalid or expired token'}), 401
        return f(*args, **kwargs)
    return decorated

def any_auth_required(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        if not token:
            return jsonify({'error': 'No token provided'}), 401
        try:
            payload = decode_token(token)
            if 'user_id' in payload:
                request.current_user  = get_user_by_id(payload['user_id'])
                request.current_staff = None
            elif 'staff_id' in payload:
                request.current_staff = get_staff_by_id(payload['staff_id'])
                request.current_user  = None
            else:
                return jsonify({'error': 'Invalid token'}), 401
        except Exception:
            return jsonify({'error': 'Invalid or expired token'}), 401
        return f(*args, **kwargs)
    return decorated