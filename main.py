"""
Survey-to-KML
=============
Interactive command-line tool: type in survey (Easting, Northing) points
for one or more parcels, and it produces a KML file you can open directly
in Google Earth, correctly placed at the real-world location.

Run:
    python main.py
"""

import sys
import os

# On Windows, the console's default codepage (e.g. cp1252/437) can't encode
# characters like "—" or "²" that this script prints — they'd come out as
# garbled "?" / mojibake, or crash with UnicodeEncodeError on older Python.
# Force UTF-8 on stdout/stderr so output renders correctly everywhere.
if sys.platform == "win32":
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from converter import choose_source_crs, build_transformer, convert_point, describe_transform_info
from geometry import perimeter, area
from kml_writer import build_and_save
from launcher import open_in_google_earth, describe_open_result
from updater import check_for_update, apply_update
from version import __version__


def offer_update():
    """Checks for a newer version and, if found, offers to update before
    continuing. Packaged builds (installed .exe/AppImage) check GitHub
    Releases and just point at the download — they can't `git pull`
    themselves. Running from a git clone instead checks the repo directly
    and can pull the update in place. No-op with no network either way."""
    if getattr(sys, "frozen", False):
        from release_check import check_for_update as check_release
        status, detail = check_release()
        if status == "update_available":
            latest_version, url = detail
            print(f"\nA new version is available: {latest_version} (you have {__version__}).")
            print(f"Download it here: {url}")
        return

    root = os.path.dirname(os.path.abspath(__file__))
    status, detail = check_for_update(root)
    if status != "update_available":
        return
    print(f"\nA new version is available ({detail} commit(s) behind).")
    choice = input("Update now before continuing? [Y/n]: ").strip().lower()
    if choice == "n":
        return
    ok, msg = apply_update(root)
    if ok:
        print("Updated. Please re-run: python main.py")
        sys.exit(0)
    print(f"Update failed ({msg}) — continuing with the current version.")


def prompt_float(prompt_text):
    while True:
        raw = input(prompt_text).strip()
        try:
            return float(raw)
        except ValueError:
            print("  Please enter a number (e.g. 381002.320).")


def is_valid_label(label):
    """A point label should be a short name like 'A'"""
    if label == "":
        return False, "empty"
    try:
        float(label)
        return False, "looks like a number, not a label — did this land in the wrong prompt?"
    except ValueError:
        pass
    if ".kml" in label.lower() or "/" in label or "\\" in label:
        return False, "looks like a filename, not a label"
    return True, ""


def validate_parcel_name(name):
    """A parcel name should be a short human-readable name, not a filename
    or a bare number. Shared by the CLI prompt and the GUI so both reject
    the same mistakes the same way."""
    ok, reason = is_valid_label(name.replace(" ", ""))  # allow spaces in names
    if ".kml" in name.lower() or "/" in name or "\\" in name:
        return False, "looks like a filename, not a parcel name"
    if not ok and reason.startswith("looks like a number"):
        return False, reason
    return True, ""


def prompt_label(point_number):
    while True:
        label = input(f"  Point {point_number} label (e.g. A) [blank to finish]: ").strip()
        if label == "":
            return ""  # signals "done with this parcel"
        ok, reason = is_valid_label(label)
        if ok:
            return label
        print(f"    That doesn't look right ({reason}). Please re-enter just the label, e.g. A")


def prompt_parcel_name(default_name):
    while True:
        name = input(f"\nName for this parcel [{default_name}]: ").strip() or default_name
        ok, reason = validate_parcel_name(name)
        if not ok:
            print(f"    That doesn't look right ({reason}). Please enter a name, e.g. 'Parcel 1' or 'North Block'.")
            continue
        return name


def collect_points_for_parcel():
    points = []
    print("Enter each corner point, in boundary order (walking around the parcel). Leave the label blank when done.")
    while True:
        label = prompt_label(len(points) + 1)
        if label == "":
            if len(points) < 3:
                print("  Need at least 3 points to form a boundary — keep going.")
                continue
            break
        easting = prompt_float(f"    Easting for {label}: ")
        northing = prompt_float(f"    Northing for {label}: ")
        points.append({"label": label, "easting": easting, "northing": northing})
    return points


def review_parcel(name, points, peri, ar):
    """Show exactly what was captured and let the user redo it if a value looks wrong,
    before it ever gets baked into the KML."""
    print(f"\n  Review — {name}  ({len(points)} points)")
    for p in points:
        print(f"    {p['label']}: E={p['easting']}, N={p['northing']}")
    print(f"    Perimeter: {peri:.2f} m   Area: {ar:.2f} m² ({ar/10000:.4f} ha)")
    print("  If you have the original diagram's side lengths, check the perimeter matches.")
    ok = input("  Does this look correct? [Y/n]: ").strip().lower()
    return ok != "n"


def main():
    print("=" * 60)
    print(" Survey Coordinates -> KML (Google Earth) ")
    print("=" * 60)

    offer_update()

    source_epsg, country_hint = choose_source_crs()
    transformer, transform_info = build_transformer(source_epsg, country_hint)
    for line in describe_transform_info(transform_info):
        print(line)

    parcels_for_kml = []  # (name, ordered_points_with_lonlat)
    summary = []
    parcel_index = 0

    while True:
        parcel_index += 1
        while True:
            name = prompt_parcel_name(f"Parcel {parcel_index}")
            raw_points = collect_points_for_parcel()

            en_pairs = [(p["easting"], p["northing"]) for p in raw_points]
            peri = perimeter(en_pairs)
            ar = area(en_pairs)

            if review_parcel(name, raw_points, peri, ar):
                break
            print("  Okay — let's redo this parcel.\n")

        for p in raw_points:
            lon, lat = convert_point(transformer, p["easting"], p["northing"])
            p["lon"], p["lat"] = lon, lat

        parcels_for_kml.append((name, raw_points))
        summary.append((name, raw_points, peri, ar))

        again = input("\nAdd another parcel? [y/N]: ").strip().lower()
        if again != "y":
            break

    # Print a final verification summary
    print("\n" + "=" * 60)
    print(" Summary ")
    print("=" * 60)
    for name, pts, peri, ar in summary:
        print(f"\n{name}  ({len(pts)} points)")
        for p in pts:
            print(f"  {p['label']}: E={p['easting']}, N={p['northing']}  ->  lat={p['lat']:.6f}, lon={p['lon']:.6f}")
        print(f"  Perimeter: {peri:.2f} m")
        print(f"  Area:      {ar:.2f} m²  ({ar/10000:.4f} ha)")

    default_out = "survey_parcels.kml"
    out_path = input(f"\nOutput KML filename [{default_out}]: ").strip() or default_out
    if not out_path.lower().endswith(".kml"):
        out_path += ".kml"

    build_and_save(parcels_for_kml, out_path)
    print(f"\nSaved: {os.path.abspath(out_path)}")

    status, detail = open_in_google_earth(out_path)
    for line in describe_open_result(status, detail, out_path):
        print(line)


if __name__ == "__main__":
    main()
