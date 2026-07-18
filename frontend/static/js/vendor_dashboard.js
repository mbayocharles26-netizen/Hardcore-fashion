// esc() / showToast() / getToken() / isLoggedIn() defined in main.js

const money = v => `RWF ${Number(v || 0).toLocaleString('en-RW', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;

// ── Chart instances ───────────────────────────────────────────────────────────
let trendChart = null;
let topChart   = null;

// ── Null-safe element getter ──────────────────────────────────────────────────
const el = id => document.getElementById(id);

// ── API helper ────────────────────────────────────────────────────────────────
async function vendorFetch(path, options = {}) {
  const token = getToken();
  const headers = { ...(token ? { Authorization: `Bearer ${token}` } : {}) };
  if (!(options.body instanceof FormData)) headers['Content-Type'] = 'application/json';
  const res = await fetch(`/api/vendor/${path}`, {
    ...options,
    headers: { ...headers, ...(options.headers || {}) },
  });
  if (res.status === 401 || res.status === 403) {
    const w = el('vendor-auth-warning');
    if (w) w.style.display = 'block';
  }
  return res;
}

function showVendorAccessMessage(message) {
  const w = el('vendor-auth-warning');
  if (w) { w.textContent = message; w.style.display = 'block'; }
  const p = el('vendor-panel');
  if (p) p.style.display = 'none';
}

async function getVendorAccountStatus() {
  const token = getToken();
  const res = await fetch('/api/vendor/status/', {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  return res.ok ? res.json() : null;
}

// ── Tab navigation ────────────────────────────────────────────────────────────
function showVendorView(name) {
  document.querySelectorAll('.admin-tab').forEach(b =>
    b.classList.toggle('active', b.dataset.tab === name));
  document.querySelectorAll('.admin-view').forEach(v =>
    v.classList.toggle('active', v.id === `tab-${name}`));
}

// ── Notification badge ────────────────────────────────────────────────────────
function updateNotifBadge(count) {
  const badge = el('notif-badge');
  if (!badge) return;
  if (count > 0) { badge.textContent = count; badge.style.display = 'inline'; }
  else badge.style.display = 'none';
}

// ── Dashboard ─────────────────────────────────────────────────────────────────
async function loadVendorDashboard() {
  const res = await vendorFetch('dashboard/');
  if (!res.ok) return;
  const data = await res.json();

  const storeName = el('vendor-store-name');
  if (storeName) storeName.textContent = data.store_name || 'My Store';

  const m    = data.metrics;
  const grid = el('vendor-metric-grid');
  if (grid) {
    grid.innerHTML = [
      ['Revenue (Total)',  money(m.revenue_total)],
      ['Revenue (Month)',  money(m.revenue_month)],
      ['Orders (Total)',   m.orders_total],
      ['Orders (Pending)', m.orders_pending],
      ['Active Products',  m.products_active],
      ['Low Stock',        m.low_stock],
      ['Unread Alerts',    m.unread_notifications],
    ].map(([label, value]) =>
      `<div class="metric"><span>${esc(String(label))}</span><strong>${esc(String(value))}</strong></div>`
    ).join('');
  }

  updateNotifBadge(m.unread_notifications);
  renderTrendChart(data.monthly_trend);
  renderTopChart(data.top_products);
}

function renderTrendChart(trend) {
  if (trendChart) { trendChart.destroy(); trendChart = null; }
  const canvas = el('vendor-trend-canvas');
  if (!canvas) return;
  trendChart = new Chart(canvas.getContext('2d'), {
    type: 'line',
    data: {
      labels: trend.map(r => r.label),
      datasets: [{
        label: 'Revenue (RWF)',
        data: trend.map(r => r.revenue),
        borderColor: '#c9a84c',
        backgroundColor: 'rgba(201,168,76,0.12)',
        tension: 0.3,
        fill: true,
        pointRadius: 4,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { labels: { color: '#aaa' } } },
      scales: {
        x: { ticks: { color: '#aaa' }, grid: { color: '#222' } },
        y: { ticks: { color: '#aaa' }, grid: { color: '#222' } },
      },
    },
  });
}

function renderTopChart(products) {
  if (topChart) { topChart.destroy(); topChart = null; }
  const canvas = el('vendor-top-canvas');
  if (!canvas) return;
  topChart = new Chart(canvas.getContext('2d'), {
    type: 'bar',
    data: {
      labels: products.map(p => p.name),
      datasets: [{
        label: 'Units Sold',
        data: products.map(p => p.quantity),
        backgroundColor: 'rgba(201,168,76,0.7)',
        borderColor: '#c9a84c',
        borderWidth: 1,
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

// ── Products ──────────────────────────────────────────────────────────────────
let vendorProducts = [];

async function loadVendorCategories() {
  const sel = el('vp-category');
  if (!sel) return;
  sel.innerHTML = '<option value="">Loading categories…</option>';
  const res = await fetch('/api/categories/');
  if (!res.ok) { sel.innerHTML = '<option value="">Failed to load categories</option>'; return; }
  const cats = await res.json();
  if (!cats.length) { sel.innerHTML = '<option value="">No categories available</option>'; return; }
  sel.innerHTML = '<option value="">— Select category —</option>' +
    cats.map(c => `<option value="${esc(String(c.id))}">${esc(c.name)}</option>`).join('');
}

async function loadVendorProducts() {
  const res = await vendorFetch('products/');
  if (!res.ok) return;
  vendorProducts = await res.json();
  renderVendorProductsTable(vendorProducts);
}

function renderVendorProductsTable(list) {
  const count = el('vp-count');
  if (count) count.textContent = `(${list.length})`;
  const tbody = el('vendor-products-table');
  if (!tbody) return;
  tbody.innerHTML = list.length
    ? list.map(p => `
        <tr>
          <td>${p.image
            ? `<img src="${esc(p.image)}" style="width:48px;height:48px;object-fit:cover;border-radius:4px" />`
            : '<span style="color:var(--muted)">—</span>'}</td>
          <td>${esc(p.name)}</td>
          <td>${esc(p.category_name)}</td>
          <td>${money(p.price)}</td>
          <td>${esc(String(p.stock))}</td>
          <td><span style="color:${p.is_active ? '#4caf50' : '#aaa'}">${p.is_active ? 'Visible' : 'Hidden'}</span></td>
          <td class="table-actions">
            <button class="btn btn-dark" onclick="editVendorProduct(${Number(p.id)})">Edit</button>
            <button class="btn btn-dark" onclick="deleteVendorProduct(${Number(p.id)})">Delete</button>
          </td>
        </tr>`).join('')
    : '<tr><td colspan="7" style="color:var(--muted);padding:1rem">No products yet.</td></tr>';
}

function filterVendorProducts() {
  const q      = (el('vp-search')?.value || '').toLowerCase();
  const status = el('vp-filter-status')?.value || '';
  const filtered = vendorProducts.filter(p => {
    const matchQ = !q || p.name.toLowerCase().includes(q) || (p.category_name || '').toLowerCase().includes(q);
    const matchS = !status
      || (status === 'active' && p.is_active)
      || (status === 'hidden' && !p.is_active);
    return matchQ && matchS;
  });
  renderVendorProductsTable(filtered);
}

async function resetVendorProductForm() {
  el('vendor-product-form')?.reset();
  const vpId = el('vp-id'); if (vpId) vpId.value = '';
  const vpActive = el('vp-active'); if (vpActive) vpActive.checked = true;
  const preview = el('vp-image-preview'); if (preview) preview.style.display = 'none';
  const title = el('vp-form-title'); if (title) title.textContent = 'Add Product';
  showVendorView('products');
  const wrap = el('vendor-product-form-wrap');
  if (wrap) {
    wrap.style.display = '';
    // Reload categories if the select is empty or still showing placeholder
    const sel = el('vp-category');
    if (!sel || sel.options.length <= 1) await loadVendorCategories();
    setTimeout(() => wrap.scrollIntoView({ behavior: 'smooth' }), 100);
  }
}

function editVendorProduct(id) {
  const p = vendorProducts.find(x => x.id === id);
  if (!p) return;
  const set = (elId, val) => { const e = el(elId); if (e) e.value = val; };
  const chk = (elId, val) => { const e = el(elId); if (e) e.checked = val; };
  set('vp-id',            p.id);
  set('vp-name',          p.name);
  set('vp-slug',          p.slug);
  set('vp-category',      p.category);
  set('vp-price',         p.price);
  set('vp-compare-price', p.compare_at_price || '');
  set('vp-stock',         p.stock);
  set('vp-shipping-days', p.shipping_days || 3);
  set('vp-description',   p.description);
  chk('vp-featured',      p.is_featured);
  chk('vp-active',        p.is_active);
  const title = el('vp-form-title'); if (title) title.textContent = 'Edit Product';
  const wrap = el('vendor-product-form-wrap');
  if (wrap) wrap.style.display = '';
  if (p.image) {
    const preview = el('vp-image-preview');
    if (preview) { preview.src = p.image; preview.style.display = 'block'; }
  }
  showVendorView('products');
  setTimeout(() => el('vendor-product-form-wrap')?.scrollIntoView({ behavior: 'smooth' }), 100);
}

async function deleteVendorProduct(id) {
  if (!confirm('Delete this product?')) return;
  const res = await vendorFetch(`products/${id}/`, { method: 'DELETE' });
  if (res.ok) { showToast('Product deleted.'); loadVendorProducts(); loadVendorDashboard(); }
  else showToast('Delete failed.');
}

async function saveVendorProduct(e) {
  e.preventDefault();
  const id = el('vp-id')?.value;
  const fd = new FormData();
  fd.append('name',             el('vp-name')?.value        || '');
  fd.append('slug',             el('vp-slug')?.value        || '');
  fd.append('category',         el('vp-category')?.value    || '');
  fd.append('price',            el('vp-price')?.value       || '');
  fd.append('compare_at_price', el('vp-compare-price')?.value || '');
  fd.append('stock',            el('vp-stock')?.value       || '');
  fd.append('shipping_days',    el('vp-shipping-days')?.value || '3');
  fd.append('description',      el('vp-description')?.value || '');
  fd.append('is_featured',      el('vp-featured')?.checked  ? 'true' : 'false');
  fd.append('is_active',        el('vp-active')?.checked    ? 'true' : 'false');
  const img = el('vp-image')?.files[0];
  if (img) fd.append('image', img);
  const res = await vendorFetch(id ? `products/${id}/` : 'products/', {
    method: id ? 'PATCH' : 'POST',
    body: fd,
  });
  if (res.ok) {
    showToast('Product saved.');
    resetVendorProductForm();
    loadVendorProducts();
    loadVendorDashboard();
  } else {
    const err = await res.json().catch(() => ({}));
    showToast(Object.values(err).flat().join(' ') || 'Could not save product.');
  }
}

async function importVendorProducts(e) {
  e.preventDefault();
  const file = el('vp-import-file')?.files[0];
  if (!file) return;
  const fd = new FormData();
  fd.append('file', file);
  const res  = await vendorFetch('products/import/', { method: 'POST', body: fd });
  const data = await res.json().catch(() => ({}));
  showToast(res.ok ? `Imported ${Number(data.imported || 0)} products.` : 'Import failed.');
  if (res.ok) loadVendorProducts();
}

// ── Refunds ───────────────────────────────────────────────────────────────────
async function loadVendorRefunds() {
  const statusFilter = el('refund-status-filter')?.value || '';
  const qs = statusFilter ? `?status=${statusFilter}` : '';
  const tbody = el('vendor-refunds-table');
  if (!tbody) return;
  tbody.innerHTML = '<tr><td colspan="8" style="padding:1.5rem;color:var(--muted)">Loading…</td></tr>';
  const res = await vendorFetch(`refunds/${qs}`);
  if (!res.ok) {
    tbody.innerHTML = '<tr><td colspan="8" style="color:#f44;padding:1rem">Failed to load refunds.</td></tr>';
    return;
  }
  const refunds = await res.json();
  if (!refunds.length) {
    tbody.innerHTML = '<tr><td colspan="8" style="padding:1.5rem;color:var(--muted)">No refund requests yet.</td></tr>';
    return;
  }
  const statusColor = s => ({ pending: '#c9a84c', approved: '#4caf50', rejected: '#f44', processed: '#4aa3ff' }[s] || '#aaa');
  tbody.innerHTML = refunds.map(r => `
    <tr>
      <td>#${Number(r.id)}</td>
      <td>#${Number(r.order_id)}</td>
      <td>${esc(r.customer || '—')}</td>
      <td style="max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${esc(r.reason)}">${esc(r.reason)}</td>
      <td><span style="color:${statusColor(r.status)};font-weight:700">${esc(r.status)}</span></td>
      <td>${esc(r.created_at ? new Date(r.created_at).toLocaleDateString() : '—')}</td>
      <td style="color:var(--muted);font-size:0.85rem">${esc(r.notes || r.admin_note || '—')}</td>
      <td class="table-actions">
        ${r.status === 'pending' ? `
          <button class="btn btn-gold" onclick="openRefundModal(${Number(r.id)}, 'approve')">Approve</button>
          <button class="btn btn-dark" onclick="openRefundModal(${Number(r.id)}, 'reject')">Reject</button>
        ` : '<span style="color:var(--muted)">—</span>'}
      </td>
    </tr>`).join('');
}

let _refundModalId = null;
let _refundModalAction = null;

function openRefundModal(id, action) {
  _refundModalId = id;
  _refundModalAction = action;
  const modal = el('refund-notes-modal');
  const title = el('refund-modal-title');
  if (title) title.textContent = action === 'approve' ? 'Approve Refund' : 'Reject Refund';
  const notes = el('refund-modal-notes');
  if (notes) notes.value = '';
  if (modal) modal.style.display = 'flex';
}

function closeRefundModal() {
  const modal = el('refund-notes-modal');
  if (modal) modal.style.display = 'none';
  _refundModalId = null;
  _refundModalAction = null;
}

async function submitRefundAction() {
  if (!_refundModalId || !_refundModalAction) return;
  const notes = el('refund-modal-notes')?.value || '';
  const res = await vendorFetch(`refunds/${_refundModalId}/action/`, {
    method: 'PATCH',
    body: JSON.stringify({ action: _refundModalAction, notes }),
  });
  showToast(res.ok ? `Refund ${_refundModalAction}d.` : 'Action failed.');
  closeRefundModal();
  if (res.ok) loadVendorRefunds();
}

// ── Orders ────────────────────────────────────────────────────────────────────
let vendorOrders = [];

async function loadVendorOrders() {
  const res = await vendorFetch('orders/');
  if (!res.ok) return;
  vendorOrders = await res.json();
  renderVendorOrdersTable(vendorOrders);
}

function renderVendorOrdersTable(list) {
  const tbody = el('vendor-orders-table');
  if (!tbody) return;
  const statuses = ['pending', 'processing', 'shipped', 'delivered', 'cancelled'];
  tbody.innerHTML = list.length
    ? list.map(o => `
        <tr>
          <td>#${Number(o.id)}</td>
          <td>${esc(o.customer_name)}<br><small style="color:var(--muted)">${esc(o.customer_email)}</small></td>
          <td>${(o.items || []).map(i => `${esc(i.product_name)} ×${i.quantity}`).join('<br>')}</td>
          <td>${money(o.subtotal)}</td>
          <td>
            <select class="status-select" onchange="updateVendorOrderStatus(${Number(o.id)}, this.value)">
              ${statuses.map(s =>
                `<option value="${s}"${o.status === s ? ' selected' : ''}>${s}</option>`
              ).join('')}
            </select>
          </td>
          <td>${esc(new Date(o.order_date).toLocaleDateString())}</td>
          <td class="table-actions">
            <button class="btn btn-dark" onclick="downloadVendorInvoice(${Number(o.id)})">Invoice</button>
            ${o.status === 'pending' ? `
              <button class="btn btn-gold" onclick="vendorPaymentAction(${Number(o.id)}, 'confirm')">✅ Confirm Payment</button>
              <button class="btn btn-dark" style="background:#6b2737" onclick="vendorPaymentAction(${Number(o.id)}, 'reject')">❌ Reject Payment</button>
            ` : ''}
          </td>
        </tr>`).join('')
    : '<tr><td colspan="7" style="color:var(--muted);padding:1rem">No orders yet.</td></tr>';
}

function filterVendorOrders() {
  const status = el('order-filter-status')?.value || '';
  renderVendorOrdersTable(status ? vendorOrders.filter(o => o.status === status) : vendorOrders);
}

async function updateVendorOrderStatus(id, newStatus) {
  const res = await vendorFetch(`orders/${id}/status/`, {
    method: 'PATCH',
    body: JSON.stringify({ status: newStatus }),
  });
  showToast(res.ok ? 'Order updated.' : 'Update failed.');
  if (res.ok) loadVendorDashboard();
}

async function vendorPaymentAction(vendorOrderId, action) {
  const label = action === 'confirm' ? 'confirm payment' : 'reject payment';
  if (!confirm(`Are you sure you want to ${label} for this order?`)) return;
  const res = await vendorFetch(`orders/${vendorOrderId}/payment-action/`, {
    method: 'PATCH',
    body: JSON.stringify({ action }),
  });
  if (!res.ok) { showToast('Action failed.'); return; }
  const data = await res.json();
  if (action === 'confirm' && data.tracking_number) {
    showToast(`Payment confirmed! Tracking code: ${data.tracking_number}`);
  } else {
    showToast('Payment rejected. Order cancelled.');
  }
  loadVendorOrders();
  loadVendorDashboard();
}

async function downloadVendorInvoice(id) {
  const res = await vendorFetch(`orders/${id}/invoice/`);
  if (!res.ok) return;
  const blob = await res.blob();
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement('a');
  a.href = url; a.download = `vendor-invoice-${id}.txt`; a.click();
  URL.revokeObjectURL(url);
}

// ── Payouts ───────────────────────────────────────────────────────────────────
async function loadVendorPayouts() {
  const [payRes, earnRes] = await Promise.all([
    vendorFetch('payouts/'),
    vendorFetch('earnings/'),
  ]);

  if (earnRes.ok) {
    const e = await earnRes.json();
    const pmTotal   = el('pm-total');   if (pmTotal)   pmTotal.textContent   = money(e.total_earned);
    const pmPaid    = el('pm-paid');    if (pmPaid)    pmPaid.textContent    = money(e.paid_out);
    const pmPending = el('pm-pending'); if (pmPending) pmPending.textContent = money(e.pending);
  }

  if (!payRes.ok) return;
  const rows  = await payRes.json();
  const tbody = el('vendor-payouts-table');
  if (!tbody) return;
  tbody.innerHTML = rows.length
    ? rows.map(p => `
        <tr>
          <td>${money(p.amount)}</td>
          <td>${esc(p.method)}</td>
          <td><span style="color:${p.status === 'completed' ? '#4caf50' : p.status === 'failed' ? '#f44' : '#c9a84c'}">${esc(p.status)}</span></td>
          <td>${esc(new Date(p.requested_at).toLocaleDateString())}</td>
          <td>${p.processed_at ? esc(new Date(p.processed_at).toLocaleDateString()) : '—'}</td>
          <td style="color:var(--muted);font-size:0.8rem">${esc(p.notes || '')}</td>
        </tr>`).join('')
    : '<tr><td colspan="6" style="color:var(--muted);padding:1rem">No payout requests yet.</td></tr>';
}

async function requestPayout(e) {
  e.preventDefault();
  const res = await vendorFetch('payouts/', {
    method: 'POST',
    body: JSON.stringify({
      amount: el('payout-amount')?.value,
      method: el('payout-method')?.value,
      notes:  el('payout-notes')?.value,
    }),
  });
  if (res.ok) { showToast('Payout requested.'); e.target.reset(); loadVendorPayouts(); }
  else showToast('Payout request failed.');
}

// ── Notifications ─────────────────────────────────────────────────────────────
async function loadVendorNotifications() {
  const res = await vendorFetch('notifications/');
  if (!res.ok) return;
  const items = await res.json();
  renderNotifications(items);
  updateNotifBadge(items.filter(n => !n.is_read).length);
}

function renderNotifications(items) {
  const list = el('vendor-notifications-list');
  if (!list) return;
  list.innerHTML = items.length
    ? items.map(n => `
        <div class="notification-item${n.is_read ? '' : ' unread'}">
          <strong>${esc(n.title)}</strong>
          <p>${esc(n.body)}</p>
          <small>${esc(new Date(n.created_at).toLocaleString())}</small>
          ${!n.is_read
            ? `<button class="btn btn-dark" onclick="markNotificationRead(${Number(n.id)})">Mark read</button>`
            : ''}
        </div>`).join('')
    : '<p style="color:var(--muted)">No notifications.</p>';
}

async function markNotificationRead(id) {
  const res = await vendorFetch(`notifications/${id}/read/`, { method: 'PATCH' });
  if (res.ok) loadVendorNotifications();
}

async function markAllNotificationsRead() {
  const res = await vendorFetch('notifications/mark-all-read/', { method: 'POST' });
  if (res.ok) { showToast('All marked as read.'); loadVendorNotifications(); }
}

async function clearAllNotifications() {
  if (!confirm('Clear all notifications?')) return;
  const res = await vendorFetch('notifications/clear/', { method: 'DELETE' });
  if (res.ok) { showToast('Notifications cleared.'); loadVendorNotifications(); }
}

// ── WebSocket ─────────────────────────────────────────────────────────────────
function initVendorWebSocket(retries = 0) {
  const MAX_RETRIES = 5;
  const token = getToken();
  if (!token) return;
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  const ws = new WebSocket(`${proto}://${location.host}/ws/vendor/notifications/?token=${token}`);
  let connected = false;

  ws.onopen = () => { connected = true; retries = 0; };

  ws.onmessage = ({ data }) => {
    const n = JSON.parse(data);
    showToast(`🔔 ${n.title}`);
    const list = el('vendor-notifications-list');
    if (!list) return;
    const noMsg = list.querySelector('p');
    if (noMsg) noMsg.remove();
    const div = document.createElement('div');
    div.className = 'notification-item unread';
    div.innerHTML = `
      <strong>${esc(n.title)}</strong>
      <p>${esc(n.body)}</p>
      <small>${esc(new Date(n.created_at).toLocaleString())}</small>`;
    const btn = document.createElement('button');
    btn.className = 'btn btn-dark';
    btn.textContent = 'Mark read';
    btn.addEventListener('click', () => markNotificationRead(Number(n.id)));
    div.appendChild(btn);
    list.prepend(div);
    loadVendorDashboard();
  };

  ws.onclose = ({ code }) => {
    if (!connected || code === 1000 || code === 1001) return;
    if (retries >= MAX_RETRIES) return;
    setTimeout(() => initVendorWebSocket(retries + 1), 5000);
  };
}

// ── Profile ───────────────────────────────────────────────────────────────────
async function loadVendorProfile() {
  const res = await vendorFetch('profile/');
  if (!res.ok) return;
  const p = await res.json();

  const set = (elId, val) => { const e = el(elId); if (e) e.value = val; };
  set('prof-store-name',    p.store_name    || '');
  set('prof-email',         p.email         || '');
  set('prof-phone',         p.phone         || '');
  set('prof-address',       p.address       || '');
  set('prof-desc',          p.description   || '');
  set('prof-payout-method', p.payout_method || 'flutterwave');

  const statusColors = { approved: '#4caf50', pending: '#c9a84c', rejected: '#f44' };
  const statusText = el('prof-status-text');
  if (statusText) statusText.innerHTML =
    `<span style="color:${statusColors[p.status] || '#aaa'}">${esc(p.status)}</span>`;
  const commission = el('prof-commission');
  if (commission) commission.textContent = `${p.commission_rate}%`;
  const since = el('prof-since');
  if (since) since.textContent = new Date(p.created_at).toLocaleDateString();

  const badge = el('prof-status-badge');
  if (badge) { badge.textContent = p.status; badge.style.color = statusColors[p.status] || '#aaa'; }

  if (p.logo) {
    const preview = el('prof-logo-preview');
    if (preview) { preview.src = p.logo; preview.style.display = 'block'; }
  }
}

async function saveVendorProfile(e) {
  e.preventDefault();
  const fd = new FormData();
  fd.append('store_name',    el('prof-store-name')?.value    || '');
  fd.append('email',         el('prof-email')?.value         || '');
  fd.append('phone',         el('prof-phone')?.value         || '');
  fd.append('address',       el('prof-address')?.value       || '');
  fd.append('description',   el('prof-desc')?.value          || '');
  fd.append('payout_method', el('prof-payout-method')?.value || '');
  const logo = el('prof-logo')?.files[0];
  if (logo) fd.append('logo', logo);
  const res = await vendorFetch('profile/', { method: 'PATCH', body: fd });
  showToast(res.ok ? 'Profile saved.' : 'Save failed.');
  if (res.ok) loadVendorProfile();
}

// ── Image preview helpers ─────────────────────────────────────────────────────
function setupImagePreview(inputId, previewId) {
  const input = el(inputId);
  if (!input) return;
  input.addEventListener('change', function () {
    const file = this.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = e => {
      const img = el(previewId);
      if (img) { img.src = e.target.result; img.style.display = 'block'; }
    };
    reader.readAsDataURL(file);
  });
}

// ── Slug auto-generation ──────────────────────────────────────────────────────
function setupSlugGeneration() {
  const nameInput = el('vp-name');
  if (!nameInput) return;
  nameInput.addEventListener('input', function () {
    if (!el('vp-id')?.value) {
      const slugEl = el('vp-slug');
      if (slugEl) slugEl.value = this.value.toLowerCase()
        .replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
    }
  });
}

// ── Refunds ───────────────────────────────────────────────────────────────────
let _refundActionState = { id: null, action: null };
let _refundInFlight = false;

function _refundStatusColor(s) {
  return { pending: '#c9a84c', approved: '#4caf50', rejected: '#f44', processed: '#4aa3ff' }[s] || '#aaa';
}

async function loadVendorRefunds() {
  if (_refundInFlight) return;
  _refundInFlight = true;
  const tbody = el('vendor-refunds-table');
  if (!tbody) { _refundInFlight = false; return; }

  tbody.innerHTML = '<tr><td colspan="8" style="padding:1.5rem;color:var(--muted)">Loading…</td></tr>';

  try {
    // getToken() reads localStorage key 'token' (set by main.js login)
    const token = getToken();
    if (!token) {
      tbody.innerHTML = '<tr><td colspan="8" style="padding:1.5rem;color:#f44">Not authenticated — please <a href="/login/" style="color:#c9a84c">log in</a>.</td></tr>';
      return;
    }

    const statusFilter = el('refund-status-filter')?.value || '';
    const url = new URL('/api/refunds/list/', window.location.origin);
    if (statusFilter) url.searchParams.set('status', statusFilter);

    let res;
    try {
      res = await fetch(url.toString(), { headers: { Authorization: `Bearer ${token}` } });
    } catch (networkErr) {
      tbody.innerHTML = '<tr><td colspan="8" style="padding:1.5rem;color:#f44">Network error — check your connection.</td></tr>';
      return;
    }

    if (res.status === 401 || res.status === 403) {
      tbody.innerHTML = '<tr><td colspan="8" style="padding:1.5rem;color:#f44">Session expired — please <a href="/login/" style="color:#c9a84c">log in again</a>.</td></tr>';
      return;
    }
    if (!res.ok) {
      const errText = await res.text().catch(() => '');
      tbody.innerHTML = `<tr><td colspan="8" style="padding:1.5rem;color:#f44">Error ${res.status}: ${esc(errText || 'Failed to load refunds')}.</td></tr>`;
      return;
    }

    let refunds;
    try {
      refunds = await res.json();
    } catch {
      tbody.innerHTML = '<tr><td colspan="8" style="padding:1.5rem;color:#f44">Invalid response from server.</td></tr>';
      return;
    }

    if (!Array.isArray(refunds) || !refunds.length) {
      tbody.innerHTML = `
        <tr>
          <td colspan="8" style="padding:2rem;text-align:center">
            <div style="color:var(--muted);font-size:1.1rem">↩️ No refund requests yet</div>
            <div style="color:var(--muted);font-size:0.85rem;margin-top:0.4rem">When customers request refunds for your orders, they will appear here.</div>
          </td>
        </tr>`;
      return;
    }

    tbody.innerHTML = refunds.map(r => {
      const actionBtn = r.status === 'pending'
        ? `<div style="display:flex;gap:0.5rem;flex-wrap:wrap">
             <button class="btn btn-gold" style="padding:0.4rem 0.6rem" onclick="openRefundModal(${r.id},'approve')">Approve</button>
             <button class="btn btn-dark" style="padding:0.4rem 0.6rem" onclick="openRefundModal(${r.id},'reject')">Reject</button>
           </div>`
        : `<span style="color:var(--muted)">—</span>`;
      return `<tr>
        <td>${esc(String(r.id))}</td>
        <td>#${esc(String(r.order_id))}</td>
        <td>${esc(r.customer_name || '—')}</td>
        <td style="max-width:180px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="${esc(r.reason)}">${esc(r.reason)}</td>
        <td><span style="color:${_refundStatusColor(r.status)};font-weight:700">${esc(r.status)}</span></td>
        <td>${r.created_at ? esc(new Date(r.created_at).toLocaleDateString()) : '—'}</td>
        <td style="color:var(--muted);font-size:0.85rem">${esc(r.notes || r.admin_note || '—')}</td>
        <td>${actionBtn}</td>
      </tr>`;
    }).join('');
  } finally {
    _refundInFlight = false;
  }
}

function openRefundModal(refundId, action) {
  _refundActionState = { id: refundId, action };
  const modal = el('refund-notes-modal');
  if (!modal) return;
  const title = el('refund-modal-title');
  if (title) title.textContent = action === 'approve' ? 'Approve refund' : 'Reject refund';
  const notes = el('refund-modal-notes');
  if (notes) notes.value = '';
  modal.style.display = 'flex';
}

function closeRefundModal() {
  const modal = el('refund-notes-modal');
  if (modal) modal.style.display = 'none';
}

async function submitRefundAction() {
  const { id, action } = _refundActionState;
  if (!id || !action) return;
  const notes = (el('refund-modal-notes')?.value || '').trim();
  const res = await fetch(`/api/refunds/vendor-action/${id}/`, {
    method: 'PATCH',
    headers: { Authorization: `Bearer ${getToken()}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ action, notes }),
  });
  if (!res.ok) {
    showToast('Action failed. ' + await res.text().catch(() => ''));
    return;
  }
  closeRefundModal();
  showToast(`Refund ${action}d successfully.`);
  await loadVendorRefunds();
}

// ── Init ──────────────────────────────────────────────────────────────────────
async function loadVendorAll() {
  if (!isLoggedIn()) {
    showVendorAccessMessage('Please log in with an approved vendor account to access this page.');
    return;
  }
  const account = await getVendorAccountStatus();
  if (!account || !account.is_vendor) {
    showVendorAccessMessage('This account is not registered as a vendor.');
    return;
  }
  if (account.status === 'pending') {
    showVendorAccessMessage('Your vendor application is pending administrator approval.');
    return;
  }
  if (account.status === 'rejected') {
    showVendorAccessMessage('Your vendor application was not approved. Please contact an administrator.');
    return;
  }
  await Promise.all([
    loadVendorDashboard(),
    loadVendorCategories(),
    loadVendorProducts(),
    loadVendorOrders(),
    loadVendorRefunds(),
    loadVendorPayouts(),
    loadVendorNotifications(),
    loadVendorProfile(),
    // Refunds loaded on tab click — tbody is hidden during init so skip here
  ]);
  initVendorWebSocket();
}

document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.admin-tab').forEach(btn =>
    btn.addEventListener('click', () => {
      showVendorView(btn.dataset.tab);
      if (btn.dataset.tab === 'products') loadVendorCategories();
      if (btn.dataset.tab === 'refunds') {
        _refundInFlight = false;
        loadVendorRefunds();
      }
    }));

  el('vendor-product-form')?.addEventListener('submit', saveVendorProduct);
  el('vendor-import-form')?.addEventListener('submit', importVendorProducts);
  el('vendor-payout-form')?.addEventListener('submit', requestPayout);
  el('vendor-profile-form')?.addEventListener('submit', saveVendorProfile);

  setupImagePreview('vp-image',  'vp-image-preview');
  setupImagePreview('prof-logo', 'prof-logo-preview');
  setupSlugGeneration();

  // Auto-switch to tab specified in URL e.g. /vendor-dashboard/?tab=refunds
  const urlTab = new URLSearchParams(window.location.search).get('tab');
  if (urlTab) showVendorView(urlTab);

  loadVendorAll();
});
