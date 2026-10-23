#!/usr/bin/env python3
"""Replan desktop 2.1 — native window for the v2 semester planner.

Install: python3 -m pip install -r requirements-desktop.txt
Run:     python3 replanv2_1.py

Keep the replanv2 HTML, CSS, and JavaScript assets beside this file.
The desktop profile is stored in .replanv2-desktop/ beside the launcher.
"""
from __future__ import annotations

import argparse
import base64
import binascii
import sys
from pathlib import Path
from replan_auth import DesktopAuth

APP_NAME = "Replan - Adaptive Semester Planner"
APP_ROOT = Path(__file__).resolve().parent
ASSETS = ("replanv2.html", "replanv2.css", "replanv2.js", "replanv2-calendar.js",
          "replanv2-engine.js", "replanv2-pdf.js", "replanv2-auth.js")
DEFAULT_PORT = 17863  # Stable origin keeps desktop autosave available between launches.


class DesktopAPI:
    """The page can save only through an explicit native Save As dialog."""

    def __init__(self, webview_module):
        self._webview = webview_module
        self._window = None
        self._auth = DesktopAuth(APP_ROOT)

    def _attach(self, window):
        self._window = window

    def sign_in(self, provider: str, calendar: bool = False) -> dict:
        """Open optional Google/Apple sign-in in the user's system browser."""
        return self._auth.sign_in(provider, calendar)

    def save_file(self, filename: str, encoded: str) -> dict:
        if self._window is None:
            raise RuntimeError("The desktop window is not ready yet.")
        if not isinstance(filename, str) or not isinstance(encoded, str):
            raise ValueError("Invalid export data.")
        # Treat the suggested name as a basename, never an arbitrary destination.
        filename = Path(filename.replace("\\", "/")).name
        suffix = Path(filename).suffix.lower()
        descriptions = {".pdf": "PDF checklist", ".json": "Replan backup",
                        ".csv": "Study schedule", ".ics": "Calendar events"}
        if suffix not in descriptions or len(filename) > 200:
            raise ValueError("Choose a PDF, JSON, CSV, or calendar export.")
        if len(encoded) > 180_000_000:
            raise ValueError("This export is too large. Export a smaller schedule.")
        try:
            content = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ValueError("The export data is not valid.") from exc
        destination = self._window.create_file_dialog(
            self._webview.FileDialog.SAVE,
            save_filename=filename,
            file_types=(f"{descriptions[suffix]} (*{suffix})",),
        )
        if not destination:
            return {"saved": False}
        selected = destination if isinstance(destination, str) else destination[0]
        path = Path(selected)
        if not path.suffix:
            path = path.with_suffix(suffix)
        path.write_bytes(content)
        return {"saved": True, "name": path.name}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=f"{APP_NAME} — desktop 2.1")
    parser.add_argument("--debug", action="store_true", help="Enable web developer tools")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT,
                        help="Local desktop port; keep it unchanged to retain the same autosave origin")
    args = parser.parse_args(argv)
    if not 1024 <= args.port <= 65535:
        parser.error("--port must be between 1024 and 65535")
    missing = [name for name in ASSETS if not (APP_ROOT / name).is_file()]
    if missing:
        print("Missing desktop assets: " + ", ".join(missing), file=sys.stderr)
        print("Keep the replanv2 web files beside replanv2_1.py.", file=sys.stderr)
        return 1
    try:
        import webview
    except ImportError:
        print("Replan desktop needs pywebview. Install it with:\n"
              "  python3 -m pip install -r requirements-desktop.txt\n"
              "Then run:\n  python3 replanv2_1.py", file=sys.stderr)
        return 1

    profile = APP_ROOT / ".replanv2-desktop"
    try:
        profile.mkdir(parents=True, exist_ok=True)
        webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = True
        api = DesktopAPI(webview)
        window = webview.create_window(
            APP_NAME,
            url=str(APP_ROOT / "replanv2.html"),
            js_api=api,
            width=1380,
            height=920,
            min_size=(900, 650),
            background_color="#100b0d",
            text_select=True,
            zoomable=True,
        )
        api._attach(window)
        webview.start(
            debug=args.debug,
            http_server=True,
            http_port=args.port,
            private_mode=False,
            storage_path=str(profile),
        )
    except Exception as exc:
        print(f"Could not start Replan desktop: {exc}", file=sys.stderr)
        print("Close an existing Replan window if the desktop port is already in use.\n"
              "On Linux, install a pywebview GTK or Qt backend if requested by the error.",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
