/* ==========================================================================
   Unithread App — Frontend SPA JavaScript
   Handles routing, API calls, and page rendering.
   ========================================================================== */

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------
const state = {
    user: window.__USER__,
    role: window.__ROLE__,
    page: 'dashboard',
    constants: null,
    chatGroupId: null,
    chatPollTimer: null,
    calYear: new Date().getFullYear(),
    calMonth: new Date().getMonth() + 1,
    selectedProjectId: null,
};

// ---------------------------------------------------------------------------
// API helper
// ---------------------------------------------------------------------------

/** Read CSRF token from cookie */
function getCsrfToken() {
    const match = document.cookie.match(/csrf_token=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : '';
}

async function api(url, opts = {}) {
    const headers = { 'Content-Type': 'application/json', ...opts.headers };
    if (opts.method && opts.method !== 'GET') {
        headers['X-CSRFToken'] = getCsrfToken();
    }
    const res = await fetch(url, { headers, ...opts });
    if (res.status === 401) { window.location.href = '/'; return null; }
    return res.json();
}

async function apiForm(url, formData) {
    const res = await fetch(url, { method: 'POST', body: formData });
    if (res.status === 401) { window.location.href = '/'; return null; }
    return res.json();
}

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------

/** Escape HTML to prevent XSS */
function escHtml(str) {
    if (str === null || str === undefined) return '';
    const div = document.createElement('div');
    div.textContent = String(str);
    return div.innerHTML;
}

function fmt(n) {
    return Number(n || 0).toLocaleString('sv-SE', { minimumFractionDigits: 0, maximumFractionDigits: 0 });
}
function fmtDate(d) {
    if (!d) return '—';
    return d;
}
function toast(msg, type = 'info') {
    const c = document.getElementById('toastContainer');
    const t = document.createElement('div');
    t.className = `toast ${type}`;
    t.textContent = msg;
    c.appendChild(t);
    setTimeout(() => t.remove(), 3000);
}
function el(id) { return document.getElementById(id); }

function statusTag(s) {
    const map = { inlamnat: ['Inväntar', 'warning'], godkannt: ['Godkänt', 'success'], avvisat: ['Avvisat', 'danger'] };
    const [label, cls] = map[s] || [s, 'neutral'];
    return `<span class="tag tag-${cls}">${label}</span>`;
}

function priorityTag(p) {
    const map = { 'Hög': 'priority-high', 'Medel': 'priority-med', 'Låg': 'priority-low' };
    return `<span class="todo-priority ${map[p] || 'priority-med'}">${p}</span>`;
}

function calEventClass(type) {
    const map = { 'Möte': 'mote', 'Deadline': 'deadline', 'Påminnelse': 'paminnelse', 'Betalning': 'betalning', 'Projektdeadline': 'projektdeadline' };
    return map[type] || 'ovrigt';
}

// ---------------------------------------------------------------------------
// Navigation
// ---------------------------------------------------------------------------
function toggleSidebar() {
    const sb = document.getElementById('sidebar');
    const ov = document.getElementById('sidebarOverlay');
    sb.classList.toggle('open');
    ov.classList.toggle('show');
}

function navigate(page) {
    state.page = page;
    document.querySelectorAll('.nav-item').forEach(n => {
        n.classList.toggle('active', n.dataset.page === page);
    });
    if (state.chatPollTimer) { clearInterval(state.chatPollTimer); state.chatPollTimer = null; }
    // Close mobile sidebar
    document.getElementById('sidebar')?.classList.remove('open');
    document.getElementById('sidebarOverlay')?.classList.remove('show');
    renderPage();
}

async function handleLogout() {
    await api('/api/logout', { method: 'POST' });
    window.location.href = '/';
}

// ---------------------------------------------------------------------------
// Modal
// ---------------------------------------------------------------------------
function openModal(title, bodyHtml, subtitle) {
    el('modalHeader').innerHTML = `<h2>${title}</h2>${subtitle ? `<p>${subtitle}</p>` : ''}`;
    el('modalBody').innerHTML = bodyHtml;
    el('modalOverlay').classList.add('show');
}
function closeModal() {
    el('modalOverlay').classList.remove('show');
}

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------
async function init() {
    state.constants = await api('/api/constants');
    renderPage();
}

function renderPage() {
    const content = el('pageContent');
    content.innerHTML = '<div class="spinner"></div>';
    const renderers = {
        dashboard: renderDashboard,
        expenses: renderExpenses,
        revenue: renderRevenue,
        budget: renderBudget,
        receipts: renderReceipts,
        customers: renderCustomers,
        pipeline: renderPipeline,
        quotes: renderQuotes,
        invoices: renderInvoices,
        integrations: renderIntegrations,
        calendar: renderCalendar,
        chat: renderChat,
        projects: renderProjects,
        settings: renderSettings,
    };
    (renderers[state.page] || renderDashboard)();
}

// ===== DASHBOARD ==========================================================
async function renderDashboard() {
    const data = await api('/api/dashboard');
    if (!data) return;
    const c = state.constants;
    const bizCards = c.businesses.map(biz => {
        const s = data.summary[biz] || {};
        return `
        <div class="metric-card primary">
            <div class="metric-label">${biz}</div>
            <div class="metric-value">${fmt(s.total_revenue - s.total_expenses)} kr</div>
            <div class="metric-sub">Resultat (totalt)</div>
        </div>
        <div class="metric-card success">
            <div class="metric-label">${biz} — Intäkter mån</div>
            <div class="metric-value">${fmt(s.month_revenue)} kr</div>
            <div class="metric-sub">Denna månad</div>
        </div>
        <div class="metric-card danger">
            <div class="metric-label">${biz} — Utgifter mån</div>
            <div class="metric-value">${fmt(s.month_expenses)} kr</div>
            <div class="metric-sub">Denna månad</div>
        </div>`;
    }).join('');

    const pendingHtml = data.pending_receipts > 0
        ? `<div class="metric-card warning">
            <div class="metric-label">Väntande kvitton</div>
            <div class="metric-value">${data.pending_receipts}</div>
            <div class="metric-sub">Inväntar granskning</div>
           </div>` : '';

    const activityHtml = (data.recent_activity || []).map(a =>
        `<div class="activity-item">
            <div class="activity-dot"></div>
            <div>
                <div><span class="activity-user">${a.user}</span> ${a.action}</div>
                <div class="activity-time">${a.timestamp}${a.details ? ' — ' + a.details : ''}</div>
            </div>
        </div>`
    ).join('') || '<div class="text-muted text-sm">Ingen aktivitet ännu</div>';

    // Build budget vs actual chart sections
    const bva = data.budget_vs_actual || {};
    let budgetChartHtml = '';
    const budgetChartIds = [];
    for (const biz of c.businesses) {
        const bizBva = bva[biz] || {};
        const cats = Object.keys(bizBva);
        if (cats.length) {
            const chartId = `budgetChart_${biz.replace(/[^a-zA-Z]/g,'')}`;
            budgetChartIds.push({ id: chartId, biz, data: bizBva });
            budgetChartHtml += `
            <div class="card mt-4">
                <div class="card-header"><h3>Budget vs Faktiskt — ${biz}</h3></div>
                <div class="card-body"><div class="chart-container" style="height:280px"><canvas id="${chartId}"></canvas></div></div>
            </div>`;
        }
    }

    el('pageContent').innerHTML = `
        <div class="page-header">
            <h1>Dashboard</h1>
            <p>Välkommen, ${state.user}. Här är en översikt av verksamheten.</p>
        </div>
        <div class="metrics-grid">${bizCards}${pendingHtml}</div>
        <div class="grid-2 mt-4">
            <div class="card">
                <div class="card-header"><h3>Intäkter vs Utgifter (6 mån)</h3></div>
                <div class="card-body"><div class="chart-container"><canvas id="trendChart"></canvas></div></div>
            </div>
            <div class="card">
                <div class="card-header"><h3>Månatlig vinst</h3></div>
                <div class="card-body"><div class="chart-container"><canvas id="profitChart"></canvas></div></div>
            </div>
        </div>
        <div class="grid-2 mt-4">
            <div class="card">
                <div class="card-header"><h3>Utgifter per kategori</h3></div>
                <div class="card-body"><div class="chart-container"><canvas id="catChart"></canvas></div></div>
            </div>
            <div class="card">
                <div class="card-header"><h3>Intäkter per kategori</h3></div>
                <div class="card-body"><div class="chart-container"><canvas id="revCatChart"></canvas></div></div>
            </div>
        </div>
        ${budgetChartHtml}
        <div id="integrationsSummaryDash"></div>
        <div class="card mt-4">
            <div class="card-header"><h3>Senaste aktivitet</h3></div>
            <div class="card-body">${activityHtml}</div>
        </div>`;

    // Trend chart (bar — revenue vs expenses)
    const labels = data.monthly_trend.map(m => m.month);
    new Chart(el('trendChart'), {
        type: 'bar',
        data: {
            labels,
            datasets: [
                { label: 'Intäkter', data: data.monthly_trend.map(m => m.revenue), backgroundColor: 'rgba(16,185,129,0.7)', borderRadius: 6 },
                { label: 'Utgifter', data: data.monthly_trend.map(m => m.expenses), backgroundColor: 'rgba(239,68,68,0.7)', borderRadius: 6 },
            ],
        },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom' } }, scales: { y: { beginAtZero: true } } },
    });

    // Profit line chart
    const profitData = data.monthly_trend.map(m => m.revenue - m.expenses);
    new Chart(el('profitChart'), {
        type: 'line',
        data: {
            labels,
            datasets: [{
                label: 'Vinst/Förlust',
                data: profitData,
                borderColor: '#6366f1',
                backgroundColor: 'rgba(99,102,241,0.1)',
                fill: true,
                tension: 0.4,
                pointBackgroundColor: profitData.map(v => v >= 0 ? '#10b981' : '#ef4444'),
                pointRadius: 5,
                pointHoverRadius: 7,
            }],
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: { legend: { position: 'bottom' } },
            scales: { y: { beginAtZero: false } },
        },
    });

    // Category doughnut (expenses)
    const catLabels = Object.keys(data.category_breakdown || {});
    const catValues = Object.values(data.category_breakdown || {});
    const chartColors = ['#6366f1', '#8b5cf6', '#06b6d4', '#10b981', '#f59e0b', '#ef4444', '#ec4899', '#14b8a6', '#64748b'];
    if (catLabels.length) {
        new Chart(el('catChart'), {
            type: 'doughnut',
            data: {
                labels: catLabels,
                datasets: [{ data: catValues, backgroundColor: chartColors }],
            },
            options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'right' } } },
        });
    }

    // Revenue category doughnut
    const revCatLabels = Object.keys(data.revenue_breakdown || {});
    const revCatValues = Object.values(data.revenue_breakdown || {});
    if (revCatLabels.length) {
        new Chart(el('revCatChart'), {
            type: 'doughnut',
            data: {
                labels: revCatLabels,
                datasets: [{ data: revCatValues, backgroundColor: ['#10b981', '#34d399', '#6ee7b7', '#a7f3d0', '#06b6d4', '#67e8f9'] }],
            },
            options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'right' } } },
        });
    } else {
        el('revCatChart')?.parentElement?.closest('.card')?.insertAdjacentHTML('beforeend',
            '<div class="empty-state" style="padding:20px"><p class="text-muted text-sm">Inga intäkter registrerade i år</p></div>');
    }

    // Budget vs Actual bar charts per business
    for (const bc of budgetChartIds) {
        const cats = Object.keys(bc.data);
        new Chart(el(bc.id), {
            type: 'bar',
            data: {
                labels: cats,
                datasets: [
                    { label: 'Budget', data: cats.map(c => bc.data[c].budget), backgroundColor: 'rgba(99,102,241,0.5)', borderRadius: 4 },
                    { label: 'Förbrukat', data: cats.map(c => bc.data[c].spent), backgroundColor: cats.map(c => bc.data[c].spent > bc.data[c].budget && bc.data[c].budget > 0 ? 'rgba(239,68,68,0.7)' : 'rgba(16,185,129,0.7)'), borderRadius: 4 },
                ],
            },
            options: {
                responsive: true, maintainAspectRatio: false, indexAxis: 'y',
                plugins: { legend: { position: 'bottom' } },
                scales: { x: { beginAtZero: true } },
            },
        });
    }

    // Budget warnings — show toasts for overspending
    checkBudgetWarnings();

    // Integration summary on dashboard
    loadDashboardIntegrations();
}

async function loadDashboardIntegrations() {
    const summary = await api('/api/integrations/summary');
    if (!summary || !summary.length) return;
    const cards = summary.map(p => {
        const statusDot = p.last_sync_status === 'success' ? '🟢'
            : p.last_sync_status === 'error' ? '🔴' : '🟡';
        return `
        <div class="integration-dash-card">
            <div class="integration-dash-icon">${p.icon}</div>
            <div class="integration-dash-info">
                <div class="integration-dash-name">${escHtml(p.display_name)} ${statusDot}</div>
                <div class="integration-dash-metrics">
                    ${p.month_expenses > 0 ? `<span class="text-danger">−${fmt(p.month_expenses)} kr</span>` : ''}
                    ${p.month_revenue > 0 ? `<span class="text-success">+${fmt(p.month_revenue)} kr</span>` : ''}
                    ${p.month_expenses === 0 && p.month_revenue === 0 ? '<span class="text-muted">Ingen data denna månad</span>' : ''}
                </div>
                ${p.last_sync ? `<div class="text-muted text-xs">Senast: ${p.last_sync}</div>` : ''}
            </div>
        </div>`;
    }).join('');

    el('integrationsSummaryDash').innerHTML = `
        <div class="card mt-4">
            <div class="card-header">
                <h3>🔗 Integrationer</h3>
                <button class="btn btn-ghost btn-sm" onclick="navigate('integrations')">Hantera →</button>
            </div>
            <div class="card-body">
                <div class="integration-dash-grid">${cards}</div>
            </div>
        </div>`;
}

async function checkBudgetWarnings() {
    const warnings = await api('/api/budget/warnings');
    if (!warnings || !warnings.length) return;
    // Show up to 3 most critical warnings as toasts
    warnings.slice(0, 3).forEach(w => {
        const icon = w.level === 'danger' ? '🚨' : '⚠️';
        const msg = w.kategori === 'Total'
            ? `${icon} ${w.bolag}: Total budget ${Math.round(w.pct)}% förbrukad!`
            : `${icon} ${w.bolag} — ${w.kategori}: ${Math.round(w.pct)}% av budget`;
        toast(msg, w.level === 'danger' ? 'error' : 'warning');
    });
}

// ===== EXPENSES ===========================================================
async function renderExpenses() {
    const c = state.constants;
    el('pageContent').innerHTML = `
        <div class="page-header">
            <div class="page-header-row">
                <div><h1>Utgifter</h1><p>Hantera företagets utgifter</p></div>
                <div class="flex gap-2">
                    <button class="btn btn-secondary" onclick="exportExpenses('excel')">📥 Excel</button>
                    <button class="btn btn-secondary" onclick="exportExpenses('pdf')">📄 PDF</button>
                    <button class="btn btn-primary" onclick="openExpenseModal()">+ Ny utgift</button>
                </div>
            </div>
        </div>
        <div class="filter-bar">
            <select id="expBolag" onchange="loadExpenses()">
                <option value="Alla">Alla verksamheter</option>
                ${c.businesses.map(b => `<option>${b}</option>`).join('')}
            </select>
            <input type="month" id="expMonth" onchange="loadExpenses()">
        </div>
        <div class="card"><div class="table-wrapper" id="expTable"><div class="spinner"></div></div></div>`;
    loadExpenses();
}

async function loadExpenses() {
    const bolag = el('expBolag')?.value || 'Alla';
    const month = el('expMonth')?.value || '';
    const params = new URLSearchParams();
    if (bolag !== 'Alla') params.set('bolag', bolag);
    if (month) params.set('month', month);
    const data = await api(`/api/expenses?${params}`);
    if (!data) return;
    const total = data.reduce((s, e) => s + Number(e.belopp || 0), 0);
    if (!data.length) {
        el('expTable').innerHTML = '<div class="empty-state"><h3>Inga utgifter</h3><p>Lägg till din första utgift med knappen ovan.</p></div>';
        return;
    }
    el('expTable').innerHTML = `
        <table>
            <thead><tr><th>Datum</th><th>Bolag</th><th>Kategori</th><th>Beskrivning</th><th>Leverantör</th><th class="text-right">Belopp</th><th class="text-right">Moms</th><th></th></tr></thead>
            <tbody>${data.map(e => `
                <tr>
                    <td>${fmtDate(e.datum)}</td>
                    <td><span class="tag tag-primary">${escHtml(e.bolag)}</span></td>
                    <td>${escHtml(e.kategori)}</td>
                    <td>${escHtml(e.beskrivning) || '—'}</td>
                    <td>${escHtml(e.leverantor) || '—'}</td>
                    <td class="text-right font-mono">${fmt(e.belopp)} kr</td>
                    <td class="text-right font-mono text-muted">${fmt(e.moms_belopp)} kr</td>
                    <td><button class="btn btn-ghost btn-xs" onclick="deleteExpense('${escHtml(e.id)}')">✕</button></td>
                </tr>`).join('')}
            </tbody>
            <tfoot><tr><td colspan="5" class="text-right" style="font-weight:700;padding:14px 16px">Totalt</td><td class="text-right font-mono" style="font-weight:700;padding:14px 16px">${fmt(total)} kr</td><td></td><td></td></tr></tfoot>
        </table>`;
}

function openExpenseModal() {
    const c = state.constants;
    openModal('Ny utgift', `
        <form onsubmit="return submitExpense(event)">
            <div class="form-row">
                <div class="form-group"><label>Verksamhet</label><select class="form-control" id="newExpBolag">${c.businesses.map(b => `<option>${b}</option>`).join('')}</select></div>
                <div class="form-group"><label>Datum</label><input type="date" class="form-control" id="newExpDatum" value="${new Date().toISOString().slice(0,10)}"></div>
            </div>
            <div class="form-row">
                <div class="form-group"><label>Kategori</label><select class="form-control" id="newExpKat">${c.expense_categories.map(k => `<option>${k}</option>`).join('')}</select></div>
                <div class="form-group"><label>Momssats (%)</label><select class="form-control" id="newExpMoms">${c.vat_rates.map(v => `<option ${v===25?'selected':''}>${v}</option>`).join('')}</select></div>
            </div>
            <div class="form-group"><label>Beskrivning</label><input class="form-control" id="newExpBesk" placeholder="Kort beskrivning"></div>
            <div class="form-row">
                <div class="form-group"><label>Leverantör</label><input class="form-control" id="newExpLev" placeholder="Leverantörsnamn"></div>
                <div class="form-group"><label>Belopp (kr)</label><input type="number" step="0.01" class="form-control" id="newExpBelopp" required placeholder="0"></div>
            </div>
            <button type="submit" class="btn btn-primary mt-4" style="width:100%">Spara utgift</button>
        </form>
    `);
}

async function submitExpense(e) {
    e.preventDefault();
    await api('/api/expenses', {
        method: 'POST',
        body: JSON.stringify({
            bolag: el('newExpBolag').value,
            datum: el('newExpDatum').value,
            kategori: el('newExpKat').value,
            beskrivning: el('newExpBesk').value,
            leverantor: el('newExpLev').value,
            belopp: el('newExpBelopp').value,
            moms_sats: el('newExpMoms').value,
        }),
    });
    closeModal();
    toast('Utgift tillagd', 'success');
    loadExpenses();
}

async function deleteExpense(id) {
    if (!confirm('Ta bort denna utgift?')) return;
    await api(`/api/expenses/${id}`, { method: 'DELETE' });
    toast('Utgift borttagen', 'success');
    loadExpenses();
}

// ===== REVENUE ============================================================
async function renderRevenue() {
    const c = state.constants;
    el('pageContent').innerHTML = `
        <div class="page-header">
            <div class="page-header-row">
                <div><h1>Intäkter</h1><p>Hantera företagets intäkter</p></div>
                <div class="flex gap-2">
                    <button class="btn btn-secondary" onclick="exportRevenue('excel')">📥 Excel</button>
                    <button class="btn btn-secondary" onclick="exportRevenue('pdf')">📄 PDF</button>
                    <button class="btn btn-primary" onclick="openRevenueModal()">+ Ny intäkt</button>
                </div>
            </div>
        </div>
        <div class="filter-bar">
            <select id="revBolag" onchange="loadRevenue()">
                <option value="Alla">Alla verksamheter</option>
                ${c.businesses.map(b => `<option>${b}</option>`).join('')}
            </select>
            <input type="month" id="revMonth" onchange="loadRevenue()">
        </div>
        <div class="card"><div class="table-wrapper" id="revTable"><div class="spinner"></div></div></div>`;
    loadRevenue();
}

async function loadRevenue() {
    const bolag = el('revBolag')?.value || 'Alla';
    const month = el('revMonth')?.value || '';
    const params = new URLSearchParams();
    if (bolag !== 'Alla') params.set('bolag', bolag);
    if (month) params.set('month', month);
    const data = await api(`/api/revenue?${params}`);
    if (!data) return;
    const total = data.reduce((s, r) => s + Number(r.belopp || 0), 0);
    if (!data.length) {
        el('revTable').innerHTML = '<div class="empty-state"><h3>Inga intäkter</h3><p>Lägg till din första intäkt med knappen ovan.</p></div>';
        return;
    }
    el('revTable').innerHTML = `
        <table>
            <thead><tr><th>Datum</th><th>Bolag</th><th>Kategori</th><th>Beskrivning</th><th>Kund</th><th class="text-right">Belopp</th><th></th></tr></thead>
            <tbody>${data.map(r => `
                <tr>
                    <td>${fmtDate(r.datum)}</td>
                    <td><span class="tag tag-primary">${escHtml(r.bolag)}</span></td>
                    <td>${escHtml(r.kategori)}</td>
                    <td>${escHtml(r.beskrivning) || '—'}</td>
                    <td>${escHtml(r.kund) || '—'}</td>
                    <td class="text-right font-mono">${fmt(r.belopp)} kr</td>
                    <td><button class="btn btn-ghost btn-xs" onclick="deleteRevenue('${escHtml(r.id)}')">✕</button></td>
                </tr>`).join('')}
            </tbody>
            <tfoot><tr><td colspan="5" class="text-right" style="font-weight:700;padding:14px 16px">Totalt</td><td class="text-right font-mono" style="font-weight:700;padding:14px 16px">${fmt(total)} kr</td><td></td></tr></tfoot>
        </table>`;
}

function openRevenueModal() {
    const c = state.constants;
    openModal('Ny intäkt', `
        <form onsubmit="return submitRevenue(event)">
            <div class="form-row">
                <div class="form-group"><label>Verksamhet</label><select class="form-control" id="newRevBolag">${c.businesses.map(b => `<option>${b}</option>`).join('')}</select></div>
                <div class="form-group"><label>Datum</label><input type="date" class="form-control" id="newRevDatum" value="${new Date().toISOString().slice(0,10)}"></div>
            </div>
            <div class="form-group"><label>Kategori</label><select class="form-control" id="newRevKat">${c.revenue_categories.map(k => `<option>${k}</option>`).join('')}</select></div>
            <div class="form-group"><label>Beskrivning</label><input class="form-control" id="newRevBesk" placeholder="Kort beskrivning"></div>
            <div class="form-row">
                <div class="form-group"><label>Kund</label><input class="form-control" id="newRevKund" placeholder="Kundnamn"></div>
                <div class="form-group"><label>Belopp (kr)</label><input type="number" step="0.01" class="form-control" id="newRevBelopp" required placeholder="0"></div>
            </div>
            <button type="submit" class="btn btn-primary mt-4" style="width:100%">Spara intäkt</button>
        </form>
    `);
}

async function submitRevenue(e) {
    e.preventDefault();
    await api('/api/revenue', {
        method: 'POST',
        body: JSON.stringify({
            bolag: el('newRevBolag').value,
            datum: el('newRevDatum').value,
            kategori: el('newRevKat').value,
            beskrivning: el('newRevBesk').value,
            kund: el('newRevKund').value,
            belopp: el('newRevBelopp').value,
        }),
    });
    closeModal();
    toast('Intäkt tillagd', 'success');
    loadRevenue();
}

async function deleteRevenue(id) {
    if (!confirm('Ta bort denna intäkt?')) return;
    await api(`/api/revenue/${id}`, { method: 'DELETE' });
    toast('Intäkt borttagen', 'success');
    loadRevenue();
}

// ===== BUDGET =============================================================
async function renderBudget() {
    const c = state.constants;
    const [budgetData, expenses, warnings] = await Promise.all([
        api('/api/budget'),
        api('/api/expenses'),
        api('/api/budget/warnings'),
    ]);

    const year = new Date().getFullYear().toString();
    let html = `<div class="page-header"><h1>Budget & Ekonomi</h1><p>Sätt och följ upp budgetar per verksamhet</p></div>`;

    // Warning banner
    if (warnings && warnings.length) {
        html += `<div class="budget-warnings mb-4">`;
        for (const w of warnings) {
            const icon = w.level === 'danger' ? '🚨' : '⚠️';
            const cls = w.level === 'danger' ? 'alert-danger' : 'alert-warning';
            const label = w.kategori === 'Total'
                ? `${w.bolag}: Total budget <strong>${Math.round(w.pct)}%</strong> förbrukad (${fmt(w.spent)} / ${fmt(w.budget)} kr)`
                : `${w.bolag} — ${w.kategori}: <strong>${Math.round(w.pct)}%</strong> av budget (${fmt(w.spent)} / ${fmt(w.budget)} kr)`;
            html += `<div class="alert ${cls}">${icon} ${label}</div>`;
        }
        html += `</div>`;
    }

    for (const biz of c.businesses) {
        const b = budgetData[biz] || { total: 0, kategorier: {} };
        const bizExp = (expenses || []).filter(e => e.bolag === biz && String(e.datum || '').startsWith(year));
        const totalSpent = bizExp.reduce((s, e) => s + Number(e.belopp || 0), 0);
        const pct = b.total > 0 ? Math.min(100, (totalSpent / b.total) * 100) : 0;
        const barClass = pct > 90 ? 'danger' : pct > 70 ? 'warning' : '';

        const catRows = c.expense_categories.map(cat => {
            const catBudget = Number(b.kategorier[cat] || 0);
            const catSpent = bizExp.filter(e => e.kategori === cat).reduce((s, e) => s + Number(e.belopp || 0), 0);
            const catPct = catBudget > 0 ? Math.min(100, (catSpent / catBudget) * 100) : 0;
            return `<tr>
                <td>${cat}</td>
                <td class="text-right font-mono">${fmt(catBudget)} kr</td>
                <td class="text-right font-mono">${fmt(catSpent)} kr</td>
                <td><div class="progress-bar"><div class="progress-bar-fill ${catPct > 90 ? 'danger' : catPct > 70 ? 'warning' : ''}" style="width:${catPct}%"></div></div></td>
            </tr>`;
        }).join('');

        html += `
        <div class="card mb-6">
            <div class="card-header">
                <h3>${biz}</h3>
                <button class="btn btn-secondary btn-sm" onclick="openBudgetModal('${biz}', ${JSON.stringify(b).replace(/"/g, '&quot;')})">Redigera</button>
            </div>
            <div class="card-body">
                <div class="flex items-center justify-between mb-4">
                    <div><span class="text-sm text-muted">Total budget:</span> <strong>${fmt(b.total)} kr</strong></div>
                    <div><span class="text-sm text-muted">Förbrukat:</span> <strong>${fmt(totalSpent)} kr</strong> (${Math.round(pct)}%)</div>
                </div>
                <div class="progress-bar mb-6" style="height:12px"><div class="progress-bar-fill ${barClass}" style="width:${pct}%"></div></div>
                <table>
                    <thead><tr><th>Kategori</th><th class="text-right">Budget</th><th class="text-right">Förbrukat</th><th style="width:200px">Status</th></tr></thead>
                    <tbody>${catRows}</tbody>
                </table>
            </div>
        </div>`;
    }

    el('pageContent').innerHTML = html;
}

function openBudgetModal(biz, current) {
    const c = state.constants;
    const catInputs = c.expense_categories.map(cat => {
        const val = (current.kategorier || {})[cat] || 0;
        return `<div class="form-row"><div class="form-group"><label>${cat}</label><input type="number" class="form-control" id="budCat_${cat.replace(/[^a-zA-Z]/g,'')}" value="${val}"></div></div>`;
    }).join('');

    openModal(`Budget — ${biz}`, `
        <form onsubmit="return submitBudget(event, '${biz}')">
            <div class="form-group"><label>Total budget (kr)</label><input type="number" class="form-control" id="budTotal" value="${current.total || 0}"></div>
            <h3 style="margin:16px 0 12px;font-size:0.9rem">Per kategori</h3>
            ${catInputs}
            <button type="submit" class="btn btn-primary mt-4" style="width:100%">Spara budget</button>
        </form>
    `);
}

async function submitBudget(e, biz) {
    e.preventDefault();
    const c = state.constants;
    const kategorier = {};
    c.expense_categories.forEach(cat => {
        const input = el(`budCat_${cat.replace(/[^a-zA-Z]/g,'')}`);
        if (input) kategorier[cat] = Number(input.value) || 0;
    });
    await api('/api/budget', {
        method: 'POST',
        body: JSON.stringify({ bolag: biz, total: Number(el('budTotal').value) || 0, kategorier }),
    });
    closeModal();
    toast('Budget sparad', 'success');
    renderBudget();
}

// ===== RECEIPTS ===========================================================
async function renderReceipts() {
    const c = state.constants;
    el('pageContent').innerHTML = `
        <div class="page-header">
            <div class="page-header-row">
                <div><h1>Kvittoredovisning</h1><p>Ladda upp, granska och godkänn kvitton</p></div>
                <button class="btn btn-primary" onclick="openReceiptModal()">+ Ladda upp kvitto</button>
            </div>
        </div>
        <div class="tabs">
            <button class="tab active" onclick="switchReceiptTab('all', this)">Alla</button>
            <button class="tab" onclick="switchReceiptTab('inlamnat', this)">Inväntar</button>
            <button class="tab" onclick="switchReceiptTab('godkannt', this)">Godkända</button>
            <button class="tab" onclick="switchReceiptTab('avvisat', this)">Avvisade</button>
        </div>
        <div class="card"><div class="table-wrapper" id="recTable"><div class="spinner"></div></div></div>`;
    loadReceipts();
}

let _receiptFilter = '';
function switchReceiptTab(filter, btn) {
    _receiptFilter = filter === 'all' ? '' : filter;
    document.querySelectorAll('.tabs .tab').forEach(t => t.classList.remove('active'));
    btn.classList.add('active');
    loadReceipts();
}

function parseReceiptFiles(raw) {
    let files = raw || '[]';
    if (typeof files === 'string') { try { files = JSON.parse(files); } catch { files = []; } }
    return Array.isArray(files) ? files : [];
}

function isImage(filename) {
    return /\.(jpg|jpeg|png|gif|webp|bmp|svg)$/i.test(filename);
}

function receiptThumbnails(files) {
    if (!files.length) return '<span class="text-muted text-sm">—</span>';
    return files.map(f => {
        if (isImage(f)) {
            return `<img src="/uploads/${f}" class="receipt-thumb" onclick="event.stopPropagation();openLightbox('/uploads/${f}')" title="Klicka för att förstora" alt="Kvitto">`;
        }
        return `<a href="/uploads/${f}" target="_blank" class="receipt-file-badge" onclick="event.stopPropagation()" title="${f}">PDF</a>`;
    }).join('');
}

async function loadReceipts() {
    const params = new URLSearchParams();
    if (_receiptFilter) params.set('status', _receiptFilter);
    const data = await api(`/api/receipts?${params}`);
    if (!data || !data.length) {
        el('recTable').innerHTML = '<div class="empty-state"><h3>Inga kvitton</h3><p>Ladda upp ditt första kvitto.</p></div>';
        return;
    }
    el('recTable').innerHTML = `
        <table>
            <thead><tr><th>Datum</th><th>Bolag</th><th>Användare</th><th>Beskrivning</th><th>Kategori</th><th class="text-right">Belopp</th><th>Status</th><th>Kvittobild</th><th></th></tr></thead>
            <tbody>${data.map(r => {
                const files = parseReceiptFiles(r.files);
                const actions = r.status === 'inlamnat'
                    ? `<button class="btn btn-success btn-xs" onclick="event.stopPropagation();receiptAction('${r.id}','godkannt')" title="Godkänn">✓</button>
                       <button class="btn btn-danger btn-xs" onclick="event.stopPropagation();receiptAction('${r.id}','avvisat')" title="Avvisa">✕</button>`
                    : '';
                return `<tr class="receipt-row" onclick="openReceiptDetail(${JSON.stringify(r).replace(/"/g, '&quot;')})">
                    <td>${fmtDate(r.datum)}</td>
                    <td><span class="tag tag-primary">${escHtml(r.bolag) || '—'}</span></td>
                    <td>${escHtml(r.user)}</td>
                    <td>${escHtml(r.beskrivning) || '—'}</td>
                    <td>${escHtml(r.kategori) || '—'}</td>
                    <td class="text-right font-mono">${fmt(r.belopp)} kr</td>
                    <td>${statusTag(r.status)}</td>
                    <td><div class="receipt-thumbs">${receiptThumbnails(files)}</div></td>
                    <td>${actions}</td>
                </tr>`;
            }).join('')}</tbody>
        </table>`;
}

// Receipt detail modal with full-size image
function openReceiptDetail(r) {
    const files = parseReceiptFiles(r.files);
    const imagePreview = files.length
        ? `<div class="receipt-preview-grid">${files.map(f => {
            if (isImage(f)) {
                return `<div class="receipt-preview-item"><img src="/uploads/${f}" class="receipt-preview-img" onclick="openLightbox('/uploads/${f}')" title="Klicka för fullskärm"></div>`;
            }
            return `<div class="receipt-preview-item"><a href="/uploads/${f}" target="_blank" class="receipt-pdf-link"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="32" height="32"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg><span>Öppna PDF</span></a></div>`;
        }).join('')}</div>`
        : '<p class="text-muted text-sm">Ingen fil bifogad</p>';

    const statusActions = r.status === 'inlamnat'
        ? `<div class="flex gap-4 mt-4">
            <button class="btn btn-success flex-1" onclick="receiptAction('${r.id}','godkannt');closeModal()">Godkänn kvitto</button>
            <button class="btn btn-danger flex-1" onclick="receiptAction('${r.id}','avvisat');closeModal()">Avvisa kvitto</button>
           </div>`
        : '';

    openModal('Kvittouppgifter', `
        <div class="receipt-detail">
            <div class="receipt-detail-meta">
                <div class="receipt-detail-row"><span class="receipt-detail-label">Användare</span><span>${r.user}</span></div>
                <div class="receipt-detail-row"><span class="receipt-detail-label">Datum</span><span>${fmtDate(r.datum)}</span></div>
                <div class="receipt-detail-row"><span class="receipt-detail-label">Bolag</span><span class="tag tag-primary">${r.bolag || '—'}</span></div>
                <div class="receipt-detail-row"><span class="receipt-detail-label">Kategori</span><span>${r.kategori || '—'}</span></div>
                <div class="receipt-detail-row"><span class="receipt-detail-label">Beskrivning</span><span>${r.beskrivning || '—'}</span></div>
                <div class="receipt-detail-row"><span class="receipt-detail-label">Belopp</span><span class="font-mono" style="font-weight:700;font-size:1.1rem">${fmt(r.belopp)} kr</span></div>
                <div class="receipt-detail-row"><span class="receipt-detail-label">Status</span>${statusTag(r.status)}</div>
                <div class="receipt-detail-row"><span class="receipt-detail-label">Inlämnat</span><span class="text-muted">${r.created || '—'}</span></div>
            </div>
            <h3 style="margin:20px 0 12px;font-size:0.9rem;font-weight:700">Bifogade filer (${files.length})</h3>
            ${imagePreview}
            ${statusActions}
        </div>
    `, 'Klicka på bilden för att förstora');
}

// Lightbox for full-size image viewing
function openLightbox(src) {
    const lb = document.createElement('div');
    lb.className = 'lightbox';
    lb.onclick = () => lb.remove();
    lb.innerHTML = `
        <div class="lightbox-close" onclick="this.parentElement.remove()">✕</div>
        <img src="${src}" class="lightbox-img" onclick="event.stopPropagation()">
    `;
    document.body.appendChild(lb);
    // Close with Escape
    const handler = (e) => { if (e.key === 'Escape') { lb.remove(); document.removeEventListener('keydown', handler); } };
    document.addEventListener('keydown', handler);
}

function openReceiptModal() {
    const c = state.constants;
    openModal('Ladda upp kvitto', `
        <form onsubmit="return submitReceipt(event)" enctype="multipart/form-data">
            <div class="form-row">
                <div class="form-group"><label>Verksamhet</label><select class="form-control" id="recBolag">${c.businesses.map(b => `<option>${b}</option>`).join('')}</select></div>
                <div class="form-group"><label>Datum</label><input type="date" class="form-control" id="recDatum" value="${new Date().toISOString().slice(0,10)}"></div>
            </div>
            <div class="form-group"><label>Kategori</label><select class="form-control" id="recKat">${c.receipt_categories.map(k => `<option>${k}</option>`).join('')}</select></div>
            <div class="form-group"><label>Beskrivning</label><input class="form-control" id="recBesk" placeholder="Vad avser kvittot?"></div>
            <div class="form-group"><label>Belopp (kr)</label><input type="number" step="0.01" class="form-control" id="recBelopp" required placeholder="0"></div>
            <div class="form-group"><label>Bifoga fil(er)</label><input type="file" class="form-control" id="recFiles" multiple accept="image/*,.pdf"></div>
            <button type="submit" class="btn btn-primary mt-4" style="width:100%">Ladda upp</button>
        </form>
    `);
}

async function submitReceipt(e) {
    e.preventDefault();
    const fd = new FormData();
    fd.append('bolag', el('recBolag').value);
    fd.append('datum', el('recDatum').value);
    fd.append('kategori', el('recKat').value);
    fd.append('beskrivning', el('recBesk').value);
    fd.append('belopp', el('recBelopp').value);
    const files = el('recFiles').files;
    for (let i = 0; i < files.length; i++) fd.append('files', files[i]);
    await apiForm('/api/receipts', fd);
    closeModal();
    toast('Kvitto uppladdat', 'success');
    loadReceipts();
}

async function receiptAction(id, status) {
    await api(`/api/receipts/${id}/status`, {
        method: 'PUT',
        body: JSON.stringify({ status }),
    });
    toast(status === 'godkannt' ? 'Kvitto godkänt' : 'Kvitto avvisat', 'success');
    loadReceipts();
}

// ===== CALENDAR ===========================================================
async function renderCalendar() {
    const c = state.constants;
    el('pageContent').innerHTML = `
        <div class="page-header">
            <div class="page-header-row">
                <div><h1>Kalender</h1><p>Planera och överblicka händelser</p></div>
                <button class="btn btn-primary" onclick="openEventModal()">+ Ny händelse</button>
            </div>
        </div>
        <div class="grid-2">
            <div>
                <div class="card">
                    <div class="card-header">
                        <button class="btn btn-ghost btn-sm" onclick="calNav(-1)">◀</button>
                        <h3 id="calTitle"></h3>
                        <button class="btn btn-ghost btn-sm" onclick="calNav(1)">▶</button>
                    </div>
                    <div class="card-body" id="calGrid"></div>
                </div>
            </div>
            <div>
                <div class="card mb-4">
                    <div class="card-header">
                        <h3>Att göra</h3>
                        <button class="btn btn-secondary btn-sm" onclick="openTodoModal()">+ Ny</button>
                    </div>
                    <div id="todoList"></div>
                </div>
                <div class="card">
                    <div class="card-header"><h3>Kommande händelser</h3></div>
                    <div class="card-body" id="upcomingEvents"></div>
                </div>
            </div>
        </div>`;
    loadCalendar();
    loadTodos();
}

const MONTH_NAMES = ['Januari','Februari','Mars','April','Maj','Juni','Juli','Augusti','September','Oktober','November','December'];
const DAY_NAMES = ['Mån','Tis','Ons','Tor','Fre','Lör','Sön'];

function calNav(dir) {
    state.calMonth += dir;
    if (state.calMonth > 12) { state.calMonth = 1; state.calYear++; }
    if (state.calMonth < 1) { state.calMonth = 12; state.calYear--; }
    loadCalendar();
}

async function loadCalendar() {
    const events = await api(`/api/calendar/events?year=${state.calYear}&month=${state.calMonth}`);
    el('calTitle').textContent = `${MONTH_NAMES[state.calMonth - 1]} ${state.calYear}`;

    const firstDay = new Date(state.calYear, state.calMonth - 1, 1);
    const lastDay = new Date(state.calYear, state.calMonth, 0);
    let startDow = firstDay.getDay(); // 0=Sun
    startDow = startDow === 0 ? 6 : startDow - 1; // Convert to Mon=0

    const today = new Date();
    const todayStr = today.toISOString().slice(0, 10);

    let html = DAY_NAMES.map(d => `<div class="cal-header">${d}</div>`).join('');

    // Previous month fill
    const prevLast = new Date(state.calYear, state.calMonth - 1, 0).getDate();
    for (let i = startDow - 1; i >= 0; i--) {
        html += `<div class="cal-day other-month"><div class="cal-day-num">${prevLast - i}</div></div>`;
    }

    // Current month
    for (let d = 1; d <= lastDay.getDate(); d++) {
        const dateStr = `${state.calYear}-${String(state.calMonth).padStart(2,'0')}-${String(d).padStart(2,'0')}`;
        const dayEvents = (events || []).filter(e => e.datum === dateStr);
        const isToday = dateStr === todayStr;
        const evHtml = dayEvents.slice(0, 3).map(e =>
            `<div class="cal-event ${calEventClass(e.type)}" title="${e.title}">${e.time ? e.time + ' ' : ''}${e.title}</div>`
        ).join('');
        const more = dayEvents.length > 3 ? `<div class="text-muted text-sm">+${dayEvents.length - 3} till</div>` : '';

        html += `<div class="cal-day${isToday ? ' today' : ''}" onclick="showDayEvents('${dateStr}')">
            <div class="cal-day-num">${d}</div>${evHtml}${more}
        </div>`;
    }

    // Next month fill
    const totalCells = startDow + lastDay.getDate();
    const remaining = (7 - (totalCells % 7)) % 7;
    for (let i = 1; i <= remaining; i++) {
        html += `<div class="cal-day other-month"><div class="cal-day-num">${i}</div></div>`;
    }

    el('calGrid').innerHTML = `<div class="cal-grid">${html}</div>`;

    // Upcoming events
    const allEvents = await api(`/api/calendar/events`);
    const upcoming = (allEvents || []).filter(e => e.datum >= todayStr).slice(0, 8);
    el('upcomingEvents').innerHTML = upcoming.length
        ? upcoming.map(e => `
            <div class="activity-item">
                <div class="activity-dot" style="background:${e.type === 'Deadline' ? 'var(--danger)' : e.type === 'Möte' ? 'var(--primary)' : 'var(--warning)'}"></div>
                <div class="flex-1">
                    <div style="font-weight:600">${e.title}</div>
                    <div class="text-muted text-sm">${e.datum}${e.time ? ' kl ' + e.time : ''} · ${e.type}</div>
                </div>
                <button class="btn btn-ghost btn-xs" onclick="deleteEvent('${e.id}')">✕</button>
            </div>`).join('')
        : '<div class="text-muted text-sm">Inga kommande händelser</div>';
}

function showDayEvents(dateStr) {
    openEventModal(dateStr);
}

function openEventModal(defaultDate) {
    const c = state.constants;
    openModal('Ny händelse', `
        <form onsubmit="return submitEvent(event)">
            <div class="form-group"><label>Titel</label><input class="form-control" id="evtTitle" required placeholder="Händelsens namn"></div>
            <div class="form-row">
                <div class="form-group"><label>Datum</label><input type="date" class="form-control" id="evtDatum" value="${defaultDate || new Date().toISOString().slice(0,10)}"></div>
                <div class="form-group"><label>Tid</label><input type="time" class="form-control" id="evtTime"></div>
            </div>
            <div class="form-row">
                <div class="form-group"><label>Typ</label><select class="form-control" id="evtType">${c.calendar_types.map(t => `<option>${t}</option>`).join('')}</select></div>
                <div class="form-group"><label>Verksamhet</label><select class="form-control" id="evtBiz"><option>Alla</option>${c.businesses.map(b => `<option>${b}</option>`).join('')}</select></div>
            </div>
            <div class="form-group"><label>Beskrivning</label><textarea class="form-control" id="evtBesk" rows="2"></textarea></div>
            <button type="submit" class="btn btn-primary mt-4" style="width:100%">Skapa händelse</button>
        </form>
    `);
}

async function submitEvent(e) {
    e.preventDefault();
    await api('/api/calendar/events', {
        method: 'POST',
        body: JSON.stringify({
            title: el('evtTitle').value,
            datum: el('evtDatum').value,
            time: el('evtTime').value,
            type: el('evtType').value,
            business: el('evtBiz').value,
            beskrivning: el('evtBesk').value,
        }),
    });
    closeModal();
    toast('Händelse skapad', 'success');
    loadCalendar();
}

async function deleteEvent(id) {
    if (!confirm('Ta bort denna händelse?')) return;
    await api(`/api/calendar/events/${id}`, { method: 'DELETE' });
    toast('Händelse borttagen', 'success');
    loadCalendar();
}

// Todos
async function loadTodos() {
    const todos = await api('/api/todos');
    if (!todos || !todos.length) {
        el('todoList').innerHTML = '<div class="card-body text-muted text-sm">Inga uppgifter ännu</div>';
        return;
    }
    el('todoList').innerHTML = todos.map(t => {
        const isDone = String(t.done).toLowerCase() === 'true';
        return `<div class="todo-item${isDone ? ' done' : ''}">
            <div class="todo-check${isDone ? ' checked' : ''}" onclick="toggleTodo('${t.id}', ${!isDone})"></div>
            <div class="todo-text">${t.task}</div>
            ${priorityTag(t.priority)}
            ${t.deadline ? `<span class="text-muted text-sm">${t.deadline}</span>` : ''}
            <button class="btn btn-ghost btn-xs" onclick="deleteTodo('${t.id}')">✕</button>
        </div>`;
    }).join('');
}

function openTodoModal() {
    openModal('Ny uppgift', `
        <form onsubmit="return submitTodo(event)">
            <div class="form-group"><label>Uppgift</label><input class="form-control" id="todoTask" required placeholder="Vad ska göras?"></div>
            <div class="form-row">
                <div class="form-group"><label>Prioritet</label><select class="form-control" id="todoPrio"><option>Medel</option><option>Hög</option><option>Låg</option></select></div>
                <div class="form-group"><label>Deadline</label><input type="date" class="form-control" id="todoDeadline"></div>
            </div>
            <button type="submit" class="btn btn-primary mt-4" style="width:100%">Lägg till</button>
        </form>
    `);
}

async function submitTodo(e) {
    e.preventDefault();
    await api('/api/todos', {
        method: 'POST',
        body: JSON.stringify({
            task: el('todoTask').value,
            priority: el('todoPrio').value,
            deadline: el('todoDeadline').value,
        }),
    });
    closeModal();
    toast('Uppgift tillagd', 'success');
    loadTodos();
}

async function toggleTodo(id, done) {
    await api(`/api/todos/${id}`, {
        method: 'PUT',
        body: JSON.stringify({ done }),
    });
    loadTodos();
}

async function deleteTodo(id) {
    await api(`/api/todos/${id}`, { method: 'DELETE' });
    toast('Uppgift borttagen', 'success');
    loadTodos();
}

// ===== CHAT (WebSocket real-time) =========================================
let socket = null;
let _typingTimeout = null;

function initSocket() {
    if (socket) return;
    socket = io({ transports: ['websocket', 'polling'] });
    socket.on('new_message', (msg) => {
        if (msg.group_id === state.chatGroupId) {
            appendChatMessage(msg);
        } else {
            // Show badge for other groups
            const badge = el('chatBadge');
            if (badge) { badge.style.display = 'inline'; badge.textContent = '!'; }
        }
    });
    socket.on('user_typing', (data) => {
        if (data.group_id === state.chatGroupId) {
            showTypingIndicator(data.user);
        }
    });
}

function showTypingIndicator(user) {
    let ti = el('typingIndicator');
    if (!ti) return;
    ti.textContent = `${user} skriver...`;
    ti.style.display = 'block';
    clearTimeout(_typingTimeout);
    _typingTimeout = setTimeout(() => { ti.style.display = 'none'; }, 2000);
}

async function renderChat() {
    initSocket();
    el('pageContent').innerHTML = `
        <div class="page-header">
            <div class="page-header-row">
                <div><h1>Chatt</h1><p>Kommunicera med ditt team i realtid</p></div>
                <button class="btn btn-primary" onclick="openCreateGroupModal()">+ Ny grupp</button>
            </div>
        </div>
        <div class="chat-layout">
            <div class="chat-sidebar">
                <div class="chat-sidebar-header"><h3>Grupper</h3></div>
                <div class="chat-group-list" id="chatGroupList"><div class="spinner"></div></div>
            </div>
            <div class="chat-main" id="chatMain">
                <div class="chat-empty">Välj en grupp för att börja chatta</div>
            </div>
        </div>`;
    loadChatGroups();
}

async function loadChatGroups() {
    const groups = await api('/api/chat/groups');
    if (!groups || !groups.length) {
        el('chatGroupList').innerHTML = '<div class="card-body text-muted text-sm">Inga grupper ännu</div>';
        return;
    }
    el('chatGroupList').innerHTML = groups.map(g => {
        const canDelete = state.role === 'admin' || g.created_by === state.user;
        return `
        <div class="chat-group-item${state.chatGroupId === g.id ? ' active' : ''}" onclick="selectChatGroup('${escHtml(g.id)}', '${escHtml(g.name).replace(/'/g, "\\'")}')">
            <div style="display:flex;justify-content:space-between;align-items:center">
                <div class="group-name">${escHtml(g.name)}</div>
                ${canDelete ? `<button class="btn btn-ghost btn-xs" onclick="event.stopPropagation();deleteChatGroup('${escHtml(g.id)}','${escHtml(g.name).replace(/'/g, "\\'")}')" title="Ta bort grupp">✕</button>` : ''}
            </div>
            <div class="group-preview">${Array.isArray(g.members) ? g.members.length + ' medlemmar' : ''}</div>
        </div>`;
    }).join('');
}

async function selectChatGroup(gid, name) {
    // Leave previous room
    if (state.chatGroupId && socket) {
        socket.emit('leave_chat', { group_id: state.chatGroupId });
    }
    // Stop old polling if still active
    if (state.chatPollTimer) { clearInterval(state.chatPollTimer); state.chatPollTimer = null; }

    state.chatGroupId = gid;
    loadChatGroups(); // Refresh active state

    el('chatMain').innerHTML = `
        <div style="padding:16px;border-bottom:1px solid var(--border);font-weight:700">${name}</div>
        <div class="chat-messages" id="chatMessages"><div class="spinner"></div></div>
        <div id="typingIndicator" class="typing-indicator" style="display:none"></div>
        <div class="chat-input-bar">
            <input type="text" id="chatInput" placeholder="Skriv ett meddelande..."
                onkeydown="if(event.key==='Enter')sendChatMessage()"
                oninput="emitTyping()">
            <button onclick="sendChatMessage()">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
            </button>
        </div>`;

    // Join WebSocket room
    if (socket) socket.emit('join_chat', { group_id: gid });

    // Load existing messages
    loadChatMessages();

    // Fallback poll every 30s (in case socket disconnects)
    state.chatPollTimer = setInterval(loadChatMessages, 30000);
}

function emitTyping() {
    if (socket && state.chatGroupId) {
        socket.emit('typing', { group_id: state.chatGroupId });
    }
}

async function loadChatMessages() {
    if (!state.chatGroupId) return;
    const msgs = await api(`/api/chat/groups/${state.chatGroupId}/messages`);
    const container = el('chatMessages');
    if (!container) return;
    if (!msgs || !msgs.length) {
        container.innerHTML = '<div class="chat-empty">Inga meddelanden ännu. Säg hej! 👋</div>';
        return;
    }
    const wasAtBottom = container.scrollTop + container.clientHeight >= container.scrollHeight - 50;
    container.innerHTML = msgs.map(m => `
        <div class="chat-msg ${m.sender === state.user ? 'own' : 'other'}">
            ${m.sender !== state.user ? `<div class="msg-sender">${escHtml(m.sender)}</div>` : ''}
            <div>${escHtml(m.content)}</div>
            <div class="msg-time">${m.timestamp ? escHtml(m.timestamp.slice(11, 16)) : ''}</div>
        </div>
    `).join('');
    if (wasAtBottom) container.scrollTop = container.scrollHeight;
}

function appendChatMessage(msg) {
    const container = el('chatMessages');
    if (!container) return;
    // Remove empty state if present
    const emptyEl = container.querySelector('.chat-empty');
    if (emptyEl) emptyEl.remove();
    const wasAtBottom = container.scrollTop + container.clientHeight >= container.scrollHeight - 50;
    const div = document.createElement('div');
    div.className = `chat-msg ${msg.sender === state.user ? 'own' : 'other'}`;
    div.innerHTML = `
        ${msg.sender !== state.user ? `<div class="msg-sender">${escHtml(msg.sender)}</div>` : ''}
        <div>${escHtml(msg.content)}</div>
        <div class="msg-time">${msg.timestamp ? escHtml(msg.timestamp.slice(11, 16)) : ''}</div>
    `;
    container.appendChild(div);
    if (wasAtBottom) container.scrollTop = container.scrollHeight;
    // Hide typing indicator
    const ti = el('typingIndicator');
    if (ti) ti.style.display = 'none';
}

async function sendChatMessage() {
    const input = el('chatInput');
    const content = input.value.trim();
    if (!content || !state.chatGroupId) return;
    input.value = '';
    await api(`/api/chat/groups/${state.chatGroupId}/messages`, {
        method: 'POST',
        body: JSON.stringify({ content }),
    });
    // Message will arrive via socket — no need to reload
}

async function openCreateGroupModal() {
    const users = await api('/api/users-list');
    openModal('Ny chattgrupp', `
        <form onsubmit="return submitChatGroup(event)">
            <div class="form-group"><label>Gruppnamn</label><input class="form-control" id="grpName" required placeholder="Namnge gruppen"></div>
            <div class="form-group">
                <label>Medlemmar</label>
                ${(users || []).map(u => `
                    <label style="display:flex;align-items:center;gap:8px;padding:6px 0;cursor:pointer">
                        <input type="checkbox" value="${u}" ${u === state.user ? 'checked disabled' : ''} class="grpMember"> ${u}
                    </label>
                `).join('')}
            </div>
            <button type="submit" class="btn btn-primary mt-4" style="width:100%">Skapa grupp</button>
        </form>
    `);
}

async function submitChatGroup(e) {
    e.preventDefault();
    const members = [state.user];
    document.querySelectorAll('.grpMember:checked').forEach(cb => {
        if (!members.includes(cb.value)) members.push(cb.value);
    });
    await api('/api/chat/groups', {
        method: 'POST',
        body: JSON.stringify({ name: el('grpName').value, members }),
    });
    closeModal();
    toast('Grupp skapad', 'success');
    loadChatGroups();
}

async function deleteChatGroup(gid, name) {
    if (!confirm(`Ta bort gruppen "${name}" och alla meddelanden?`)) return;
    await api(`/api/chat/groups/${gid}`, { method: 'DELETE' });
    if (state.chatGroupId === gid) {
        state.chatGroupId = null;
        el('chatMain').innerHTML = '<div class="chat-empty">Välj en grupp för att börja chatta</div>';
    }
    toast('Grupp borttagen', 'success');
    loadChatGroups();
}

// ===== EXPORT HELPERS =====================================================
function exportExpenses(format) {
    const bolag = el('expBolag')?.value || 'Alla';
    const month = el('expMonth')?.value || '';
    const params = new URLSearchParams({ format });
    if (bolag !== 'Alla') params.set('bolag', bolag);
    if (month) params.set('month', month);
    window.open(`/api/export/expenses?${params}`, '_blank');
}
function exportRevenue(format) {
    const bolag = el('revBolag')?.value || 'Alla';
    const month = el('revMonth')?.value || '';
    const params = new URLSearchParams({ format });
    if (bolag !== 'Alla') params.set('bolag', bolag);
    if (month) params.set('month', month);
    window.open(`/api/export/revenue?${params}`, '_blank');
}

// ===== CRM — CUSTOMERS ====================================================
async function renderCustomers() {
    const c = state.constants;
    el('pageContent').innerHTML = `
        <div class="page-header">
            <div class="page-header-row">
                <div><h1>Kundregister</h1><p>Hantera kontakter och kundrelationer</p></div>
                <div class="flex gap-2">
                    <button class="btn btn-secondary" onclick="window.location='/api/export/customers?format=excel'">📥 Excel</button>
                    <button class="btn btn-primary" onclick="openCustomerModal()">+ Ny kund</button>
                </div>
            </div>
        </div>
        <div class="filter-bar">
            <input type="text" class="form-control" id="custSearch" placeholder="Sök kund..." onkeyup="loadCustomers()" style="max-width:260px">
            <select id="custStage" onchange="loadCustomers()">
                <option value="Alla">Alla stadier</option>
                ${c.customer_stages.map(s => `<option>${s}</option>`).join('')}
            </select>
            <select id="custBolag" onchange="loadCustomers()">
                <option value="Alla">Alla bolag</option>
                ${c.businesses.map(b => `<option>${b}</option>`).join('')}
            </select>
        </div>
        <div class="card"><div class="table-wrapper" id="custTable"><div class="spinner"></div></div></div>`;
    loadCustomers();
}

async function loadCustomers() {
    const params = new URLSearchParams();
    const stage = el('custStage')?.value;
    const bolag = el('custBolag')?.value;
    const q = el('custSearch')?.value;
    if (stage && stage !== 'Alla') params.set('stage', stage);
    if (bolag && bolag !== 'Alla') params.set('bolag', bolag);
    if (q) params.set('q', q);
    const data = await api(`/api/customers?${params}`);
    if (!data || !data.length) {
        el('custTable').innerHTML = '<div class="empty-state"><h3>Inga kunder</h3><p>Lägg till din första kund.</p></div>';
        return;
    }
    el('custTable').innerHTML = `
        <table>
            <thead><tr><th>Namn</th><th>Företag</th><th>E-post</th><th>Telefon</th><th>Bolag</th><th>Stadie</th><th class="text-right">Värde</th><th>Ansvarig</th><th></th></tr></thead>
            <tbody>${data.map(c => `
                <tr class="receipt-row" onclick="openCustomerDetail('${c.id}')">
                    <td style="font-weight:600">${c.name || '—'}</td>
                    <td>${c.company || '—'}</td>
                    <td>${c.email ? `<a href="mailto:${c.email}" onclick="event.stopPropagation()">${c.email}</a>` : '—'}</td>
                    <td>${c.phone || '—'}</td>
                    <td><span class="tag tag-primary">${c.bolag || '—'}</span></td>
                    <td>${stageTag(c.stage)}</td>
                    <td class="text-right font-mono">${fmt(c.value)} kr</td>
                    <td>${c.assigned_to || '—'}</td>
                    <td><button class="btn btn-ghost btn-xs" onclick="event.stopPropagation();deleteCustomer('${c.id}')">✕</button></td>
                </tr>`).join('')}
            </tbody>
        </table>`;
}

function stageTag(stage) {
    const map = {
        'Lead': 'neutral', 'Kontaktad': 'warning', 'Offert skickad': 'primary',
        'Förhandling': 'warning', 'Vunnen': 'success', 'Förlorad': 'danger'
    };
    return `<span class="tag tag-${map[stage] || 'neutral'}">${stage || '—'}</span>`;
}

function openCustomerModal(existing) {
    const c = state.constants;
    const e = existing || {};
    const isEdit = !!e.id;
    openModal(isEdit ? 'Redigera kund' : 'Ny kund', `
        <form onsubmit="return submitCustomer(event, ${isEdit ? `'${e.id}'` : 'null'})">
            <div class="form-row">
                <div class="form-group"><label>Namn *</label><input class="form-control" id="custName" required value="${e.name || ''}" placeholder="Kontaktperson"></div>
                <div class="form-group"><label>Företag</label><input class="form-control" id="custCompany" value="${e.company || ''}" placeholder="Företagsnamn"></div>
            </div>
            <div class="form-row">
                <div class="form-group"><label>E-post</label><input type="email" class="form-control" id="custEmail" value="${e.email || ''}" placeholder="namn@foretag.se"></div>
                <div class="form-group"><label>Telefon</label><input class="form-control" id="custPhone" value="${e.phone || ''}" placeholder="070-123 45 67"></div>
            </div>
            <div class="form-row">
                <div class="form-group"><label>Bolag</label><select class="form-control" id="custBolagF">${c.businesses.map(b => `<option ${b === e.bolag ? 'selected' : ''}>${b}</option>`).join('')}</select></div>
                <div class="form-group"><label>Stadie</label><select class="form-control" id="custStageF">${c.customer_stages.map(s => `<option ${s === e.stage ? 'selected' : ''}>${s}</option>`).join('')}</select></div>
            </div>
            <div class="form-row">
                <div class="form-group"><label>Källa</label><select class="form-control" id="custSource">${c.customer_sources.map(s => `<option ${s === e.source ? 'selected' : ''}>${s}</option>`).join('')}</select></div>
                <div class="form-group"><label>Uppskattat värde (kr)</label><input type="number" class="form-control" id="custValue" value="${e.value || 0}" placeholder="0"></div>
            </div>
            <div class="form-group"><label>Anteckningar</label><textarea class="form-control" id="custNotes" rows="2" placeholder="Kort bakgrund...">${e.notes || ''}</textarea></div>
            <button type="submit" class="btn btn-primary mt-4" style="width:100%">${isEdit ? 'Uppdatera' : 'Skapa kund'}</button>
        </form>
    `);
}

async function submitCustomer(ev, editId) {
    ev.preventDefault();
    const body = {
        name: el('custName').value,
        company: el('custCompany').value,
        email: el('custEmail').value,
        phone: el('custPhone').value,
        bolag: el('custBolagF').value,
        stage: el('custStageF').value,
        source: el('custSource').value,
        value: el('custValue').value,
        notes: el('custNotes').value,
    };
    if (editId) {
        await api(`/api/customers/${editId}`, { method: 'PUT', body: JSON.stringify(body) });
        toast('Kund uppdaterad', 'success');
    } else {
        await api('/api/customers', { method: 'POST', body: JSON.stringify(body) });
        toast('Kund tillagd', 'success');
    }
    closeModal();
    loadCustomers();
}

async function openCustomerDetail(cid) {
    const [customers, notes] = await Promise.all([
        api('/api/customers'),
        api(`/api/customers/${cid}/notes`),
    ]);
    const c = customers.find(x => x.id === cid);
    if (!c) return;

    const notesHtml = (notes || []).map(n => `
        <div class="activity-item">
            <div class="activity-dot"></div>
            <div class="flex-1">
                <div>${n.text}</div>
                <div class="activity-time">${n.author} · ${n.created}</div>
            </div>
        </div>
    `).join('') || '<div class="text-muted text-sm">Inga anteckningar</div>';

    openModal(c.name, `
        <div class="receipt-detail">
            <div class="receipt-detail-meta">
                <div class="receipt-detail-row"><span class="receipt-detail-label">Företag</span><span>${c.company || '—'}</span></div>
                <div class="receipt-detail-row"><span class="receipt-detail-label">E-post</span><span>${c.email ? `<a href="mailto:${c.email}">${c.email}</a>` : '—'}</span></div>
                <div class="receipt-detail-row"><span class="receipt-detail-label">Telefon</span><span>${c.phone || '—'}</span></div>
                <div class="receipt-detail-row"><span class="receipt-detail-label">Bolag</span><span class="tag tag-primary">${c.bolag}</span></div>
                <div class="receipt-detail-row"><span class="receipt-detail-label">Stadie</span>${stageTag(c.stage)}</div>
                <div class="receipt-detail-row"><span class="receipt-detail-label">Källa</span><span>${c.source || '—'}</span></div>
                <div class="receipt-detail-row"><span class="receipt-detail-label">Värde</span><span class="font-mono" style="font-weight:700">${fmt(c.value)} kr</span></div>
                <div class="receipt-detail-row"><span class="receipt-detail-label">Ansvarig</span><span>${c.assigned_to || '—'}</span></div>
                <div class="receipt-detail-row"><span class="receipt-detail-label">Skapad</span><span class="text-muted">${c.created || '—'}</span></div>
            </div>
            ${c.notes ? `<div style="margin:16px 0;padding:12px;background:var(--bg);border-radius:var(--radius-sm);font-size:0.9rem">${c.notes}</div>` : ''}
            <div class="flex gap-2 mt-4">
                <button class="btn btn-secondary flex-1" onclick="closeModal();openCustomerModal(${JSON.stringify(c).replace(/"/g, '&quot;')})">✏️ Redigera</button>
                <button class="btn btn-primary flex-1" onclick="closeModal();navigate('quotes');setTimeout(()=>openQuoteModalForCustomer(${JSON.stringify({id:c.id,name:c.name}).replace(/"/g, '&quot;')}),300)">📄 Skapa offert</button>
            </div>
            <h3 style="margin:20px 0 12px;font-size:0.9rem;font-weight:700">Anteckningar</h3>
            ${notesHtml}
            <form onsubmit="return submitCustomerNote(event, '${c.id}')" class="mt-4">
                <div class="form-group"><textarea class="form-control" id="noteText" rows="2" placeholder="Lägg till anteckning..." required></textarea></div>
                <button type="submit" class="btn btn-secondary btn-sm">Lägg till</button>
            </form>
        </div>
    `, c.company || '');
}

async function submitCustomerNote(ev, cid) {
    ev.preventDefault();
    await api(`/api/customers/${cid}/notes`, {
        method: 'POST',
        body: JSON.stringify({ text: el('noteText').value }),
    });
    toast('Anteckning tillagd', 'success');
    openCustomerDetail(cid);
}

async function deleteCustomer(id) {
    if (!confirm('Ta bort denna kund?')) return;
    await api(`/api/customers/${id}`, { method: 'DELETE' });
    toast('Kund borttagen', 'success');
    loadCustomers();
}

// ===== CRM — PIPELINE (Kanban) ============================================
async function renderPipeline() {
    const c = state.constants;
    el('pageContent').innerHTML = `
        <div class="page-header">
            <div class="page-header-row">
                <div><h1>Pipeline</h1><p>Överblicka kundresan visuellt</p></div>
                <select id="pipeBolag" onchange="loadPipeline()" class="form-control" style="max-width:180px">
                    <option value="Alla">Alla bolag</option>
                    ${c.businesses.map(b => `<option>${b}</option>`).join('')}
                </select>
            </div>
        </div>
        <div class="kanban-board" id="pipelineBoard"><div class="spinner"></div></div>`;
    loadPipeline();
}

async function loadPipeline() {
    const bolag = el('pipeBolag')?.value || 'Alla';
    const params = new URLSearchParams();
    if (bolag !== 'Alla') params.set('bolag', bolag);
    const data = await api(`/api/pipeline?${params}`);
    if (!data) return;

    const c = state.constants;
    const stageColors = {
        'Lead': '#64748b', 'Kontaktad': '#f59e0b', 'Offert skickad': '#6366f1',
        'Förhandling': '#f97316', 'Vunnen': '#10b981', 'Förlorad': '#ef4444'
    };

    el('pipelineBoard').innerHTML = c.customer_stages.map(stage => {
        const s = data[stage] || { customers: [], count: 0, total_value: 0 };
        const color = stageColors[stage] || '#64748b';
        return `
        <div class="kanban-column">
            <div class="kanban-header" style="border-top:3px solid ${color}">
                <div class="kanban-title">${stage}</div>
                <div class="kanban-count">${s.count} · ${fmt(s.total_value)} kr</div>
            </div>
            <div class="kanban-cards" ondragover="event.preventDefault()" ondrop="dropCard(event,'${stage}')">
                ${s.customers.map(cust => `
                    <div class="kanban-card" draggable="true" ondragstart="dragCard(event,'${cust.id}')" onclick="openCustomerDetail('${cust.id}')">
                        <div class="kanban-card-name">${cust.name}</div>
                        <div class="kanban-card-sub">${cust.company || '—'}</div>
                        <div class="kanban-card-footer">
                            <span class="tag tag-primary">${cust.bolag}</span>
                            <span class="font-mono text-sm">${fmt(cust.value)} kr</span>
                        </div>
                    </div>
                `).join('') || '<div class="kanban-empty">Inga kunder</div>'}
            </div>
        </div>`;
    }).join('');
}

let _dragCardId = null;
function dragCard(ev, id) { _dragCardId = id; ev.dataTransfer.effectAllowed = 'move'; }
async function dropCard(ev, stage) {
    ev.preventDefault();
    if (!_dragCardId) return;
    await api(`/api/customers/${_dragCardId}/stage`, {
        method: 'PUT',
        body: JSON.stringify({ stage }),
    });
    _dragCardId = null;
    toast(`Kund flyttad till ${stage}`, 'success');
    loadPipeline();
}

// ===== QUOTES / OFFERTER ==================================================
async function renderQuotes() {
    const c = state.constants;
    el('pageContent').innerHTML = `
        <div class="page-header">
            <div class="page-header-row">
                <div><h1>Offerter</h1><p>Skapa, skicka och spåra offerter</p></div>
                <button class="btn btn-primary" onclick="openQuoteModal()">+ Ny offert</button>
            </div>
        </div>
        <div class="filter-bar">
            <select id="quoteStatus" onchange="loadQuotes()">
                <option value="Alla">Alla statusar</option>
                ${c.quote_statuses.map(s => `<option>${s}</option>`).join('')}
            </select>
            <select id="quoteBolag" onchange="loadQuotes()">
                <option value="Alla">Alla bolag</option>
                ${c.businesses.map(b => `<option>${b}</option>`).join('')}
            </select>
        </div>
        <div class="card"><div class="table-wrapper" id="quoteTable"><div class="spinner"></div></div></div>`;
    loadQuotes();
}

async function loadQuotes() {
    const params = new URLSearchParams();
    const status = el('quoteStatus')?.value;
    const bolag = el('quoteBolag')?.value;
    if (status && status !== 'Alla') params.set('status', status);
    if (bolag && bolag !== 'Alla') params.set('bolag', bolag);
    const data = await api(`/api/quotes?${params}`);
    if (!data || !data.length) {
        el('quoteTable').innerHTML = '<div class="empty-state"><h3>Inga offerter</h3><p>Skapa din första offert.</p></div>';
        return;
    }
    el('quoteTable').innerHTML = `
        <table>
            <thead><tr><th>ID</th><th>Kund</th><th>Titel</th><th>Bolag</th><th class="text-right">Summa</th><th>Status</th><th>Skapad</th><th></th></tr></thead>
            <tbody>${data.map(q => `
                <tr class="receipt-row" onclick="openQuoteDetail('${q.id}')">
                    <td class="font-mono text-sm" style="font-weight:600">${q.id}</td>
                    <td>${q.customer_name || '—'}</td>
                    <td>${q.title || '—'}</td>
                    <td><span class="tag tag-primary">${q.bolag}</span></td>
                    <td class="text-right font-mono">${fmt(q.total)} kr</td>
                    <td>${quoteStatusTag(q.status)}</td>
                    <td class="text-muted text-sm">${(q.created || '').slice(0, 10)}</td>
                    <td class="flex gap-1">
                        <a href="/api/quotes/${q.id}/pdf" target="_blank" class="btn btn-ghost btn-xs" onclick="event.stopPropagation()" title="Ladda ner PDF">📄</a>
                        <button class="btn btn-ghost btn-xs" onclick="event.stopPropagation();deleteQuote('${q.id}')">✕</button>
                    </td>
                </tr>`).join('')}
            </tbody>
        </table>`;
}

function quoteStatusTag(s) {
    const map = {
        'Utkast': 'neutral', 'Skickad': 'warning', 'Accepterad': 'success',
        'Avvisad': 'danger', 'Fakturerad': 'primary'
    };
    return `<span class="tag tag-${map[s] || 'neutral'}">${s || '—'}</span>`;
}

function openQuoteModal() {
    const c = state.constants;
    openModal('Ny offert', `
        <form onsubmit="return submitQuote(event)">
            <div class="form-row">
                <div class="form-group"><label>Titel</label><input class="form-control" id="qTitle" required placeholder="Offertens titel"></div>
                <div class="form-group"><label>Bolag</label><select class="form-control" id="qBolag">${c.businesses.map(b => `<option>${b}</option>`).join('')}</select></div>
            </div>
            <div class="form-row">
                <div class="form-group"><label>Kund-namn</label><input class="form-control" id="qCustName" placeholder="Kundnamn" list="customerList"></div>
                <div class="form-group"><label>Giltig till</label><input type="date" class="form-control" id="qValidUntil"></div>
            </div>
            <datalist id="customerList"></datalist>
            <div class="form-group"><label>Beskrivning</label><textarea class="form-control" id="qDesc" rows="2" placeholder="Kort beskrivning av offerten"></textarea></div>
            <h3 style="margin:16px 0 8px;font-size:0.9rem;font-weight:700">Rader</h3>
            <div id="quoteItems">
                <div class="quote-item-row">
                    <input class="form-control" placeholder="Beskrivning" data-field="description" style="flex:3">
                    <input type="number" class="form-control" placeholder="Antal" value="1" data-field="quantity" style="flex:0.7">
                    <input type="number" class="form-control" placeholder="À-pris" data-field="unit_price" style="flex:1">
                    <select class="form-control" data-field="moms" style="flex:0.7">
                        ${c.vat_rates.map(v => `<option ${v===25?'selected':''}>${v}</option>`).join('')}
                    </select>
                    <button type="button" class="btn btn-ghost btn-xs" onclick="this.closest('.quote-item-row').remove()">✕</button>
                </div>
            </div>
            <button type="button" class="btn btn-secondary btn-sm mt-2" onclick="addQuoteItemRow()">+ Lägg till rad</button>
            <button type="submit" class="btn btn-primary mt-4" style="width:100%">Skapa offert</button>
        </form>
    `);
    loadCustomerDatalist();
}

function openQuoteModalForCustomer(cust) {
    openQuoteModal();
    setTimeout(() => {
        if (el('qCustName')) el('qCustName').value = cust.name || '';
    }, 100);
}

async function loadCustomerDatalist() {
    const customers = await api('/api/customers');
    const dl = document.getElementById('customerList');
    if (dl && customers) {
        dl.innerHTML = customers.map(c => `<option value="${c.name}">`).join('');
    }
}

function addQuoteItemRow() {
    const c = state.constants;
    const row = document.createElement('div');
    row.className = 'quote-item-row';
    row.innerHTML = `
        <input class="form-control" placeholder="Beskrivning" data-field="description" style="flex:3">
        <input type="number" class="form-control" placeholder="Antal" value="1" data-field="quantity" style="flex:0.7">
        <input type="number" class="form-control" placeholder="À-pris" data-field="unit_price" style="flex:1">
        <select class="form-control" data-field="moms" style="flex:0.7">
            ${c.vat_rates.map(v => `<option ${v===25?'selected':''}>${v}</option>`).join('')}
        </select>
        <button type="button" class="btn btn-ghost btn-xs" onclick="this.closest('.quote-item-row').remove()">✕</button>
    `;
    document.getElementById('quoteItems').appendChild(row);
}

async function submitQuote(ev) {
    ev.preventDefault();
    const items = [];
    document.querySelectorAll('.quote-item-row').forEach(row => {
        const desc = row.querySelector('[data-field="description"]').value;
        const qty = Number(row.querySelector('[data-field="quantity"]').value) || 1;
        const price = Number(row.querySelector('[data-field="unit_price"]').value) || 0;
        const moms = Number(row.querySelector('[data-field="moms"]').value) || 25;
        if (desc || price) {
            items.push({ description: desc, quantity: qty, unit_price: price, moms, total: qty * price });
        }
    });
    // Find customer_id by name
    const customers = await api('/api/customers');
    const custName = el('qCustName').value;
    const custMatch = (customers || []).find(c => c.name === custName);

    await api('/api/quotes', {
        method: 'POST',
        body: JSON.stringify({
            title: el('qTitle').value,
            bolag: el('qBolag').value,
            customer_name: custName,
            customer_id: custMatch?.id || '',
            valid_until: el('qValidUntil').value,
            description: el('qDesc').value,
            items,
        }),
    });
    closeModal();
    toast('Offert skapad', 'success');
    loadQuotes();
}

async function openQuoteDetail(qid) {
    const quotes = await api('/api/quotes');
    const q = (quotes || []).find(x => x.id === qid);
    if (!q) return;

    let items = q.items || '[]';
    if (typeof items === 'string') { try { items = JSON.parse(items); } catch { items = []; } }

    const c = state.constants;
    const statusButtons = c.quote_statuses.map(s =>
        `<button class="btn ${s === q.status ? 'btn-primary' : 'btn-secondary'} btn-sm" onclick="changeQuoteStatus('${q.id}','${s}')">${s}</button>`
    ).join(' ');

    const itemsHtml = items.length ? `
        <table style="margin:12px 0">
            <thead><tr><th>Beskrivning</th><th class="text-right">Antal</th><th class="text-right">À-pris</th><th class="text-right">Moms</th><th class="text-right">Summa</th></tr></thead>
            <tbody>${items.map(it => `
                <tr>
                    <td>${it.description || '—'}</td>
                    <td class="text-right">${it.quantity}</td>
                    <td class="text-right font-mono">${fmt(it.unit_price)} kr</td>
                    <td class="text-right">${it.moms}%</td>
                    <td class="text-right font-mono">${fmt(it.total)} kr</td>
                </tr>`).join('')}
            </tbody>
            <tfoot>
                <tr><td colspan="4" class="text-right" style="font-weight:600">Delsumma</td><td class="text-right font-mono">${fmt(q.subtotal)} kr</td></tr>
                <tr><td colspan="4" class="text-right text-muted">Moms</td><td class="text-right font-mono text-muted">${fmt(q.moms_total)} kr</td></tr>
                <tr><td colspan="4" class="text-right" style="font-weight:700;font-size:1.05rem">Totalt</td><td class="text-right font-mono" style="font-weight:700;font-size:1.05rem">${fmt(q.total)} kr</td></tr>
            </tfoot>
        </table>` : '<p class="text-muted">Inga rader</p>';

    openModal(`Offert ${q.id}`, `
        <div class="receipt-detail">
            <div class="receipt-detail-meta">
                <div class="receipt-detail-row"><span class="receipt-detail-label">Kund</span><span style="font-weight:600">${q.customer_name || '—'}</span></div>
                <div class="receipt-detail-row"><span class="receipt-detail-label">Titel</span><span>${q.title}</span></div>
                <div class="receipt-detail-row"><span class="receipt-detail-label">Bolag</span><span class="tag tag-primary">${q.bolag}</span></div>
                <div class="receipt-detail-row"><span class="receipt-detail-label">Giltig till</span><span>${q.valid_until || '—'}</span></div>
                <div class="receipt-detail-row"><span class="receipt-detail-label">Skapad av</span><span>${q.created_by}</span></div>
                <div class="receipt-detail-row"><span class="receipt-detail-label">Datum</span><span class="text-muted">${(q.created || '').slice(0,10)}</span></div>
            </div>
            ${q.description ? `<div style="margin:12px 0;padding:12px;background:var(--bg);border-radius:var(--radius-sm);font-size:0.9rem">${q.description}</div>` : ''}
            <h3 style="margin:16px 0 8px;font-size:0.9rem;font-weight:700">Rader</h3>
            ${itemsHtml}
            <h3 style="margin:16px 0 8px;font-size:0.9rem;font-weight:700">Status</h3>
            <div class="flex gap-2 flex-wrap">${statusButtons}</div>
            <div class="flex gap-2 mt-4">
                <a href="/api/quotes/${q.id}/pdf" target="_blank" class="btn btn-secondary flex-1">📄 Ladda ner PDF</a>
                ${q.status === 'Accepterad' ? `<button class="btn btn-primary flex-1" onclick="convertQuoteToInvoice('${q.id}')">🧾 Skapa faktura</button>` : ''}
                ${q.status === 'Fakturerad' ? `<span class="tag tag-primary" style="align-self:center;padding:8px 16px">✓ Fakturerad</span>` : ''}
            </div>
        </div>
    `, q.customer_name || '');
}

async function changeQuoteStatus(qid, status) {
    await api(`/api/quotes/${qid}/status`, {
        method: 'PUT',
        body: JSON.stringify({ status }),
    });
    toast(`Offert ändrad till ${status}`, 'success');
    openQuoteDetail(qid);
    // Also refresh the table in background
    setTimeout(() => { if (state.page === 'quotes') loadQuotes(); }, 500);
}

async function deleteQuote(id) {
    if (!confirm('Ta bort denna offert?')) return;
    await api(`/api/quotes/${id}`, { method: 'DELETE' });
    toast('Offert borttagen', 'success');
    loadQuotes();
}

async function convertQuoteToInvoice(qid) {
    if (!confirm('Konvertera denna offert till en faktura?')) return;
    const res = await api(`/api/quotes/${qid}/convert-to-invoice`, { method: 'POST' });
    if (res && res.ok) {
        toast(`Faktura ${res.invoice.id} skapad!`, 'success');
        closeModal();
        navigate('invoices');
    } else {
        toast(res?.error || 'Kunde inte skapa faktura', 'error');
    }
}

// ===== INVOICES / FAKTUROR ================================================
async function renderInvoices() {
    const c = state.constants;
    el('pageContent').innerHTML = `
        <div class="page-header">
            <div class="page-header-row">
                <div><h1>Fakturor</h1><p>Hantera fakturor och betalningsstatus</p></div>
                <button class="btn btn-primary" onclick="openInvoiceModal()">+ Ny faktura</button>
            </div>
        </div>
        <div class="filter-bar">
            <select id="invStatus" onchange="loadInvoices()">
                <option value="Alla">Alla statusar</option>
                ${c.invoice_statuses.map(s => `<option>${s}</option>`).join('')}
            </select>
            <select id="invBolag" onchange="loadInvoices()">
                <option value="Alla">Alla bolag</option>
                ${c.businesses.map(b => `<option>${b}</option>`).join('')}
            </select>
        </div>
        <div class="card"><div class="table-wrapper" id="invTable"><div class="spinner"></div></div></div>`;
    loadInvoices();
}

async function loadInvoices() {
    const params = new URLSearchParams();
    const status = el('invStatus')?.value;
    const bolag = el('invBolag')?.value;
    if (status && status !== 'Alla') params.set('status', status);
    if (bolag && bolag !== 'Alla') params.set('bolag', bolag);
    const data = await api(`/api/invoices?${params}`);
    if (!data || !data.length) {
        el('invTable').innerHTML = '<div class="empty-state"><h3>Inga fakturor</h3><p>Skapa din första faktura eller konvertera en offert.</p></div>';
        return;
    }
    const totalSum = data.reduce((s, inv) => s + Number(inv.total || 0), 0);
    const unpaid = data.filter(inv => inv.status === 'Obetald').reduce((s, inv) => s + Number(inv.total || 0), 0);
    el('invTable').innerHTML = `
        <div class="flex gap-4 mb-4" style="padding:0 4px">
            <div class="text-sm"><span class="text-muted">Totalt fakturerat:</span> <strong class="font-mono">${fmt(totalSum)} kr</strong></div>
            <div class="text-sm"><span class="text-muted">Obetalt:</span> <strong class="font-mono" style="color:var(--danger)">${fmt(unpaid)} kr</strong></div>
        </div>
        <table>
            <thead><tr><th>Faktura-ID</th><th>Kund</th><th>Titel</th><th>Bolag</th><th class="text-right">Summa</th><th>Förfallodatum</th><th>Status</th><th></th></tr></thead>
            <tbody>${data.map(inv => `
                <tr class="receipt-row" onclick="openInvoiceDetail('${inv.id}')">
                    <td class="font-mono text-sm" style="font-weight:600">${inv.id}</td>
                    <td>${inv.customer_name || '—'}</td>
                    <td>${inv.title || '—'}</td>
                    <td><span class="tag tag-primary">${inv.bolag}</span></td>
                    <td class="text-right font-mono">${fmt(inv.total)} kr</td>
                    <td class="${isOverdue(inv) ? 'text-danger' : ''}">${inv.due_date || '—'}</td>
                    <td>${invoiceStatusTag(inv.status)}</td>
                    <td class="flex gap-1">
                        <a href="/api/invoices/${inv.id}/pdf" target="_blank" class="btn btn-ghost btn-xs" onclick="event.stopPropagation()" title="Ladda ner PDF">📄</a>
                        <button class="btn btn-ghost btn-xs" onclick="event.stopPropagation();deleteInvoice('${inv.id}')">✕</button>
                    </td>
                </tr>`).join('')}
            </tbody>
        </table>`;
}

function isOverdue(inv) {
    return inv.status === 'Obetald' && inv.due_date && inv.due_date < new Date().toISOString().slice(0, 10);
}

function invoiceStatusTag(s) {
    const map = { 'Obetald': 'warning', 'Betald': 'success', 'Förfallen': 'danger', 'Krediterad': 'neutral' };
    return `<span class="tag tag-${map[s] || 'neutral'}">${s || '—'}</span>`;
}

function openInvoiceModal() {
    const c = state.constants;
    openModal('Ny faktura', `
        <form onsubmit="return submitInvoice(event)">
            <div class="form-row">
                <div class="form-group"><label>Titel</label><input class="form-control" id="invTitle" required placeholder="Fakturans titel"></div>
                <div class="form-group"><label>Bolag</label><select class="form-control" id="invBolagF">${c.businesses.map(b => `<option>${b}</option>`).join('')}</select></div>
            </div>
            <div class="form-row">
                <div class="form-group"><label>Kund-namn</label><input class="form-control" id="invCustName" placeholder="Kundnamn" list="invCustomerList"></div>
                <div class="form-group"><label>Förfallodatum</label><input type="date" class="form-control" id="invDueDate" value="${new Date(Date.now() + 30*86400000).toISOString().slice(0,10)}"></div>
            </div>
            <datalist id="invCustomerList"></datalist>
            <div class="form-group"><label>Beskrivning</label><textarea class="form-control" id="invDesc" rows="2" placeholder="Kort beskrivning"></textarea></div>
            <h3 style="margin:16px 0 8px;font-size:0.9rem;font-weight:700">Rader</h3>
            <div id="invoiceItems">
                <div class="quote-item-row">
                    <input class="form-control" placeholder="Beskrivning" data-field="description" style="flex:3">
                    <input type="number" class="form-control" placeholder="Antal" value="1" data-field="quantity" style="flex:0.7">
                    <input type="number" class="form-control" placeholder="À-pris" data-field="unit_price" style="flex:1">
                    <select class="form-control" data-field="moms" style="flex:0.7">
                        ${c.vat_rates.map(v => `<option ${v===25?'selected':''}>${v}</option>`).join('')}
                    </select>
                    <button type="button" class="btn btn-ghost btn-xs" onclick="this.closest('.quote-item-row').remove()">✕</button>
                </div>
            </div>
            <button type="button" class="btn btn-secondary btn-sm mt-2" onclick="addInvoiceItemRow()">+ Lägg till rad</button>
            <button type="submit" class="btn btn-primary mt-4" style="width:100%">Skapa faktura</button>
        </form>
    `);
    loadInvoiceCustomerDatalist();
}

async function loadInvoiceCustomerDatalist() {
    const customers = await api('/api/customers');
    const dl = document.getElementById('invCustomerList');
    if (dl && customers) {
        dl.innerHTML = customers.map(c => `<option value="${c.name}">`).join('');
    }
}

function addInvoiceItemRow() {
    const c = state.constants;
    const row = document.createElement('div');
    row.className = 'quote-item-row';
    row.innerHTML = `
        <input class="form-control" placeholder="Beskrivning" data-field="description" style="flex:3">
        <input type="number" class="form-control" placeholder="Antal" value="1" data-field="quantity" style="flex:0.7">
        <input type="number" class="form-control" placeholder="À-pris" data-field="unit_price" style="flex:1">
        <select class="form-control" data-field="moms" style="flex:0.7">
            ${c.vat_rates.map(v => `<option ${v===25?'selected':''}>${v}</option>`).join('')}
        </select>
        <button type="button" class="btn btn-ghost btn-xs" onclick="this.closest('.quote-item-row').remove()">✕</button>
    `;
    document.getElementById('invoiceItems').appendChild(row);
}

async function submitInvoice(ev) {
    ev.preventDefault();
    const items = [];
    document.querySelectorAll('#invoiceItems .quote-item-row').forEach(row => {
        const desc = row.querySelector('[data-field="description"]').value;
        const qty = Number(row.querySelector('[data-field="quantity"]').value) || 1;
        const price = Number(row.querySelector('[data-field="unit_price"]').value) || 0;
        const moms = Number(row.querySelector('[data-field="moms"]').value) || 25;
        if (desc || price) {
            items.push({ description: desc, quantity: qty, unit_price: price, moms, total: qty * price });
        }
    });
    const customers = await api('/api/customers');
    const custName = el('invCustName').value;
    const custMatch = (customers || []).find(c => c.name === custName);
    await api('/api/invoices', {
        method: 'POST',
        body: JSON.stringify({
            title: el('invTitle').value,
            bolag: el('invBolagF').value,
            customer_name: custName,
            customer_id: custMatch?.id || '',
            due_date: el('invDueDate').value,
            description: el('invDesc').value,
            items,
        }),
    });
    closeModal();
    toast('Faktura skapad', 'success');
    loadInvoices();
}

async function openInvoiceDetail(iid) {
    const invoices = await api('/api/invoices');
    const inv = (invoices || []).find(x => x.id === iid);
    if (!inv) return;

    let items = inv.items || '[]';
    if (typeof items === 'string') { try { items = JSON.parse(items); } catch { items = []; } }

    const c = state.constants;
    const statusButtons = c.invoice_statuses.map(s =>
        `<button class="btn ${s === inv.status ? 'btn-primary' : 'btn-secondary'} btn-sm" onclick="changeInvoiceStatus('${inv.id}','${s}')">${s}</button>`
    ).join(' ');

    const itemsHtml = items.length ? `
        <table style="margin:12px 0">
            <thead><tr><th>Beskrivning</th><th class="text-right">Antal</th><th class="text-right">À-pris</th><th class="text-right">Moms</th><th class="text-right">Summa</th></tr></thead>
            <tbody>${items.map(it => `
                <tr>
                    <td>${it.description || '—'}</td>
                    <td class="text-right">${it.quantity}</td>
                    <td class="text-right font-mono">${fmt(it.unit_price)} kr</td>
                    <td class="text-right">${it.moms}%</td>
                    <td class="text-right font-mono">${fmt(it.total)} kr</td>
                </tr>`).join('')}
            </tbody>
            <tfoot>
                <tr><td colspan="4" class="text-right" style="font-weight:600">Delsumma</td><td class="text-right font-mono">${fmt(inv.subtotal)} kr</td></tr>
                <tr><td colspan="4" class="text-right text-muted">Moms</td><td class="text-right font-mono text-muted">${fmt(inv.moms_total)} kr</td></tr>
                <tr><td colspan="4" class="text-right" style="font-weight:700;font-size:1.05rem">Att betala</td><td class="text-right font-mono" style="font-weight:700;font-size:1.05rem">${fmt(inv.total)} kr</td></tr>
            </tfoot>
        </table>` : '<p class="text-muted">Inga rader</p>';

    const overdue = isOverdue(inv);

    openModal(`Faktura ${inv.id}`, `
        <div class="receipt-detail">
            ${overdue ? '<div class="alert alert-danger mb-4">🚨 Denna faktura är förfallen!</div>' : ''}
            <div class="receipt-detail-meta">
                <div class="receipt-detail-row"><span class="receipt-detail-label">Kund</span><span style="font-weight:600">${inv.customer_name || '—'}</span></div>
                <div class="receipt-detail-row"><span class="receipt-detail-label">Titel</span><span>${inv.title}</span></div>
                <div class="receipt-detail-row"><span class="receipt-detail-label">Bolag</span><span class="tag tag-primary">${inv.bolag}</span></div>
                <div class="receipt-detail-row"><span class="receipt-detail-label">Förfallodatum</span><span class="${overdue ? 'text-danger' : ''}" style="font-weight:600">${inv.due_date || '—'}</span></div>
                ${inv.quote_id ? `<div class="receipt-detail-row"><span class="receipt-detail-label">Offert-ref</span><span class="font-mono text-sm">${inv.quote_id}</span></div>` : ''}
                <div class="receipt-detail-row"><span class="receipt-detail-label">Skapad av</span><span>${inv.created_by}</span></div>
                <div class="receipt-detail-row"><span class="receipt-detail-label">Datum</span><span class="text-muted">${(inv.created || '').slice(0,10)}</span></div>
            </div>
            ${inv.description ? `<div style="margin:12px 0;padding:12px;background:var(--bg);border-radius:var(--radius-sm);font-size:0.9rem">${inv.description}</div>` : ''}
            <h3 style="margin:16px 0 8px;font-size:0.9rem;font-weight:700">Rader</h3>
            ${itemsHtml}
            <h3 style="margin:16px 0 8px;font-size:0.9rem;font-weight:700">Betalningsstatus</h3>
            <div class="flex gap-2 flex-wrap">${statusButtons}</div>
            <div class="flex gap-2 mt-4">
                <a href="/api/invoices/${inv.id}/pdf" target="_blank" class="btn btn-secondary flex-1">📄 Ladda ner PDF</a>
            </div>
        </div>
    `, inv.customer_name || '');
}

async function changeInvoiceStatus(iid, status) {
    await api(`/api/invoices/${iid}/status`, {
        method: 'PUT',
        body: JSON.stringify({ status }),
    });
    toast(`Faktura ändrad till ${status}`, 'success');
    openInvoiceDetail(iid);
    setTimeout(() => { if (state.page === 'invoices') loadInvoices(); }, 500);
}

async function deleteInvoice(id) {
    if (!confirm('Ta bort denna faktura?')) return;
    await api(`/api/invoices/${id}`, { method: 'DELETE' });
    toast('Faktura borttagen', 'success');
    loadInvoices();
}

// ===== INTEGRATIONS =======================================================
async function renderIntegrations() {
    if (state.role !== 'admin') {
        el('pageContent').innerHTML = `
            <div class="page-header"><h1>Integrationer</h1></div>
            <div class="card card-body"><p>Du behöver admin-behörighet för att hantera integrationer.</p></div>`;
        return;
    }

    el('pageContent').innerHTML = `
        <div class="page-header">
            <div class="page-header-row">
                <div><h1>🔗 Integrationer</h1><p>Koppla externa tjänster för automatisk synkning av data</p></div>
                <div class="flex gap-2">
                    <button class="btn btn-secondary" onclick="syncAllIntegrations()">🔄 Synka alla</button>
                    <button class="btn btn-primary" onclick="openAddIntegrationModal()">+ Ny integration</button>
                </div>
            </div>
        </div>
        <div id="integrationsContent"><div class="spinner"></div></div>`;
    loadIntegrations();
}

async function loadIntegrations() {
    const [integrations, platforms] = await Promise.all([
        api('/api/integrations'),
        api('/api/integrations/platforms'),
    ]);
    if (!integrations) return;

    if (!integrations.length) {
        el('integrationsContent').innerHTML = `
            <div class="empty-state">
                <h3>Inga integrationer konfigurerade</h3>
                <p>Koppla Shopify, annonsplattformar och mer för att automatisera din bokföring.</p>
                <button class="btn btn-primary mt-4" onclick="openAddIntegrationModal()">+ Lägg till integration</button>
            </div>
            <div class="grid-3 mt-6" id="platformShowcase"></div>`;
        renderPlatformShowcase(platforms);
        return;
    }

    const cards = integrations.map(integ => {
        const enabled = String(integ.enabled).toLowerCase() === 'true';
        const platform = (platforms || []).find(p => p.platform === integ.platform) || {};
        const icon = platform.icon || '🔗';
        const name = platform.display_name || integ.platform;

        const statusClass = integ.last_sync_status === 'success' ? 'tag-success'
            : integ.last_sync_status === 'error' ? 'tag-danger' : 'tag-neutral';
        const statusLabel = integ.last_sync_status === 'success' ? 'OK'
            : integ.last_sync_status === 'error' ? 'Fel' : 'Aldrig synkad';

        return `
        <div class="card integration-card ${!enabled ? 'integration-disabled' : ''}">
            <div class="card-body">
                <div class="integration-header">
                    <div class="integration-icon">${icon}</div>
                    <div class="integration-title">
                        <h3>${escHtml(name)}</h3>
                        <span class="tag tag-sm ${enabled ? 'tag-success' : 'tag-neutral'}">${enabled ? 'Aktiv' : 'Pausad'}</span>
                    </div>
                </div>
                <div class="integration-details">
                    <div><strong>Bolag:</strong> ${escHtml(integ.bolag)}</div>
                    <div><strong>Senast synkad:</strong> ${integ.last_sync || 'Aldrig'}</div>
                    <div><strong>Status:</strong> <span class="tag tag-sm ${statusClass}">${statusLabel}</span></div>
                    ${integ.sync_errors ? `<div class="text-danger text-sm mt-2">${escHtml(integ.sync_errors)}</div>` : ''}
                </div>
                <div class="integration-actions mt-4">
                    <button class="btn btn-primary btn-sm" onclick="syncIntegration('${escHtml(integ.id)}')">🔄 Synka nu</button>
                    <button class="btn btn-secondary btn-sm" onclick="testIntegration('${escHtml(integ.id)}')">🧪 Testa</button>
                    <button class="btn btn-ghost btn-sm" onclick="toggleIntegration('${escHtml(integ.id)}')">${enabled ? '⏸ Pausa' : '▶ Aktivera'}</button>
                    <button class="btn btn-ghost btn-sm" onclick="editIntegration('${escHtml(integ.id)}', '${escHtml(integ.platform)}')">✏️</button>
                    <button class="btn btn-ghost btn-sm text-danger" onclick="deleteIntegration('${escHtml(integ.id)}')">🗑️</button>
                </div>
            </div>
        </div>`;
    }).join('');

    // Available platforms that aren't configured yet
    const configuredPlatforms = integrations.map(i => i.platform);
    const available = (platforms || []).filter(p => !configuredPlatforms.includes(p.platform));
    const availableHtml = available.length ? `
        <div class="mt-6">
            <h3 class="text-muted mb-4">Tillgängliga integrationer</h3>
            <div class="grid-3">${available.map(p => `
                <div class="card card-body integration-available" onclick="openAddIntegrationModal('${p.platform}')" style="cursor:pointer">
                    <div class="integration-header">
                        <div class="integration-icon">${p.icon}</div>
                        <div><h4>${escHtml(p.display_name)}</h4><p class="text-sm text-muted">${escHtml(p.description)}</p></div>
                    </div>
                </div>`).join('')}
            </div>
        </div>` : '';

    el('integrationsContent').innerHTML = `
        <div class="grid-2">${cards}</div>
        ${availableHtml}`;
}

function renderPlatformShowcase(platforms) {
    const container = el('platformShowcase');
    if (!container || !platforms) return;
    container.innerHTML = platforms.map(p => `
        <div class="card card-body integration-available" onclick="openAddIntegrationModal('${p.platform}')" style="cursor:pointer">
            <div class="integration-header">
                <div class="integration-icon">${p.icon}</div>
                <div>
                    <h4>${escHtml(p.display_name)}</h4>
                    <p class="text-sm text-muted">${escHtml(p.description)}</p>
                </div>
            </div>
        </div>`).join('');
}

async function openAddIntegrationModal(preselect) {
    const platforms = await api('/api/integrations/platforms');
    if (!platforms) return;
    const c = state.constants;

    const platformOpts = platforms.map(p =>
        `<option value="${p.platform}" ${p.platform === preselect ? 'selected' : ''}>${p.icon} ${p.display_name}</option>`
    ).join('');

    openModal('Ny integration', `
        <form onsubmit="return submitIntegration(event)">
            <div class="form-group">
                <label>Plattform</label>
                <select class="form-control" id="intPlatform" onchange="updateIntegrationFields()" required>
                    <option value="">Välj plattform...</option>
                    ${platformOpts}
                </select>
            </div>
            <div class="form-group">
                <label>Bolag</label>
                <select class="form-control" id="intBolag">
                    ${c.businesses.map(b => `<option>${b}</option>`).join('')}
                </select>
            </div>
            <div id="intFields"></div>
            <div id="intDescription" class="text-sm text-muted mb-4"></div>
            <button type="submit" class="btn btn-primary" style="width:100%">Spara integration</button>
        </form>
    `);
    if (preselect) updateIntegrationFields();

    // Store platforms for field rendering
    window._intPlatforms = platforms;
}

function updateIntegrationFields() {
    const platform = el('intPlatform')?.value;
    const platforms = window._intPlatforms || [];
    const p = platforms.find(x => x.platform === platform);
    if (!p) { el('intFields').innerHTML = ''; el('intDescription').innerHTML = ''; return; }

    el('intDescription').innerHTML = `<p>${escHtml(p.description)}</p>`;
    el('intFields').innerHTML = p.required_fields.map(f => `
        <div class="form-group">
            <label>${escHtml(f.label)}</label>
            <input class="form-control int-field" data-key="${f.key}" type="${f.type === 'password' ? 'password' : 'text'}" required placeholder="${escHtml(f.label)}">
        </div>`).join('');
}

async function submitIntegration(e) {
    e.preventDefault();
    const body = {
        platform: el('intPlatform').value,
        bolag: el('intBolag').value,
    };
    document.querySelectorAll('.int-field').forEach(input => {
        body[input.dataset.key] = input.value;
    });

    const res = await api('/api/integrations', {
        method: 'POST',
        body: JSON.stringify(body),
    });
    closeModal();
    if (res && res.ok) {
        toast('Integration sparad!', 'success');
    } else {
        toast(res?.error || 'Kunde inte spara', 'error');
    }
    loadIntegrations();
}

async function editIntegration(intId, platform) {
    // Re-open the add modal with the platform preselected
    await openAddIntegrationModal(platform);
}

async function syncIntegration(intId) {
    toast('Synkar...', 'info');
    const res = await api(`/api/integrations/${intId}/sync`, {
        method: 'POST',
        body: JSON.stringify({}),
    });
    if (res && res.ok) {
        const msg = `Synk klar! +${res.added_expenses} utgifter, +${res.added_revenue} intäkter` +
                    (res.skipped > 0 ? `, ${res.skipped} redan importerade` : '');
        toast(msg, 'success');
    } else {
        toast(`Synkfel: ${res?.error || 'Okänt fel'}`, 'error');
    }
    loadIntegrations();
}

async function testIntegration(intId) {
    toast('Testar anslutning...', 'info');
    const res = await api(`/api/integrations/${intId}/test`, { method: 'POST' });
    if (res && res.ok) {
        toast(`✅ ${res.message}`, 'success');
    } else {
        toast(`❌ ${res?.message || res?.error || 'Kunde inte ansluta'}`, 'error');
    }
}

async function toggleIntegration(intId) {
    await api(`/api/integrations/${intId}/toggle`, { method: 'PUT' });
    loadIntegrations();
}

async function deleteIntegration(intId) {
    if (!confirm('Ta bort denna integration? All konfiguration tas bort.')) return;
    await api(`/api/integrations/${intId}`, { method: 'DELETE' });
    toast('Integration borttagen', 'success');
    loadIntegrations();
}

async function syncAllIntegrations() {
    toast('Synkar alla integrationer...', 'info');
    const res = await api('/api/integrations/sync-all', {
        method: 'POST',
        body: JSON.stringify({}),
    });
    if (res && res.ok) {
        const results = res.results || [];
        const ok = results.filter(r => r.ok).length;
        const fail = results.filter(r => !r.ok).length;
        toast(`Klart! ${ok} lyckades${fail > 0 ? `, ${fail} misslyckades` : ''}`, ok > 0 ? 'success' : 'error');
    } else {
        toast('Synk misslyckades', 'error');
    }
    loadIntegrations();
}

// ===== SETTINGS ===========================================================
async function renderSettings() {
    if (state.role !== 'admin') {
        el('pageContent').innerHTML = `<div class="page-header"><h1>Inställningar</h1></div><div class="card card-body"><p>Du har inte behörighet att komma åt inställningar.</p></div>`;
        return;
    }

    el('pageContent').innerHTML = `
        <div class="page-header"><h1>Inställningar</h1><p>Administrera användare, mål och systemet</p></div>
        <div class="tabs">
            <button class="tab active" onclick="switchSettingsTab('users', this)">Användare</button>
            <button class="tab" onclick="switchSettingsTab('goals', this)">Årsmål</button>
            <button class="tab" onclick="switchSettingsTab('log', this)">Aktivitetslogg</button>
        </div>
        <div id="settingsContent"><div class="spinner"></div></div>`;
    loadSettingsUsers();
}

function switchSettingsTab(tab, btn) {
    document.querySelectorAll('.tabs .tab').forEach(t => t.classList.remove('active'));
    btn.classList.add('active');
    if (tab === 'users') loadSettingsUsers();
    else if (tab === 'goals') loadSettingsGoals();
    else if (tab === 'log') loadSettingsLog();
}

async function loadSettingsUsers() {
    const users = await api('/api/admin/users');
    el('settingsContent').innerHTML = `
        <div class="card">
            <div class="card-header">
                <h3>Användare</h3>
                <button class="btn btn-primary btn-sm" onclick="openAddUserModal()">+ Ny användare</button>
            </div>
            <div class="table-wrapper">
                <table>
                    <thead><tr><th>Användare</th><th>Roll</th><th>Behörigheter</th><th></th></tr></thead>
                    <tbody>${(users || []).map(u => `
                        <tr>
                            <td style="font-weight:600">${escHtml(u.username)}</td>
                            <td><span class="tag ${u.role === 'admin' ? 'tag-primary' : 'tag-neutral'}">${escHtml(u.role)}</span></td>
                            <td class="text-sm text-muted">${(u.permissions || []).map(p => escHtml(p)).join(', ') || '—'}</td>
                            <td>
                                <button class="btn btn-ghost btn-xs" onclick="openEditUserModal('${escHtml(u.username)}', '${escHtml(u.role)}', ${JSON.stringify(u.permissions || []).replace(/"/g, '&quot;')})">✏️</button>
                                ${u.username !== 'Viktor' ? `<button class="btn btn-ghost btn-xs" onclick="deleteUser('${escHtml(u.username)}')">🗑️</button>` : ''}
                            </td>
                        </tr>
                    `).join('')}</tbody>
                </table>
            </div>
        </div>`;
}

function openAddUserModal() {
    openModal('Ny användare', `
        <form onsubmit="return submitNewUser(event)">
            <div class="form-group"><label>Användarnamn</label><input class="form-control" id="newUserName" required></div>
            <div class="form-group"><label>Lösenord (minst 6 tecken)</label><input class="form-control" id="newUserPw" type="password" required minlength="6" placeholder="Ange lösenord"></div>
            <div class="form-group"><label>Roll</label><select class="form-control" id="newUserRole"><option>user</option><option>admin</option></select></div>
            <button type="submit" class="btn btn-primary mt-4" style="width:100%">Skapa</button>
        </form>
    `);
}

async function submitNewUser(e) {
    e.preventDefault();
    const res = await api('/api/admin/users', {
        method: 'POST',
        body: JSON.stringify({
            username: el('newUserName').value,
            password: el('newUserPw').value,
            role: el('newUserRole').value,
        }),
    });
    closeModal();
    if (res && res.ok) toast('Användare skapad', 'success');
    else toast(res?.error || 'Kunde inte skapa', 'error');
    loadSettingsUsers();
}

function openEditUserModal(username, role, permissions) {
    const allPerms = ['access_settings', 'access_reports', 'create_chat', 'archive_chat'];
    openModal(`Redigera — ${username}`, `
        <form onsubmit="return submitEditUser(event, '${username}')">
            <div class="form-group"><label>Roll</label><select class="form-control" id="editRole"><option ${role==='user'?'selected':''}>user</option><option ${role==='admin'?'selected':''}>admin</option></select></div>
            <div class="form-group"><label>Nytt lösenord (lämna tomt för att behålla)</label><input class="form-control" id="editPw" placeholder="Nytt lösenord"></div>
            <div class="form-group"><label>Behörigheter</label>
                ${allPerms.map(p => `<label style="display:flex;align-items:center;gap:8px;padding:4px 0;cursor:pointer"><input type="checkbox" value="${p}" class="editPerm" ${permissions.includes(p)?'checked':''}> ${p}</label>`).join('')}
            </div>
            <button type="submit" class="btn btn-primary mt-4" style="width:100%">Spara</button>
        </form>
    `);
}

async function submitEditUser(e, username) {
    e.preventDefault();
    const perms = [];
    document.querySelectorAll('.editPerm:checked').forEach(cb => perms.push(cb.value));
    const body = { role: el('editRole').value, permissions: perms };
    const pw = el('editPw').value;
    if (pw) body.password = pw;
    await api(`/api/admin/users/${username}`, {
        method: 'PUT',
        body: JSON.stringify(body),
    });
    closeModal();
    toast('Användare uppdaterad', 'success');
    loadSettingsUsers();
}

async function deleteUser(username) {
    if (!confirm(`Ta bort ${username}?`)) return;
    await api(`/api/admin/users/${username}`, { method: 'DELETE' });
    toast('Användare borttagen', 'success');
    loadSettingsUsers();
}

// Goals
async function loadSettingsGoals() {
    const [goals, c] = [await api('/api/goals'), state.constants];
    let html = '';
    for (const biz of c.businesses) {
        const g = goals[biz] || {};
        html += `
        <div class="card mb-4">
            <div class="card-header"><h3>${biz}</h3></div>
            <div class="card-body">
                <form onsubmit="return submitGoal(event, '${biz}')">
                    <div class="form-row">
                        <div class="form-group"><label>Årligt intäktsmål (kr)</label><input type="number" class="form-control" id="goal_rev_${biz}" value="${g.annual_revenue || 0}"></div>
                        <div class="form-group"><label>Årligt vinstmål (kr)</label><input type="number" class="form-control" id="goal_prof_${biz}" value="${g.annual_profit || 0}"></div>
                    </div>
                    <button type="submit" class="btn btn-primary btn-sm mt-4">Spara mål</button>
                </form>
            </div>
        </div>`;
    }
    el('settingsContent').innerHTML = html;
}

async function submitGoal(e, biz) {
    e.preventDefault();
    await api('/api/goals', {
        method: 'POST',
        body: JSON.stringify({
            bolag: biz,
            annual_revenue: Number(el(`goal_rev_${biz}`).value) || 0,
            annual_profit: Number(el(`goal_prof_${biz}`).value) || 0,
        }),
    });
    toast('Mål sparat', 'success');
}

// Activity log
async function loadSettingsLog() {
    const logs = await api('/api/admin/activity-log');
    el('settingsContent').innerHTML = `
        <div class="card">
            <div class="card-header"><h3>Aktivitetslogg</h3></div>
            <div class="card-body">
                ${(logs || []).map(a => `
                    <div class="activity-item">
                        <div class="activity-dot"></div>
                        <div class="flex-1">
                            <div><span class="activity-user">${escHtml(a.user)}</span> ${escHtml(a.action)}</div>
                            <div class="activity-time">${escHtml(a.timestamp)}${a.details ? ' — ' + escHtml(a.details) : ''}</div>
                        </div>
                    </div>
                `).join('') || '<div class="text-muted text-sm">Ingen aktivitet</div>'}
            </div>
        </div>`;
}

// ===== PROJECTS ===========================================================

async function renderProjects() {
    const c = state.constants;
    el('pageContent').innerHTML = `
        <div class="page-header">
            <div class="page-header-row">
                <div><h1>Projekt</h1><p>Hantera arbetsgrupper, uppgifter och filer</p></div>
                <button class="btn btn-primary" onclick="openCreateProjectModal()">+ Nytt projekt</button>
            </div>
        </div>
        <div class="project-layout">
            <div class="project-sidebar" id="projectSidebar">
                <div class="project-sidebar-header"><h3>Projekt</h3></div>
                <div class="project-list" id="projectList"><div class="spinner"></div></div>
            </div>
            <div class="project-main" id="projectMain">
                <div class="project-empty">Välj ett projekt eller skapa ett nytt</div>
            </div>
        </div>`;
    loadProjectList();
}

async function loadProjectList() {
    const projects = await api('/api/projects');
    if (!projects || !projects.length) {
        el('projectList').innerHTML = '<div class="card-body text-muted text-sm">Inga projekt ännu</div>';
        return;
    }
    el('projectList').innerHTML = projects.map(p => {
        const statusIcon = p.status === 'Aktivt' ? '🟢' : p.status === 'Pausat' ? '🟡' : '⚪';
        const canDelete = state.role === 'admin' || p.created_by === state.user;
        return `
        <div class="project-list-item${state.selectedProjectId === p.id ? ' active' : ''}" onclick="selectProject('${escHtml(p.id)}')">
            <div style="display:flex;justify-content:space-between;align-items:center">
                <div class="project-list-name">${statusIcon} ${escHtml(p.name)}</div>
                ${canDelete ? `<button class="btn btn-ghost btn-xs" onclick="event.stopPropagation();deleteProject('${escHtml(p.id)}','${escHtml(p.name).replace(/'/g, "\\'")}')" title="Ta bort">✕</button>` : ''}
            </div>
            <div class="project-list-meta">${escHtml(p.bolag)} · ${Array.isArray(p.members) ? p.members.length : 0} medlemmar</div>
        </div>`;
    }).join('');
}

async function selectProject(pid) {
    state.selectedProjectId = pid;
    loadProjectList();
    const projects = await api('/api/projects');
    const proj = (projects || []).find(p => p.id === pid);
    if (!proj) return;
    const members = Array.isArray(proj.members) ? proj.members : [];
    el('projectMain').innerHTML = `
        <div class="project-detail">
            <div class="project-detail-header">
                <div>
                    <h2>${escHtml(proj.name)}</h2>
                    <p class="text-muted">${escHtml(proj.description || 'Ingen beskrivning')}</p>
                </div>
                <div class="flex gap-2">
                    <select class="form-control" style="width:auto" onchange="updateProjectStatus('${pid}',this.value)">
                        ${(state.constants?.project_statuses || ['Aktivt','Pausat','Avslutat']).map(s => `<option${s === proj.status ? ' selected' : ''}>${s}</option>`).join('')}
                    </select>
                    <button class="btn btn-secondary btn-sm" onclick="openEditProjectModal('${pid}')">✏️ Redigera</button>
                </div>
            </div>
            <div class="project-tabs">
                <button class="project-tab active" onclick="switchProjectTab(this, 'tasks', '${pid}')">📋 Uppgifter</button>
                <button class="project-tab" onclick="switchProjectTab(this, 'members', '${pid}')">👥 Medlemmar (${members.length})</button>
                <button class="project-tab" onclick="switchProjectTab(this, 'files', '${pid}')">📁 Filer</button>
            </div>
            <div id="projectTabContent"><div class="spinner"></div></div>
        </div>`;
    loadProjectTasks(pid);
}

function switchProjectTab(btn, tab, pid) {
    document.querySelectorAll('.project-tab').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    if (tab === 'tasks') loadProjectTasks(pid);
    else if (tab === 'members') loadProjectMembers(pid);
    else if (tab === 'files') loadProjectFiles(pid);
}

// ----- Tasks (Kanban) -----
async function loadProjectTasks(pid) {
    const tasks = await api(`/api/projects/${pid}/tasks`);
    const statuses = ['Att göra', 'Pågår', 'Klar'];
    const statusColors = { 'Att göra': 'var(--warning)', 'Pågår': 'var(--primary)', 'Klar': 'var(--success)' };
    const content = el('projectTabContent');
    content.innerHTML = `
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
            <span class="text-muted text-sm">${(tasks || []).length} uppgifter</span>
            <button class="btn btn-primary btn-sm" onclick="openCreateTaskModal('${pid}')">+ Ny uppgift</button>
        </div>
        <div class="kanban-board">
            ${statuses.map(s => {
                const col = (tasks || []).filter(t => t.status === s);
                return `
                <div class="kanban-column">
                    <div class="kanban-header">
                        <div class="kanban-title" style="color:${statusColors[s]}">${s}</div>
                        <div class="kanban-count">${col.length}</div>
                    </div>
                    <div class="kanban-cards">
                        ${col.length ? col.map(t => `
                            <div class="kanban-card" onclick="openTaskDetailModal('${pid}','${t.id}')">
                                <div class="kanban-card-name">${escHtml(t.title)}</div>
                                ${t.assigned_to ? `<div class="kanban-card-sub">→ ${escHtml(t.assigned_to)}</div>` : ''}
                                <div class="kanban-card-footer">
                                    ${priorityTag(t.priority)}
                                    ${t.deadline ? `<span class="text-muted text-sm">📅 ${t.deadline}</span>` : ''}
                                </div>
                            </div>
                        `).join('') : '<div class="kanban-empty">Inga uppgifter</div>'}
                    </div>
                </div>`;
            }).join('')}
        </div>`;
}

async function openCreateTaskModal(pid) {
    const projects = await api('/api/projects');
    const proj = (projects || []).find(p => p.id === pid);
    const members = Array.isArray(proj?.members) ? proj.members : [];
    const c = state.constants;
    openModal('Ny uppgift', `
        <form onsubmit="return submitProjectTask(event, '${pid}')">
            <div class="form-group"><label>Titel</label><input class="form-control" id="ptaskTitle" required placeholder="Uppgiftens titel"></div>
            <div class="form-group"><label>Beskrivning</label><textarea class="form-control" id="ptaskDesc" rows="2" placeholder="Valfri beskrivning"></textarea></div>
            <div class="form-row">
                <div class="form-group"><label>Tilldelad till</label>
                    <select class="form-control" id="ptaskAssign">
                        <option value="">— Ingen —</option>
                        ${members.map(m => `<option value="${escHtml(m)}">${escHtml(m)}</option>`).join('')}
                    </select>
                </div>
                <div class="form-group"><label>Prioritet</label>
                    <select class="form-control" id="ptaskPriority">
                        ${(c?.task_priorities || ['Hög','Medel','Låg']).map(p => `<option${p==='Medel'?' selected':''}>${p}</option>`).join('')}
                    </select>
                </div>
            </div>
            <div class="form-group"><label>Deadline</label><input type="date" class="form-control" id="ptaskDeadline"></div>
            <button type="submit" class="btn btn-primary mt-4" style="width:100%">Skapa uppgift</button>
        </form>
    `);
}

async function submitProjectTask(e, pid) {
    e.preventDefault();
    await api(`/api/projects/${pid}/tasks`, {
        method: 'POST',
        body: JSON.stringify({
            title: el('ptaskTitle').value,
            description: el('ptaskDesc').value,
            assigned_to: el('ptaskAssign').value,
            priority: el('ptaskPriority').value,
            deadline: el('ptaskDeadline').value,
        }),
    });
    closeModal();
    toast('Uppgift skapad', 'success');
    loadProjectTasks(pid);
}

async function openTaskDetailModal(pid, tid) {
    const tasks = await api(`/api/projects/${pid}/tasks`);
    const task = (tasks || []).find(t => t.id === tid);
    if (!task) return;
    const projects = await api('/api/projects');
    const proj = (projects || []).find(p => p.id === pid);
    const members = Array.isArray(proj?.members) ? proj.members : [];
    const c = state.constants;
    openModal('Uppgift: ' + escHtml(task.title), `
        <form onsubmit="return updateProjectTask(event, '${pid}', '${tid}')">
            <div class="form-group"><label>Titel</label><input class="form-control" id="ptaskEditTitle" value="${escHtml(task.title)}"></div>
            <div class="form-group"><label>Beskrivning</label><textarea class="form-control" id="ptaskEditDesc" rows="2">${escHtml(task.description || '')}</textarea></div>
            <div class="form-row">
                <div class="form-group"><label>Status</label>
                    <select class="form-control" id="ptaskEditStatus">
                        ${(c?.task_statuses || ['Att göra','Pågår','Klar']).map(s => `<option${s===task.status?' selected':''}>${s}</option>`).join('')}
                    </select>
                </div>
                <div class="form-group"><label>Prioritet</label>
                    <select class="form-control" id="ptaskEditPriority">
                        ${(c?.task_priorities || ['Hög','Medel','Låg']).map(p => `<option${p===task.priority?' selected':''}>${p}</option>`).join('')}
                    </select>
                </div>
            </div>
            <div class="form-row">
                <div class="form-group"><label>Tilldelad till</label>
                    <select class="form-control" id="ptaskEditAssign">
                        <option value="">— Ingen —</option>
                        ${members.map(m => `<option value="${escHtml(m)}"${m===task.assigned_to?' selected':''}>${escHtml(m)}</option>`).join('')}
                    </select>
                </div>
                <div class="form-group"><label>Deadline</label><input type="date" class="form-control" id="ptaskEditDeadline" value="${task.deadline || ''}"></div>
            </div>
            <div class="text-muted text-sm mt-2">Skapad av ${escHtml(task.created_by)} · ${escHtml(task.created_at || '')}</div>
            <div class="flex gap-2 mt-4">
                <button type="submit" class="btn btn-primary" style="flex:1">Spara</button>
                <button type="button" class="btn btn-danger" onclick="deleteProjectTask('${pid}','${tid}')">Ta bort</button>
            </div>
        </form>
    `);
}

async function updateProjectTask(e, pid, tid) {
    e.preventDefault();
    await api(`/api/projects/${pid}/tasks/${tid}`, {
        method: 'PUT',
        body: JSON.stringify({
            title: el('ptaskEditTitle').value,
            description: el('ptaskEditDesc').value,
            status: el('ptaskEditStatus').value,
            priority: el('ptaskEditPriority').value,
            assigned_to: el('ptaskEditAssign').value,
            deadline: el('ptaskEditDeadline').value,
        }),
    });
    closeModal();
    toast('Uppgift uppdaterad', 'success');
    loadProjectTasks(pid);
}

async function deleteProjectTask(pid, tid) {
    if (!confirm('Ta bort denna uppgift?')) return;
    await api(`/api/projects/${pid}/tasks/${tid}`, { method: 'DELETE' });
    closeModal();
    toast('Uppgift borttagen', 'success');
    loadProjectTasks(pid);
}

async function updateProjectStatus(pid, status) {
    await api(`/api/projects/${pid}`, {
        method: 'PUT',
        body: JSON.stringify({ status }),
    });
    toast('Status uppdaterad', 'success');
    loadProjectList();
}

// ----- Members tab -----
async function loadProjectMembers(pid) {
    const projects = await api('/api/projects');
    const proj = (projects || []).find(p => p.id === pid);
    if (!proj) return;
    const members = Array.isArray(proj.members) ? proj.members : [];
    const allUsers = await api('/api/users-list');
    const content = el('projectTabContent');
    content.innerHTML = `
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
            <span class="text-muted text-sm">${members.length} medlemmar</span>
            <button class="btn btn-primary btn-sm" onclick="openAddMembersModal('${pid}')">+ Lägg till</button>
        </div>
        <div class="card">
        ${members.map(m => `
            <div class="activity-item" style="padding:12px 16px">
                <div class="user-avatar" style="width:32px;height:32px;font-size:0.8rem">${m[0]?.toUpperCase() || '?'}</div>
                <div class="flex-1">
                    <div style="font-weight:600">${escHtml(m)}</div>
                    <div class="text-muted text-sm">${m === proj.created_by ? 'Skapare' : 'Medlem'}</div>
                </div>
                ${m !== proj.created_by ? `<button class="btn btn-ghost btn-xs" onclick="removeProjectMember('${pid}','${escHtml(m)}')">✕</button>` : ''}
            </div>
        `).join('')}
        </div>`;
}

async function openAddMembersModal(pid) {
    const projects = await api('/api/projects');
    const proj = (projects || []).find(p => p.id === pid);
    const members = Array.isArray(proj?.members) ? proj.members : [];
    const allUsers = await api('/api/users-list');
    const nonMembers = (allUsers || []).filter(u => !members.includes(u));
    if (!nonMembers.length) {
        toast('Alla användare är redan medlemmar', 'info');
        return;
    }
    openModal('Lägg till medlemmar', `
        <form onsubmit="return submitAddMembers(event, '${pid}')">
            ${nonMembers.map(u => `
                <label style="display:flex;align-items:center;gap:8px;padding:6px 0;cursor:pointer">
                    <input type="checkbox" value="${escHtml(u)}" class="addMemberCb"> ${escHtml(u)}
                </label>
            `).join('')}
            <button type="submit" class="btn btn-primary mt-4" style="width:100%">Lägg till valda</button>
        </form>
    `);
}

async function submitAddMembers(e, pid) {
    e.preventDefault();
    const projects = await api('/api/projects');
    const proj = (projects || []).find(p => p.id === pid);
    const members = Array.isArray(proj?.members) ? [...proj.members] : [];
    document.querySelectorAll('.addMemberCb:checked').forEach(cb => {
        if (!members.includes(cb.value)) members.push(cb.value);
    });
    await api(`/api/projects/${pid}`, {
        method: 'PUT',
        body: JSON.stringify({ members }),
    });
    closeModal();
    toast('Medlemmar tillagda', 'success');
    selectProject(pid);
}

async function removeProjectMember(pid, username) {
    if (!confirm(`Ta bort ${username} från projektet?`)) return;
    const projects = await api('/api/projects');
    const proj = (projects || []).find(p => p.id === pid);
    const members = Array.isArray(proj?.members) ? proj.members.filter(m => m !== username) : [];
    await api(`/api/projects/${pid}`, {
        method: 'PUT',
        body: JSON.stringify({ members }),
    });
    toast('Medlem borttagen', 'success');
    selectProject(pid);
}

// ----- Files tab -----
async function loadProjectFiles(pid) {
    const files = await api(`/api/projects/${pid}/files`);
    const content = el('projectTabContent');
    content.innerHTML = `
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
            <span class="text-muted text-sm">${(files || []).length} filer</span>
            <button class="btn btn-primary btn-sm" onclick="openUploadProjectFileModal('${pid}')">📎 Ladda upp fil</button>
        </div>
        ${(files || []).length ? `<div class="card">
            ${files.map(f => `
                <div class="activity-item" style="padding:12px 16px">
                    <div style="font-size:1.2rem">📄</div>
                    <div class="flex-1">
                        <a href="/api/projects/files/${escHtml(f.filename)}" target="_blank" style="font-weight:600;color:var(--primary)">${escHtml(f.original_name || f.filename)}</a>
                        <div class="text-muted text-sm">Uppladdad av ${escHtml(f.uploaded_by)} · ${escHtml(f.uploaded_at || '')}</div>
                    </div>
                    <button class="btn btn-ghost btn-xs" onclick="deleteProjectFile('${pid}','${f.id}')">✕</button>
                </div>
            `).join('')}
        </div>` : '<div class="text-muted text-sm">Inga filer uppladdade ännu</div>'}`;
}

function openUploadProjectFileModal(pid) {
    openModal('Ladda upp fil', `
        <form onsubmit="return submitProjectFile(event, '${pid}')">
            <div class="form-group">
                <label>Välj fil(er)</label>
                <input type="file" class="form-control" id="projFileInput" multiple required>
            </div>
            <button type="submit" class="btn btn-primary mt-4" style="width:100%">Ladda upp</button>
        </form>
    `);
}

async function submitProjectFile(e, pid) {
    e.preventDefault();
    const fileInput = el('projFileInput');
    if (!fileInput.files.length) return;
    const formData = new FormData();
    for (const f of fileInput.files) formData.append('files', f);
    const res = await fetch(`/api/projects/${pid}/files`, { method: 'POST', body: formData });
    const data = await res.json();
    closeModal();
    if (data.ok) {
        toast(`${data.files.length} fil(er) uppladdade`, 'success');
        loadProjectFiles(pid);
    } else {
        toast(data.error || 'Uppladdning misslyckades', 'error');
    }
}

async function deleteProjectFile(pid, fid) {
    if (!confirm('Ta bort denna fil?')) return;
    await api(`/api/projects/${pid}/files/${fid}`, { method: 'DELETE' });
    toast('Fil borttagen', 'success');
    loadProjectFiles(pid);
}

// ----- Create / Edit project modals -----
async function openCreateProjectModal() {
    const c = state.constants;
    const users = await api('/api/users-list');
    openModal('Nytt projekt', `
        <form onsubmit="return submitProject(event)">
            <div class="form-group"><label>Projektnamn</label><input class="form-control" id="projName" required placeholder="Namnge projektet"></div>
            <div class="form-group"><label>Beskrivning</label><textarea class="form-control" id="projDesc" rows="2" placeholder="Valfri beskrivning"></textarea></div>
            <div class="form-group"><label>Verksamhet</label>
                <select class="form-control" id="projBolag">${(c?.businesses || []).map(b => `<option>${b}</option>`).join('')}</select>
            </div>
            <div class="form-group">
                <label>Medlemmar</label>
                ${(users || []).map(u => `
                    <label style="display:flex;align-items:center;gap:8px;padding:6px 0;cursor:pointer">
                        <input type="checkbox" value="${escHtml(u)}" ${u === state.user ? 'checked disabled' : ''} class="projMember"> ${escHtml(u)}
                    </label>
                `).join('')}
            </div>
            <button type="submit" class="btn btn-primary mt-4" style="width:100%">Skapa projekt</button>
        </form>
    `);
}

async function submitProject(e) {
    e.preventDefault();
    const members = [state.user];
    document.querySelectorAll('.projMember:checked').forEach(cb => {
        if (!members.includes(cb.value)) members.push(cb.value);
    });
    await api('/api/projects', {
        method: 'POST',
        body: JSON.stringify({
            name: el('projName').value,
            description: el('projDesc').value,
            bolag: el('projBolag').value,
            members,
        }),
    });
    closeModal();
    toast('Projekt skapat', 'success');
    loadProjectList();
}

async function openEditProjectModal(pid) {
    const projects = await api('/api/projects');
    const proj = (projects || []).find(p => p.id === pid);
    if (!proj) return;
    openModal('Redigera projekt', `
        <form onsubmit="return submitEditProject(event, '${pid}')">
            <div class="form-group"><label>Projektnamn</label><input class="form-control" id="projEditName" value="${escHtml(proj.name)}"></div>
            <div class="form-group"><label>Beskrivning</label><textarea class="form-control" id="projEditDesc" rows="2">${escHtml(proj.description || '')}</textarea></div>
            <button type="submit" class="btn btn-primary mt-4" style="width:100%">Spara</button>
        </form>
    `);
}

async function submitEditProject(e, pid) {
    e.preventDefault();
    await api(`/api/projects/${pid}`, {
        method: 'PUT',
        body: JSON.stringify({
            name: el('projEditName').value,
            description: el('projEditDesc').value,
        }),
    });
    closeModal();
    toast('Projekt uppdaterat', 'success');
    selectProject(pid);
    loadProjectList();
}

async function deleteProject(pid, name) {
    if (!confirm(`Ta bort projektet "${name}" med alla uppgifter och filer?`)) return;
    await api(`/api/projects/${pid}`, { method: 'DELETE' });
    if (state.selectedProjectId === pid) {
        state.selectedProjectId = null;
        el('projectMain').innerHTML = '<div class="project-empty">Välj ett projekt eller skapa ett nytt</div>';
    }
    toast('Projekt borttaget', 'success');
    loadProjectList();
}

// ===== INIT ===============================================================

// Stop chat polling when tab is hidden, restart when visible
document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
        if (state.chatPollTimer) { clearInterval(state.chatPollTimer); state.chatPollTimer = null; }
    } else if (state.page === 'chat' && state.chatGroupId) {
        loadChatMessages();
        state.chatPollTimer = setInterval(loadChatMessages, 30000);
    }
});

init();
