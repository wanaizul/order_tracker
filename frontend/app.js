const API = "/api";

// ---------------------------------------------------------------- tabs ----
document.querySelectorAll(".tab-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById("tab-" + btn.dataset.tab).classList.add("active");
  });
});

async function api(path, opts = {}) {
  const res = await fetch(API + path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!res.ok) {
    const body = await res.text();
    alert("Error: " + body);
    throw new Error(body);
  }
  if (res.status === 204) return null;
  return res.json();
}

function money(n) {
  return "$" + Number(n || 0).toFixed(2);
}

// ------------------------------------------------------------- state ------
let itemsCache = [];
let categoriesCache = [];
let locationsCache = [];
let ordersCache = [];
let selectedOrderId = null;

// ------------------------------------------------------------- items ------
async function loadItems() {
  itemsCache = await api("/items");
  const tbody = document.querySelector("#items-table tbody");
  tbody.innerHTML = "";
  itemsCache.forEach((item) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><input value="${item.name}" data-field="name" /></td>
      <td><input value="${item.category || ""}" data-field="category" /></td>
      <td><button class="danger" data-action="delete">Delete</button></td>
    `;
    tr.querySelectorAll("input").forEach((inp) => {
      inp.addEventListener("change", async () => {
        const name = tr.querySelector('[data-field="name"]').value;
        const category = tr.querySelector('[data-field="category"]').value;
        await api(`/items/${item.id}`, { method: "PUT", body: JSON.stringify({ name, category }) });
        await refreshAll();
      });
    });
    tr.querySelector('[data-action="delete"]').addEventListener("click", async () => {
      if (!confirm(`Delete item "${item.name}"?`)) return;
      await api(`/items/${item.id}`, { method: "DELETE" });
      await refreshAll();
    });
    tbody.appendChild(tr);
  });

  // item dropdown on the "add line" form
  const itemSelect = document.querySelector('#form-add-line select[name="item_name"]');
  itemSelect.innerHTML = itemsCache.map((i) => `<option value="${i.name}">${i.name}</option>`).join("");
}

document.getElementById("form-add-item").addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  await api("/items", { method: "POST", body: JSON.stringify({ name: fd.get("name"), category: fd.get("category") }) });
  e.target.reset();
  await refreshAll();
});

// -------------------------------------------------------- categories ------
async function loadCategories() {
  categoriesCache = await api("/categories");
  const tbody = document.querySelector("#categories-table tbody");
  tbody.innerHTML = "";
  categoriesCache.forEach((cat) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><input value="${cat.name}" data-field="name" /></td>
      <td>
        <select data-field="status">
          <option ${cat.status === "Limited" ? "selected" : ""}>Limited</option>
          <option ${cat.status === "Always Active" ? "selected" : ""}>Always Active</option>
        </select>
      </td>
      <td><button class="danger" data-action="delete">Delete</button></td>
    `;
    tr.querySelectorAll("input,select").forEach((inp) => {
      inp.addEventListener("change", async () => {
        const name = tr.querySelector('[data-field="name"]').value;
        const status = tr.querySelector('[data-field="status"]').value;
        await api(`/categories/${cat.id}`, { method: "PUT", body: JSON.stringify({ name, status }) });
        await refreshAll();
      });
    });
    tr.querySelector('[data-action="delete"]').addEventListener("click", async () => {
      if (!confirm(`Delete category "${cat.name}"?`)) return;
      await api(`/categories/${cat.id}`, { method: "DELETE" });
      await refreshAll();
    });
    tbody.appendChild(tr);
  });

  const opts = categoriesCache.map((c) => `<option value="${c.name}">${c.name}</option>`).join("");
  document.querySelector('#form-add-order select[name="category"]').innerHTML = opts;
  document.getElementById("filter-category").innerHTML =
    `<option value="">All</option>` + opts;
}

document.getElementById("form-add-category").addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  await api("/categories", { method: "POST", body: JSON.stringify({ name: fd.get("name"), status: fd.get("status") }) });
  e.target.reset();
  await refreshAll();
});

// --------------------------------------------------------- locations ------
async function loadLocations() {
  locationsCache = await api("/locations");
  const tbody = document.querySelector("#locations-table tbody");
  tbody.innerHTML = "";
  locationsCache.forEach((loc) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${loc.name}</td><td><button class="danger" data-action="delete">Delete</button></td>`;
    tr.querySelector('[data-action="delete"]').addEventListener("click", async () => {
      if (!confirm(`Delete location "${loc.name}"?`)) return;
      await api(`/locations/${loc.id}`, { method: "DELETE" });
      await refreshAll();
    });
    tbody.appendChild(tr);
  });

  const opts = locationsCache.map((l) => `<option value="${l.name}">${l.name}</option>`).join("");
  document.querySelector('#form-add-order select[name="location"]').innerHTML = opts;
  document.getElementById("filter-location").innerHTML =
    `<option value="">All</option>` + opts;
}

document.getElementById("form-add-location").addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  await api("/locations", { method: "POST", body: JSON.stringify({ name: fd.get("name") }) });
  e.target.reset();
  await refreshAll();
});

// ------------------------------------------------------------- orders -----
function currentFilters() {
  const params = new URLSearchParams();
  const category = document.getElementById("filter-category").value;
  const location = document.getElementById("filter-location").value;
  const dateFrom = document.getElementById("filter-date-from").value;
  const dateTo = document.getElementById("filter-date-to").value;
  if (category) params.set("category", category);
  if (location) params.set("location", location);
  if (dateFrom) params.set("date_from", dateFrom);
  if (dateTo) params.set("date_to", dateTo);
  return params.toString();
}

async function loadOrders() {
  const qs = currentFilters();
  ordersCache = await api("/orders" + (qs ? `?${qs}` : ""));
  const tbody = document.querySelector("#orders-table tbody");
  tbody.innerHTML = "";
  let grandTotal = 0;
  ordersCache.forEach((o) => {
    grandTotal += Number(o.total_price || 0);
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><input value="${o.order_code}" data-field="order_code" /></td>
      <td><select data-field="category">${categoriesCache
        .map((c) => `<option value="${c.name}" ${c.name === o.category ? "selected" : ""}>${c.name}</option>`)
        .join("")}</select></td>
      <td><select data-field="location">${locationsCache
        .map((l) => `<option value="${l.name}" ${l.name === o.location ? "selected" : ""}>${l.name}</option>`)
        .join("")}</select></td>
      <td>${o.order_date || ""}</td>
      <td>${o.line_count}</td>
      <td>${money(o.total_price)}</td>
      <td><button class="danger" data-action="delete">Delete</button></td>
    `;
    tr.querySelectorAll("input,select").forEach((inp) => {
      inp.addEventListener("change", async () => {
        const order_code = tr.querySelector('[data-field="order_code"]').value;
        const category = tr.querySelector('[data-field="category"]').value;
        const location = tr.querySelector('[data-field="location"]').value;
        await api(`/orders/${o.id}`, { method: "PUT", body: JSON.stringify({ order_code, category, location }) });
        await refreshOrdersAndLines();
      });
    });
    tr.querySelector('[data-action="delete"]').addEventListener("click", async () => {
      if (!confirm(`Delete order "${o.order_code}" and all its lines?`)) return;
      await api(`/orders/${o.id}`, { method: "DELETE" });
      await refreshOrdersAndLines();
    });
    tbody.appendChild(tr);
  });
  document.getElementById("grand-total").textContent = money(grandTotal);

  // order dropdown for the line-items section
  const sel = document.getElementById("line-order-select");
  const prev = selectedOrderId;
  sel.innerHTML = ordersCache.map((o) => `<option value="${o.id}">${o.order_code}</option>`).join("");
  if (ordersCache.some((o) => o.id === prev)) {
    sel.value = prev;
    selectedOrderId = prev;
  } else {
    selectedOrderId = ordersCache.length ? ordersCache[0].id : null;
    if (selectedOrderId) sel.value = selectedOrderId;
  }
}

document.getElementById("form-add-order").addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  await api("/orders", {
    method: "POST",
    body: JSON.stringify({ order_code: fd.get("order_code"), category: fd.get("category"), location: fd.get("location") }),
  });
  e.target.reset();
  await refreshOrdersAndLines();
});

["filter-category", "filter-location", "filter-date-from", "filter-date-to"].forEach((id) => {
  document.getElementById(id).addEventListener("change", loadOrders);
});
document.getElementById("btn-clear-filters").addEventListener("click", () => {
  document.getElementById("filter-category").value = "";
  document.getElementById("filter-location").value = "";
  document.getElementById("filter-date-from").value = "";
  document.getElementById("filter-date-to").value = "";
  loadOrders();
});

document.getElementById("line-order-select").addEventListener("change", (e) => {
  selectedOrderId = Number(e.target.value);
  loadOrderLines();
});

// -------------------------------------------------------- order lines -----
async function loadOrderLines() {
  const tbody = document.querySelector("#lines-table tbody");
  tbody.innerHTML = "";
  if (!selectedOrderId) return;
  const lines = await api(`/order_lines?order_id=${selectedOrderId}`);
  lines.forEach((line) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><input type="date" value="${line.order_date || ""}" data-field="order_date" /></td>
      <td><select data-field="item_name">${itemsCache
        .map((i) => `<option value="${i.name}" ${i.name === line.item_name ? "selected" : ""}>${i.name}</option>`)
        .join("")}</select></td>
      <td>${line.item_type || ""}</td>
      <td><input type="number" step="0.01" value="${line.unit_price}" data-field="unit_price" /></td>
      <td><input type="number" step="1" value="${line.quantity}" data-field="quantity" /></td>
      <td>${money(line.line_total)}</td>
      <td><button class="danger" data-action="delete">Delete</button></td>
    `;
    tr.querySelectorAll("input,select").forEach((inp) => {
      inp.addEventListener("change", async () => {
        const order_date = tr.querySelector('[data-field="order_date"]').value || null;
        const item_name = tr.querySelector('[data-field="item_name"]').value;
        const unit_price = parseFloat(tr.querySelector('[data-field="unit_price"]').value || 0);
        const quantity = parseInt(tr.querySelector('[data-field="quantity"]').value || 0, 10);
        await api(`/order_lines/${line.id}`, {
          method: "PUT",
          body: JSON.stringify({ order_id: selectedOrderId, item_name, order_date, unit_price, quantity }),
        });
        await refreshOrdersAndLines();
      });
    });
    tr.querySelector('[data-action="delete"]').addEventListener("click", async () => {
      await api(`/order_lines/${line.id}`, { method: "DELETE" });
      await refreshOrdersAndLines();
    });
    tbody.appendChild(tr);
  });
}

document.getElementById("form-add-line").addEventListener("submit", async (e) => {
  e.preventDefault();
  if (!selectedOrderId) {
    alert("Add an order first.");
    return;
  }
  const fd = new FormData(e.target);
  await api("/order_lines", {
    method: "POST",
    body: JSON.stringify({
      order_id: selectedOrderId,
      item_name: fd.get("item_name"),
      order_date: fd.get("order_date") || null,
      unit_price: parseFloat(fd.get("unit_price")),
      quantity: parseInt(fd.get("quantity"), 10),
    }),
  });
  e.target.reset();
  await refreshOrdersAndLines();
});

// --------------------------------------------------------------- glue -----
async function refreshOrdersAndLines() {
  await loadOrders();
  await loadOrderLines();
}

async function refreshAll() {
  await loadItems();
  await loadCategories();
  await loadLocations();
  await refreshOrdersAndLines();
}

refreshAll();
