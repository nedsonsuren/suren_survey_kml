"""
converter.py
------------
Handles coordinate-system selection and conversion of survey (Easting,
Northing) points into WGS84 (lat, lon) — the system Google Earth/KML needs.
"""

from pyproj import Transformer
from pyproj.exceptions import CRSError
from pyproj.transformer import TransformerGroup

# Common presets for southern-African cadastral work. Add more here if you
# survey in other zones/datums.
#
# Third element is a "country hint" (see build_transformer below): some of
# these EPSG codes cover more than one country under the same zone/datum,
# and PROJ's default pick for them is a broad multi-country compromise, not
# necessarily the transformation actually calibrated for the ground being
# surveyed. The hint tells build_transformer() which one is right for this
# preset's intended use.
PRESETS = {
    "1": ("WGS84 UTM Zone 35S  (modern GPS default, Livingstone/Lusaka area)", "EPSG:32735", None),
    "2": ("Arc 1950 UTM Zone 35S  (older Zambian cadastral plans)", "EPSG:20935", "Zambia"),
    "3": ("WGS84 UTM Zone 36S  (eastern Zambia)", "EPSG:32736", None),
    "4": ("Arc 1950 UTM Zone 36S  (older Zambian cadastral plans, east)", "EPSG:20936", "Zambia"),
    "5": ("Custom EPSG code", None, None),
}

TARGET_CRS = "EPSG:4326"  # WGS84 lat/lon, what KML/Google Earth expects


def choose_source_crs():
    """Interactively ask the user which coordinate system their E/N values
    are in. Returns (epsg, country_hint) — see PRESETS/build_transformer."""
    print("\nWhich coordinate system are your survey coordinates in?")
    for key, (label, _epsg, _hint) in PRESETS.items():
        print(f"  {key}. {label}")
    while True:
        choice = input("Choose [1-5]: ").strip()
        if choice in PRESETS:
            label, epsg, hint = PRESETS[choice]
            if epsg is None:
                epsg = input("Enter EPSG code (e.g. EPSG:32735): ").strip()
                if not epsg.upper().startswith("EPSG:"):
                    epsg = f"EPSG:{epsg}"
                if not is_valid_epsg(epsg):
                    print(f"  '{epsg}' isn't a recognized EPSG code. Please try again.")
                    continue
            print(f"Using {label if epsg != label else ''} -> {epsg}")
            return epsg, hint
        print("Invalid choice, try again.")


def is_valid_epsg(epsg):
    """Check a custom EPSG code actually resolves before we build a
    Transformer with it — an unrecognized code otherwise crashes with an
    unhandled pyproj.exceptions.CRSError deep in build_transformer()."""
    try:
        Transformer.from_crs(epsg, TARGET_CRS, always_xy=True)
        return True
    except CRSError:
        return False


def build_transformer(source_epsg, country_hint=None):
    """
    Returns (transformer, info).

    Some legacy datums (e.g. Arc 1950) were tied to the ground with
    different, separately-surveyed parameters in each country they cover.
    A single EPSG code like "Arc 1950 / UTM zone 35S" spans Botswana,
    Zambia *and* Zimbabwe, and PROJ's default pick among the transformations
    on file for it is a broad multi-country compromise — not necessarily the
    one actually calibrated for the ground being surveyed, which can put a
    parcel boundary tens of metres off its true position in Google Earth.

    When more than one transformation to WGS84 exists for source_epsg, this
    prefers the one whose area of use matches `country_hint` (e.g.
    "Zambia"), falling back to PROJ's default pick otherwise.

    info is None when there was nothing to disambiguate (only one
    transformation exists — the common case for modern WGS84 UTM zones).
    Otherwise it's a dict describing which transformation was used and how
    accurate it's expected to be, so the caller can show that to the user
    instead of silently trusting a pick they can't see.
    """
    try:
        candidates = list(TransformerGroup(source_epsg, TARGET_CRS, always_xy=True).transformers)
    except Exception:
        candidates = []

    if len(candidates) <= 1:
        return Transformer.from_crs(source_epsg, TARGET_CRS, always_xy=True), None

    default_pick = candidates[0]
    chosen = default_pick
    if country_hint:
        # Match the hint against individual countries listed in each
        # operation's area of use (names look like "Zambia." or "Botswana;
        # Eswatini (Swaziland); ...; Zambia; Zimbabwe."), not a plain
        # substring check — "Zambia" is a substring of that multi-country
        # list too, which would defeat the whole point of the hint.
        def area_tokens(t):
            name = t.area_of_use.name if t.area_of_use else ""
            return [tok.strip().rstrip(".").lower() for tok in name.split(";")]

        matches = [t for t in candidates if country_hint.strip().lower() in area_tokens(t)]
        if matches:
            # Prefer the most specific match — fewest countries listed —
            # over one that merely includes this country among several.
            matches.sort(key=lambda t: len(area_tokens(t)))
            chosen = matches[0]

    info = {
        "description": chosen.description,
        "accuracy_m": chosen.accuracy if chosen.accuracy is not None and chosen.accuracy >= 0 else None,
        "area": chosen.area_of_use.name if chosen.area_of_use else "unknown",
        "overrode_default": chosen is not default_pick,
        "country_hint": country_hint,
    }
    return chosen, info


def describe_transform_info(info):
    """Format build_transformer()'s info dict into human-readable lines,
    shared by the CLI and GUI so both explain a disambiguated transformation
    the same way."""
    if info is None:
        return []
    acc = f"~{info['accuracy_m']:.0f} m" if info["accuracy_m"] is not None else "unknown"
    lines = [
        f"Datum transformation in use: {info['description']}",
        f"  Valid for: {info['area']}   Estimated accuracy: {acc}",
    ]
    if info["overrode_default"]:
        lines.append(
            f"  (Multiple transformations exist for this coordinate system; picked the one "
            f"calibrated for {info['country_hint']} instead of PROJ's broader default, "
            f"so the boundary lands at its true position.)"
        )
    return lines


def convert_point(transformer, easting, northing):
    """Returns (lon, lat) for a given (easting, northing) pair."""
    lon, lat = transformer.transform(easting, northing)
    return lon, lat
