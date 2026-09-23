# Building installable packages

Two outputs, one per platform. Neither requires Python (or anything else)
on the machine that ends up running the app.

- **Windows** — `Survey-to-KML-Setup.exe`, a normal installer (Start Menu
  shortcut, optional desktop shortcut, uninstaller registered in
  Add/Remove Programs).
- **Linux** — `Survey-to-KML-<version>-x86_64.AppImage`, a single
  double-clickable file — no install step.

Both bundle the app's version from [version.py](version.py). Bump
`__version__` there before building a release.

## Windows installer

Build on a Windows machine, from the repo root, in a Python environment
with `requirements.txt` installed:

```
pip install pyinstaller
python -m PyInstaller survey_to_kml.spec --noconfirm
```

This produces `dist\Survey-to-KML.exe` — a standalone windowed binary,
already usable on its own. Wrap it in the installer with
[Inno Setup](https://jrsoft.org/isinfo.php) (`ISCC.exe`, installed via
`winget install JRSoftware.InnoSetup` if you don't have it):

```
ISCC installer.iss
```

Output: `installer_output\Survey-to-KML-Setup.exe`.

## Linux AppImage

Build on a Linux machine (PyInstaller doesn't cross-compile, so this
can't be produced from Windows):

```
bash packaging/build_linux_appimage.sh
```

That script creates a build venv, runs PyInstaller against the same
`survey_to_kml.spec`, assembles an AppDir (`packaging/survey-to-kml.desktop`
+ `assets/icon.png`), downloads `appimagetool` if it isn't already present,
and produces `Survey-to-KML-<version>-x86_64.AppImage` in the repo root.
Requires `python3-tk` to be installed on the build machine (Tkinter isn't
pulled in by pip) — e.g. `sudo apt install python3-tk` on Debian/Ubuntu.

## Publishing a release

Both artifacts are meant to be attached to a GitHub Release tagged
`vX.Y.Z` matching `version.py`. The installed app's built-in update check
([release_check.py](release_check.py)) looks at
`https://github.com/nedsonsuren/suren_survey_kml/releases/latest` and
tells the user when a newer tag exists — it only ever points them at the
release page, it never downloads or replaces anything itself.

1. Bump `__version__` in `version.py`, commit, `git push`.
2. Build both artifacts (above).
3. On GitHub: Releases → Draft a new release → tag `vX.Y.Z` → upload
   `Survey-to-KML-Setup.exe` and the `.AppImage` → publish.

## Developer installs (git clone)

If you're running from a git clone instead of an installed package —
e.g. while developing — see the "Installing on another machine, and
getting updates" section in [README.md](README.md) instead. That flow
uses [updater.py](updater.py) (`git pull`), not the release-based check
above; `main.py`/`gui.py` pick whichever applies automatically based on
whether they're running frozen (packaged) or from source.
