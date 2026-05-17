"""
app.py — Flask web server for the Pantry Display.

Run locally on the Raspberry Pi with:
    python app.py

Then open http://<pi-hostname>.local:5000 on your phone.

Routes
------
GET  /                    Mobile web UI
GET  /api/items           Return all items as JSON
POST /api/items           Add a new item
PATCH /api/items/<id>     Update use_by_date and/or expiry_date
DELETE /api/items/<id>    Delete an item by id
POST /api/refresh-display Manually trigger an e-paper refresh
GET  /preview.png         Serve the latest rendered preview image (dev mode)
"""

import os
import re
import threading

from flask import Flask, jsonify, request, send_from_directory, render_template

import db
import display as disp
from defaults import PRODUCE_DEFAULTS, USE_BY_OFFSET_DAYS

app = Flask(__name__)

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Lock so simultaneous requests don't both try to write to the e-paper at once
_display_lock = threading.Lock()


def _trigger_display_refresh():
    """Fetch current items and refresh the display in a background thread."""
    def _run():
        with _display_lock:
            items = db.get_all_items()
            disp.refresh_display(items)

    threading.Thread(target=_run, daemon=True).start()


def _valid_date(value: str, field: str) -> str | None:
    """Return an error message if value is not YYYY-MM-DD, else None."""
    if not _DATE_RE.match(value):
        return f"{field} must be YYYY-MM-DD"
    return None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    """Serve the mobile web UI."""
    return render_template(
        "index.html",
        produce_defaults=PRODUCE_DEFAULTS,
        use_by_offset_days=USE_BY_OFFSET_DAYS,
    )


@app.route("/api/items", methods=["GET"])
def get_items():
    """Return all items sorted by expiry date."""
    items = db.get_all_items()
    return jsonify(items)


@app.route("/api/items", methods=["POST"])
def add_item():
    """Add a new item. Expects JSON: { name, expiry_date, use_by_date? }."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400

    name = (data.get("name") or "").strip()
    expiry_date = (data.get("expiry_date") or "").strip()
    use_by_date = (data.get("use_by_date") or "").strip() or None

    if not name:
        return jsonify({"error": "name is required"}), 400
    if not expiry_date:
        return jsonify({"error": "expiry_date is required"}), 400

    if err := _valid_date(expiry_date, "expiry_date"):
        return jsonify({"error": err}), 400
    if use_by_date and (err := _valid_date(use_by_date, "use_by_date")):
        return jsonify({"error": err}), 400

    new_id = db.add_item(name, expiry_date, use_by_date)
    row = db.get_all_items()
    created = next((i for i in row if i["id"] == new_id), None)
    _trigger_display_refresh()

    return jsonify(created or {"id": new_id, "name": name, "expiry_date": expiry_date}), 201


@app.route("/api/items/<int:item_id>", methods=["PATCH"])
def patch_item(item_id: int):
    """Update use_by_date and/or expiry_date on an existing item."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400

    expiry_date = (data.get("expiry_date") or "").strip() or None
    use_by_date = (data.get("use_by_date") or "").strip() or None

    if expiry_date is None and use_by_date is None:
        return jsonify({"error": "Provide expiry_date and/or use_by_date"}), 400

    if expiry_date and (err := _valid_date(expiry_date, "expiry_date")):
        return jsonify({"error": err}), 400
    if use_by_date and (err := _valid_date(use_by_date, "use_by_date")):
        return jsonify({"error": err}), 400

    if not db.update_item(item_id, expiry_date=expiry_date, use_by_date=use_by_date):
        return jsonify({"error": "Item not found"}), 404

    _trigger_display_refresh()
    updated = next((i for i in db.get_all_items() if i["id"] == item_id), None)
    return jsonify(updated)


@app.route("/api/items/<int:item_id>", methods=["DELETE"])
def delete_item(item_id: int):
    """Delete an item by id."""
    deleted = db.delete_item(item_id)
    if not deleted:
        return jsonify({"error": "Item not found"}), 404

    _trigger_display_refresh()
    return jsonify({"deleted": item_id})


@app.route("/api/refresh-display", methods=["POST"])
def refresh_display():
    """Manually trigger an e-paper display refresh."""
    _trigger_display_refresh()
    return jsonify({"status": "refresh triggered"})


@app.route("/preview.png")
def preview_image():
    """Serve the latest rendered preview image (updated on every display refresh)."""
    preview_path = disp.PREVIEW_PATH
    if not os.path.exists(preview_path):
        items = db.get_all_items()
        disp.refresh_display(items)

    directory = os.path.dirname(preview_path)
    filename = os.path.basename(preview_path)
    response = send_from_directory(directory, filename, mimetype="image/png")
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    return response


@app.route("/api/defaults", methods=["GET"])
def get_defaults():
    """Return the produce defaults dict as JSON (used by the frontend)."""
    return jsonify(PRODUCE_DEFAULTS)


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    db.init_db()

    items = db.get_all_items()
    disp.refresh_display(items)

    app.run(host="0.0.0.0", port=5000, debug=False)
