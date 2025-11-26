const API_BASE = "http://localhost:5000/api";

let state = {
    currentRole: "sales",
    currentLang: "en",
    translations: {},
    orderItems: [],
    stageEntries: [],
    products: [],
    customers: [],
    orders: [],
};

const COMMISSION_RATES = { Ruby: 0.08, Kirsty: 0.1, Admin: 0.05 };

async function loadTranslations() {
    const langs = ["en", "zh-TW"];
    for (const lang of langs) {
        const res = await fetch(`lang/${lang}.json`);
        state.translations[lang] = await res.json();
    }
}

function t(key) {
    const dict = state.translations[state.currentLang] || {};
    return dict[key] || state.translations.en?.[key] || key;
}

function applyTranslations() {
    document.documentElement.lang = state.currentLang;
    document.querySelectorAll("[data-i18n]").forEach(el => {
        const key = el.dataset.i18n;
        const translated = t(key);
        if (translated) el.textContent = translated;
    });
    document.querySelectorAll("[data-i18n-placeholder]").forEach(el => {
        const key = el.dataset.i18nPlaceholder;
        const translated = t(key);
        if (translated) el.placeholder = translated;
    });
}

async function fetchJSON(url, options = {}) {
    const headers = { ...(options.headers || {}), "X-Role": state.currentRole };
    if (!(options.body instanceof FormData)) {
        headers["Content-Type"] = "application/json";
    }
    const opts = { ...options, headers };
    if (opts.body && !(opts.body instanceof FormData)) {
        opts.body = JSON.stringify(opts.body);
    }
    const res = await fetch(url, opts);
    if (!res.ok) {
        const msg = await res.text();
        throw new Error(msg || "Request failed");
    }
    const contentType = res.headers.get("content-type") || "";
    if (contentType.includes("application/json")) return res.json();
    return res;
}

function renderTable(el, rows, columns) {
    el.innerHTML = "";
    const thead = document.createElement("thead");
    const headerRow = document.createElement("tr");
    columns.forEach(col => {
        const th = document.createElement("th");
        th.textContent = col.label;
        headerRow.appendChild(th);
    });
    thead.appendChild(headerRow);
    const tbody = document.createElement("tbody");
    rows.forEach(row => {
        const tr = document.createElement("tr");
        columns.forEach(col => {
            const td = document.createElement("td");
            td.innerHTML = col.render ? col.render(row) : (row[col.key] ?? "");
            tr.appendChild(td);
        });
        tbody.appendChild(tr);
    });
    el.appendChild(thead);
    el.appendChild(tbody);
}

function formatCurrency(value, currency = "USD") {
    return new Intl.NumberFormat(state.currentLang === "zh-TW" ? "zh-TW" : "en-GB", { style: "currency", currency }).format(value || 0);
}

function computeVAT(country, amount) {
    if (!amount) return 0;
    const vatCountries = ["UK", "United Kingdom"];
    return vatCountries.includes(country) ? amount * 0.2 : 0;
}

function computeCommission(total) {
    const salesName = document.querySelector(`#orderSales option[value='${document.getElementById("orderSales")?.value}']`)?.textContent || "";
    const rate = COMMISSION_RATES[salesName] || 0.05;
    return total * rate;
}

async function loadDashboard() {
    const data = await fetchJSON(`${API_BASE}/dashboard`);
    document.getElementById("kpiOrders").textContent = data.order_count;
    document.getElementById("kpiRevenue").textContent = formatCurrency(data.revenue, "USD");
    document.getElementById("kpiStock").textContent = data.low_stock;
    document.getElementById("kpiPreorders").textContent = data.preorders;
}

async function loadCustomers() {
    state.customers = await fetchJSON(`${API_BASE}/customers`);
    renderTable(document.getElementById("customerTable"), state.customers, [
        { key: "name", label: t("name") },
        { key: "email", label: "Email" },
        { key: "phone", label: t("phone") },
        { key: "address", label: t("address") },
    ]);
    const select = document.getElementById("orderCustomer");
    select.innerHTML = state.customers.map(c => `<option value="${c.id}">${c.name}</option>`).join("");
}

async function loadProducts() {
    state.products = await fetchJSON(`${API_BASE}/products`);
    renderTable(document.getElementById("productTable"), state.products, [
        { key: "name", label: t("name") },
        { key: "sku", label: "SKU" },
        { key: "base_price", label: t("price"), render: p => formatCurrency(p.base_price) },
        { key: "stock", label: t("stock") },
        { key: "safety_stock", label: t("safetyStock") },
        { key: "preorder", label: t("preorder"), render: p => p.preorder ? "✅" : "—" },
    ]);
    const select = document.getElementById("orderProduct");
    select.innerHTML = state.products.map(p => `<option value="${p.id}">${p.name} (${p.sku})</option>`).join("");
    updateStageOptions();
}

async function loadOrders() {
    state.orders = await fetchJSON(`${API_BASE}/orders`);
    const columns = [
        { key: "id", label: "#" },
        { key: "customer", label: t("customer"), render: o => o.customer?.name || "" },
        { key: "status", label: t("status") },
        { key: "total", label: t("total"), render: o => formatCurrency(o.total, o.currency) },
        { key: "vat_amount", label: t("vat"), render: o => formatCurrency(o.vat_amount, o.currency) },
        { key: "shipping_courier", label: t("courier") },
        { key: "tracking_number", label: t("tracking") },
        {
            key: "actions",
            label: "",
            render: o => `
                <button class="secondary" data-action="edit" data-id="${o.id}">${t("edit")}</button>
                <button class="ghost" data-action="fulfill" data-id="${o.id}">${t("fulfill")}</button>
                <button class="ghost" data-action="invoice" data-type="pdf" data-id="${o.id}">PDF</button>
                <button class="ghost" data-action="invoice" data-type="excel" data-id="${o.id}">XLSX</button>
                <button class="ghost" data-action="delete" data-id="${o.id}">${t("delete")}</button>
            `,
        },
    ];
    const table = document.getElementById("orderTable");
    renderTable(table, state.orders, columns);
    table.querySelectorAll("button[data-action]").forEach(btn => {
        const id = btn.dataset.id;
        const action = btn.dataset.action;
        btn.addEventListener("click", () => handleOrderAction(action, id, btn.dataset.type));
    });
}

async function handleOrderAction(action, id, type) {
    if (action === "invoice") {
        const endpoint = type === "excel" ? "excel" : "pdf";
        const res = await fetch(`${API_BASE}/orders/${id}/invoice/${endpoint}`, { headers: { "X-Role": state.currentRole } });
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = endpoint === "excel" ? `order-${id}.xlsx` : `order-${id}.pdf`;
        a.click();
        URL.revokeObjectURL(url);
        return;
    }
    if (action === "fulfill") {
        await fetchJSON(`${API_BASE}/orders/${id}/fulfill`, { method: "POST" });
        await loadOrders();
        await loadDashboard();
        return;
    }
    if (action === "delete") {
        await fetchJSON(`${API_BASE}/orders/${id}`, { method: "DELETE" });
        await loadOrders();
        await loadDashboard();
        return;
    }
    if (action === "edit") {
        const order = state.orders.find(o => o.id === Number(id));
        populateOrderForm(order);
    }
}

function populateOrderForm(order) {
    if (!order) return;
    document.getElementById("editingOrderId").value = order.id;
    document.getElementById("orderCustomer").value = order.customer?.id;
    document.getElementById("orderSales").value = order.sales_person || "";
    document.getElementById("orderCountry").value = order.country;
    document.getElementById("orderCourier").value = order.shipping_courier || "";
    document.getElementById("orderTracking").value = order.tracking_number || "";
    document.getElementById("orderStatus").value = order.status;
    state.orderItems = order.items.map(item => ({
        product_id: item.product.id,
        quantity: item.quantity,
        unit_price: item.unit_price,
    }));
    renderOrderItems();
    updateSummary();
}

function updateStageOptions() {
    const productId = Number(document.getElementById("orderProduct").value);
    const product = state.products.find(p => p.id === productId);
    const select = document.getElementById("priceStage");
    if (!product) {
        select.innerHTML = "";
        select.dataset.prices = JSON.stringify([]);
        return;
    }
    const options = [
        { label: `${t("basePrice")}: ${formatCurrency(product.base_price, product.currency)}`, price: product.base_price },
    ];
    if (product.preorder && product.early_bird_price) {
        options.push({ label: `${t("earlyBirdPrice")}: ${formatCurrency(product.early_bird_price, product.currency)}`, price: product.early_bird_price });
    }
    product.preorder_stages?.forEach(stage => {
        options.push({ label: `${stage.name} (${stage.start_date} - ${stage.end_date}) - ${formatCurrency(stage.price, product.currency)}`, price: stage.price });
    });
    select.innerHTML = options.map((o, idx) => `<option value="${idx}">${o.label}</option>`).join("");
    select.dataset.prices = JSON.stringify(options.map(o => o.price));
    updateUnitPrice();
}

function updateUnitPrice() {
    const select = document.getElementById("priceStage");
    const prices = JSON.parse(select.dataset.prices || "[]");
    const idx = Number(select.value || 0);
    const price = prices[idx] ?? 0;
    document.getElementById("unitPrice").value = price;
}

function renderOrderItems() {
    const tbody = document.querySelector("#orderItemsTable tbody");
    tbody.innerHTML = "";
    state.orderItems.forEach((item, idx) => {
        const product = state.products.find(p => p.id === item.product_id);
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td>${product?.name || ""}</td>
            <td>${item.quantity}</td>
            <td>${formatCurrency(item.unit_price)}</td>
            <td>${formatCurrency(item.unit_price * item.quantity)}</td>
            <td><button class="ghost" data-remove="${idx}">✕</button></td>
        `;
        tbody.appendChild(tr);
    });
    tbody.querySelectorAll("button[data-remove]").forEach(btn => {
        btn.addEventListener("click", () => {
            const idx = Number(btn.dataset.remove);
            state.orderItems.splice(idx, 1);
            renderOrderItems();
            updateSummary();
        });
    });
}

function updateSummary() {
    const subtotal = state.orderItems.reduce((acc, item) => acc + item.unit_price * item.quantity, 0);
    const vat = computeVAT(document.getElementById("orderCountry").value, subtotal);
    const total = subtotal + vat;
    const commission = computeCommission(total);
    document.getElementById("summarySubtotal").textContent = formatCurrency(subtotal);
    document.getElementById("summaryVAT").textContent = formatCurrency(vat);
    document.getElementById("summaryTotal").textContent = formatCurrency(total);
    document.getElementById("summaryCommission").textContent = formatCurrency(commission);
}

function resetOrderForm() {
    document.getElementById("editingOrderId").value = "";
    document.getElementById("orderForm").reset();
    document.getElementById("orderCountry").value = "UK";
    state.orderItems = [];
    renderOrderItems();
    updateSummary();
}

async function bindProductForm() {
    const form = document.getElementById("productForm");
    form.addEventListener("submit", async e => {
        e.preventDefault();
        const data = Object.fromEntries(new FormData(form).entries());
        data.base_price = parseFloat(data.base_price);
        data.stock = parseInt(data.stock);
        data.safety_stock = parseInt(data.safety_stock);
        data.preorder = form.querySelector("input[name='preorder']").checked;
        if (!data.early_bird_price) delete data.early_bird_price;
        data.preorder_stages = state.stageEntries;
        await fetchJSON(`${API_BASE}/products`, { method: "POST", body: data });
        state.stageEntries = [];
        document.getElementById("stageList").innerHTML = "";
        form.reset();
        await loadProducts();
    });

    document.getElementById("addStage").addEventListener("click", () => {
        const name = document.getElementById("stageName").value;
        const price = parseFloat(document.getElementById("stagePrice").value);
        const start_date = document.getElementById("stageStart").value;
        const end_date = document.getElementById("stageEnd").value;
        if (!name || !price || !start_date || !end_date) return;
        state.stageEntries.push({ name, price, start_date, end_date });
        const li = document.createElement("li");
        li.textContent = `${name} • ${formatCurrency(price)} (${start_date} → ${end_date})`;
        const btn = document.createElement("button");
        btn.className = "ghost";
        btn.textContent = "✕";
        btn.addEventListener("click", () => {
            li.remove();
            state.stageEntries = state.stageEntries.filter(s => s.name !== name);
        });
        li.appendChild(btn);
        document.getElementById("stageList").appendChild(li);
        document.getElementById("stageName").value = "";
        document.getElementById("stagePrice").value = "";
        document.getElementById("stageStart").value = "";
        document.getElementById("stageEnd").value = "";
    });

    document.getElementById("exportProducts").addEventListener("click", async () => {
        const res = await fetch(`${API_BASE}/products/export`, { headers: { "X-Role": state.currentRole } });
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = "products.csv";
        a.click();
        URL.revokeObjectURL(url);
    });

    document.getElementById("importProducts").addEventListener("click", () => document.getElementById("importFile").click());
    document.getElementById("importFile").addEventListener("change", async e => {
        const file = e.target.files[0];
        if (!file) return;
        const text = await file.text();
        await fetch(`${API_BASE}/products/import`, { method: "POST", headers: { "Content-Type": "text/csv", "X-Role": state.currentRole }, body: text });
        await loadProducts();
    });
}

async function bindOrderForm() {
    document.getElementById("orderProduct").addEventListener("change", updateStageOptions);
    document.getElementById("priceStage").addEventListener("change", updateUnitPrice);
    document.getElementById("orderCountry").addEventListener("input", updateSummary);

    document.getElementById("addItem").addEventListener("click", () => {
        const productId = Number(document.getElementById("orderProduct").value);
        const qty = parseInt(document.getElementById("orderQty").value || "1");
        const unitPrice = parseFloat(document.getElementById("unitPrice").value || "0");
        if (!productId || qty <= 0) return;
        state.orderItems.push({ product_id: productId, quantity: qty, unit_price: unitPrice });
        renderOrderItems();
        updateSummary();
    });

    document.getElementById("resetOrder").addEventListener("click", resetOrderForm);

    document.getElementById("orderForm").addEventListener("submit", async e => {
        e.preventDefault();
        const formData = new FormData(e.target);
        const payload = Object.fromEntries(formData.entries());
        payload.customer_id = Number(payload.customer_id);
        payload.sales_person_id = Number(payload.sales_person_id || document.getElementById("staffSelector").value);
        payload.items = state.orderItems;
        const isEditing = Boolean(document.getElementById("editingOrderId").value);
        const endpoint = isEditing ? `${API_BASE}/orders/${document.getElementById("editingOrderId").value}` : `${API_BASE}/orders`;
        const method = isEditing ? "PUT" : "POST";
        await fetchJSON(endpoint, { method, body: payload });
        resetOrderForm();
        await loadOrders();
        await loadDashboard();
    });
}

function bindCustomerForm() {
    document.getElementById("customerForm").addEventListener("submit", async e => {
        e.preventDefault();
        const data = Object.fromEntries(new FormData(e.target).entries());
        await fetchJSON(`${API_BASE}/customers`, { method: "POST", body: data });
        e.target.reset();
        await loadCustomers();
    });
}

function bindControls() {
    document.getElementById("languageSelector").addEventListener("change", e => {
        state.currentLang = e.target.value;
        applyTranslations();
        loadDashboard();
        loadCustomers();
        loadProducts();
        loadOrders();
    });
    document.getElementById("roleSelector").addEventListener("change", e => {
        state.currentRole = e.target.value;
        const disabled = state.currentRole !== "admin";
        document.getElementById("importProducts").disabled = disabled;
        document.getElementById("exportProducts").disabled = disabled;
    });
    document.getElementById("staffSelector").addEventListener("change", e => {
        const target = document.getElementById("orderSales");
        if (target) target.value = e.target.value;
        updateSummary();
    });
    document.getElementById("refreshOrders").addEventListener("click", () => {
        loadOrders();
        loadDashboard();
    });
    document.getElementById("refreshCustomers").addEventListener("click", loadCustomers);

    document.getElementById("exportOrdersHtml").addEventListener("click", exportOrdersHTML);
    document.getElementById("exportOrdersCsv").addEventListener("click", exportOrdersCSV);

    document.getElementById("weightInput").addEventListener("input", syncWeight);
    document.getElementById("weightUnit").addEventListener("change", syncWeight);
    document.getElementById("convertWeight").addEventListener("click", syncWeight);
    document.getElementById("kgInput").addEventListener("input", () => syncConverters("kg"));
    document.getElementById("gInput").addEventListener("input", () => syncConverters("g"));

    document.getElementById("exportOrdersPdf").addEventListener("click", () => quickInvoiceDownload("pdf"));
    document.getElementById("exportOrdersExcel").addEventListener("click", () => quickInvoiceDownload("excel"));
}

function syncWeight() {
    const value = parseFloat(document.getElementById("weightInput").value || "0");
    const unit = document.getElementById("weightUnit").value;
    if (unit === "kg") {
        document.getElementById("kgInput").value = value.toFixed(3);
        document.getElementById("gInput").value = (value * 1000).toFixed(0);
    } else {
        document.getElementById("gInput").value = value.toFixed(0);
        document.getElementById("kgInput").value = (value / 1000).toFixed(3);
    }
}

function syncConverters(source) {
    if (source === "kg") {
        const kg = parseFloat(document.getElementById("kgInput").value || "0");
        document.getElementById("gInput").value = (kg * 1000).toFixed(0);
        document.getElementById("weightInput").value = kg;
        document.getElementById("weightUnit").value = "kg";
    } else {
        const g = parseFloat(document.getElementById("gInput").value || "0");
        document.getElementById("kgInput").value = (g / 1000).toFixed(3);
        document.getElementById("weightInput").value = g;
        document.getElementById("weightUnit").value = "g";
    }
}

function exportOrdersHTML() {
    const rows = state.orders.map(o => `<tr><td>${o.id}</td><td>${o.customer?.name || ""}</td><td>${o.status}</td><td>${formatCurrency(o.total)}</td><td>${o.shipping_courier || ""}</td><td>${o.tracking_number || ""}</td></tr>`).join("");
    const html = `<table><thead><tr><th>#</th><th>${t("customer")}</th><th>${t("status")}</th><th>${t("total")}</th><th>${t("courier")}</th><th>${t("tracking")}</th></tr></thead><tbody>${rows}</tbody></table>`;
    const blob = new Blob([`<html><body>${html}</body></html>`], { type: "text/html" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "orders.html";
    a.click();
    URL.revokeObjectURL(url);
}

function exportOrdersCSV() {
    if (!state.orders.length) return;
    const headers = ["id", "customer", "status", "total", "courier", "tracking"];
    const rows = state.orders.map(o => [o.id, o.customer?.name || "", o.status, o.total, o.shipping_courier || "", o.tracking_number || ""].join(","));
    const csv = [headers.join(","), ...rows].join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "orders.csv";
    a.click();
    URL.revokeObjectURL(url);
}

async function quickInvoiceDownload(type) {
    if (!state.orders.length) return;
    const latest = state.orders[0];
    await handleOrderAction("invoice", latest.id, type);
}

async function init() {
    await loadTranslations();
    applyTranslations();
    bindControls();
    bindCustomerForm();
    await bindProductForm();
    await bindOrderForm();
    await Promise.all([loadDashboard(), loadCustomers(), loadProducts(), loadOrders()]);
    document.getElementById("orderSales").innerHTML = Array.from(document.getElementById("staffSelector").options).map(o => `<option value="${o.value}">${o.textContent}</option>`).join("");
    document.getElementById("orderSales").value = document.getElementById("staffSelector").value;
    updateStageOptions();
    updateSummary();
}

init().catch(err => console.error(err));
