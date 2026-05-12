"""
app.py — Flask web server for the Pantry Display.

Run locally on the Raspberry Pi with:
    python app.py

Then open http://<pi-hostname>.local:5000 on your phone.

Routes
------
GET  /                    Mobile web UI
GET  /api/items           Return all items as JSON
POST /api/items           Add a new item  { "name": "...", "expiry_date": "YYYY-MM-DD" }
DELETE /api/items/<id>    Delete an item by id
POST /api/refresh-display Manually trigger an e-paper refresh
GET  /preview.png         Serve the latest rendered preview image (dev mode)
"""

import os
import threading

from flask import Flask, jsonify, request, send_from_directory, render_template

import db
import display as disp
from defaults import PRODUCE_DEFAULTS

app = Flask(__name__)

# Lock so simultaneous requests don't both try to write to the e-paper at once
_display_lock = threading.Lock()


def _trigger_display_refresh():
    """Fetch current items and refresh the display in a background thread."""
    def _run():
        with _display_lock:
            items = db.get_all_items()
            disp.refresh_display(items)

    threading.Thread(target=_run, daemon=True).start()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    """Serve the mobile web UI."""
    return render_template("index.html", produce_defaults=PRODUCE_DEFAULTS)


@app.route("/api/items", methods=["GET"])
def get_items():
    """Return all items sorted by expiry date."""
    items = db.get_all_items()
    return jsonify(items)


@app.route("/api/items", methods=["POST"])
def add_item():
    """Add a new item. Expects JSON body: { name, expiry_date }."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400

    name = (data.get("name") or "").strip()
    expiry_date = (data.get("expiry_date") or "").strip()

    if not name:
        return jsonify({"error": "name is required"}), 400
    if not expiry_date:
        return jsonify({"error": "expiry_date is required"}), 400

    # Basic date format validation
    import re
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", expiry_date):
        return jsonify({"error": "expiry_date must be YYYY-MM-DD"}), 400

    new_id = db.add_item(name, expiry_date)
    _trigger_display_refresh()

    return jsonify({"id": new_id, "name": name, "expiry_date": expiry_date}), 201


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
    """Serve the latest rendered preview image (useful in dev mode)."""
    preview_path = disp.PREVIEW_PATH
    if not os.path.exists(preview_path):
        # Generate a fresh preview if one doesn't exist yet
        items = db.get_all_items()
        disp.refresh_display(items)

    directory = os.path.dirname(preview_path)
    filename  = os.path.basename(preview_path)
    return send_from_directory(directory, filename, mimetype="image/png")


@app.route("/api/defaults", methods=["GET"])
def get_defaults():
    """Return the produce defaults dict as JSON (used by the frontend)."""
    return jsonify(PRODUCE_DEFAULTS)


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    db.init_db()

    # Render an initial display image on startup so /preview.png works immediately
    items = db.get_all_items()
    disp.refresh_display(items)

    # host="0.0.0.0" makes Flask reachable from other devices on the local network
    app.run(host="0.0.0.0", port=5000, debug=False)
