const API = '/api';

// ── XSS utilities (available globally to all pages) ──────────────────────────

// esc(): encode plain text values injected into innerHTML template literals.
// Use for names, emails, IDs, labels — anything that must render as plain text.
function esc(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#x27;');
}

// safeHTML(): use when content MAY contain intentional HTML (e.g. product
// descriptions with <b>, <a>, <ul> tags). DOMPurify strips all dangerous
// tags/attributes while preserving safe formatting.
// Falls back to esc() if DOMPurify is not loaded.
function safeHTML(html) {
  if (window.DOMPurify) {
    return DOMPurify.sanitize(String(html ?? ''), {
      ALLOWED_TAGS: ['b', 'i', 'em', 'strong', 'a', 'ul', 'ol', 'li', 'br', 'p', 'span'],
      ALLOWED_ATTR: ['href', 'title', 'target'],
      ALLOW_DATA_ATTR: false,
    });
  }
  return esc(html);
}

// ── Skeleton helpers ──
function productSkeletonCard() {
  return `
    <div class="product-card skeleton">
      <div class="skeleton-image"></div>
      <div class="card-body">
        <div class="skeleton-line short"></div>
        <div class="skeleton-line"></div>
        <div class="card-actions" style="margin-top:1rem;display:flex;gap:0.5rem;">
          <div class="skeleton-button"></div>
          <div class="skeleton-button" style="width:90px"></div>
        </div>
      </div>
    </div>
  `;
}

function productSkeletonCards(count = 6) {
  return Array.from({ length: count }).map(() => productSkeletonCard()).join('');
}

function categorySkeletonPills(count = 4) {
  return Array.from({ length: count }).map(() => '<div class="skeleton-pill skeleton"></div>').join('');
}

function cartSkeletonRows(count = 3) {
  return Array.from({ length: count }).map(() => `
    <div class="cart-skeleton-row skeleton">
      <div class="skeleton-image"></div>
      <div class="skeleton-text">
        <div class="skeleton-line"></div>
        <div class="skeleton-line short"></div>
      </div>
      <div class="skeleton-cell"></div>
      <div class="skeleton-cell"></div>
    </div>
  `).join('');
}

function cartSkeletonTable(count = 3) {
  return `
    <table class="cart-table skeleton">
      <thead><tr><th></th><th></th><th></th><th></th><th></th><th></th></tr></thead>
      <tbody>
        ${Array.from({ length: count }).map(() => `
          <tr class="cart-skeleton-row">
            <td><div class="skeleton-image"></div></td>
            <td><div class="skeleton-line short"></div><div class="skeleton-line"></div></td>
            <td><div class="skeleton-cell"></div></td>
            <td><div class="skeleton-cell"></div></td>
            <td><div class="skeleton-cell"></div></td>
            <td><div class="skeleton-cell" style="width:80px;height:36px;border-radius:999px"></div></td>
          </tr>
        `).join('')}
      </tbody>
    </table>
    <div class="cart-summary skeleton" style="margin-top:2rem;">
      <div class="skeleton-line short" style="width:40%;"></div>
      <div class="skeleton-line" style="width:60%;"></div>
      <div class="skeleton-line" style="width:80%; height:24px;"></div>
    </div>
  `;
}

function vendorSkeletonTableRows(count = 4) {
  return Array.from({ length: count }).map(() => `
    <div class="vendor-skeleton-row skeleton">
      <div class="skeleton-cell" style="width:100px"></div>
      <div class="skeleton-cell" style="width:160px"></div>
      <div class="skeleton-cell" style="width:120px"></div>
      <div class="skeleton-cell" style="width:120px"></div>
    </div>
  `).join('');
}

function showLoadingPlaceholder(containerId, placeholderHtml) {
  const container = document.getElementById(containerId);
  if (!container) return;
  container.dataset.loading = 'true';
  container.innerHTML = placeholderHtml;
}

function hideLoadingPlaceholder(containerId) {
  const container = document.getElementById(containerId);
  if (!container) return;
  container.dataset.loading = 'false';
}

async function loadWithSkeleton(containerId, placeholderHtml, loadFn) {
  showLoadingPlaceholder(containerId, placeholderHtml);
  try {
    return await loadFn();
  } finally {
    hideLoadingPlaceholder(containerId);
  }
}

// ── Auth helpers ──
const getToken = () => localStorage.getItem('token');
const getRefreshToken = () => localStorage.getItem('refresh_token');

function setToken(token) {
  localStorage.setItem('token', token);
  // Server-rendered pages, including the Flutterwave return page, read this
  // cookie while API requests use the Authorization header below.
  document.cookie = `access_token=${encodeURIComponent(token)}; path=/; SameSite=Lax`;
}

function setAuthTokens(tokens) {
  if (tokens?.access) setToken(tokens.access);
  if (tokens?.refresh) localStorage.setItem('refresh_token', tokens.refresh);
}

function removeToken() {
  localStorage.removeItem('token');
  localStorage.removeItem('refresh_token');
  document.cookie = 'access_token=; path=/; max-age=0; SameSite=Lax';
}

const isLoggedIn = () => !!getToken();

let refreshPromise = null;

async function refreshAccessToken() {
  const refresh = getRefreshToken();
  if (!refresh) return false;

  // Several requests may resume at the same time after a payment redirect.
  // Use one refresh request and let all of them retry with its new access token.
  if (!refreshPromise) {
    refreshPromise = fetch(`${API}/token/refresh/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh }),
    })
      .then(async response => {
        if (!response.ok) return false;
        const tokens = await response.json();
        if (!tokens?.access) return false;
        setAuthTokens(tokens);
        return true;
      })
      .catch(() => false)
      .finally(() => { refreshPromise = null; });
  }

  return refreshPromise;
}

function authHeaders() {
  return { 'Content-Type': 'application/json', ...(getToken() ? { Authorization: `Bearer ${getToken()}` } : {}) };
}

async function apiFetch(path, options = {}, canRetry = true) {
  const { headers: requestHeaders = {}, ...requestOptions } = options;
  const res = await fetch(API + path, {
    ...requestOptions,
    headers: { ...authHeaders(), ...requestHeaders },
  });

  if (res.status === 401 && canRetry && path !== '/token/refresh/' && await refreshAccessToken()) {
    return apiFetch(path, options, false);
  }

  if (res.status === 401) {
    removeToken();
    updateNavAuth();
  }

  return res;
}

// ── Toast ──
function showToast(msg) {
  let t = document.getElementById('toast');
  if (!t) { t = document.createElement('div'); t.id = 'toast'; t.className = 'toast'; document.body.appendChild(t); }
  t.textContent = msg;
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 2500);
}

// ── Cart badge ──
async function updateCartBadge() {
  const res = await apiFetch('/cart/');
  if (!res.ok) return;
  const data = await res.json();
  const count = data.items?.reduce((s, i) => s + i.quantity, 0) || 0;
  document.querySelectorAll('.cart-badge').forEach(el => el.textContent = count || '');
}

// ── Nav auth state ──
function updateNavAuth() {
  const loginLink  = document.getElementById('nav-login');
  const logoutLink = document.getElementById('nav-logout');
  const avatarLink = document.getElementById('nav-avatar-link');
  if (!loginLink) return;
  if (isLoggedIn()) {
    loginLink.style.display = 'none';
    if (logoutLink)  logoutLink.style.display  = 'inline';
    if (avatarLink)  avatarLink.style.display  = 'inline-flex';
  } else {
    loginLink.style.display = 'inline';
    if (logoutLink)  logoutLink.style.display  = 'none';
    if (avatarLink)  avatarLink.style.display  = 'none';
  }
}

// ── Hamburger ──
function initHamburger() {
  const btn = document.getElementById('hamburger');
  const links = document.getElementById('nav-links');
  if (btn && links) btn.addEventListener('click', () => links.classList.toggle('open'));
}

// ── Add to cart ──
async function addToCart(productId, qty = 1) {
  const res = await apiFetch('/cart/', {
    method: 'POST',
    body: JSON.stringify({ product_id: productId, quantity: qty })
  });
  if (res.ok) { showToast('Added to cart!'); updateCartBadge(); }
  else showToast('Could not add to cart.');
}

// ── Remove from cart ──
async function removeFromCart(itemId, rowEl) {
  const res = await apiFetch(`/cart/${itemId}/`, { method: 'DELETE' });
  if (res.ok) { rowEl?.remove(); updateCartTotal(); showToast('Item removed.'); }
}

function updateCartTotal() {
  const prices = [...document.querySelectorAll('.item-subtotal')].map(el => parseFloat(el.dataset.value) || 0);
  const total = prices.reduce((a, b) => a + b, 0);
  const el = document.getElementById('cart-total');
  if (el) el.textContent = `£${total.toFixed(2)}`;
}

// ── Profile avatar (navbar) ──
function setNavAvatar(url) {
  const DEFAULT = `data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 40 40'%3E%3Ccircle cx='20' cy='20' r='20' fill='%23333'/%3E%3Ccircle cx='20' cy='15' r='7' fill='%23888'/%3E%3Cellipse cx='20' cy='35' rx='12' ry='8' fill='%23888'/%3E%3C/svg%3E`;
  document.querySelectorAll('.nav-avatar').forEach(img => {
    img.src = url || DEFAULT;
  });
}

const THEME_KEY = 'hardcore_theme';

function getPreferredTheme() {
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

function getSavedTheme() {
  const theme = localStorage.getItem(THEME_KEY);
  return theme === 'light' || theme === 'dark' ? theme : null;
}

function applyTheme(theme) {
  const body = document.body;
  if (theme === 'light') {
    body.classList.add('theme-light');
    body.classList.remove('theme-dark');
  } else {
    body.classList.add('theme-dark');
    body.classList.remove('theme-light');
  }

  const isDark = theme === 'dark';
  const icon  = isDark ? '☀️' : '🌙';
  const label = isDark ? 'Light Mode' : 'Dark Mode';
  const title = isDark ? 'Switch to light mode' : 'Switch to dark mode';

  // Navbar toggle
  const navToggle = document.getElementById('theme-toggle');
  if (navToggle) { navToggle.textContent = icon; navToggle.title = title; }

  // Admin / vendor sidebar toggles
  ['admin-theme-btn', 'vendor-theme-btn', 'customer-theme-btn'].forEach(id => {
    const btn = document.getElementById(id);
    if (btn) btn.textContent = `${icon} ${label}`;
  });

  document.documentElement.setAttribute('data-theme', theme);
  localStorage.setItem(THEME_KEY, theme);
}

function initTheme() {
  applyTheme(getSavedTheme() || getPreferredTheme());
}

function toggleTheme() {
  applyTheme(document.body.classList.contains('theme-dark') ? 'light' : 'dark');
}

document.addEventListener('DOMContentLoaded', () => {
  initHamburger();
  updateNavAuth();
  updateCartBadge();
  initTheme();

  document.getElementById('theme-toggle')?.addEventListener('click', toggleTheme);

  // Logout
  document.getElementById('nav-logout')?.addEventListener('click', e => {
    e.preventDefault();
    removeToken();
    document.cookie = 'access_token=; path=/; max-age=0';
    window.location.href = '/';
  });
});
