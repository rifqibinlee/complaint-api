from db import get_db
from datetime import datetime

# ── Users ─────────────────────────────────────────────────────────────

def create_user(ic, full_name, phone, address, hashed_password):
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                '''INSERT INTO users (ic, full_name, phone, address, password)
                   VALUES (%s, %s, %s, %s, %s)
                   RETURNING *''',
                (ic, full_name, phone, address, hashed_password)
            )
            user = cur.fetchone()
        db.commit()
        return dict(user)
    finally:
        db.close()

def get_user_by_ic(ic):
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute('SELECT * FROM users WHERE ic = %s', (ic,))
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        db.close()

def get_user_by_id(user_id):
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute('SELECT * FROM users WHERE id = %s', (user_id,))
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        db.close()

# ── Staff ─────────────────────────────────────────────────────────────

def get_staff_by_email(email):
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                '''SELECT s.*, d.name as department_name
                   FROM staff s
                   JOIN departments d ON s.department_id = d.id
                   WHERE s.email = %s''',
                (email,)
            )
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        db.close()

def get_staff_by_id(staff_id):
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                '''SELECT s.*, d.name as department_name
                   FROM staff s
                   JOIN departments d ON s.department_id = d.id
                   WHERE s.id = %s''',
                (staff_id,)
            )
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        db.close()

# ── Complaints ────────────────────────────────────────────────────────

def create_complaint(user_id, title, description, category_id,
                     subcategory, lat, lng, image_path):
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                '''INSERT INTO complaints
                   (user_id, title, description, category_id,
                    subcategory, lat, lng, image_path)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                   RETURNING *''',
                (user_id, title, description, category_id,
                 subcategory, lat, lng, image_path)
            )
            complaint = dict(cur.fetchone())
            # Log initial status to history
            cur.execute(
                '''INSERT INTO complaint_history
                   (complaint_id, changed_by_user, field_changed, new_value)
                   VALUES (%s, %s, %s, %s)''',
                (complaint['id'], user_id, 'status', 'open')
            )
        db.commit()
        return get_complaint_by_id(complaint['id'])
    finally:
        db.close()

def get_complaint_by_id(complaint_id):
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                '''SELECT c.*, u.full_name as submitted_by
                   FROM complaints c
                   JOIN users u ON c.user_id = u.id
                   WHERE c.id = %s''',
                (complaint_id,)
            )
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        db.close()

def get_all_complaints(status=None, category_id=None, limit=100, offset=0):
    db = get_db()
    try:
        with db.cursor() as cur:
            where  = []
            params = []
            if status:
                where.append('c.status = %s')
                params.append(status)
            if category_id:
                where.append('c.category_id = %s')
                params.append(category_id)
            where_sql = ('WHERE ' + ' AND '.join(where)) if where else ''
            cur.execute(
                f'''SELECT c.*, u.full_name as submitted_by
                    FROM complaints c
                    JOIN users u ON c.user_id = u.id
                    {where_sql}
                    ORDER BY c.submitted_at DESC
                    LIMIT %s OFFSET %s''',
                params + [limit, offset]
            )
            return [dict(r) for r in cur.fetchall()]
    finally:
        db.close()

def get_complaints_by_user(user_id):
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                '''SELECT * FROM complaints
                   WHERE user_id = %s
                   ORDER BY submitted_at DESC''',
                (user_id,)
            )
            return [dict(r) for r in cur.fetchall()]
    finally:
        db.close()

def update_complaint_status(complaint_id, new_status, changed_by_staff_id=None):
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                'SELECT status FROM complaints WHERE id = %s',
                (complaint_id,)
            )
            row = cur.fetchone()
            if not row:
                return None
            old_status = row['status']

            if new_status == 'resolved':
                cur.execute(
                    '''UPDATE complaints
                       SET status = %s, resolved_at = NOW()
                       WHERE id = %s''',
                    (new_status, complaint_id)
                )
            elif new_status == 'closed':
                cur.execute(
                    '''UPDATE complaints
                       SET status = %s, closed_at = NOW()
                       WHERE id = %s''',
                    (new_status, complaint_id)
                )
            else:
                cur.execute(
                    'UPDATE complaints SET status = %s WHERE id = %s',
                    (new_status, complaint_id)
                )

            cur.execute(
                '''INSERT INTO complaint_history
                   (complaint_id, changed_by_staff, field_changed,
                    old_value, new_value)
                   VALUES (%s, %s, %s, %s, %s)''',
                (complaint_id, changed_by_staff_id,
                 'status', old_status, new_status)
            )
        db.commit()
        return get_complaint_by_id(complaint_id)
    finally:
        db.close()

def get_stats():
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute('''
                SELECT
                  COUNT(*)                                         AS total,
                  SUM(CASE WHEN status = 'open'
                      THEN 1 ELSE 0 END)                         AS open,
                  SUM(CASE WHEN status = 'in_progress'
                      THEN 1 ELSE 0 END)                         AS in_progress,
                  SUM(CASE WHEN status = 'resolved'
                      THEN 1 ELSE 0 END)                         AS resolved,
                  SUM(CASE WHEN status = 'closed'
                      THEN 1 ELSE 0 END)                         AS closed,
                  SUM(CASE WHEN DATE(submitted_at) = CURRENT_DATE
                      THEN 1 ELSE 0 END)                         AS today,
                  ROUND(AVG(
                    CASE WHEN resolved_at IS NOT NULL
                    THEN EXTRACT(EPOCH FROM
                         (resolved_at - submitted_at)) / 3600.0
                    END
                  )::NUMERIC, 1)                                  AS avg_resolution_hours
                FROM complaints
            ''')
            stats = dict(cur.fetchone())

            cur.execute('''
                SELECT category_id, COUNT(*) as count
                FROM complaints
                GROUP BY category_id
                ORDER BY count DESC
            ''')
            stats['by_category'] = [dict(r) for r in cur.fetchall()]
            return stats
    finally:
        db.close()
