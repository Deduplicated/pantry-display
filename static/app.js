/* app.js — Pantry Display frontend logic */

"use strict";

// ---------------------------------------------------------------------------
// Utility helpers
// ---------------------------------------------------------------------------

function isoToday() {
  return new Date().toISOString().slice(0, 10);
}

function addDaysToToday(days) {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
}

function subtractDaysFromIso(isoDate, days) {
  const d = new Date(isoDate + "T12:00:00");
  d.setDate(d.getDate() - days);
  return d.toISOString().slice(0, 10);
}

function daysUntil(isoDate) {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const target = new Date(isoDate + "T12:00:00");
  target.setHours(0, 0, 0, 0);
  return Math.round((target - today) / 86400000);
}

function formatDisplayDate(isoDate) {
  if (!isoDate) return "—";
  const d = new Date(isoDate + "T12:00:00");
  return d.toLocaleDateString("en-GB", { day: "numeric", month: "short" });
}

function resolveUseBy(item) {
  if (item.use_by_date) return item.use_by_date;
  const offset = window.USE_BY_OFFSET_DAYS ?? 2;
  return subtractDaysFromIso(item.expiry_date, offset);
}

function showToast(msg, isError = false) {
  const toast = document.getElementById("toast");
  toast.textContent = msg;
  toast.className = "toast" + (isError ? " error" : "");
  clearTimeout(toast._timer);
  toast._timer = setTimeout(() => toast.classList.add("hidden"), 3000);
}

// ---------------------------------------------------------------------------
// Rendering helpers
// ---------------------------------------------------------------------------

const GROUP_ORDER = ["EXPIRED", "USE FIRST", "THIS WEEK", "FRESH"];
const GROUP_SLUG = {
  EXPIRED: "expired",
  "USE FIRST": "use-first",
  "THIS WEEK": "this-week",
  FRESH: "fresh",
};

function groupItems(items) {
  const groups = { EXPIRED: [], "USE FIRST": [], "THIS WEEK": [], FRESH: [] };
  for (const item of items) {
    const days = daysUntil(item.expiry_date);
    const enriched = { ...item, days, use_by: resolveUseBy(item) };
    if (days < 0) groups.EXPIRED.push(enriched);
    else if (days <= 2) groups["USE FIRST"].push(enriched);
    else if (days <= 7) groups["THIS WEEK"].push(enriched);
    else groups.FRESH.push(enriched);
  }
  return groups;
}

function renderItems(items) {
  const container = document.getElementById("items-list");
  const countBadge = document.getElementById("item-count");
  const header = document.querySelector(".items-columns-header");

  countBadge.textContent = items.length;
  if (header) header.style.display = items.length ? "" : "none";

  if (items.length === 0) {
    container.innerHTML =
      '<p class="placeholder">No items yet — add something above.</p>';
    return;
  }

  const groups = groupItems(items);
  const frag = document.createDocumentFragment();

  for (const groupName of GROUP_ORDER) {
    const entries = groups[groupName];
    if (entries.length === 0) continue;

    const headerEl = document.createElement("div");
    headerEl.className = `group-header group--${GROUP_SLUG[groupName]}`;
    headerEl.innerHTML = `<span class="group-dot"></span>${groupName}`;
    frag.appendChild(headerEl);

    for (const item of entries) {
      const row = document.createElement("div");
      row.className = "item-row";
      row.dataset.id = item.id;

      const name = document.createElement("span");
      name.className = "item-name";
      name.textContent = item.name;

      const useBy = document.createElement("span");
      useBy.className = "item-date col-use-by";
      useBy.textContent = formatDisplayDate(item.use_by);

      const expiry = document.createElement("span");
      expiry.className = "item-date col-expiry";
      expiry.textContent = formatDisplayDate(item.expiry_date);

      const actions = document.createElement("div");
      actions.className = "item-actions";

      const editBtn = document.createElement("button");
      editBtn.type = "button";
      editBtn.className = "btn btn-edit";
      editBtn.textContent = "Edit";
      editBtn.setAttribute("aria-label", `Edit dates for ${item.name}`);
      editBtn.addEventListener("click", () => openEditDates(item));

      const delBtn = document.createElement("button");
      delBtn.type = "button";
      delBtn.className = "btn btn-delete";
      delBtn.textContent = "Delete";
      delBtn.setAttribute("aria-label", `Delete ${item.name}`);
      delBtn.addEventListener("click", () => deleteItem(item.id, item.name));

      actions.appendChild(editBtn);
      actions.appendChild(delBtn);

      row.appendChild(name);
      row.appendChild(useBy);
      row.appendChild(expiry);
      row.appendChild(actions);
      frag.appendChild(row);
    }
  }

  container.innerHTML = "";
  container.appendChild(frag);
}

// ---------------------------------------------------------------------------
// API calls
// ---------------------------------------------------------------------------

async function loadItems() {
  try {
    const res = await fetch("/api/items");
    if (!res.ok) throw new Error("Failed to load items");
    const items = await res.json();
    renderItems(items);
  } catch (err) {
    console.error(err);
    document.getElementById("items-list").innerHTML =
      '<p class="placeholder">Could not load items.</p>';
  }
}

async function addItem(name, expiryDate, useByDate) {
  const res = await fetch("/api/items", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      name,
      expiry_date: expiryDate,
      use_by_date: useByDate,
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || "Failed to add item");
  }
  return res.json();
}

async function patchItem(id, payload) {
  const res = await fetch(`/api/items/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || "Update failed");
  }
  return res.json();
}

async function deleteItem(id, name) {
  if (!confirm(`Remove "${name}" from the pantry?`)) return;
  try {
    const res = await fetch(`/api/items/${id}`, { method: "DELETE" });
    if (!res.ok) throw new Error("Delete failed");
    showToast(`"${name}" removed`);
    loadItems();
    schedulePreviewRefresh();
  } catch (err) {
    showToast(err.message, true);
  }
}

function openEditDates(item) {
  const useByDefault = resolveUseBy(item);
  const useByInput = prompt(
    "Use by date (YYYY-MM-DD):",
    item.use_by_date || useByDefault
  );
  if (useByInput === null) return;

  const expiryInput = prompt(
    "Expiry date (YYYY-MM-DD):",
    item.expiry_date
  );
  if (expiryInput === null) return;

  patchItem(item.id, {
    use_by_date: useByInput.trim(),
    expiry_date: expiryInput.trim(),
  })
    .then(() => {
      showToast(`"${item.name}" updated`);
      loadItems();
      schedulePreviewRefresh();
    })
    .catch((err) => showToast(err.message, true));
}

async function triggerDisplayRefresh() {
  const btn = document.getElementById("btn-refresh");
  btn.disabled = true;
  btn.textContent = "Refreshing…";
  try {
    await fetch("/api/refresh-display", { method: "POST" });
    showToast("Display refresh triggered");
    schedulePreviewRefresh();
  } catch {
    showToast("Refresh failed", true);
  } finally {
    btn.disabled = false;
    btn.innerHTML = "&#8635; Refresh display";
  }
}

function refreshPreview() {
  const img = document.getElementById("preview-img");
  if (!img) return;
  img.src = `/preview.png?t=${Date.now()}`;
}

/** Re-fetch preview after background e-paper refresh (render saves PNG first). */
function schedulePreviewRefresh() {
  refreshPreview();
  setTimeout(refreshPreview, 800);
  setTimeout(refreshPreview, 2500);
}

function initPreview() {
  const section = document.getElementById("preview-section");
  if (section) section.style.display = "";
}

// ---------------------------------------------------------------------------
// Form logic
// ---------------------------------------------------------------------------

function initForm() {
  const selectEl = document.getElementById("select-produce");
  const customRow = document.getElementById("custom-name-row");
  const customNameEl = document.getElementById("input-custom-name");
  const useByEl = document.getElementById("input-use-by");
  const expiryEl = document.getElementById("input-expiry");
  const hintEl = document.getElementById("expiry-hint");
  const form = document.getElementById("add-form");

  let useByManual = false;
  const offset = () => window.USE_BY_OFFSET_DAYS ?? 2;

  function syncUseByFromExpiry() {
    if (useByManual || !expiryEl.value) return;
    useByEl.value = subtractDaysFromIso(expiryEl.value, offset());
  }

  expiryEl.min = isoToday();

  useByEl.addEventListener("input", () => {
    useByManual = true;
  });

  expiryEl.addEventListener("change", syncUseByFromExpiry);
  expiryEl.addEventListener("input", syncUseByFromExpiry);

  selectEl.addEventListener("change", () => {
    const val = selectEl.value;
    useByManual = false;

    if (val === "__custom__") {
      customRow.classList.remove("hidden");
      customNameEl.required = true;
      expiryEl.value = "";
      useByEl.value = "";
      hintEl.textContent = "";
      return;
    }

    customRow.classList.add("hidden");
    customNameEl.required = false;
    customNameEl.value = "";

    if (val && window.PRODUCE_DEFAULTS[val] !== undefined) {
      const days = window.PRODUCE_DEFAULTS[val];
      expiryEl.value = addDaysToToday(days);
      syncUseByFromExpiry();
      hintEl.textContent = `Default shelf life: ${days} day${days !== 1 ? "s" : ""}`;
    } else {
      expiryEl.value = "";
      useByEl.value = "";
      hintEl.textContent = "";
    }
  });

  form.addEventListener("submit", async (e) => {
    e.preventDefault();

    let name;
    if (selectEl.value === "__custom__") {
      name = customNameEl.value.trim();
      if (!name) {
        customNameEl.focus();
        showToast("Please enter a custom name", true);
        return;
      }
    } else if (selectEl.value) {
      name = selectEl.value;
    } else {
      selectEl.focus();
      showToast("Please choose a produce item", true);
      return;
    }

    const expiryDate = expiryEl.value;
    const useByDate = useByEl.value;
    if (!expiryDate) {
      expiryEl.focus();
      showToast("Please set an expiry date", true);
      return;
    }
    if (!useByDate) {
      useByEl.focus();
      showToast("Please set a use by date", true);
      return;
    }

    const submitBtn = form.querySelector('[type="submit"]');
    submitBtn.disabled = true;
    submitBtn.textContent = "Adding…";

    try {
      await addItem(name, expiryDate, useByDate);
      showToast(`"${name}" added`);
      form.reset();
      customRow.classList.add("hidden");
      useByManual = false;
      hintEl.textContent = "";
      loadItems();
      schedulePreviewRefresh();
    } catch (err) {
      showToast(err.message, true);
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = "Add to pantry";
    }
  });
}

document.addEventListener("DOMContentLoaded", () => {
  initForm();
  initPreview();
  loadItems();
  document
    .getElementById("btn-refresh")
    .addEventListener("click", triggerDisplayRefresh);
});
