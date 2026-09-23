"""
release_check.py
-----------------
Update check for packaged (frozen) builds — installed via the Windows
installer or Linux AppImage, where there's no Python/git on the target
machine to `git pull` with. Compares the running version.__version__
against the latest GitHub Release tag and, if newer, hands back the
release page URL so the app can point the user at it. This never
downloads or modifies the installed program itself — see updater.py for
the git-based flow used when running from a source checkout instead.
"""

import json
import urllib.error
import urllib.request

from version import __version__

REPO = "nedsonsuren/suren_survey_kml"
_API_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
_RELEASES_PAGE = f"https://github.com/{REPO}/releases/latest"


def _parse_version(tag):
    """'v1.2.0' -> (1, 2, 0); tolerates a missing 'v' prefix or trailing text."""
    raw = tag[1:] if tag.lower().startswith("v") else tag
    parts = []
    for chunk in raw.split("."):
        digits = ""
        for ch in chunk:
            if ch.isdigit():
                digits += ch
            else:
                break
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


def check_for_update(timeout=5):
    """
    Returns (status, detail):
      "up_to_date"        - already on the latest release.
      "update_available"  - detail = (latest_version_str, release_url).
      "offline"           - detail = error message; no network / GitHub unreachable.
    """
    request = urllib.request.Request(
        _API_URL,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "survey-to-kml-updater"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.load(response)
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return "offline", str(exc)

    tag = data.get("tag_name", "")
    url = data.get("html_url", _RELEASES_PAGE)
    if not tag:
        return "offline", "release feed had no tag_name"

    try:
        is_newer = _parse_version(tag) > _parse_version(__version__)
    except ValueError:
        return "offline", f"couldn't parse release tag '{tag}'"

    if is_newer:
        return "update_available", (tag, url)
    return "up_to_date", None
