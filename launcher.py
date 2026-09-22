"""
launcher.py
-----------
Opens a saved KML file in Google Earth right after it's written, so the
user sees their parcel(s) at their real-world position immediately instead
of having to find the file and double-click it themselves.
"""

import os
import subprocess
import sys

# Common install locations for Google Earth Pro, checked in order. Preferred
# over just handing the file to the OS's default handler for .kml, since
# that's frequently unset (or set to a browser) even when Google Earth Pro
# is installed.
_GOOGLE_EARTH_CANDIDATES = {
    "win32": [
        r"C:\Program Files\Google\Google Earth Pro\client\googleearth.exe",
        r"C:\Program Files (x86)\Google\Google Earth Pro\client\googleearth.exe",
    ],
    "darwin": [
        "/Applications/Google Earth Pro.app/Contents/MacOS/Google Earth Pro",
    ],
    "linux": [
        "/usr/bin/google-earth-pro",
        "/opt/google/earth/pro/googleearth",
    ],
}


def find_google_earth():
    """Path to a locally installed Google Earth Pro executable, or None if
    it isn't at any of the common install locations for this OS."""
    for path in _GOOGLE_EARTH_CANDIDATES.get(sys.platform, []):
        if os.path.isfile(path):
            return path
    return None


def open_in_google_earth(kml_path):
    """
    Launches kml_path in Google Earth Pro if it's installed, otherwise
    falls back to the OS's default handler for .kml files.

    Returns (status, detail):
      status  "google_earth" — launched Google Earth Pro directly.
              "fallback"     — Google Earth Pro wasn't found; handed the
                               file to the OS's default .kml handler
                               instead (which may or may not be Earth).
              "failed"       — nothing could be opened; `detail` explains
                               why (e.g. no application is associated with
                               .kml files at all).
      detail  None, or an error message when status == "failed".
    """
    kml_path = os.path.abspath(kml_path)
    exe = find_google_earth()

    if exe:
        try:
            subprocess.Popen([exe, kml_path])
            return "google_earth", None
        except OSError as exc:
            return "failed", str(exc)

    try:
        if sys.platform == "win32":
            os.startfile(kml_path)  # noqa: S606 - opens with whatever's registered for .kml
        elif sys.platform == "darwin":
            subprocess.Popen(["open", kml_path])
        else:
            subprocess.Popen(["xdg-open", kml_path])
        return "fallback", None
    except OSError as exc:
        return "failed", str(exc)


def describe_open_result(status, detail, kml_path):
    """Human-readable line(s) explaining what happened, shared by the CLI
    and GUI so both report it the same way."""
    if status == "google_earth":
        return ["Opening in Google Earth Pro..."]
    if status == "fallback":
        return [
            "Google Earth Pro wasn't found in its usual install location — "
            "opened the KML with your system's default handler for .kml files instead.",
        ]
    return [
        f"Couldn't auto-open the KML ({detail}).",
        "Install Google Earth Pro (https://www.google.com/earth/about/versions/#earth-pro), "
        f"or open the file manually: {os.path.abspath(kml_path)}",
    ]
