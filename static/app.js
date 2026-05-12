/* app.js — Pantry Display frontend logic
 *
 * Responsibilities:
 *  - Load and render the items list from /api/items
 *  - Auto-fill expiry date when a produce item is selected
 *  - Handle the Add form submission (POST /api/items)
 *  - Handle Delete buttons (DELETE /api/items/<id>)
 *  - Handle the manual Refresh Display button (POST /api/refresh-display)
 *  - Show a dev-mode display preview if running without hardware
 */

"use strict";

// PRODUCE_DEFAULTS is injected by Flask via index.html as window.PRODUCE_DEFAULTS

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

function daysUntil(isoDate) {
  const today = new Date(); today.setHours(0, 0, 0, 0);
  const expiry = new Date(isoDate); expiry.setHours(0, 0, 0, 0);
  return Math.round((expiry - today) / 86400000);
}

function daysLabel(days) {
  if (days < 0) {
    const n = Math.abs(days);
    return `expired ${n} day${n !== 1 ? "s" : ""} ago`;
  }
  if (days === 0) return "expires today";
  return `${days} day${days !== 1 ? "s" : ""}`;
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
const GROUP_SLUG  = { "EXPIRED": "expired", "USE FIRST": "use-first", "THIS WEEK": "this-week", "FRESH": "fresh" };

function groupItems(items) {
  const groups = { "EXPIRED": [], "USE FIRST": [], "THIS WEEK": [], "FRESH": [] };
  for (const item of items) {
    const days = daysUntil(item.expiry_date);
    if (days < 0)      groups["EXPIRED"].push({ ...item, days });
    else if (days <= 2) groups["USE FIRST"].push({ ...item, days });
    else if (days <= 7) groups["THIS WEEK"].push({ ...item, days });
    else               groups["FRESH"].push({ ...item, days });
  }
  return groups;
}

function renderItems(items) {
  const container = document.getElementById("items-list");
  const countBadge = document.getElementById("item-count");

  countBadge.textContent = items.length;

  if (items.length === 0) {
    container.innerHTML = '<p class="placeholder">No items yet — add something above.</p>';
    return;
  }

  const groups = groupItems(items);
  const frag   = document.createDocumentFragment();

  for (const groupName of GROUP_ORDER) {
    const entries = groups[groupName];
    if (entries.length === 0) continue;

    // Group header
    const header = document.createElement("div");
    header.className = `group-header group--${GROUP_SLUG[groupName]}`;
    header.innerHTML = `<span class="group-dot"></span>${groupName}`;
    frag.appendChild(header);

    // Item rows
    for (const item of entries) {
      const row = document.createElement("div");
      row.className = "item-row";
      row.dataset.id = item.id;

      const name = document.createElement("span");
      name.className = "item-name";
      name.textContent = item.name;

      const label = document.createElement("span");
      label.className = "item-days";
      label.textContent = daysLabel(item.days);

      const delBtn = document.createElement("button");
      delBtn.className = "btn btn-delete";
      delBtn.textContent = "Delete";
      delBtn.setAttribute("aria-label", `Delete ${item.name}`);
      delBtn.addEventListener("click", () => deleteItem(item.id, item.name));

      row.appendChild(name);
      row.appendChild(label);
      row.appendChild(delBtn);
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

async function addItem(name, expiryDate) {
  const res = await fetch("/api/items", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, expiry_date: expiryDate }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || "Failed to add item");
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
    refreshPreview();
  } catch (err) {
    showToast(err.message, true);
  }
}

async function triggerDisplayRefresh() {
  const btn = document.getElementById("btn-refresh");
  btn.disabled = true;
  btn.textContent = "Refreshing…";
  try {
    await fetch("/api/refresh-display", { method: "POST" });
    showToast("Display refresh triggered");
    setTimeout(refreshPreview, 1500); // give the render a moment
  } catch {
    showToast("Refresh failed", true);
  } finally {
    btn.disabled = false;
    btn.innerHTML = "&#8635; Refresh display";
  }
}

// ---------------------------------------------------------------------------
// Dev-mode preview
// ---------------------------------------------------------------------------

function refreshPreview() {
  const img = document.getElementById("preview-img");
  if (!img) return;
  // Cache-bust so the browser always fetches the latest PNG
  img.src = `/preview.png?t=${Date.now()}`;
}

// Show the preview section — we always show it so users can see the layout
// even when real hardware is attached (useful for verifying render output).
function initPreview() {
  const section = document.getElementById("preview-section");
  if (section) section.style.display = "";
}

// ---------------------------------------------------------------------------
// Form logic
// ---------------------------------------------------------------------------

function initForm() {
  const selectEl      = document.getElementById("select-produce");
  const customRow     = document.getElementById("custom-name-row");
  const customNameEl  = document.getElementById("input-custom-name");
  const expiryEl      = document.getElementById("input-expiry");
  const hintEl        = document.getElementById("expiry-hint");
  const form          = document.getElementById("add-form");

  // Set min date to today so past dates are blocked
  expiryEl.min = isoToday();

  selectEl.addEventListener("change", () => {
    const val = selectEl.value;

    if (val === "__custom__") {
      customRow.classList.remove("hidden");
      customNameEl.required = true;
      expiryEl.value = "";
      hintEl.textContent = "";
      return;
    }

    customRow.classList.add("hidden");
    customNameEl.required = false;
    customNameEl.value    = "";

    if (val && window.PRODUCE_DEFAULTS[val] !== undefined) {
      const days     = window.PRODUCE_DEFAULTS[val];
      const date     = addDaysToToday(days);
      expiryEl.value = date;
      hintEl.textContent = `Default shelf life: ${days} day${days !== 1 ? "s" : ""}`;
    } else {
      expiryEl.value    = "";
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
    if (!expiryDate) {
      expiryEl.focus();
      showToast("Please set an expiry date", true);
      return;
    }

    const submitBtn = form.querySelector('[type="submit"]');
    submitBtn.disabled = true;
    submitBtn.textContent = "Adding…";

    try {
      await addItem(name, expiryDate);
      showToast(`"${name}" added`);

      // Reset form
      form.reset();
      customRow.classList.add("hidden");
      hintEl.textContent = "";

      loadItems();
      refreshPreview();
    } catch (err) {
      showToast(err.message, true);
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = "Add to pantry";
    }
  });
}

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------

document.addEventListener("DOMContentLoaded", () => {
  initForm();
  initPreview();
  loadItems();

  document.getElementById("btn-refresh").addEventListener("click", triggerDisplayRefresh);
});
