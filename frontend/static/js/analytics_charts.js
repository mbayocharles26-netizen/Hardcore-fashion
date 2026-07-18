(() => {
  const page = document.querySelector('[data-analytics-dashboard]');
  if (!page) return;

  const refreshButton = page.querySelector('[data-analytics-refresh]');
  const updatedText = page.querySelector('[data-analytics-updated]');
  const notice = page.querySelector('[data-analytics-notice]');
  const charts = { trend: null, top: null };
  let abortController = null;
  let refreshTimer = null;
  let lastRefreshAt = 0;

  const formatNumber = value => new Intl.NumberFormat().format(Number(value || 0));
  const hasChartLibrary = () => typeof window.Chart === 'function';

  function setNotice(message = '', isError = false) {
    notice.textContent = message;
    notice.classList.toggle('is-error', isError);
  }

  function elementsFor(cardName) {
    return {
      loading: page.querySelector(`[data-analytics-loading="${cardName}"]`),
      canvas: page.querySelector(`[data-analytics-chart="${cardName}"]`),
      empty: page.querySelector(`[data-analytics-empty="${cardName}"]`),
    };
  }

  function setLoading(cardName, isLoading) {
    const { loading } = elementsFor(cardName);
    loading.hidden = !isLoading;
  }

  function destroyChart(cardName) {
    if (charts[cardName]) {
      charts[cardName].destroy();
      charts[cardName] = null;
    }
  }

  function showEmpty(cardName, message) {
    const { canvas, empty } = elementsFor(cardName);
    destroyChart(cardName);
    canvas.hidden = true;
    empty.textContent = message;
    empty.hidden = false;
  }

  function showChart(cardName) {
    const { canvas, empty } = elementsFor(cardName);
    canvas.hidden = false;
    empty.hidden = true;
  }

  async function fetchJson(url, signal) {
    const token = typeof getToken === 'function' ? getToken() : null;
    const response = await fetch(url, {
      credentials: 'same-origin',
      headers: {
        Accept: 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      signal,
    });
    if (!response.ok) {
      throw new Error(response.status === 401 || response.status === 403
        ? 'Your account is not authorised to view analytics.'
        : 'Analytics data could not be loaded.');
    }
    return response.json();
  }

  function renderTrend(data) {
    const labels = Array.isArray(data.labels) ? data.labels : [];
    const values = Array.isArray(data.revenue) ? data.revenue : [];
    if (!labels.length || !values.length) {
      showEmpty('trend', 'No data available.');
      return;
    }

    showChart('trend');
    destroyChart('trend');
    charts.trend = new Chart(elementsFor('trend').canvas, {
      type: 'line',
      data: {
        labels,
        datasets: [{
          label: page.dataset.trendLabel || 'Revenue',
          data: values,
          borderColor: '#c9a84c',
          backgroundColor: 'rgba(201, 168, 76, .16)',
          borderWidth: 2,
          pointRadius: 3,
          pointHoverRadius: 5,
          tension: .3,
          fill: true,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { intersect: false, mode: 'index' },
        plugins: {
          legend: { labels: { color: '#d7d7d7' } },
          tooltip: { callbacks: { label: item => `${item.dataset.label}: ${formatNumber(item.parsed.y)}` } },
        },
        scales: {
          x: { ticks: { color: '#a8a8a8', maxRotation: 0, autoSkip: true }, grid: { color: 'rgba(255,255,255,.06)' } },
          y: { beginAtZero: true, ticks: { color: '#a8a8a8', callback: value => formatNumber(value) }, grid: { color: 'rgba(255,255,255,.08)' } },
        },
      },
    });
  }

  function renderTopProducts(data) {
    const items = Array.isArray(data.items) ? data.items : [];
    const valueKey = page.dataset.topKey || 'revenue';
    if (!items.length) {
      showEmpty('top', 'No data available.');
      return;
    }

    showChart('top');
    destroyChart('top');
    charts.top = new Chart(elementsFor('top').canvas, {
      type: 'bar',
      data: {
        labels: items.map(item => item.name || 'Unknown product'),
        datasets: [{
          label: page.dataset.topLabel || 'Revenue',
          data: items.map(item => Number(item[valueKey] || 0)),
          backgroundColor: 'rgba(201, 168, 76, .68)',
          borderColor: '#c9a84c',
          borderWidth: 1,
          borderRadius: 5,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        indexAxis: 'y',
        plugins: {
          legend: { labels: { color: '#d7d7d7' } },
          tooltip: { callbacks: { label: item => `${item.dataset.label}: ${formatNumber(item.parsed.x)}` } },
        },
        scales: {
          x: { beginAtZero: true, ticks: { color: '#a8a8a8', callback: value => formatNumber(value) }, grid: { color: 'rgba(255,255,255,.08)' } },
          y: { ticks: { color: '#d7d7d7' }, grid: { display: false } },
        },
      },
    });
  }

  async function refreshAnalytics() {
    if (!hasChartLibrary()) {
      showEmpty('trend', 'Charts could not be loaded. Please refresh the page.');
      showEmpty('top', 'Charts could not be loaded. Please refresh the page.');
      return;
    }

    if (abortController) abortController.abort();
    const controller = new AbortController();
    abortController = controller;
    refreshButton.disabled = true;
    refreshButton.textContent = 'Refreshing…';
    ['trend', 'top'].forEach(card => setLoading(card, true));
    setNotice('Refreshing analytics…');

    const [trendResult, topResult] = await Promise.allSettled([
      fetchJson(page.dataset.trendUrl, controller.signal),
      fetchJson(page.dataset.topUrl, controller.signal),
    ]);

    // A newer manual or timed refresh has started, so it owns the UI state.
    if (abortController !== controller) return;

    if (trendResult.status === 'fulfilled') {
      renderTrend(trendResult.value);
    } else if (trendResult.reason.name !== 'AbortError') {
      showEmpty('trend', 'No data available. Please try again.');
    }

    if (topResult.status === 'fulfilled') {
      renderTopProducts(topResult.value);
    } else if (topResult.reason.name !== 'AbortError') {
      showEmpty('top', 'No data available. Please try again.');
    }

    const failures = [trendResult, topResult].filter(result => result.status === 'rejected' && result.reason.name !== 'AbortError');
    if (failures.length) {
      const message = failures[0].reason.message || 'Analytics data could not be loaded.';
      setNotice(message, true);
    } else if (trendResult.status === 'fulfilled' || topResult.status === 'fulfilled') {
      lastRefreshAt = Date.now();
      updatedText.textContent = `Last updated ${new Date(lastRefreshAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
      setNotice('');
    }

    ['trend', 'top'].forEach(card => setLoading(card, false));
    refreshButton.disabled = false;
    refreshButton.textContent = 'Refresh data';
  }

  refreshButton.addEventListener('click', refreshAnalytics);
  refreshAnalytics();
  refreshTimer = window.setInterval(refreshAnalytics, 60_000);

  document.addEventListener('visibilitychange', () => {
    if (!document.hidden && Date.now() - lastRefreshAt > 60_000) refreshAnalytics();
  });
  window.addEventListener('beforeunload', () => {
    if (refreshTimer) window.clearInterval(refreshTimer);
    if (abortController) abortController.abort();
  });
})();
