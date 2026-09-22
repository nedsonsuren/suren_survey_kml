"""
geometry.py
-----------
Perimeter and area calculations done directly on the projected (Easting,
Northing) survey coordinates, in metres — this is accurate, unlike doing
the same math on lat/lon degrees.
"""

import math


def perimeter(points_en):
    """points_en: ordered list of (easting, northing) tuples (open ring)."""
    pts = points_en + [points_en[0]]
    total = 0.0
    for (e1, n1), (e2, n2) in zip(pts, pts[1:]):
        total += math.hypot(e2 - e1, n2 - n1)
    return total


def area(points_en):
    """Shoelace formula. points_en: ordered list of (easting, northing), open ring."""
    pts = points_en + [points_en[0]]
    s = 0.0
    for (e1, n1), (e2, n2) in zip(pts, pts[1:]):
        s += e1 * n2 - e2 * n1
    return abs(s) / 2.0
