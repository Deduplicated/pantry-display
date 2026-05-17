#!/usr/bin/env python3
"""Refresh the e-paper display from cron or a systemd timer."""

import os
import sys

# Project root (parent of scripts/)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import db
import display

if __name__ == "__main__":
    db.init_db()
    display.refresh_display(db.get_all_items())
