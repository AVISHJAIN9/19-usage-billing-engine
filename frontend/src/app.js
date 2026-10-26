/**
 * Usage & Billing Engine Frontend Application (BIL-139, BIL-145, BIL-146).
 * Manages:
 * - Billing Dashboard KPIs (Gross revenue, MRR, Active subscriptions, Unpaid due)
 * - Invoices List catalog with status filters
 * - Interactive Invoice Detail console with live line items and ledger preview
 */

const API_BASE = window.location.hostname.includes("github.io")
  ? "https://aj-usage-billing-engine.onrender.com"
  : "http://localhost:8190";

let state = {
  tenantId: "tenant-saas",
  customerId: "cust-enterprise-42",
  invoiceId: "inv-2026-demo",
  invoiceNumber: "INV-2026-0001",
  status: "DRAFT",
  issueDate: "2026-10-24",
  dueDate: "2026-11-23",
  subtotalCents: 0,
  discountCents: 0,
  taxCents: 0,
  totalCents: 0,
  lineItems: [],
  invoicesList: [],
  dashboardSummary: null
};

// Formatting utility
function formatCents(cents) {
  const dollars = ((cents || 0) / 100).toFixed(2);
  return `$${dollars}`;
}

// BIL-139: Dashboard updates
async function fetchDashboard() {
  try {
    const res = await fetch(`${API_BASE}/v1/dashboard/summary?tenant_id=${state.tenantId}`);
    if (res.ok) {
      const data = await res.json();
      state.dashboardSummary = data;
      renderDashboard(data);
    }
  } catch (err) {
    console.warn("Could not fetch dashboard summary:", err);
  }
}

function renderDashboard(data) {
  if (!data) return;
  const grossEl = document.getElementById("kpi-gross-revenue");
  if (grossEl) grossEl.textContent = formatCents(data.gross_revenue_cents);

  const mrrEl = document.getElementById("kpi-mrr");
  if (mrrEl) mrrEl.textContent = formatCents(data.mrr_cents);

  const arrSubEl = document.getElementById("kpi-arr-sub");
  if (arrSubEl) arrSubEl.textContent = `ARR: ${formatCents(data.arr_cents)}`;

  const subsEl = document.getElementById("kpi-active-subs");
  if (subsEl) subsEl.textContent = (data.active_subscriptions || 0).toLocaleString();

  const unpaidEl = document.getElementById("kpi-unpaid-invoices");
  if (unpaidEl) unpaidEl.textContent = formatCents(data.unpaid_amount_cents);

  const unpaidCountSub = document.getElementById("kpi-unpaid-count-sub");
  if (unpaidCountSub) unpaidCountSub.textContent = `${data.unpaid_invoices_count || 0} pending collection`;
}

// BIL-145: Invoice List
async function fetchInvoiceList(statusFilter = "") {
  try {
    let url = `${API_BASE}/v1/invoices?tenant_id=${state.tenantId}`;
    if (statusFilter) {
      url += `&status=${statusFilter}`;
    }
    const res = await fetch(url);
    if (res.ok) {
      const data = await res.json();
      state.invoicesList = data;
      renderInvoiceList(data);
    }
  } catch (err) {
    console.warn("Could not fetch invoice list:", err);
  }
}

function renderInvoiceList(invoices) {
  const tbody = document.getElementById("invoice-list-tbody");
  if (!tbody) return;
  tbody.innerHTML = "";

  if (!invoices || invoices.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; color: var(--text-dim); padding: 20px;">No invoices found.</td></tr>`;
    return;
  }

  invoices.forEach(inv => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td class="font-mono" style="font-weight: 600;">${inv.invoice_number || inv.id}</td>
      <td class="font-mono">${inv.customer_id}</td>
      <td><span class="badge badge-${(inv.status || 'draft').toLowerCase()}">${inv.status}</span></td>
      <td class="font-mono">${formatCents(inv.total_cents)}</td>
      <td>${inv.due_date ? new Date(inv.due_date).toLocaleDateString() : '—'}</td>
      <td class="text-right">
        <button class="btn btn-secondary btn-sm" onclick="viewInvoiceDetail('${inv.id}')">View</button>
      </td>
    `;
    tbody.appendChild(tr);
  });
}

window.viewInvoiceDetail = function(invoiceId) {
  state.invoiceId = invoiceId;
  fetchInvoice();
  switchTab("invoice-detail");
};

// BIL-146: Invoice Detail Console
function updateUI() {
  const breadcrumb = document.getElementById("breadcrumb-inv");
  if (breadcrumb) breadcrumb.textContent = state.invoiceNumber || state.invoiceId;

  const invNum = document.getElementById("inv-number");
  if (invNum) invNum.textContent = state.invoiceNumber || "(Unassigned Draft)";

  const custId = document.getElementById("inv-customer-id");
  if (custId) custId.textContent = state.customerId;

  const tenantId = document.getElementById("inv-tenant-id");
  if (tenantId) tenantId.textContent = state.tenantId;

  const issueDate = document.getElementById("inv-issue-date");
  if (issueDate) issueDate.textContent = state.issueDate;

  const dueDate = document.getElementById("inv-due-date");
  if (dueDate) dueDate.textContent = state.dueDate;

  const badge = document.getElementById("inv-status-badge");
  if (badge) {
    badge.textContent = state.status;
    badge.className = `badge badge-${state.status.toLowerCase()}`;
  }

  const tbody = document.getElementById("line-items-tbody");
  if (tbody) {
    tbody.innerHTML = "";
    if (state.lineItems.length === 0) {
      tbody.innerHTML = `<tr><td colspan="5" style="text-align:center; color: var(--text-dim); padding: 24px;">No line items recorded yet.</td></tr>`;
    } else {
      state.lineItems.forEach(item => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td style="font-weight: 500;">${item.description}</td>
          <td><span class="pill-badge font-mono" style="font-size: 11px;">${item.event_type || item.item_type || 'fixed'}</span></td>
          <td class="font-mono">${item.quantity.toLocaleString()}</td>
          <td class="font-mono">${formatCents(item.unit_price_cents)}</td>
          <td class="text-right font-mono" style="font-weight: 600;">${formatCents(item.amount_cents)}</td>
        `;
        tbody.appendChild(tr);
      });
    }
  }

  const itemCountBadge = document.getElementById("item-count-badge");
  if (itemCountBadge) itemCountBadge.textContent = `${state.lineItems.length} Items`;

  const totalDisplay = document.getElementById("inv-total-display");
  if (totalDisplay) totalDisplay.textContent = formatCents(state.totalCents);

  const subtotalVal = document.getElementById("val-subtotal");
  if (subtotalVal) subtotalVal.textContent = formatCents(state.subtotalCents);

  const discountVal = document.getElementById("val-discount");
  if (discountVal) discountVal.textContent = `-${formatCents(state.discountCents)}`;

  const taxVal = document.getElementById("val-tax");
  if (taxVal) taxVal.textContent = formatCents(state.taxCents);

  const totalVal = document.getElementById("val-total");
  if (totalVal) totalVal.textContent = formatCents(state.totalCents);

  const ledgerCust = document.getElementById("ledger-cust-tag");
  if (ledgerCust) ledgerCust.textContent = state.customerId;

  const drEl = document.getElementById("ledger-dr-amount");
  if (drEl) drEl.textContent = formatCents(state.totalCents);

  const crEl = document.getElementById("ledger-cr-amount");
  if (crEl) crEl.textContent = formatCents(state.totalCents);

  const finalizeBtn = document.getElementById("btn-finalize");
  if (finalizeBtn) {
    if (state.status !== "DRAFT") {
      finalizeBtn.disabled = true;
      finalizeBtn.textContent = "Finalized";
      finalizeBtn.classList.remove("btn-primary");
      finalizeBtn.classList.add("btn-secondary");
    } else {
      finalizeBtn.disabled = false;
      finalizeBtn.textContent = "Finalize Invoice";
      finalizeBtn.classList.add("btn-primary");
      finalizeBtn.classList.remove("btn-secondary");
    }
  }
}

async function fetchInvoice() {
  try {
    const res = await fetch(`${API_BASE}/v1/invoices/${state.invoiceId}`);
    if (res.ok) {
      const data = await res.json();
      state.invoiceNumber = data.invoice_number;
      state.status = data.status;
      state.subtotalCents = data.subtotal_cents;
      state.discountCents = data.discount_cents;
      state.taxCents = data.tax_cents;
      state.totalCents = data.total_cents;
      state.customerId = data.customer_id;
      state.tenantId = data.tenant_id;
      state.lineItems = data.line_items || [];
      if (data.created_at) state.issueDate = data.created_at.split("T")[0];
      if (data.due_date) state.dueDate = data.due_date.split("T")[0];
      updateUI();
    }
  } catch (err) {
    console.warn("Could not fetch invoice:", err);
  }
}

function switchTab(tabName) {
  const dashSec = document.getElementById("section-dashboard");
  const listSec = document.getElementById("section-invoice-list");
  const detailSec = document.getElementById("section-invoice-detail");

  const navDash = document.getElementById("nav-dashboard");
  const navInv = document.getElementById("nav-invoices");
  const navDetail = document.getElementById("nav-detail");
  const finalizeBtn = document.getElementById("btn-finalize");

  if (navDash) navDash.classList.remove("active");
  if (navInv) navInv.classList.remove("active");
  if (navDetail) navDetail.classList.remove("active");

  if (tabName === "dashboard") {
    if (dashSec) dashSec.style.display = "block";
    if (listSec) listSec.style.display = "none";
    if (detailSec) detailSec.style.display = "none";
    if (navDash) navDash.classList.add("active");
    if (finalizeBtn) finalizeBtn.style.display = "none";
    fetchDashboard();
  } else if (tabName === "invoices") {
    if (dashSec) dashSec.style.display = "none";
    if (listSec) listSec.style.display = "block";
    if (detailSec) detailSec.style.display = "none";
    if (navInv) navInv.classList.add("active");
    if (finalizeBtn) finalizeBtn.style.display = "none";
    fetchInvoiceList();
  } else {
    if (dashSec) dashSec.style.display = "none";
    if (listSec) listSec.style.display = "none";
    if (detailSec) detailSec.style.display = "block";
    if (navDetail) navDetail.classList.add("active");
    if (finalizeBtn) finalizeBtn.style.display = "inline-block";
  }
}

document.addEventListener("DOMContentLoaded", () => {
  // Navigation
  const navDash = document.getElementById("nav-dashboard");
  if (navDash) navDash.addEventListener("click", (e) => { e.preventDefault(); switchTab("dashboard"); });

  const navInv = document.getElementById("nav-invoices");
  if (navInv) navInv.addEventListener("click", (e) => { e.preventDefault(); switchTab("invoices"); });

  const navDetail = document.getElementById("nav-detail");
  if (navDetail) navDetail.addEventListener("click", (e) => { e.preventDefault(); switchTab("invoice-detail"); });

  // Status filter
  const filterStatus = document.getElementById("filter-status");
  if (filterStatus) {
    filterStatus.addEventListener("change", (e) => {
      fetchInvoiceList(e.target.value);
    });
  }

  // Refresh
  const btnRefresh = document.getElementById("btn-refresh");
  if (btnRefresh) {
    btnRefresh.addEventListener("click", () => {
      fetchDashboard();
      fetchInvoiceList();
      fetchInvoice();
    });
  }

  // Initial load
  fetchDashboard();
  fetchInvoiceList();
  fetchInvoice();
});
