// customer_dashboard.js — powers customer_dashboard.html

const money = v => `RWF ${Number(v || 0).toLocaleString('en-RW', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;

function customerApiFetch(path, options = {}) {
  const token = getToken();
  const headers = { ...(token ? { Authorization: `Bearer ${token}` } : {}) };
  if (!(options.body instanceof FormData)) headers['Content-Type'] = 'application/json';
  return fetch(`/api/customer/${path}`, {
    ...options,
    headers: { ...headers, ...(options.headers || {}) },
  });
}

// ── Tab switching ─────────────────────────────────────────────────────────────
function switchTab(name) {
  document.querySelectorAll('.admin-tab').forEach(b => b.classList.toggle('active', b.dataset.tab === name));
  document.querySelectorAll('.admin-view').forEach(v => v.classList.toggle('active', v.id === `tab-${name}`));
}

// ── Dashboard overview ────────────────────────────────────────────────────────
async function loadDashboardOverview() {
  const res = await customerApiFetch('dashboard/');
  if (!res.ok) return;
  const d = await res.json();

  document.getElementById('customer-greeting').textContent = `Welcome back, ${esc(d.first_name || d.username || 'there')}!`;
  document.getElementById('customer-points-badge').textContent = `${d.loyalty_points || 0} pts`;

  const grid = document.getElementById('customer-metric-grid');
  if (grid) {
    grid.innerHTML = [
      `<div class="metric"><span>Total Orders</span><strong>${esc(d.total_orders)}</strong></div>`,
      `<div class="metric"><span>Total Spent</span><strong style="color:var(--gold)">${money(d.total_spent)}</strong></div>`,
      `<div class="metric"><span>Loyalty Points</span><strong>${esc(d.loyalty_points)}</strong></div>`,
      `<div class="metric"><span>Wishlist Items</span><strong>${esc(d.wishlist_count)}</strong></div>`,
      `<div class="metric"><span>Pending Orders</span><strong>${esc(d.pending_orders)}</strong></div>`,
    ].join('');
  }

  // Recent orders preview
  const recentEl = document.getElementById('recent-orders-list');
  if (recentEl && Array.isArray(d.recent_orders)) {
    recentEl.innerHTML = d.recent_orders.length
      ? d.recent_orders.map(o => `
          <div style="display:flex;justify-content:space-between;padding:0.5rem 0;border-bottom:1px solid rgba(255,255,255,0.07)">
            <span>#${Number(o.id)} — ${esc(o.status)}</span>
            <span style="color:var(--gold)">${money(o.total_price)}</span>
          </div>`).join('')
      : '<p style="color:var(--muted)">No orders yet.</p>';
  }

  // Spending trend chart
  if (Array.isArray(d.spend_trend)) {
    const canvas = document.getElementById('spend-trend-canvas');
    if (canvas && window.Chart) {
      if (window._spendChart) window._spendChart.destroy();
      window._spendChart = new Chart(canvas.getContext('2d'), {
        type: 'line',
        data: {
          labels: d.spend_trend.map(r => r.label),
          datasets: [{
            label: 'Spent (RWF)',
            data: d.spend_trend.map(r => r.total),
            borderColor: '#c9a84c',
            backgroundColor: 'rgba(201,168,76,0.12)',
            tension: 0.3,
            fill: true,
          }],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { labels: { color: '#aaa' } } },
          scales: {
            x: { ticks: { color: '#aaa' }, grid: { color: '#222' } },
            y: { ticks: { color: '#aaa' }, grid: { color: '#222' }, beginAtZero: true },
          },
        },
      });
    }
  }
}

// ── Orders ────────────────────────────────────────────────────────────────────
async function loadOrders() {
  const statusFilter = document.getElementById('order-status-filter')?.value || '';
  const qs = statusFilter ? `?status=${statusFilter}` : '';
  const res = await customerApiFetch(`orders/${qs}`);
  const el = document.getElementById('orders-list');
  if (!el) return;
  if (!res.ok) { el.innerHTML = '<p style="color:var(--muted)">Failed to load orders.</p>'; return; }
  const orders = await res.json();
  if (!orders.length) { el.innerHTML = '<p style="color:var(--muted)">No orders found.</p>'; return; }
  el.innerHTML = orders.map(o => {
    const statusColor = { pending: '#c9a84c', processing: '#4aa3ff', shipped: '#4caf50', delivered: '#4caf50', cancelled: '#f44' }[o.status] || '#aaa';
    const paymentBanner = o.status === 'processing' && o.shipment?.tracking_number
      ? `<div style="background:rgba(76,175,80,0.12);border:1px solid #4caf50;border-radius:6px;padding:0.5rem 0.75rem;margin-top:0.5rem;font-size:0.9rem">
           ✅ <strong>Payment Confirmed</strong> — Tracking code: <strong style="color:var(--gold)">${esc(o.shipment.tracking_number)}</strong>
           <a href="/track-shipment/?code=${esc(o.shipment.tracking_number)}" class="btn btn-gold" style="padding:0.3rem 0.6rem;font-size:0.8rem;margin-left:0.5rem">Track</a>
         </div>`
      : o.status === 'cancelled'
      ? `<div style="background:rgba(244,67,54,0.1);border:1px solid #f44;border-radius:6px;padding:0.5rem 0.75rem;margin-top:0.5rem;font-size:0.9rem">
           ❌ <strong>Payment Rejected</strong> — This order was cancelled.
         </div>`
      : '';
    return `
    <div class="admin-block" style="margin-bottom:0.75rem">
      <div style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:0.5rem">
        <div>
          <strong>Order #${Number(o.id)}</strong>
          <span class="pill" style="margin-left:0.5rem;color:${statusColor}">${esc(o.status)}</span>
        </div>
        <div style="color:var(--gold);font-weight:700">${money(o.total_price)}</div>
      </div>
      <div style="color:var(--muted);font-size:0.85rem;margin-top:0.3rem">${esc(new Date(o.order_date).toLocaleDateString())}</div>
      ${paymentBanner}
      <div style="margin-top:0.5rem;display:flex;gap:0.5rem;flex-wrap:wrap">
        <button class="btn btn-dark" onclick="openOrderDetail(${Number(o.id)})">View Details</button>
        <button class="btn btn-dark" onclick="downloadOrderInvoice(${Number(o.id)})">Invoice</button>
      </div>
    </div>`;
  }).join('');
}

async function openOrderDetail(orderId) {
  const modal = document.getElementById('order-modal');
  const body = document.getElementById('modal-order-body');
  document.getElementById('modal-order-title').textContent = `Order #${orderId}`;
  body.innerHTML = '<p style="color:var(--muted)">Loading…</p>';
  modal.style.display = 'flex';
  const res = await customerApiFetch(`orders/${orderId}/`);
  if (!res.ok) { body.innerHTML = '<p style="color:var(--muted)">Failed to load.</p>'; return; }
  const o = await res.json();
  body.innerHTML = `
    <div style="display:grid;gap:0.5rem;margin-bottom:1rem">
      <div class="metric"><span>Status</span><strong>${esc(o.status)}</strong></div>
      <div class="metric"><span>Total</span><strong style="color:var(--gold)">${money(o.total_price)}</strong></div>
      <div class="metric"><span>Date</span><strong>${esc(new Date(o.order_date).toLocaleString())}</strong></div>
      ${o.shipment ? `
        <div class="metric"><span>Tracking Code</span><strong style="color:var(--gold)">${esc(o.shipment.tracking_number)}</strong></div>
        <div class="metric"><span>Shipment Status</span><strong>${esc(o.shipment.status)}</strong></div>
      ` : o.status === 'cancelled' ? `
        <div style="color:#f44;padding:0.5rem 0">❌ Payment was rejected — order cancelled.</div>
      ` : `
        <div style="color:#c9a84c;padding:0.5rem 0">🕐 Awaiting payment confirmation from vendor.</div>
      `}
    </div>
    <table class="admin-table">
      <thead><tr><th>Product</th><th>Qty</th><th>Price</th></tr></thead>
      <tbody>${(o.items || []).map(i => `
        <tr>
          <td>${esc(i.product_name || i.product)}</td>
          <td>${esc(i.quantity)}</td>
          <td>${money(i.price)}</td>
        </tr>`).join('')}
      </tbody>
    </table>`;
}

function closeOrderModal(e) {
  if (!e || e.target === e.currentTarget) {
    document.getElementById('order-modal').style.display = 'none';
  }
}

async function downloadOrderInvoice(orderId) {
  const res = await customerApiFetch(`orders/${orderId}/invoice/`);
  if (!res.ok) { showToast('Invoice not available.'); return; }
  const blob = await res.blob();
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `invoice-${orderId}.txt`;
  a.click();
  URL.revokeObjectURL(a.href);
}

// ── Refunds ───────────────────────────────────────────────────────────────────
async function loadCustomerRefunds() {
  const table = document.getElementById('customer-refunds-table');
  if (!table) return;
  table.innerHTML = '<tr><td colspan="6" style="padding:1.5rem;color:var(--muted)">Loading…</td></tr>';

  const token = getToken();
  if (!token) {
    table.innerHTML = '<tr><td colspan="6" style="padding:1.5rem;color:#f44">Not authenticated. Please log in.</td></tr>';
    return;
  }

  const res = await fetch('/api/refunds/list/', {
    headers: { Authorization: `Bearer ${token}` },
  });

  if (res.status === 401 || res.status === 403) {
    table.innerHTML = '<tr><td colspan="6" style="padding:1.5rem;color:#f44">Session expired. Please log in again.</td></tr>';
    return;
  }
  if (!res.ok) {
    table.innerHTML = `<tr><td colspan="6" style="padding:1.5rem;color:var(--muted)">Failed to load refunds (${res.status}).</td></tr>`;
    return;
  }

  const refunds = await res.json();
  if (!Array.isArray(refunds) || !refunds.length) {
    table.innerHTML = '<tr><td colspan="6" style="padding:1.5rem;color:var(--muted)">No refund requests yet.</td></tr>';
    return;
  }

  const statusColor = s => ({ pending: '#c9a84c', approved: '#4caf50', rejected: '#f44', processed: '#4aa3ff' }[s] || '#aaa');
  table.innerHTML = refunds.map(r => `
    <tr>
      <td>#${Number(r.id)}</td>
      <td>#${Number(r.order_id)}</td>
      <td style="max-width:200px">${esc(r.reason)}</td>
      <td><span style="color:${statusColor(r.status)};font-weight:700">${esc(r.status)}</span></td>
      <td>${esc(r.notes || r.admin_note || '—')}</td>
      <td>${esc(r.created_at ? new Date(r.created_at).toLocaleDateString() : '')}</td>
    </tr>`).join('');
}

// Populate eligible orders in the refund request form
async function showRefundForm() {
  document.getElementById('refund-form-wrap').style.display = '';
  const sel = document.getElementById('refund-order-id');
  if (sel.options.length > 1) return; // already populated
  const res = await customerApiFetch('orders/?status=delivered');
  if (!res.ok) return;
  const orders = await res.json();
  orders.forEach(o => {
    const opt = document.createElement('option');
    opt.value = o.id;
    opt.textContent = `Order #${o.id} — ${money(o.total_price)}`;
    sel.appendChild(opt);
  });
}

function hideRefundForm() {
  document.getElementById('refund-form-wrap').style.display = 'none';
}

async function submitRefundRequest(e) {
  e.preventDefault();
  const order_id = document.getElementById('refund-order-id').value;
  const reason   = document.getElementById('refund-reason').value.trim();
  const notes    = document.getElementById('refund-notes').value.trim();
  if (!order_id || !reason) { showToast('Please select an order and provide a reason.'); return; }

  const token = getToken();
  const res = await fetch('/api/refunds/request/', {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ order_id, reason, notes }),
  });

  if (res.ok) {
    showToast('Refund request submitted.');
    hideRefundForm();
    document.getElementById('refund-request-form').reset();
    await loadCustomerRefunds();
  } else {
    const data = await res.json().catch(() => ({}));
    showToast(data.detail || 'Failed to submit refund request.');
  }
}

// ── Wishlist ──────────────────────────────────────────────────────────────────
async function loadWishlist() {
  const grid = document.getElementById('wishlist-grid');
  if (!grid) return;
  const res = await customerApiFetch('wishlist/');
  if (!res.ok) { grid.innerHTML = '<p style="color:var(--muted)">Failed to load wishlist.</p>'; return; }
  const items = await res.json();
  const countEl = document.getElementById('wishlist-count-label');
  if (countEl) countEl.textContent = `${items.length} item${items.length !== 1 ? 's' : ''}`;
  const badge = document.getElementById('wishlist-badge');
  if (badge) { badge.textContent = items.length; badge.style.display = items.length ? '' : 'none'; }
  grid.innerHTML = items.length
    ? items.map(i => `
        <div class="admin-block" style="text-align:center">
          ${i.image ? `<img src="${esc(i.image)}" alt="${esc(i.name)}" style="width:100%;max-height:140px;object-fit:cover;border-radius:6px;margin-bottom:0.5rem" />` : ''}
          <strong>${esc(i.name)}</strong>
          <div style="color:var(--gold);margin:0.3rem 0">${money(i.price)}</div>
          <div style="display:flex;gap:0.4rem;justify-content:center;flex-wrap:wrap">
            <a class="btn btn-gold" href="/products/${esc(i.slug)}/" style="padding:0.4rem 0.6rem">View</a>
            <button class="btn btn-dark" style="padding:0.4rem 0.6rem" onclick="removeWishlistItem(${Number(i.id)})">Remove</button>
          </div>
        </div>`).join('')
    : '<p style="color:var(--muted)">Your wishlist is empty.</p>';
}

async function removeWishlistItem(itemId) {
  const res = await customerApiFetch(`wishlist/${itemId}/`, { method: 'DELETE' });
  if (res.ok) loadWishlist();
}

// ── Wallet / Loyalty ──────────────────────────────────────────────────────────
async function loadWallet() {
  const res = await customerApiFetch('wallet/');
  if (!res.ok) return;
  const d = await res.json();
  document.getElementById('wallet-balance').textContent = d.balance ?? '—';
  document.getElementById('wallet-earned').textContent  = d.total_earned ?? '—';
  document.getElementById('wallet-spent').textContent   = d.total_spent ?? '—';

  const tbody = document.getElementById('loyalty-table');
  if (tbody && Array.isArray(d.transactions)) {
    tbody.innerHTML = d.transactions.length
      ? d.transactions.map(t => `
          <tr>
            <td>${esc(t.type)}</td>
            <td style="color:${t.points > 0 ? '#4caf50' : '#f44'}">${t.points > 0 ? '+' : ''}${esc(t.points)}</td>
            <td>${esc(t.balance_after)}</td>
            <td>${esc(t.note || '—')}</td>
            <td>${esc(new Date(t.created_at).toLocaleDateString())}</td>
          </tr>`).join('')
      : '<tr><td colspan="5" style="color:var(--muted)">No transactions yet.</td></tr>';
  }
}

// ── Search History ───────────────────────────────────────────────────────────
function loadSearchHistory() {
  const el = document.getElementById('search-history-list');
  if (!el) return;
  const raw = localStorage.getItem('hfs_search_history');
  const history = raw ? JSON.parse(raw) : [];
  if (!history.length) {
    el.innerHTML = '<p style="color:var(--muted)">No searches yet.</p>';
    return;
  }
  el.innerHTML = history.map((entry, i) => `
    <div class="admin-block" style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.4rem;padding:0.6rem 1rem">
      <a href="/products/?search=${encodeURIComponent(entry.q)}" style="color:var(--gold);text-decoration:none;font-weight:500">
        🔍 ${esc(entry.q)}
      </a>
      <span style="color:var(--muted);font-size:0.8rem">${esc(new Date(entry.ts).toLocaleString())}</span>
    </div>`).join('');
}

function clearSearchHistory() {
  if (!confirm('Clear all search history?')) return;
  localStorage.removeItem('hfs_search_history');
  loadSearchHistory();
}

// ── Notifications ─────────────────────────────────────────────────────────────
async function loadNotifications() {
  const el = document.getElementById('customer-notifications-list');
  if (!el) return;
  const res = await customerApiFetch('notifications/');
  if (!res.ok) { el.innerHTML = '<p style="color:var(--muted)">Failed to load.</p>'; return; }
  const items = await res.json();
  el.innerHTML = items.length
    ? items.map(n => `
        <div class="admin-block" style="margin-bottom:0.5rem;${n.is_read ? 'opacity:0.6' : ''}">
          <strong>${esc(n.title)}</strong>
          <p style="color:var(--muted);font-size:0.85rem;margin:0.2rem 0">${esc(n.body || '')}</p>
          <small style="color:var(--muted)">${esc(new Date(n.created_at).toLocaleString())}</small>
        </div>`).join('')
    : '<p style="color:var(--muted)">No notifications.</p>';
}

// ── Profile ───────────────────────────────────────────────────────────────────
async function loadProfile() {
  const res = await customerApiFetch('profile/');
  if (!res.ok) return;
  const d = await res.json();
  document.getElementById('prof-username').textContent = d.username || '—';
  document.getElementById('prof-email').textContent    = d.email    || '—';
  document.getElementById('prof-since').textContent    = d.date_joined ? new Date(d.date_joined).toLocaleDateString() : '—';
  document.getElementById('prof-first-name').value     = d.first_name || '';
  document.getElementById('prof-last-name').value      = d.last_name  || '';
  document.getElementById('prof-phone').value          = d.phone      || '';
  const avatar = document.getElementById('prof-avatar-preview');
  if (avatar && d.avatar) { avatar.src = d.avatar; avatar.style.display = ''; }

  // Sidebar
  const sidebarName = document.getElementById('customer-sidebar-name');
  if (sidebarName) sidebarName.textContent = d.first_name || d.username || '';
  const sidebarAvatar = document.getElementById('customer-sidebar-avatar');
  if (sidebarAvatar && d.avatar) { sidebarAvatar.src = d.avatar; sidebarAvatar.style.display = ''; }
}

async function saveProfile(e) {
  e.preventDefault();
  const fd = new FormData();
  fd.append('first_name', document.getElementById('prof-first-name').value);
  fd.append('last_name',  document.getElementById('prof-last-name').value);
  fd.append('phone',      document.getElementById('prof-phone').value);
  const file = document.getElementById('prof-avatar').files[0];
  if (file) fd.append('avatar', file);
  const res = await customerApiFetch('profile/', { method: 'PATCH', body: fd });
  showToast(res.ok ? 'Profile saved.' : 'Save failed.');
  if (res.ok) loadProfile();
}

async function removeCustomerAvatar() {
  const res = await customerApiFetch('profile/avatar/', { method: 'DELETE' });
  if (res.ok) {
    const avatar = document.getElementById('prof-avatar-preview');
    if (avatar) { avatar.src = ''; avatar.style.display = 'none'; }
    showToast('Avatar removed.');
  }
}

async function changePassword(e) {
  e.preventDefault();
  const old_password     = document.getElementById('pw-old').value;
  const new_password     = document.getElementById('pw-new').value;
  const confirm_password = document.getElementById('pw-confirm').value;
  if (new_password !== confirm_password) { showToast('Passwords do not match.'); return; }
  const res = await customerApiFetch('profile/password/', {
    method: 'POST',
    body: JSON.stringify({ old_password, new_password }),
  });
  showToast(res.ok ? 'Password updated.' : 'Password change failed.');
  if (res.ok) e.target.reset();
}

async function confirmDeleteAccount() {
  if (!confirm('Are you sure? This cannot be undone.')) return;
  const res = await customerApiFetch('profile/delete/', { method: 'DELETE' });
  if (res.ok) { showToast('Account deleted.'); window.location.href = '/'; }
  else showToast('Delete failed.');
}

// ── Addresses ─────────────────────────────────────────────────────────────────
async function loadAddresses() {
  const el = document.getElementById('addresses-list');
  if (!el) return;
  const res = await customerApiFetch('addresses/');
  if (!res.ok) { el.innerHTML = '<p style="color:var(--muted)">Failed to load.</p>'; return; }
  const addrs = await res.json();
  el.innerHTML = addrs.length
    ? addrs.map(a => `
        <div class="admin-block" style="margin-bottom:0.5rem">
          <div style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:0.4rem">
            <strong>${esc(a.label || a.type)}</strong>
            ${a.is_default ? '<span class="pill pill-gold">Default</span>' : ''}
          </div>
          <p style="margin:0.3rem 0;color:var(--muted);font-size:0.9rem">${esc(a.full_name)} · ${esc(a.line1)}, ${esc(a.city)}, ${esc(a.postcode)}</p>
          <div style="display:flex;gap:0.4rem;flex-wrap:wrap;margin-top:0.4rem">
            <button class="btn btn-dark" onclick="editAddress(${Number(a.id)})">Edit</button>
            <button class="btn btn-dark" onclick="deleteAddress(${Number(a.id)})">Delete</button>
          </div>
        </div>`).join('')
    : '<p style="color:var(--muted)">No saved addresses.</p>';
}

function showAddressForm() { document.getElementById('address-form-wrap').style.display = ''; }
function hideAddressForm() {
  document.getElementById('address-form-wrap').style.display = 'none';
  document.getElementById('address-form').reset();
  document.getElementById('addr-id').value = '';
}

async function editAddress(id) {
  const res = await customerApiFetch(`addresses/${id}/`);
  if (!res.ok) return;
  const a = await res.json();
  document.getElementById('addr-id').value        = a.id;
  document.getElementById('addr-label').value     = a.label     || '';
  document.getElementById('addr-type').value      = a.type      || 'shipping';
  document.getElementById('addr-full-name').value = a.full_name || '';
  document.getElementById('addr-phone').value     = a.phone     || '';
  document.getElementById('addr-line1').value     = a.line1     || '';
  document.getElementById('addr-line2').value     = a.line2     || '';
  document.getElementById('addr-city').value      = a.city      || '';
  document.getElementById('addr-state').value     = a.state     || '';
  document.getElementById('addr-postcode').value  = a.postcode  || '';
  document.getElementById('addr-country').value   = a.country   || 'United Kingdom';
  document.getElementById('addr-default').checked = a.is_default || false;
  showAddressForm();
}

async function saveAddress(e) {
  e.preventDefault();
  const id = document.getElementById('addr-id').value;
  const body = {
    label:     document.getElementById('addr-label').value,
    type:      document.getElementById('addr-type').value,
    full_name: document.getElementById('addr-full-name').value,
    phone:     document.getElementById('addr-phone').value,
    line1:     document.getElementById('addr-line1').value,
    line2:     document.getElementById('addr-line2').value,
    city:      document.getElementById('addr-city').value,
    state:     document.getElementById('addr-state').value,
    postcode:  document.getElementById('addr-postcode').value,
    country:   document.getElementById('addr-country').value,
    is_default: document.getElementById('addr-default').checked,
  };
  const res = await customerApiFetch(id ? `addresses/${id}/` : 'addresses/', {
    method: id ? 'PATCH' : 'POST',
    body: JSON.stringify(body),
  });
  showToast(res.ok ? 'Address saved.' : 'Save failed.');
  if (res.ok) { hideAddressForm(); loadAddresses(); }
}

async function deleteAddress(id) {
  if (!confirm('Delete this address?')) return;
  const res = await customerApiFetch(`addresses/${id}/`, { method: 'DELETE' });
  if (res.ok) loadAddresses();
}

// ── Reviews ───────────────────────────────────────────────────────────────────
async function loadReviews() {
  const el = document.getElementById('reviews-list');
  if (!el) return;
  const res = await customerApiFetch('reviews/');
  if (!res.ok) { el.innerHTML = '<p style="color:var(--muted)">Failed to load.</p>'; return; }
  const reviews = await res.json();
  el.innerHTML = reviews.length
    ? reviews.map(r => `
        <div class="admin-block" style="margin-bottom:0.5rem">
          <div style="display:flex;justify-content:space-between">
            <strong>${esc(r.product_name || r.product)}</strong>
            <span style="color:var(--gold)">${'★'.repeat(r.rating)}${'☆'.repeat(5 - r.rating)}</span>
          </div>
          <p style="color:var(--muted);font-size:0.9rem;margin:0.3rem 0">${esc(r.body || '')}</p>
        </div>`).join('')
    : '<p style="color:var(--muted)">No reviews yet.</p>';
}

// ── Init ──────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  const panel  = document.getElementById('customer-panel');
  const warning = document.getElementById('customer-auth-warning');

  if (!isLoggedIn()) {
    if (warning) warning.style.display = '';
    return;
  }
  if (panel) panel.style.display = '';

  // Tab click handlers
  document.querySelectorAll('.admin-tab[data-tab]').forEach(btn => {
    btn.addEventListener('click', () => {
      const tab = btn.dataset.tab;
      switchTab(tab);
      if (tab === 'orders')        loadOrders();
      if (tab === 'refunds')       loadCustomerRefunds();
      if (tab === 'wishlist')      loadWishlist();
      if (tab === 'wallet')        loadWallet();
      if (tab === 'notifications') loadNotifications();
      if (tab === 'search-history') loadSearchHistory();
      if (tab === 'profile')       { loadProfile(); loadAddresses(); loadReviews(); }
    });
  });

  // Form handlers
  document.getElementById('refund-request-form')?.addEventListener('submit', submitRefundRequest);
  document.getElementById('profile-form')?.addEventListener('submit', saveProfile);
  document.getElementById('password-form')?.addEventListener('submit', changePassword);
  document.getElementById('address-form')?.addEventListener('submit', saveAddress);

  // Initial load
  await loadDashboardOverview();
});
