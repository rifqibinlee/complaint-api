import os
import bcrypt
import uuid
from datetime import datetime, timedelta, timezone
from flask import (Flask, request, jsonify,
                   send_from_directory, render_template, redirect)
from flask_cors import CORS

from config import Config
from db import get_db
from middleware import generate_token, citizen_required, staff_required, any_auth_required
from models import (
    create_user, get_user_by_ic,
    get_staff_by_email, get_staff_by_id, create_staff,
    get_departments,
    create_complaint, get_all_complaints,
    get_complaints_by_user, get_complaint_by_id,
    update_complaint_status, get_stats,
)

app = Flask(__name__)
CORS(app)
app.config['MAX_CONTENT_LENGTH'] = Config.MAX_IMAGE_SIZE
os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)


def allowed_file(filename):
    return ('.' in filename and
            filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_EXTENSIONS)


def serialize(obj):
    result = dict(obj)
    for k, v in result.items():
        if hasattr(v, 'isoformat'): result[k] = v.isoformat()
        elif hasattr(v, '__float__'): result[k] = float(v)
    if result.get('image_path'):
        result['image_url'] = f"{request.host_url}uploads/{result['image_path']}"
    return result


# ── Health ────────────────────────────────────────────────────────────

@app.route('/api/health')
def health():
    return jsonify({'status':'ok','timestamp':datetime.now(timezone.utc).isoformat()})


# ── Departments ───────────────────────────────────────────────────────

@app.route('/api/departments')
def departments():
    return jsonify(get_departments())


# ── Citizen Auth ──────────────────────────────────────────────────────

@app.route('/api/auth/register', methods=['POST'])
def register():
    data = request.get_json()
    for f in ['ic','full_name','phone','address','password']:
        if not data.get(f,'').strip():
            return jsonify({'error':f'{f} is required'}), 400
    if len(data['ic'].strip()) != 12:
        return jsonify({'error':'IC must be 12 digits'}), 400
    if len(data['password']) < 8:
        return jsonify({'error':'Password must be at least 8 characters'}), 400
    if get_user_by_ic(data['ic'].strip()):
        return jsonify({'error':'An account with this IC already exists'}), 409

    hashed = bcrypt.hashpw(data['password'].encode(), bcrypt.gensalt()).decode()
    user   = create_user(data['ic'].strip(), data['full_name'].strip(),
                         data['phone'].strip(), data['address'].strip(), hashed)
    token  = generate_token({
        'user_id': user['id'], 'ic': user['ic'],
        'exp': datetime.now(timezone.utc) + timedelta(days=30),
    })
    return jsonify({'token':token,'user':{
        'id':user['id'],'ic':user['ic'],
        'full_name':user['full_name'],'phone':user['phone'],
    }}), 201


@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data.get('ic') or not data.get('password'):
        return jsonify({'error':'IC and password are required'}), 400
    user = get_user_by_ic(data['ic'].strip())
    if not user or not bcrypt.checkpw(data['password'].encode(), user['password'].encode()):
        return jsonify({'error':'Invalid IC or password'}), 401
    token = generate_token({
        'user_id': user['id'], 'ic': user['ic'],
        'exp': datetime.now(timezone.utc) + timedelta(days=30),
    })
    return jsonify({'token':token,'user':{
        'id':user['id'],'ic':user['ic'],
        'full_name':user['full_name'],'phone':user['phone'],
    }})


# ── Staff Auth ────────────────────────────────────────────────────────

@app.route('/api/staff/login', methods=['POST'])
def staff_login():
    data  = request.get_json()
    email = data.get('email','').strip()
    pwd   = data.get('password','')
    if not email or not pwd:
        return jsonify({'error':'Email and password are required'}), 400
    staff = get_staff_by_email(email)
    if not staff or not bcrypt.checkpw(pwd.encode(), staff['password'].encode()):
        return jsonify({'error':'Invalid email or password'}), 401
    token = generate_token({
        'staff_id': staff['id'], 'email': staff['email'], 'role': staff['role'],
        'exp': datetime.now(timezone.utc) + timedelta(days=7),
    })
    return jsonify({'token':token,'staff':{
        'id':staff['id'],'full_name':staff['full_name'],
        'email':staff['email'],'role':staff['role'],
        'department':staff['department_name'],
    }})


@app.route('/api/staff/register', methods=['POST'])
def staff_register():
    data        = request.get_json()
    full_name   = data.get('full_name','').strip()
    email       = data.get('email','').strip()
    phone       = data.get('phone','').strip()
    password    = data.get('password','')
    invite_code = data.get('invite_code','').strip()
    dept_id     = data.get('department_id')

    if invite_code != Config.INVITE_CODE:
        return jsonify({'error':'Invalid invite code'}), 403
    if not all([full_name, email, password, dept_id]):
        return jsonify({'error':'All fields are required'}), 400
    if len(password) < 8:
        return jsonify({'error':'Password must be at least 8 characters'}), 400
    if get_staff_by_email(email):
        return jsonify({'error':'An account with this email already exists'}), 409

    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    staff  = create_staff(int(dept_id), full_name, email, phone, hashed)
    token  = generate_token({
        'staff_id': staff['id'], 'email': staff['email'], 'role': staff['role'],
        'exp': datetime.now(timezone.utc) + timedelta(days=7),
    })
    return jsonify({'token':token,'staff':{
        'id':staff['id'],'full_name':staff['full_name'],
        'email':staff['email'],'role':staff['role'],
        'department':staff['department_name'],
    }}), 201


# ── Complaints ────────────────────────────────────────────────────────

@app.route('/api/complaints', methods=['GET'])
@any_auth_required
def get_complaints():
    if request.current_user:
        return jsonify([serialize(c) for c in
                        get_complaints_by_user(request.current_user['id'])])
    return jsonify([serialize(c) for c in
                    get_all_complaints(
                        request.args.get('status'),
                        request.args.get('category_id'),
                        int(request.args.get('limit', 500)),
                        int(request.args.get('offset', 0)),
                    )])


@app.route('/api/complaints', methods=['POST'])
@citizen_required
def submit_complaint():
    title       = request.form.get('title','').strip()
    description = request.form.get('description','').strip()
    category_id = request.form.get('category_id','').strip()
    subcategory = request.form.get('subcategory','').strip()
    lat         = request.form.get('lat')
    lng         = request.form.get('lng')

    if not all([title, description, category_id, subcategory]):
        return jsonify({'error':'title, description, category_id, subcategory required'}), 400

    image_path = None
    if 'image' in request.files:
        f = request.files['image']
        if f and f.filename and allowed_file(f.filename):
            ext  = f.filename.rsplit('.', 1)[1].lower()
            name = f"{uuid.uuid4().hex}.{ext}"
            f.save(os.path.join(Config.UPLOAD_FOLDER, name))
            image_path = name

    complaint = create_complaint(
        request.current_user['id'], title, description,
        category_id, subcategory,
        float(lat) if lat else None,
        float(lng) if lng else None,
        image_path,
    )
    return jsonify(serialize(complaint)), 201


@app.route('/api/complaints/<int:cid>', methods=['GET'])
@any_auth_required
def get_complaint(cid):
    c = get_complaint_by_id(cid)
    if not c: return jsonify({'error':'Not found'}), 404
    return jsonify(serialize(c))


@app.route('/api/complaints/<int:cid>/status', methods=['PATCH'])
@staff_required
def update_status(cid):
    new_status = request.get_json().get('status')
    if new_status not in ['open','in_progress','resolved','closed']:
        return jsonify({'error':'Invalid status'}), 400
    c = update_complaint_status(cid, new_status, request.current_staff['id'])
    if not c: return jsonify({'error':'Not found'}), 404
    return jsonify(serialize(c))


# ── Stats ─────────────────────────────────────────────────────────────

@app.route('/api/stats')
@staff_required
def stats():
    return jsonify(get_stats())


# ── Uploads ───────────────────────────────────────────────────────────

@app.route('/uploads/<path:filename>')
def serve_upload(filename):
    return send_from_directory(Config.UPLOAD_FOLDER, filename)


# ── Dashboard pages ───────────────────────────────────────────────────

@app.route('/')
def root():
    return redirect('/dashboard/login')

@app.route('/dashboard/login')
def dashboard_login():
    return render_template('login.html')

@app.route('/dashboard/register')
def dashboard_register():
    return render_template('register.html')

@app.route('/dashboard')
def dashboard_index():
    return render_template('dashboard/index.html')

@app.route('/dashboard/complaints')
def dashboard_complaints():
    return render_template('dashboard/complaints.html')

@app.route('/dashboard/map')
def dashboard_map():
    return render_template('dashboard/map.html')


if __name__ == '__main__':
    app.run(debug=True)
