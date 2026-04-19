// ── Auth ──────────────────────────────────────────────────
const getToken  = () => localStorage.getItem('staff_token');
const getStaff  = () => JSON.parse(localStorage.getItem('staff_user') || 'null');
const setAuth   = (t,s) => { localStorage.setItem('staff_token',t); localStorage.setItem('staff_user',JSON.stringify(s)); };
const clearAuth = () => { localStorage.removeItem('staff_token'); localStorage.removeItem('staff_user'); };

function requireAuth() {
  if (!getToken()) { window.location.href = '/dashboard/login'; return false; }
  return true;
}

function logout() { clearAuth(); window.location.href = '/dashboard/login'; }

// ── API fetch (never auto-logout, let callers decide) ─────
async function apiFetch(path, opts = {}) {
  const token = getToken();
  try {
    const res = await fetch(path, {
      ...opts,
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(opts.headers || {}),
      },
    });
    const data = await res.json();
    return { ok: res.ok, status: res.status, data };
  } catch (e) {
    console.error('apiFetch error', path, e);
    return { ok: false, status: 0, data: null };
  }
}

// Backwards compat alias used by login/register pages
async function api(path, opts = {}) {
  const r = await apiFetch(path, opts);
  if (r.status === 401) { logout(); return null; }
  return r.data;
}

// ── Toast ─────────────────────────────────────────────────
function showToast(msg, type = 'success') {
  const icon = type === 'success'
    ? '<polyline points="20 6 9 17 4 12"/>'
    : '<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>';
  const t = document.createElement('div');
  t.className = 'toast';
  t.style.background = type === 'success' ? 'var(--primary)' : '#991B1B';
  t.innerHTML = `<svg viewBox="0 0 24 24">${icon}</svg>${msg}`;
  document.body.appendChild(t);
  requestAnimationFrame(() => t.classList.add('show'));
  setTimeout(() => { t.classList.remove('show'); setTimeout(() => t.remove(), 300); }, 3000);
}

// ── Sidebar ───────────────────────────────────────────────
function setActiveNav(page) {
  document.querySelectorAll('.nav-link').forEach(el =>
    el.classList.toggle('active', el.dataset.page === page));
}

function renderStaffInfo() {
  const s = getStaff();
  if (!s) return;
  const av = document.getElementById('staff-av');
  const nm = document.getElementById('staff-name');
  const rl = document.getElementById('staff-role');
  if (av) av.textContent  = s.full_name?.[0]?.toUpperCase() ?? 'S';
  if (nm) nm.textContent  = s.full_name ?? '';
  if (rl) rl.textContent  = (s.role ?? '').replace('_', ' ');
}

// ── Category helpers ──────────────────────────────────────
const CAT_COLORS = {
  infrastructure:'#1D6FA4', waste:'#6B4F8A', water:'#1B7A8A',
  construction:'#8A5B1B', facilities:'#1B6B3A', nuisance:'#8A6B1B',
  health:'#9B1C1C', council:'#0F1F3D', financial:'#5A6A7E',
};
const CAT_LABELS = {
  infrastructure:'Infrastructure', waste:'Waste & Cleanliness',
  water:'Water & Flooding', construction:'Construction',
  facilities:'Public Facilities', nuisance:'Nuisance & Community',
  health:'Public Health', council:'Council Complaint', financial:'Financial & Policy',
};
const catColor = id => CAT_COLORS[id] ?? '#9AA5B4';
const catLabel = id => CAT_LABELS[id] ?? id;

// ── Date helpers ──────────────────────────────────────────
const fmtDate = iso => iso
  ? new Date(iso).toLocaleDateString('en-MY',{day:'numeric',month:'short',year:'numeric'})
  : '—';
const fmtDT = iso => iso
  ? new Date(iso).toLocaleString('en-MY',{day:'numeric',month:'short',year:'numeric',hour:'2-digit',minute:'2-digit'})
  : '—';

// ── Status pill ───────────────────────────────────────────
const STATUS_LABELS = { open:'Open', in_progress:'In Progress', resolved:'Resolved', closed:'Closed' };
const statusPill = s =>
  `<span class="pill ${s}"><span class="pill-dot"></span>${STATUS_LABELS[s] ?? s}</span>`;
