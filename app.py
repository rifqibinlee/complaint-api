import os
import bcrypt
import uuid
from datetime import datetime, timedelta, timezone
from flask import Flask, request, jsonify, send_from_directory, render_template, redirectfrom flask_cors import CORS

from config import Config
from middleware import generate_token, citizen_required, staff_required, any_auth_required
from models import (
    create_user, get_user_by_ic,
    get_staff_by_email,
    create_complaint, get_all_complaints,
    get_complaints_by_user, get_complaint_by_id,
    update_complaint_status, get_stats,
)

app = Flask(__name__)
CORS(app)
app.config['MAX_CONTENT_LENGTH'] = Config.MAX_IMAGE_SIZE
os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return (
        '.' in filename and
        filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_EXTENSIONS
    )

def serialize(obj):
    """Convert DB row to JSON-safe dict."""
    result = dict(obj)
    for key, val in result.items():
        if hasattr(val, 'isoformat'):
            result[key] = val.isoformat()
        elif hasattr(val, '__float__'):
            result[key] = float(val)
    if result.get('image_path'):
        result['image_url'] = (
            f"{request.host_url}uploads/{result['image_path']}"
        )
    return result

# ── Health ────────────────────────────────────────────────────────────

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'ok',
        'timestamp': datetime.now(timezone.utc).isoformat()
    })

# ── Citizen Auth ──────────────────────────────────────────────────────

@app.route('/api/auth/register', methods=['POST'])
def register():
    data = request.get_json()
    for field in ['ic', 'full_name', 'phone', 'address', 'password']:
        if not data.get(field, '').strip():
            return jsonify({'error': f'{field} is required'}), 400

    if len(data['ic'].strip()) != 12:
        return jsonify({'error': 'IC must be 12 digits'}), 400
    if len(data['password']) < 8:
        return jsonify({'error': 'Password must be at least 8 characters'}), 400
    if get_user_by_ic(data['ic'].strip()):
        return jsonify({'error': 'An account with this IC already exists'}), 409

    hashed = bcrypt.hashpw(
        data['password'].encode(), bcrypt.gensalt()
    ).decode()
    user = create_user(
        ic=data['ic'].strip(),
        full_name=data['full_name'].strip(),
        phone=data['phone'].strip(),
        address=data['address'].strip(),
        hashed_password=hashed,
    )
    token = generate_token({
        'user_id': user['id'],
        'ic':      user['ic'],
        'exp':     datetime.now(timezone.utc) + timedelta(days=30),
    })
    return jsonify({
        'token': token,
        'user': {
            'id':        user['id'],
            'ic':        user['ic'],
            'full_name': user['full_name'],
            'phone':     user['phone'],
        }
    }), 201

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data.get('ic') or not data.get('password'):
        return jsonify({'error': 'IC and password are required'}), 400

    user = get_user_by_ic(data['ic'].strip())
    if not user or not bcrypt.checkpw(
        data['password'].encode(), user['password'].encode()
    ):
        return jsonify({'error': 'Invalid IC or password'}), 401

    token = generate_token({
        'user_id': user['id'],
        'ic':      user['ic'],
        'exp':     datetime.now(timezone.utc) + timedelta(days=30),
    })
    return jsonify({
        'token': token,
        'user': {
            'id':        user['id'],
            'ic':        user['ic'],
            'full_name': user['full_name'],
            'phone':     user['phone'],
        }
    })

# ── Staff Auth ────────────────────────────────────────────────────────

@app.route('/api/staff/login', methods=['POST'])
def staff_login():
    data  = request.get_json()
    email = data.get('email', '').strip()
    pwd   = data.get('password', '')
    if not email or not pwd:
        return jsonify({'error': 'Email and password are required'}), 400

    staff = get_staff_by_email(email)
    if not staff or not bcrypt.checkpw(
        pwd.encode(), staff['password'].encode()
    ):
        return jsonify({'error': 'Invalid email or password'}), 401

    token = generate_token({
        'staff_id': staff['id'],
        'email':    staff['email'],
        'role':     staff['role'],
        'exp':      datetime.now(timezone.utc) + timedelta(days=7),
    })
    return jsonify({
        'token': token,
        'staff': {
            'id':         staff['id'],
            'full_name':  staff['full_name'],
            'email':      staff['email'],
            'role':       staff['role'],
            'department': staff['department_name'],
        }
    })

# ── Complaints ────────────────────────────────────────────────────────

@app.route('/api/complaints', methods=['GET'])
@any_auth_required
def get_complaints():
    if request.current_user:
        complaints = get_complaints_by_user(request.current_user['id'])
    else:
        status      = request.args.get('status')
        category_id = request.args.get('category_id')
        limit       = int(request.args.get('limit', 100))
        offset      = int(request.args.get('offset', 0))
        complaints  = get_all_complaints(status, category_id, limit, offset)
    return jsonify([serialize(c) for c in complaints])

@app.route('/api/complaints', methods=['POST'])
@citizen_required
def submit_complaint():
    title       = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()
    category_id = request.form.get('category_id', '').strip()
    subcategory = request.form.get('subcategory', '').strip()
    lat         = request.form.get('lat')
    lng         = request.form.get('lng')

    if not all([title, description, category_id, subcategory]):
        return jsonify({
            'error': 'title, description, category_id and subcategory are required'
        }), 400

    image_path = None
    if 'image' in request.files:
        file = request.files['image']
        if file and file.filename and allowed_file(file.filename):
            ext      = file.filename.rsplit('.', 1)[1].lower()
            filename = f"{uuid.uuid4().hex}.{ext}"
            file.save(os.path.join(Config.UPLOAD_FOLDER, filename))
            image_path = filename

    complaint = create_complaint(
        user_id     = request.current_user['id'],
        title       = title,
        description = description,
        category_id = category_id,
        subcategory = subcategory,
        lat         = float(lat) if lat else None,
        lng         = float(lng) if lng else None,
        image_path  = image_path,
    )
    return jsonify(serialize(complaint)), 201

@app.route('/api/complaints/<int:complaint_id>', methods=['GET'])
@any_auth_required
def get_complaint(complaint_id):
    complaint = get_complaint_by_id(complaint_id)
    if not complaint:
        return jsonify({'error': 'Complaint not found'}), 404
    return jsonify(serialize(complaint))

@app.route('/api/complaints/<int:complaint_id>/status', methods=['PATCH'])
@staff_required
def update_status(complaint_id):
    data       = request.get_json()
    new_status = data.get('status')
    valid      = ['open', 'in_progress', 'resolved', 'closed']
    if new_status not in valid:
        return jsonify({'error': f'Status must be one of {valid}'}), 400

    complaint = update_complaint_status(
        complaint_id,
        new_status,
        changed_by_staff_id=request.current_staff['id']
    )
    if not complaint:
        return jsonify({'error': 'Complaint not found'}), 404
    return jsonify(serialize(complaint))

# ── Stats ─────────────────────────────────────────────────────────────

@app.route('/api/stats', methods=['GET'])
@staff_required
def stats():
    return jsonify(get_stats())

# ── Serve uploads ─────────────────────────────────────────────────────

@app.route('/uploads/<path:filename>')
def serve_upload(filename):
    return send_from_directory(Config.UPLOAD_FOLDER, filename)

# ── Dashboard routes ──────────────────────────────────────────────────

@app.route('/dashboard/login')
def dashboard_login():
    return render_template('login.html')

@app.route('/dashboard')
def dashboard_index():
    return render_template('dashboard/index.html')

@app.route('/dashboard/complaints')
def dashboard_complaints():
    return render_template('dashboard/complaints.html')

@app.route('/dashboard/map')
def dashboard_map():
    return render_template('dashboard/map.html')

@app.route('/')
def root():
    return redirect('/dashboard/login')
    
if __name__ == '__main__':
    app.run(debug=True)
