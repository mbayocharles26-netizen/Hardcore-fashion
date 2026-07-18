const adminState = {
  categories: [],
  products: [],
  role: null,
  settingsDraft: {},
};

// esc() and safeHTML() are defined globally in main.js
const money = value => `RWF ${Number(value || 0).toLocaleString('en-RW', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;

async function adminFetch(path, options = {}) {
  const token = getToken();
  const headers = { ...(token ? { Authorization: `Bearer ${token}` } : {}) };
  if (!(options.body instanceof FormData)) headers['Content-Type'] = 'application/json';
  const res = await fetch(`/api/admin/${path}`, { ...options, headers: { ...headers, ...(options.headers || {}) } });
  if (res.status === 401 || res.status === 403) {
    document.getElementById('admin-auth-warning').style.display = 'block';
  }
  const originalJson = res.json.bind(res);
  res.json = async () => {
    try { return await originalJson(); }
    catch { return {}; }
  };
  return res;
}

// ── Role gating ──
const ROLE_TABS = {
  super_admin:     ['dashboard', 'products', 'orders', 'customers', 'vendor-mgmt', 'vendors', 'refunds', 'inventory', 'reports', 'transactions', 'settings'],
  product_manager: ['dashboard', 'products', 'inventory', 'reports'],
  order_manager:   ['dashboard', 'orders', 'customers', 'refunds', 'transactions', 'reports'],
};

async function loadAdminRole() {
  const res = await adminFetch('me/');
  if (!res.ok) return;
  const data = await res.json();
  adminState.role = data.role;
  const allowed = ROLE_TABS[data.role] || [];
  document.querySelectorAll('.admin-tab').forEach(btn => {
    btn.style.display = allowed.includes(btn.dataset.tab) ? '' : 'none';
  });
  const saveBtn = document.getElementById('settings-save-btn');
  if (saveBtn && data.role === 'super_admin') saveBtn.style.display = '';
  if (allowed.length) showView(allowed[0]);
}

function showView(name) {
  document.querySelectorAll('.admin-tab').forEach(btn => btn.classList.toggle('active', btn.dataset.tab === name));
  document.querySelectorAll('.admin-view').forEach(view => view.classList.toggle('active', view.id === `tab-${name}`));
}

function metric(label, value) {
  return `<div class="metric"><span>${esc(String(label))}</span><strong>${esc(String(value))}</strong></div>`;
}

// ── Dashboard charts (Chart.js instances) ────────────────────────────────────
const _charts = {};
function _mkChart(id, config) {
  if (_charts[id]) { _charts[id].destroy(); }
  const canvas = document.getElementById(id);
  if (!canvas) return;
  _charts[id] = new Chart(canvas.getContext('2d'), config);
}

const _chartDefaults = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { labels: { color: '#aaa' } } },
  scales: {
    x: { ticks: { color: '#aaa' }, grid: { color: '#222' } },
    y: { ticks: { color: '#aaa' }, grid: { color: '#222' }, beginAtZero: true },
  },
};

// ── Dashboard filter helpers ──────────────────────────────────────────────────
function _dashFilters() {
  const p = new URLSearchParams();
  const from = document.getElementById('filter-from')?.value;
  const to   = document.getElementById('filter-to')?.value;
  const cat  = document.getElementById('filter-category')?.value;
  const ven  = document.getElementById('filter-vendor')?.value;
  if (from) p.set('from', from);
  if (to)   p.set('to',   to);
  if (cat)  p.set('category', cat);
  if (ven)  p.set('vendor',   ven);
  return p.toString() ? '?' + p.toString() : '';
}

function resetDashboardFilters() {
  ['filter-from','filter-to','filter-category','filter-vendor'].forEach(id => {
    const e = document.getElementById(id);
    if (e) e.value = '';
  });
  loadDashboard();
}

async function _populateDashboardFilters() {
  // Categories
  const catSel = document.getElementById('filter-category');
  if (catSel && catSel.options.length <= 1) {
    const res = await adminFetch('categories/');
    if (res.ok) {
      const cats = await res.json();
      cats.forEach(c => {
        const o = document.createElement('option');
        o.value = esc(c.slug); o.textContent = esc(c.name);
        catSel.appendChild(o);
      });
    }
  }
  // Vendors
  const venSel = document.getElementById('filter-vendor');
  if (venSel && venSel.options.length <= 1) {
    const res = await fetch('/api/analytics/revenue-per-vendor/', {
      headers: getToken() ? { Authorization: `Bearer ${getToken()}` } : {},
    });
    if (res.ok) {
      const vendors = await res.json();
      vendors.forEach(v => {
        const o = document.createElement('option');
        o.value = v.vendor_id; o.textContent = esc(v.store_name);
        venSel.appendChild(o);
      });
    }
  }
}

// ── CSV export ────────────────────────────────────────────────────────────────
function exportDashboardCSV() {
  const rows = [['Metric', 'Value']];
  document.querySelectorAll('#metric-grid .metric').forEach(m => {
    const label = m.querySelector('span')?.textContent || '';
    const value = m.querySelector('strong')?.textContent || '';
    rows.push([label, value]);
  });
  const csv = rows.map(r => r.map(c => `"${c.replace(/"/g, '""')}"`).join(',')).join('\n');
  const blob = new Blob([csv], { type: 'text/csv' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `dashboard-${new Date().toISOString().slice(0,10)}.csv`;
  a.click();
  URL.revokeObjectURL(a.href);
}

// ── Auto-refresh ──────────────────────────────────────────────────────────────
let _autoRefreshTimer = null;
function _startAutoRefresh() {
  if (_autoRefreshTimer) clearInterval(_autoRefreshTimer);
  _autoRefreshTimer = setInterval(() => {
    if (document.getElementById('tab-dashboard')?.classList.contains('active')) {
      loadDashboard();
    }
  }, 60_000);
}

async function loadDashboard() {
  const qs = _dashFilters();
  const trendRange = document.getElementById('trend-range')?.value || 'weekly';
  const topMetric  = document.getElementById('top-metric')?.value  || 'revenue';

  const [dashRes, trendRes, topRes, userRes, vendorRes] = await Promise.all([
    adminFetch(`dashboard/${qs}`),
    fetch(`/api/analytics/sales-trend/?range=${trendRange}`, { headers: getToken() ? { Authorization: `Bearer ${getToken()}` } : {} }),
    fetch(`/api/analytics/top-products/?metric=${topMetric}&limit=8`, { headers: getToken() ? { Authorization: `Bearer ${getToken()}` } : {} }),
    fetch(`/api/analytics/revenue-per-user/?limit=10`, { headers: getToken() ? { Authorization: `Bearer ${getToken()}` } : {} }),
    fetch(`/api/analytics/revenue-per-vendor/`, { headers: getToken() ? { Authorization: `Bearer ${getToken()}` } : {} }),
  ]);

  // ── KPI cards ──
  const metricGrid = document.getElementById('metric-grid');
  if (dashRes.ok && metricGrid) {
    const data = await dashRes.json();
    const m = data.metrics || {};
    metricGrid.innerHTML = [
      metric('Revenue (30d)',    money(m.revenue)),
      metric('Total Orders',     m.orders),
      metric('Pending Orders',   m.pending_orders),
      metric('Customers',        m.customers),
      metric('Low Stock',        m.low_stock),
      metric('Visible Products', m.active_products),
    ].join('');
  }

  // ── Sales trend chart ──
  if (trendRes.ok) {
    const t = await trendRes.json();
    _mkChart('trend-canvas', {
      type: 'line',
      data: {
        labels: t.labels,
        datasets: [
          { label: 'Revenue (RWF)', data: t.revenue, borderColor: '#c9a84c', backgroundColor: 'rgba(201,168,76,0.12)', tension: 0.3, fill: true, yAxisID: 'y' },
          { label: 'Orders',      data: t.orders,  borderColor: '#4caf50', backgroundColor: 'rgba(76,175,80,0.08)',   tension: 0.3, fill: false, yAxisID: 'y1' },
        ],
      },
      options: { ...structuredClone(_chartDefaults),
        scales: {
          x:  { ticks: { color: '#aaa' }, grid: { color: '#222' } },
          y:  { ticks: { color: '#aaa' }, grid: { color: '#222' }, beginAtZero: true, position: 'left' },
          y1: { ticks: { color: '#4caf50' }, grid: { drawOnChartArea: false }, beginAtZero: true, position: 'right' },
        },
      },
    });
  }

  // ── Top products chart ──
  if (topRes.ok) {
    const tp = await topRes.json();
    _mkChart('top-products-canvas', {
      type: 'bar',
      data: {
        labels: tp.items.map(p => p.name),
        datasets: [{
          label: topMetric === 'revenue' ? 'Revenue (RWF)' : 'Units Sold',
          data:  tp.items.map(p => topMetric === 'revenue' ? p.revenue : p.quantity),
          backgroundColor: 'rgba(201,168,76,0.7)',
          borderColor: '#c9a84c', borderWidth: 1,
        }],
      },
      options: _chartDefaults,
    });
  }

  // ── Revenue per user chart + table ──
  if (userRes.ok) {
    const users = await userRes.json();
    _mkChart('revenue-user-canvas', {
      type: 'bar',
      data: {
        labels: users.map(u => u.username),
        datasets: [{ label: 'Total Spent (RWF)', data: users.map(u => u.total), backgroundColor: 'rgba(76,175,80,0.7)', borderColor: '#4caf50', borderWidth: 1 }],
      },
      options: _chartDefaults,
    });
    const tbody = document.getElementById('top-customers-table');
    if (tbody) {
      tbody.innerHTML = users.length
        ? users.map((u, i) => `
            <tr>
              <td>${i + 1}</td>
              <td>${esc(u.username)}</td>
              <td style="color:var(--muted);font-size:0.85rem">${esc(u.email)}</td>
              <td>${esc(u.orders)}</td>
              <td style="color:var(--gold);font-weight:600">${money(u.total)}</td>
            </tr>`).join('')
        : '<tr><td colspan="5" style="color:var(--muted)">No customer data yet.</td></tr>';
    }
  }

  // ── Revenue per vendor chart + table ──
  if (vendorRes.ok) {
    const vendors = await vendorRes.json();
    _mkChart('revenue-vendor-canvas', {
      type: 'bar',
      data: {
        labels: vendors.map(v => v.store_name),
        datasets: [
          { label: 'Gross (RWF)',      data: vendors.map(v => v.gross),      backgroundColor: 'rgba(201,168,76,0.7)', borderColor: '#c9a84c', borderWidth: 1 },
          { label: 'Commission (RWF)', data: vendors.map(v => v.commission), backgroundColor: 'rgba(244,67,54,0.5)',  borderColor: '#f44336', borderWidth: 1 },
          { label: 'Net (RWF)',        data: vendors.map(v => v.net),        backgroundColor: 'rgba(76,175,80,0.6)',  borderColor: '#4caf50', borderWidth: 1 },
        ],
      },
      options: _chartDefaults,
    });
    const tbody = document.getElementById('vendor-revenue-table');
    if (tbody) {
      tbody.innerHTML = vendors.length
        ? vendors.map(v => `
            <tr>
              <td>${esc(v.store_name)}</td>
              <td>${esc(v.orders)}</td>
              <td>${money(v.gross)}</td>
              <td style="color:#f44">${money(v.commission)} (${v.commission_rate}%)</td>
              <td style="color:#4caf50;font-weight:600">${money(v.net)}</td>
            </tr>`).join('')
        : '<tr><td colspan="5" style="color:var(--muted)">No vendor sales yet.</td></tr>';
    }
  }

  await _populateDashboardFilters();
}

async function loadCategories() {
  const res = await adminFetch('categories/');
  if (!res.ok) return;
  adminState.categories = await res.json();

  // Update product form dropdown
  const catSelect = document.getElementById('product-category');
  if (catSelect) {
    catSelect.innerHTML = adminState.categories
      .map(c => `<option value="${esc(c.id)}">${esc(c.name)}</option>`)
      .join('');
  }

  // Update category pill list
  const catList = document.getElementById('category-list');
  if (catList) {
    catList.innerHTML = adminState.categories.length
      ? adminState.categories.map(c =>
          `<span class="pill">${esc(c.name)} <small style="opacity:.6">(${esc(c.product_count || 0)})</small></span>`
        ).join('')
      : '<span style="color:var(--muted);font-size:0.9rem">No categories yet.</span>';
  }

  // Also refresh the dashboard filter dropdown
  const filterCat = document.getElementById('filter-category');
  if (filterCat) {
    const current = filterCat.value;
    filterCat.innerHTML = '<option value="">All categories</option>' +
      adminState.categories.map(c =>
        `<option value="${esc(c.slug)}" ${current === c.slug ? 'selected' : ''}>${esc(c.name)}</option>`
      ).join('');
  }
}

async function loadProducts() {
  const res = await adminFetch('products/');
  if (!res.ok) return;
  adminState.products = await res.json();
  document.getElementById('products-table').innerHTML = adminState.products.map(p => `
    <tr>
      <td>${esc(p.name)}</td>
      <td>${esc(p.category_name)}</td>
      <td>${money(p.price)}</td>
      <td>${esc(p.stock)}</td>
      <td>${p.is_active ? 'Visible' : 'Hidden'}</td>
      <td class="table-actions">
        <button class="btn btn-dark" data-id="${esc(p.id)}" onclick="editProduct(${Number(p.id)})">Edit</button>
        <button class="btn btn-dark" data-id="${esc(p.id)}" onclick="deleteProduct(${Number(p.id)})">Delete</button>
      </td>
    </tr>
  `).join('');
}

function resetProductForm() {
  document.getElementById('product-form').reset();
  document.getElementById('product-id').value = '';
  document.getElementById('product-active').checked = true;
}

function editProduct(id) {
  const p = adminState.products.find(item => item.id === id);
  if (!p) return;
  document.getElementById('product-id').value = p.id;
  document.getElementById('product-name').value = p.name;
  document.getElementById('product-slug').value = p.slug;
  document.getElementById('product-category').value = p.category;
  document.getElementById('product-price').value = p.price;
  document.getElementById('product-stock').value = p.stock;
  document.getElementById('product-shipping-days').value = p.shipping_days || 3;
  document.getElementById('product-description').value = p.description;
  document.getElementById('product-featured').checked = p.is_featured;
  document.getElementById('product-active').checked = p.is_active;
  showView('products');
}

async function deleteProduct(id) {
  if (!confirm('Delete this product?')) return;
  const res = await adminFetch(`products/${id}/`, { method: 'DELETE' });
  if (res.ok) {
    showToast('Product deleted.');
    loadProducts();
  }
}

async function saveProduct(e) {
  e.preventDefault();
  const id = document.getElementById('product-id').value;
  const fd = new FormData();
  fd.append('name', document.getElementById('product-name').value);
  fd.append('slug', document.getElementById('product-slug').value);
  fd.append('category', document.getElementById('product-category').value);
  fd.append('price', document.getElementById('product-price').value);
  fd.append('stock', document.getElementById('product-stock').value);
  fd.append('shipping_days', document.getElementById('product-shipping-days').value || '3');
  fd.append('description', document.getElementById('product-description').value);
  fd.append('is_featured', document.getElementById('product-featured').checked ? 'true' : 'false');
  fd.append('is_active', document.getElementById('product-active').checked ? 'true' : 'false');
  const image = document.getElementById('product-image').files[0];
  if (image) fd.append('image', image);
  const res = await adminFetch(id ? `products/${id}/` : 'products/', { method: id ? 'PATCH' : 'POST', body: fd });
  if (res.ok) {
    showToast('Product saved.');
    resetProductForm();
    loadProducts();
    loadDashboard();
  } else {
    showToast('Product could not be saved.');
  }
}

async function addCategory(e) {
  e.preventDefault();
  const name = document.getElementById('category-name').value.trim();
  const slug = document.getElementById('category-slug').value.trim();
  if (!name || !slug) { showToast('Name and slug are required.'); return; }
  const res = await adminFetch('categories/', {
    method: 'POST',
    body: JSON.stringify({ name, slug }),
  });
  if (res.ok) {
    e.target.reset();
    await loadCategories();
    showToast(`Category "${name}" added.`);
  } else {
    let msg = 'Category could not be saved.';
    try {
      const err = await res.clone().json();
      const flat = Object.values(err).flat().join(' ');
      if (flat) msg = flat;
    } catch {}
    showToast(msg);
  }
}

async function loadOrders() {
  const res = await adminFetch('orders/');
  if (!res.ok) return;
  const orders = await res.json();
  const statuses = ['pending', 'processing', 'shipped', 'delivered', 'cancelled'];
  document.getElementById('orders-table').innerHTML = orders.map(o => `
    <tr>
      <td>#${Number(o.id)}</td>
      <td>${esc(o.customer_name)}<br><small>${esc(o.customer_email)}</small></td>
      <td>${money(o.total_price)}</td>
      <td>
        <select class="status-select" onchange="updateOrderStatus(${Number(o.id)}, this.value)">
          ${statuses.map(s => `<option value="${s}" ${o.status === s ? 'selected' : ''}>${s}</option>`).join('')}
        </select>
      </td>
      <td>${esc(o.flutterwave_transaction_id || 'Not confirmed')}</td>
      <td><button class="btn btn-dark" onclick="downloadInvoice(${Number(o.id)})">Invoice</button></td>
    </tr>
  `).join('');
}

async function updateOrderStatus(id, status) {
  const res = await adminFetch(`orders/${id}/status/`, { method: 'PATCH', body: JSON.stringify({ status }) });
  showToast(res.ok ? 'Order updated.' : 'Order update failed.');
}

async function downloadInvoice(id) {
  const res = await adminFetch(`orders/${id}/invoice/`);
  if (!res.ok) return;
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `invoice-${id}.txt`;
  a.click();
  URL.revokeObjectURL(url);
}

// ── Customers ────────────────────────────────────────────────────────────────
let _allCustomers = [];

async function loadCustomers() {
  const res = await adminFetch('customers/');
  if (!res.ok) {
    document.getElementById('customers-table').innerHTML = '<tr><td colspan="7" class="muted">Failed to load customers.</td></tr>';
    return;
  }
  _allCustomers = await res.json();
  renderCustomers(_allCustomers);
}

function filterCustomers() {
  const q = (document.getElementById('customer-search')?.value || '').toLowerCase();
  renderCustomers(q ? _allCustomers.filter(c =>
    c.username.toLowerCase().includes(q) || (c.email || '').toLowerCase().includes(q)
  ) : _allCustomers);
}

function renderCustomers(customers) {
  const tbody = document.getElementById('customers-table');
  if (!tbody) return;
  if (!customers.length) {
    tbody.innerHTML = '<tr><td colspan="7" class="muted">No customers found.</td></tr>';
    return;
  }
  tbody.innerHTML = customers.map(c => `
    <tr>
      <td>${esc(c.username)}${c.admin_role ? `<br><small style="color:var(--gold)">${esc(c.admin_role)}</small>` : ''}</td>
      <td style="color:var(--muted);font-size:0.85rem">${esc(c.email || '—')}</td>
      <td>${esc(c.order_count || 0)}</td>
      <td style="color:var(--gold);font-weight:600">${money(c.total_spent || 0)}</td>
      <td><span class="pill ${c.is_active ? '' : 'pill-red'}">${c.is_active ? 'Active' : 'Inactive'}</span></td>
      <td style="color:var(--muted);font-size:0.8rem">${esc(formatAdminDate(c.date_joined))}</td>
      <td class="table-actions">
        <button class="btn btn-dark" onclick="openCustomerOrders(${Number(c.id)}, ${JSON.stringify(esc(c.username))})">Orders</button>
        <button class="btn btn-dark" onclick="setCustomerActive(${Number(c.id)}, ${!c.is_active})">${c.is_active ? 'Deactivate' : 'Activate'}</button>
        <button class="btn btn-dark" onclick="deleteCustomer(${Number(c.id)}, ${JSON.stringify(esc(c.username))})">Delete</button>
      </td>
    </tr>
  `).join('');
}

function formatAdminDate(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '—' : date.toLocaleDateString(undefined, { dateStyle: 'medium' });
}

async function loadPendingVendors() {
  const body = document.getElementById('pending-vendors-table');
  if (!body) return;
  body.innerHTML = '<tr><td colspan="8" class="muted">Loading vendor history…</td></tr>';
  const res = await adminFetch('vendors/');
  if (!res.ok) {
    body.innerHTML = '<tr><td colspan="8" class="muted">Unable to load vendor history.</td></tr>';
    return;
  }
  const vendors = await res.json();
  body.innerHTML = vendors.length
    ? vendors.map(vendor => {
        const isPending = vendor.status === 'pending';
        const actions = isPending
          ? `<button class="btn btn-gold" type="button" onclick="verifyVendor(${Number(vendor.id)}, 'approve')">Approve</button>
             <button class="btn btn-dark" type="button" onclick="verifyVendor(${Number(vendor.id)}, 'reject')">Reject</button>`
          : '<span class="muted">Decision recorded</span>';
        return `<tr>
        <td>${esc(vendor.store_name)}</td>
        <td>${esc(vendor.username)}</td>
        <td>${esc(vendor.email || '—')}</td>
        <td>${esc(vendor.phone || '—')}</td>
        <td><span class="pill">${esc(vendor.status)}</span></td>
        <td>${esc(formatAdminDate(vendor.created_at))}</td>
        <td>${esc(formatAdminDate(vendor.updated_at))}</td>
        <td class="table-actions">${actions}</td>
      </tr>`;
      }).join('')
    : '<tr><td colspan="8" class="muted">No vendor applications yet.</td></tr>';
}

async function verifyVendor(vendorId, action) {
  const verb = action === 'approve' ? 'approve' : 'reject';
  if (!window.confirm(`Are you sure you want to ${verb} this vendor?`)) return;
  const res = await adminFetch(`vendors/${vendorId}/verification/`, {
    method: 'PATCH',
    body: JSON.stringify({ action: verb }),
  });
  const data = await res.json();
  showToast(res.ok ? data.message : 'Vendor action failed. Please refresh and try again.');
  if (res.ok) loadPendingVendors();
}

async function deleteCustomer(id, username) {
  if (!confirm(`Delete user ${username}? This cannot be undone.`)) return;
  const res = await adminFetch(`customers/${id}/`, { method: 'DELETE' });
  if (res.ok) {
    showToast('User deleted.');
    loadCustomers();
  } else {
    const data = await res.json().catch(() => ({}));
    showToast(data.detail || 'User could not be deleted.');
  }
}

async function setCustomerActive(id, isActive) {
  const res = await adminFetch(`customers/${id}/status/`, { method: 'PATCH', body: JSON.stringify({ is_active: isActive }) });
  if (res.ok) loadCustomers();
}

async function openCustomerOrders(userId, username) {
  document.getElementById('modal-title').textContent = `Orders — ${username}`;
  document.getElementById('modal-orders-table').innerHTML = '<tr><td colspan="5">Loading…</td></tr>';
  document.getElementById('customer-orders-modal').style.display = 'flex';
  const res = await adminFetch(`customers/${userId}/orders/`);
  if (!res.ok) {
    document.getElementById('modal-orders-table').innerHTML = '<tr><td colspan="5">Failed to load.</td></tr>';
    return;
  }
  const orders = await res.json();
  document.getElementById('modal-orders-table').innerHTML = orders.length
    ? orders.map(o => `
        <tr>
          <td>#${Number(o.id)}</td>
          <td>${money(o.total_price)}</td>
          <td>${esc(o.status)}</td>
          <td>${esc(new Date(o.order_date).toLocaleDateString())}</td>
          <td>${esc(o.item_count)}</td>
        </tr>`).join('')
    : '<tr><td colspan="5" class="muted">No orders found.</td></tr>';
}

function closeCustomerOrders() {
  document.getElementById('customer-orders-modal').style.display = 'none';
}

async function loadInventory() {
  const res = await adminFetch('inventory/');
  if (!res.ok) return;
  const products = await res.json();
  document.getElementById('inventory-table').innerHTML = products.map(p => `
    <tr>
      <td>${esc(p.name)}</td>
      <td>${esc(p.stock)}</td>
      <td><span class="alert-pill ${p.stock <= 5 ? 'low' : ''}">${p.stock <= 5 ? 'Low stock' : 'OK'}</span></td>
      <td>${money(p.price)}</td>
      <td>${p.is_active ? 'Visible' : 'Hidden'}</td>
    </tr>
  `).join('');
}

async function importInventory(e) {
  e.preventDefault();
  const file = document.getElementById('inventory-file').files[0];
  if (!file) return;
  const fd = new FormData();
  fd.append('file', file);
  const res = await adminFetch('inventory/import/', { method: 'POST', body: fd });
  const data = await res.json().catch(() => ({}));
  showToast(res.ok ? `Imported ${Number(data.imported || 0)} products.` : 'Import failed.');
  loadInventory();
  loadProducts();
}

async function downloadWithToken(e, href) {
  e.preventDefault();
  const res = await adminFetch('inventory/export/');
  if (!res.ok) return false;
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'inventory.csv';
  a.click();
  URL.revokeObjectURL(url);
  return false;
}

async function loadReports() {
  const res = await adminFetch('reports/');
  if (!res.ok) return;
  const data = await res.json();
  document.getElementById('monthly-sales').innerHTML =
    data.monthly_sales.map(row =>
      `<div class="pill">${esc(row.label)}: ${money(row.revenue)} (${esc(row.orders)} orders)</div>`
    ).join('') || '<p class="muted">No sales yet.</p>';
  document.getElementById('product-performance').innerHTML =
    data.product_performance.map(row =>
      `<div class="pill">${esc(row.name)}: ${esc(row.quantity)} sold - ${money(row.revenue)}</div>`
    ).join('') || '<p class="muted">No product performance yet.</p>';
}

async function loadTransactions() {
  const res = await adminFetch('transactions/');
  if (!res.ok) return;
  const rows = await res.json();
  document.getElementById('transactions-table').innerHTML = rows.length
    ? rows.map(t => {
        const isPending = t.status === 'pending';
        const actions = isPending
          ? `<button class="btn btn-gold" onclick="transactionAction(${Number(t.order_id)}, 'confirm')">Confirm</button>
             <button class="btn btn-dark" onclick="transactionAction(${Number(t.order_id)}, 'reject')">Reject</button>`
          : `<span class="muted">${esc(t.status)}</span>`;
        return `<tr>
          <td>#${Number(t.order_id)}</td>
          <td>${esc(t.customer_name)}<br><small>${esc(t.customer_email)}</small></td>
          <td><code>${esc(t.transaction_id)}</code></td>
          <td>${money(t.amount)}</td>
          <td>${esc(t.status)}</td>
          <td>${esc(t.date)}</td>
          <td class="table-actions">${actions}</td>
        </tr>`;
      }).join('')
    : '<tr><td colspan="7" class="muted">No transactions yet.</td></tr>';
}

async function transactionAction(orderId, action) {
  const res = await adminFetch(`transactions/${orderId}/action/`, {
    method: 'PATCH',
    body: JSON.stringify({ action }),
  });
  showToast(res.ok ? `Payment ${action}ed.` : 'Action failed.');
  if (res.ok) loadTransactions();
}

async function loadSettings() {
  const res = await adminFetch('settings/');
  if (!res.ok) return;
  const data = await res.json();
  adminState.settingsDraft = JSON.parse(JSON.stringify(data));
  renderSettings(data);
}

function renderSettings(data) {
  document.getElementById('settings-grid').innerHTML = Object.entries(data).map(([key, value]) => {
    const editable = adminState.role === 'super_admin' && typeof value === 'object' && !Array.isArray(value);
    const body = editable
      ? Object.entries(value).map(([k, v]) =>
          `<label class="setting-label">${esc(k)}<input class="setting-input" data-section="${esc(key)}" data-key="${esc(k)}" value="${esc(v)}" /></label>`
        ).join('')
      : `<pre>${esc(JSON.stringify(value, null, 2))}</pre>`;
    return `<div class="setting-card"><h2>${esc(key.replaceAll('_', ' '))}</h2>${body}</div>`;
  }).join('');

  if (adminState.role === 'super_admin') {
    document.querySelectorAll('.setting-input').forEach(input => {
      input.addEventListener('input', e => {
        const { section, key } = e.target.dataset;
        if (!adminState.settingsDraft[section]) adminState.settingsDraft[section] = {};
        adminState.settingsDraft[section][key] = e.target.value;
      });
    });
  }
}

async function saveSettings() {
  const res = await adminFetch('settings/', { method: 'PATCH', body: JSON.stringify(adminState.settingsDraft) });
  showToast(res.ok ? 'Settings saved.' : 'Save failed.');
  if (res.ok) { const data = await res.json(); renderSettings(data); }
}

async function loadAll() {
  if (!isLoggedIn()) {
    document.getElementById('admin-auth-warning').style.display = 'block';
    return;
  }
  await loadAdminRole();
  const allowed = ROLE_TABS[adminState.role] || [];
  await Promise.all([
    allowed.includes('dashboard')    && loadDashboard(),
    allowed.includes('products')     && loadCategories(),
    allowed.includes('products')     && loadProducts(),
    allowed.includes('orders')       && loadOrders(),
    allowed.includes('customers')    && loadCustomers(),
    allowed.includes('vendor-mgmt')  && loadVendorManagement(),
    allowed.includes('vendors')      && loadPendingVendors(),
    allowed.includes('refunds')      && loadAdminRefunds(),
    allowed.includes('inventory')    && loadInventory(),
    allowed.includes('reports')      && loadReports(),
    allowed.includes('transactions') && loadTransactions(),
    allowed.includes('settings')     && loadSettings(),
  ].filter(Boolean));
  _startAutoRefresh();
}

document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.admin-tab').forEach(btn => btn.addEventListener('click', () => showView(btn.dataset.tab)));
  document.getElementById('product-form').addEventListener('submit', saveProduct);
  document.getElementById('category-form').addEventListener('submit', addCategory);
  document.getElementById('import-form').addEventListener('submit', importInventory);
  document.getElementById('customer-orders-modal').addEventListener('click', e => {
    if (e.target === e.currentTarget) closeCustomerOrders();
  });
  document.getElementById('vendor-detail-modal').addEventListener('click', e => {
    if (e.target === e.currentTarget) closeVendorDetail();
  });
  loadAll();
});

// ── Vendor Management ────────────────────────────────────────────────────────────────

async function loadVendorManagement() {
  const statusFilter = document.getElementById('vendor-mgmt-filter')?.value || '';
  const qs = statusFilter ? `?status=${statusFilter}` : '';

  const [listRes, analyticsRes] = await Promise.all([
    adminFetch(`vendor-management/${qs}`),
    adminFetch('vendor-analytics/'),
  ]);

  if (analyticsRes.ok) {
    const a = await analyticsRes.json();
    const metricsEl = document.getElementById('vendor-mgmt-metrics');
    if (metricsEl) {
      metricsEl.innerHTML = [
        metric('Total Vendors',    a.totals.total),
        metric('Approved',         a.totals.approved),
        metric('Pending',          a.totals.pending),
        metric('Rejected/Suspended', a.totals.rejected),
      ].join('');
    }
    _mkChart('vendor-mgmt-chart', {
      type: 'bar',
      data: {
        labels: a.top_vendors.map(v => v.store_name),
        datasets: [{ label: 'Revenue (RWF)', data: a.top_vendors.map(v => v.revenue),
          backgroundColor: 'rgba(201,168,76,0.7)', borderColor: '#c9a84c', borderWidth: 1 }],
      },
      options: _chartDefaults,
    });
  }

  if (!listRes.ok) {
    document.getElementById('vendor-mgmt-table').innerHTML = '<tr><td colspan="8" class="muted">Failed to load vendors.</td></tr>';
    return;
  }
  const vendors = await listRes.json();
  const tbody = document.getElementById('vendor-mgmt-table');
  tbody.innerHTML = vendors.length ? vendors.map(v => {
    const isPending = v.status === 'pending';
    const isApproved = v.status === 'approved';
    return `<tr>
      <td><strong>${esc(v.store_name)}</strong></td>
      <td>${esc(v.username)}</td>
      <td style="color:var(--muted);font-size:0.85rem">${esc(v.email || '—')}</td>
      <td><span class="pill ${v.status === 'approved' ? 'pill-green' : v.status === 'pending' ? 'pill-gold' : 'pill-red'}">${esc(v.status)}</span></td>
      <td>${esc(v.product_count)}</td>
      <td style="color:var(--gold);font-weight:600">${money(v.total_revenue)}</td>
      <td style="color:var(--muted);font-size:0.8rem">${esc(formatAdminDate(v.created_at))}</td>
      <td class="table-actions">
        <button class="btn btn-dark" onclick="openVendorDetail(${Number(v.id)})">Detail</button>
        ${isPending ? `<button class="btn btn-gold" onclick="vendorMgmtAction(${Number(v.id)}, 'approve')">Approve</button>` : ''}
        ${isPending ? `<button class="btn btn-dark" onclick="vendorMgmtAction(${Number(v.id)}, 'reject')">Reject</button>` : ''}
        ${isApproved ? `<button class="btn btn-dark" onclick="vendorMgmtAction(${Number(v.id)}, 'suspend')">Suspend</button>` : ''}
        <button class="btn btn-dark" onclick="deleteVendor(${Number(v.id)}, ${JSON.stringify(esc(v.store_name))})">Delete</button>
      </td>
    </tr>`;
  }).join('') : '<tr><td colspan="8" class="muted">No vendors found.</td></tr>';
}

async function vendorMgmtAction(vendorId, action) {
  if (!confirm(`${action.charAt(0).toUpperCase() + action.slice(1)} this vendor?`)) return;
  const res = await adminFetch(`vendor-management/${vendorId}/action/`, {
    method: 'PATCH',
    body: JSON.stringify({ action }),
  });
  const data = await res.json();
  showToast(res.ok ? data.message : 'Action failed.');
  if (res.ok) loadVendorManagement();
}

async function deleteVendor(vendorId, storeName) {
  if (!confirm(`Permanently delete vendor "${storeName}"? This cannot be undone.`)) return;
  const res = await adminFetch(`vendor-management/${vendorId}/action/`, { method: 'DELETE' });
  showToast(res.ok ? 'Vendor deleted.' : 'Delete failed.');
  if (res.ok) loadVendorManagement();
}

async function openVendorDetail(vendorId) {
  document.getElementById('vendor-detail-title').textContent = 'Loading…';
  document.getElementById('vendor-detail-body').innerHTML = '<p class="muted">Loading…</p>';
  document.getElementById('vendor-detail-modal').style.display = 'flex';
  const res = await adminFetch(`vendor-management/${vendorId}/`);
  if (!res.ok) {
    document.getElementById('vendor-detail-body').innerHTML = '<p class="muted">Failed to load.</p>';
    return;
  }
  const d = await res.json();
  const v = d.vendor;
  document.getElementById('vendor-detail-title').textContent = v.store_name;
  document.getElementById('vendor-detail-body').innerHTML = `
    <div class="admin-grid two" style="margin-bottom:1rem">
      <div>
        <div class="metric"><span>Owner</span><strong>${esc(v.username)}</strong></div>
        <div class="metric"><span>Email</span><strong>${esc(v.email || '—')}</strong></div>
        <div class="metric"><span>Phone</span><strong>${esc(v.phone || '—')}</strong></div>
        <div class="metric"><span>Status</span><strong>${esc(v.status)}</strong></div>
      </div>
      <div>
        <div class="metric"><span>Products</span><strong>${esc(v.product_count)}</strong></div>
        <div class="metric"><span>Total Revenue</span><strong style="color:var(--gold)">${money(v.total_revenue)}</strong></div>
        <div class="metric"><span>Registered</span><strong>${esc(formatAdminDate(v.created_at))}</strong></div>
      </div>
    </div>
    <h3 style="margin-bottom:0.5rem">Top Products</h3>
    <table class="admin-table" style="margin-bottom:1rem">
      <thead><tr><th>Product</th><th>Units Sold</th><th>Revenue</th></tr></thead>
      <tbody>${d.top_products.length
        ? d.top_products.map(p => `<tr><td>${esc(p.name)}</td><td>${esc(p.quantity)}</td><td>${money(p.revenue)}</td></tr>`).join('')
        : '<tr><td colspan="3" class="muted">No sales yet.</td></tr>'}
      </tbody>
    </table>
    <h3 style="margin-bottom:0.5rem">Payout History</h3>
    <table class="admin-table">
      <thead><tr><th>Amount</th><th>Method</th><th>Status</th><th>Requested</th></tr></thead>
      <tbody>${d.payouts.length
        ? d.payouts.map(p => `<tr><td>${money(p.amount)}</td><td>${esc(p.method)}</td><td>${esc(p.status)}</td><td>${esc(formatAdminDate(p.requested_at))}</td></tr>`).join('')
        : '<tr><td colspan="4" class="muted">No payouts yet.</td></tr>'}
      </tbody>
    </table>`;
}

function closeVendorDetail() {
  document.getElementById('vendor-detail-modal').style.display = 'none';
}

// ── Admin Refunds ───────────────────────────────────────────────────────────────────────

async function loadAdminRefunds() {
  const statusFilter = document.getElementById('admin-refund-filter')?.value || '';
  const qs = statusFilter ? `?status=${statusFilter}` : '';

  const [listRes, reportRes] = await Promise.all([
    adminFetch(`refunds/${qs}`),
    adminFetch('refunds/reports/'),
  ]);

  if (reportRes.ok) {
    const r = await reportRes.json();
    const metricsEl = document.getElementById('refund-metrics');
    if (metricsEl) {
      metricsEl.innerHTML = [
        metric('Total Refunds',  r.total_refunds),
        metric('Refund Rate',    r.refund_rate + '%'),
        metric('Pending',        r.by_status.pending || 0),
        metric('Approved',       r.by_status.approved || 0),
        metric('Processed',      r.by_status.processed || 0),
      ].join('');
    }
    _mkChart('refund-vendor-chart', {
      type: 'bar',
      data: {
        labels: r.per_vendor.map(v => v.vendor__store_name),
        datasets: [{ label: 'Refunds', data: r.per_vendor.map(v => v.count),
          backgroundColor: 'rgba(244,67,54,0.6)', borderColor: '#f44336', borderWidth: 1 }],
      },
      options: _chartDefaults,
    });
  }

  if (!listRes.ok) {
    document.getElementById('admin-refunds-table').innerHTML = '<tr><td colspan="8" class="muted">Failed to load refunds.</td></tr>';
    return;
  }
  const refunds = await listRes.json();
  const REFUND_STATUSES = ['pending', 'approved', 'rejected', 'processed'];
  document.getElementById('admin-refunds-table').innerHTML = refunds.length
    ? refunds.map(r => `
        <tr>
          <td>#${Number(r.id)}</td>
          <td>#${Number(r.order_id)}</td>
          <td>${esc(r.customer)}</td>
          <td>${esc(r.vendor || '—')}</td>
          <td style="max-width:180px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="${esc(r.reason)}">${esc(r.reason)}</td>
          <td>
            <select class="status-select" onchange="updateRefundStatus(${Number(r.id)}, this.value)">
              ${REFUND_STATUSES.map(s => `<option value="${s}" ${r.status === s ? 'selected' : ''}>${s}</option>`).join('')}
            </select>
          </td>
          <td style="color:var(--muted);font-size:0.8rem">${esc(r.created_at)}</td>
          <td class="table-actions">
            <button class="btn btn-dark" onclick="promptRefundNote(${Number(r.id)})">Note</button>
          </td>
        </tr>`).join('')
    : '<tr><td colspan="8" class="muted">No refund requests yet.</td></tr>';
}

async function updateRefundStatus(refundId, newStatus) {
  const res = await adminFetch(`refunds/${refundId}/action/`, {
    method: 'PATCH',
    body: JSON.stringify({ status: newStatus }),
  });
  showToast(res.ok ? `Refund marked as ${newStatus}.` : 'Update failed.');
  if (res.ok) loadAdminRefunds();
}

async function promptRefundNote(refundId) {
  const note = prompt('Add admin note for this refund:');
  if (note === null) return;
  const res = await adminFetch(`refunds/${refundId}/action/`, {
    method: 'PATCH',
    body: JSON.stringify({ admin_note: note }),
  });
  showToast(res.ok ? 'Note saved.' : 'Failed to save note.');
}
