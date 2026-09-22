"""
kml_writer.py
-------------
Builds the KML file: one polygon per parcel, plus a labeled placemark at
each corner point showing its original survey coordinates.

IMPORTANT — thread safety:
simplekml tracks style IDs using variables shared across the whole Python
process (Kmlable._globalid, _currentroot, _processedstyles), not per KML
object. If two Kml() objects get built/saved concurrently (e.g. from two
threads, as will happen once a live-tracking web server is regenerating
KML on each request), that shared state can get stomped on mid-compile —
the symptom is exactly "styleUrl references a style that does not exist"
when the file is opened in Google Earth. build_and_save() below serializes
all KML building through a single lock so this can't happen.
"""

import math
import threading
import simplekml

_METERS_PER_DEGREE_LAT = 111_320  # near enough everywhere; longitude is scaled by cos(latitude) below

PALETTE = [
    simplekml.Color.red,
    simplekml.Color.blue,
    simplekml.Color.green,
    simplekml.Color.orange,
    simplekml.Color.magenta,
    simplekml.Color.yellow,
]

_KML_LOCK = threading.Lock()  # serializes all simplekml build+save calls


def new_kml():
    return simplekml.Kml()


def _lookat_for_points(points):
    """
    A LookAt centered on points' bounding box, zoomed to comfortably fit it —
    so opening the KML (or a single parcel's placemark) flies straight to
    the real boundary at an accurate scale, instead of Google Earth's
    default global view or an arbitrary zoom level.

    Looks straight down (tilt=0) rather than an oblique angle: for reading
    a survey boundary's shape and position accurately, a true top-down map
    view is what matches the original cadastral diagram, and avoids an
    oblique angle foreshortening the parcel or hiding a corner behind
    terrain/trees.
    """
    if not points:
        return None
    lats = [p["lat"] for p in points]
    lons = [p["lon"] for p in points]
    min_lat, max_lat = min(lats), max(lats)
    min_lon, max_lon = min(lons), max(lons)
    center_lat = (min_lat + max_lat) / 2
    center_lon = (min_lon + max_lon) / 2

    lat_span_m = (max_lat - min_lat) * _METERS_PER_DEGREE_LAT
    lon_span_m = (max_lon - min_lon) * _METERS_PER_DEGREE_LAT * math.cos(math.radians(center_lat))
    diagonal_m = math.hypot(lat_span_m, lon_span_m)

    # Padding so the boundary/labels aren't flush against the viewport edge,
    # and a floor so a small parcel (or a single point) doesn't zoom in
    # uncomfortably close or to a degenerate range of ~0.
    range_m = max(diagonal_m * 1.8, 250)

    return simplekml.LookAt(
        latitude=center_lat,
        longitude=center_lon,
        range=range_m,
        tilt=0,
        heading=0,
        altitudemode=simplekml.AltitudeMode.clamptoground,
    )


def add_parcel(kml, name, ordered_points, color_index=0):
    """
    ordered_points: list of dicts, each with keys:
        label, easting, northing, lon, lat
    in boundary order (as walked A -> B -> C -> ... -> back to A).
    """
    color = PALETTE[color_index % len(PALETTE)]

    coords = [(p["lon"], p["lat"]) for p in ordered_points]
    coords_closed = coords + [coords[0]]

    pol = kml.newpolygon(name=name)
    pol.outerboundaryis = coords_closed
    pol.style.linestyle.color = color
    pol.style.linestyle.width = 3
    pol.style.polystyle.color = simplekml.Color.changealphaint(60, color)
    # So double-clicking this parcel in Google Earth's sidebar flies
    # straight to its exact boundary, not just to wherever the last view was.
    pol.lookat = _lookat_for_points(ordered_points)

    folder = kml.newfolder(name=f"{name} - corner points")
    for p in ordered_points:
        pnt = folder.newpoint(name=f"{name} {p['label']}", coords=[(p["lon"], p["lat"])])
        pnt.description = (
            f"Label: {p['label']}\n"
            f"Easting: {p['easting']}\n"
            f"Northing: {p['northing']}\n"
            f"Lat: {p['lat']:.6f}\n"
            f"Lon: {p['lon']:.6f}"
        )
        pnt.style.iconstyle.scale = 0.7
        pnt.style.iconstyle.color = color


def save(kml, path):
    kml.save(path)


def _set_document_lookat(kml, parcels):
    """Sets the document-level LookAt from every parcel's points combined,
    so opening the KML file itself (not just one parcel's placemark) flies
    straight to the real boundary/boundaries."""
    all_points = [p for _name, ordered_points in parcels for p in ordered_points]
    lookat = _lookat_for_points(all_points)
    if lookat is not None:
        kml.document.lookat = lookat


def build_and_save(parcels, path):
    """
    Atomic, thread-safe build: parcels is a list of (name, ordered_points)
    tuples. Holds the lock for the whole build+save so no other thread's
    KML compile can interleave and corrupt shared style-tracking state.
    Returns the path written.
    """
    with _KML_LOCK:
        kml = new_kml()
        for i, (name, ordered_points) in enumerate(parcels):
            add_parcel(kml, name, ordered_points, color_index=i)
        _set_document_lookat(kml, parcels)
        kml.save(path)
    return path


def build_kml_string(parcels):
    """Same as build_and_save, but returns the KML as an in-memory string
    (no disk write) — useful for a server endpoint that streams KML directly."""
    with _KML_LOCK:
        kml = new_kml()
        for i, (name, ordered_points) in enumerate(parcels):
            add_parcel(kml, name, ordered_points, color_index=i)
        _set_document_lookat(kml, parcels)
        return kml.kml()
