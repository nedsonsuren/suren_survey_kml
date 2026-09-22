# Survey-to-KML

Turns survey coordinate tables (Easting/Northing, from a UTM-based cadastral
diagram) into a KML file you can open directly in Google Earth, with the
parcel boundary drawn at its true real-world position.

## Setup (in VS Code)

1. Open this folder in VS Code (`File > Open Folder...`).
2. Open a terminal in VS Code (`` Ctrl+` `` / `` Cmd+` ``).
3. Create a virtual environment (recommended):
   ```
   python -m venv .venv
   ```
   Activate it:
   - Windows: `.venv\Scripts\activate`
   - Mac/Linux: `source .venv/bin/activate`
4. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

## Running it

**Desktop app (no browser, no terminal typing):**

```
python gui.py
```

Pick your coordinate system, add parcels and their corner points in the
form, watch the shape/perimeter/area preview update live, then click
"Save all parcels to KML...". Requires Tkinter, which ships with standard
Python installs (if it's missing, install the `python3-tk` package on
Linux; Windows/Mac installs already include it).

**Command line (step-by-step prompts):**

```
python main.py
```

It will walk you through, step by step:

1. **Pick the coordinate system** your survey uses (a numbered menu — pick
   the preset that matches your plan, or enter a custom EPSG code).
2. **Type in each corner point**: a label (A, B, C...), then its Easting,
   then its Northing. Leave the label blank when a parcel is finished.
3. Repeat for as many parcels as you have on one job.
4. It prints a summary (converted lat/lon, perimeter, and area for each
   parcel) so you can sanity-check the numbers before saving.
5. Name the output file — it saves a `.kml` and opens it for you automatically.

## Opening in Google Earth

Once a KML is saved (CLI or GUI), the tool launches it right away:

- If **Google Earth Pro** is installed at its usual location, it's opened
  directly there.
- Otherwise, the file is handed to your OS's default handler for `.kml`
  files (Google Earth if you've set it as default, otherwise whatever is).
- If neither works (Google Earth Pro isn't installed and there's no default
  handler), you'll get a clear message telling you so, plus the file's
  full path to open manually.

The KML itself also carries a `<LookAt>` computed from your parcel's actual
corner points — a straight-down view centered and zoomed to fit the
boundary — on both the file as a whole and on each individual parcel. That
means opening the file (or double-clicking one parcel in Google Earth's
sidebar) flies straight to the real boundary at a sensible scale, instead
of Google Earth's default global view.

## Getting the boundary in the exact right spot

An EPSG code like "Arc 1950 UTM Zone 35S" isn't tied to just one set of
datum-shift parameters — Arc 1950 was surveyed into the ground separately
per country, and this one code covers Botswana, Zambia *and* Zimbabwe.
Left to its own defaults, the underlying conversion library picks a generic
compromise transformation for whichever code you choose, which can place a
parcel boundary **tens of metres** off its true position — enough to land
it on the wrong side of a road in Google Earth.

For the Arc 1950 presets, this tool instead picks the transformation
specifically calibrated for Zambia, and tells you so:

```
Datum transformation in use: Inverse of UTM zone 35S + Arc 1950 to WGS 84 (8) + axis order change (2D)
  Valid for: Zambia.   Estimated accuracy: ~41 m
  (Multiple transformations exist for this coordinate system; picked the one
  calibrated for Zambia instead of PROJ's broader default, so the boundary
  lands at its true position.)
```

You'll see this message (CLI) or a note in the save dialog (GUI) whenever
more than one transformation exists for your chosen coordinate system — for
the modern WGS84 presets there's only one, so nothing extra is printed.
If you enter a **custom EPSG code** covering multiple countries, there's no
hint to pick the right one automatically; check the "Valid for" line that's
printed, and if it doesn't match your survey's country, that's your signal
the boundary may be off — consider adding a preset with a country hint for
it in `src/converter.py` (`PRESETS`) instead.

## Checking you picked the right coordinate system

If the parcel opens in the wrong part of the map (wrong country, wrong side
of town, etc.), you likely picked the wrong zone or datum. Re-run and try
the alternative preset (e.g. Arc 1950 instead of WGS84 for the same zone) —
common on older Zambian survey plans.

You can also cross-check using the survey diagram's own **side lengths**:
the tool prints the total perimeter it computed from your points, which
should match the sum of side lengths on the original diagram (e.g. AB + BC
+ CD + DA). If they don't match, double check the Easting/Northing values
were typed correctly.

## Installing on another machine, and getting updates

This project lives at
[github.com/nedsonsuren/suren_survey_kml](https://github.com/nedsonsuren/suren_survey_kml).
To set it up on a machine for the first time, clone it instead of copying
the folder:

```
git clone https://github.com/nedsonsuren/suren_survey_kml.git
```

then follow "Setup" above inside that folder. Because it's a real clone,
every time you run `python gui.py` or `python main.py` it checks GitHub
for a newer commit and, if one exists, asks whether to pull it in before
continuing (GUI: a Yes/No dialog before the window opens; CLI: a `[Y/n]`
prompt) — no separate updater or reinstall needed. Declining just runs the
current version as-is; if the check can't reach GitHub (no network), it's
skipped silently.

To push a change so every clone picks it up on next launch, commit and
`git push` from your working copy as usual.

## Packaging as a Windows installer

To hand this to someone without Python installed, build
`Survey-to-KML-Setup.exe` (a normal installer with a Start Menu shortcut
and uninstaller) — see [BUILD.md](BUILD.md).

## Project structure

```
survey-to-kml/
├── gui.py              # desktop GUI entry point (Tkinter)
├── main.py             # interactive CLI entry point
├── requirements.txt
├── assets/
│   ├── icon.ico         # window/taskbar icon (multi-resolution)
│   └── icon.png         # same icon, for cross-platform iconphoto()
├── src/
│   ├── converter.py    # coordinate system presets + UTM -> lat/lon conversion
│   ├── geometry.py     # perimeter/area calculations
│   ├── kml_writer.py   # builds the KML polygons + labeled points + LookAt
│   └── launcher.py     # opens the saved KML in Google Earth
└── README.md
```

`gui.py` and `main.py` share the same validation and conversion logic —
`validate_parcel_name`/`is_valid_label` live in `main.py`, everything else
in `src/` — so both front ends reject the same mistakes and produce
identical KML output.

## Extending it

- Add more coordinate-system presets in `src/converter.py` (`PRESETS` dict)
  if you regularly survey in other zones/datums — each entry is
  `(label, epsg, country_hint)`; set `country_hint` (e.g. `"Zambia"`) when
  the EPSG code's datum transformation is shared across multiple countries,
  so the right one gets picked automatically (see "Getting the boundary in
  the exact right spot" above).
- `src/kml_writer.py` controls styling (colors, line width) — edit `PALETTE`
  to change parcel colors.
