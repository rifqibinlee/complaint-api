const API = '';  // same origin — Flask serves both

// ── Auth ──────────────────────────────────────────────────
function getToken()  { return localStorage.getItem('staff_token'); }
function getStaff()  { return JSON.parse(localStorage.getItem('staff_user') || 'null'); }
function setAuth(token, staff) {
  localStorage.setItem('staff_token', token);
  localStorage.setItem('staff_user', JSON.stringify(staff));
}
function clearAuth() {
  localStorage.removeItem('staff_token');
  localStorage.removeItem('staff_user');
}

function requireAuth() {
  if (!getToken()) { window.location.href = '/dashboard/login'; return false; }
  return true;
}

function logout() {
  clearAuth();
  window.location.href = '/dashboard/login';
}

// ── Fetch wrapper ─────────────────────────────────────────
async function api(path, options = {}) {
  const token = getToken();
  const res   = await fetch(API + path, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers || {}),
    },
  });
  if (res.status === 401) { logout(); return null; }
  return res.json();
}

// ── Toast ─────────────────────────────────────────────────
function showToast(msg, icon = 'check') {
  const icons = {
    check: '<polyline points="20 6 9 17 4 12"/>',
    x:     '<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>',
  };
  const t = document.createElement('div');
  t.className = 'toast';
  t.innerHTML = `<svg viewBox="0 0 24 24">${icons[icon]}</svg>${msg}`;
  document.body.appendChild(t);
  requestAnimationFrame(() => { t.classList.add('show'); });
  setTimeout(() => {
    t.classList.remove('show');
    setTimeout(() => t.remove(), 300);
  }, 3000);
}

// ── Sidebar active state ──────────────────────────────────
function setActiveNav(page) {
  document.querySelectorAll('.nav-item').forEach(el => {
    el.classList.toggle('active', el.dataset.page === page);
  });
}

// ── Staff info in sidebar ─────────────────────────────────
function renderStaffInfo() {
  const staff = getStaff();
  if (!staff) return;
  const name    = document.getElementById('staff-name');
  const role    = document.getElementById('staff-role');
  const dept    = document.getElementById('staff-dept');
  const avatar  = document.getElementById('staff-avatar');
  if (name)   name.textContent   = staff.full_name;
  if (role)   role.textContent   = staff.role?.replace('_', ' ');
  if (dept)   dept.textContent   = staff.department ?? '';
  if (avatar) avatar.textContent = staff.full_name?.[0]?.toUpperCase() ?? 'S';
}

// ── Category colours ──────────────────────────────────────
const CAT_COLORS = {
  infrastructure: '#1D6FA4', waste: '#6B4F8A', water: '#1B7A8A',
  construction: '#8A5B1B',   facilities: '#1B6B3A', nuisance: '#8A6B1B',
  health: '#9B1C1C',         council: '#0F1F3D',    financial: '#5A6A7E',
};

const CAT_LABELS = {
  infrastructure: 'Infrastructure', waste: 'Waste & Cleanliness',
  water: 'Water & Flooding',        construction: 'Construction',
  facilities: 'Public Facilities',  nuisance: 'Nuisance & Community',
  health: 'Public Health',          council: 'Council Complaint',
  financial: 'Financial & Policy',
};

function catColor(id) { return CAT_COLORS[id] ?? '#9AA5B4'; }
function catLabel(id) { return CAT_LABELS[id] ?? id; }

// ── Date formatting ───────────────────────────────────────
function fmtDate(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('en-MY', {
    day: 'numeric', month: 'short', year: 'numeric',
  });
}

function fmtDateTime(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('en-MY', {
    day: 'numeric', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
}

// ── Status pill HTML ──────────────────────────────────────
function statusPill(status) {
  const labels = { open: 'Open', in_progress: 'In Progress', resolved: 'Resolved', closed: 'Closed' };
  return `<span class="pill ${status}"><span class="pill-dot"></span>${labels[status] ?? status}</span>`;
}
