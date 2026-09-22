"""
Survey-to-KML — desktop GUI
============================
A native Tkinter app (no browser, no HTML) that does everything main.py's
command-line version does: pick a coordinate system, enter parcel corner
points, preview the shape/perimeter/area, and save a .kml for Google Earth.

Reuses the same logic as the CLI (src/converter.py, src/geometry.py,
src/kml_writer.py, and the shared validators in main.py) so both front
ends stay consistent and there is exactly one place each rule lives.

Run:
    python gui.py
"""

import sys
import os

if sys.platform == "win32":
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

import tkinter as tk
from tkinter import ttk, messagebox, filedialog

# These live in src/, added to sys.path above at runtime — static analysis
# (Pylance/pyright) can't see that, so it flags them as unresolved even
# though they import fine. Suppressed here rather than relying solely on
# .vscode/settings.json's extraPaths, which needs a window reload to apply.
from converter import PRESETS, build_transformer, convert_point, is_valid_epsg, describe_transform_info  # pyright: ignore[reportMissingImports]
from geometry import perimeter, area  # pyright: ignore[reportMissingImports]
from kml_writer import build_and_save  # pyright: ignore[reportMissingImports]
from launcher import open_in_google_earth, describe_open_result  # pyright: ignore[reportMissingImports]
from updater import check_for_update, apply_update  # pyright: ignore[reportMissingImports]
from main import is_valid_label, validate_parcel_name

PRESET_LABELS = [label for (label, _epsg, _hint) in PRESETS.values()]
PRESET_KEYS = list(PRESETS.keys())

APP_NAME = "Suren"
_ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")
ICON_ICO = os.path.join(_ASSETS_DIR, "icon.ico")
ICON_PNG = os.path.join(_ASSETS_DIR, "icon.png")


class Parcel:
    """One parcel being built in the GUI: a name plus ordered corner points."""

    def __init__(self, name):
        self.name = name
        self.points = []  # list of {"label", "easting", "northing"}

    def en_pairs(self):
        return [(p["easting"], p["northing"]) for p in self.points]

    def perimeter(self):
        return perimeter(self.en_pairs()) if len(self.points) >= 2 else 0.0

    def area(self):
        return area(self.en_pairs()) if len(self.points) >= 3 else 0.0


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self._set_icon()
        self.geometry("980x620")
        self.minsize(860, 540)

        self.parcels = []
        self.current_parcel = None
        self.last_saved_path = None

        self._build_crs_section()
        self._build_body()
        self._build_save_bar()

        self._new_parcel(select=True)

    def _set_icon(self):
        """Sets the title-bar/taskbar icon. Best-effort: a missing or
        unreadable icon file (e.g. running from a stripped-down copy of the
        repo) shouldn't stop the app from starting."""
        try:
            self.iconbitmap(ICON_ICO)  # classic Windows title-bar/taskbar icon
        except Exception:
            pass
        try:
            # Cross-platform fallback (also covers Alt-Tab/dock on some
            # window managers where iconbitmap alone isn't enough). Keep a
            # reference on self — Tk drops the icon if the PhotoImage gets
            # garbage-collected.
            self._icon_photo = tk.PhotoImage(file=ICON_PNG)
            self.iconphoto(True, self._icon_photo)
        except Exception:
            pass

    # ---------------------------------------------------------------- CRS

    def _build_crs_section(self):
        frame = ttk.LabelFrame(self, text="Coordinate system of your survey (Easting/Northing)")
        frame.pack(fill="x", padx=10, pady=(10, 5))

        self.crs_choice = tk.StringVar(value=PRESET_LABELS[0])
        combo = ttk.Combobox(
            frame, textvariable=self.crs_choice, values=PRESET_LABELS,
            state="readonly", width=55,
        )
        combo.grid(row=0, column=0, padx=8, pady=8, sticky="w")
        combo.bind("<<ComboboxSelected>>", self._on_crs_change)

        ttk.Label(frame, text="Custom EPSG code:").grid(row=0, column=1, padx=(15, 4))
        self.custom_epsg = tk.StringVar()
        self.custom_epsg_entry = ttk.Entry(frame, textvariable=self.custom_epsg, width=16, state="disabled")
        self.custom_epsg_entry.grid(row=0, column=2, padx=4)

    def _on_crs_change(self, _event=None):
        is_custom = self.crs_choice.get() == PRESET_LABELS[-1]
        self.custom_epsg_entry.configure(state="normal" if is_custom else "disabled")

    def _selected_epsg(self):
        """Returns (epsg_code, country_hint, error_message). error_message is None on success."""
        idx = PRESET_LABELS.index(self.crs_choice.get())
        key = PRESET_KEYS[idx]
        label, epsg, hint = PRESETS[key]
        if epsg is not None:
            return epsg, hint, None

        raw = self.custom_epsg.get().strip()
        if not raw:
            return None, None, "Enter a custom EPSG code (e.g. EPSG:32735)."
        epsg = raw if raw.upper().startswith("EPSG:") else f"EPSG:{raw}"
        if not is_valid_epsg(epsg):
            return None, None, f"'{epsg}' isn't a recognized EPSG code."
        return epsg, None, None

    # --------------------------------------------------------------- body

    def _build_body(self):
        body = ttk.Frame(self)
        body.pack(fill="both", expand=True, padx=10, pady=5)
        body.columnconfigure(0, weight=0)
        body.columnconfigure(1, weight=1)
        body.columnconfigure(2, weight=1)
        body.rowconfigure(0, weight=1)

        self._build_parcel_list(body)
        self._build_points_panel(body)
        self._build_preview_panel(body)

    def _build_parcel_list(self, parent):
        frame = ttk.LabelFrame(parent, text="Parcels")
        frame.grid(row=0, column=0, sticky="ns", padx=(0, 8))

        self.parcel_listbox = tk.Listbox(frame, width=22, exportselection=False)
        self.parcel_listbox.pack(fill="y", expand=True, padx=6, pady=6)
        self.parcel_listbox.bind("<<ListboxSelect>>", self._on_select_parcel)

        btns = ttk.Frame(frame)
        btns.pack(fill="x", padx=6, pady=(0, 6))
        ttk.Button(btns, text="New", command=lambda: self._new_parcel(select=True)).pack(side="left", expand=True, fill="x")
        ttk.Button(btns, text="Rename", command=self._rename_parcel).pack(side="left", expand=True, fill="x")
        ttk.Button(btns, text="Delete", command=self._delete_parcel).pack(side="left", expand=True, fill="x")

    def _build_points_panel(self, parent):
        frame = ttk.LabelFrame(parent, text="Corner points (boundary order)")
        frame.grid(row=0, column=1, sticky="nsew", padx=8)
        frame.rowconfigure(1, weight=1)
        frame.columnconfigure(0, weight=1)

        entry_row = ttk.Frame(frame)
        entry_row.grid(row=0, column=0, sticky="ew", padx=6, pady=6)
        ttk.Label(entry_row, text="Label:").grid(row=0, column=0)
        self.point_label_var = tk.StringVar()
        ttk.Entry(entry_row, textvariable=self.point_label_var, width=6).grid(row=0, column=1, padx=(2, 10))
        ttk.Label(entry_row, text="Easting:").grid(row=0, column=2)
        self.point_easting_var = tk.StringVar()
        ttk.Entry(entry_row, textvariable=self.point_easting_var, width=14).grid(row=0, column=3, padx=(2, 10))
        ttk.Label(entry_row, text="Northing:").grid(row=0, column=4)
        self.point_northing_var = tk.StringVar()
        ttk.Entry(entry_row, textvariable=self.point_northing_var, width=14).grid(row=0, column=5, padx=(2, 10))
        ttk.Button(entry_row, text="Add point", command=self._add_point).grid(row=0, column=6, padx=(4, 0))

        columns = ("label", "easting", "northing")
        self.points_tree = ttk.Treeview(frame, columns=columns, show="headings", height=10)
        for col, width in zip(columns, (60, 140, 140)):
            self.points_tree.heading(col, text=col.capitalize())
            self.points_tree.column(col, width=width, anchor="center")
        self.points_tree.grid(row=1, column=0, sticky="nsew", padx=6)

        btns = ttk.Frame(frame)
        btns.grid(row=2, column=0, sticky="ew", padx=6, pady=6)
        ttk.Button(btns, text="Move up", command=lambda: self._move_point(-1)).pack(side="left")
        ttk.Button(btns, text="Move down", command=lambda: self._move_point(1)).pack(side="left", padx=6)
        ttk.Button(btns, text="Remove selected", command=self._remove_point).pack(side="left")

        self.summary_label = ttk.Label(frame, text="Need at least 3 points to form a boundary.")
        self.summary_label.grid(row=3, column=0, sticky="w", padx=6, pady=(0, 6))

    def _build_preview_panel(self, parent):
        frame = ttk.LabelFrame(parent, text="Shape preview")
        frame.grid(row=0, column=2, sticky="nsew", padx=(8, 0))
        self.canvas = tk.Canvas(frame, bg="white", width=320, height=320)
        self.canvas.pack(fill="both", expand=True, padx=6, pady=6)

    def _build_save_bar(self):
        bar = ttk.Frame(self)
        bar.pack(fill="x", padx=10, pady=(0, 10))
        ttk.Button(bar, text="Save all parcels to KML...", command=self._save_kml).pack(side="right")
        ttk.Button(bar, text="View in Google Earth...", command=self._view_kml).pack(side="right", padx=(0, 8))

    # ------------------------------------------------------------ parcels

    def _new_parcel(self, select=False):
        name = f"Parcel {len(self.parcels) + 1}"
        parcel = Parcel(name)
        self.parcels.append(parcel)
        self.parcel_listbox.insert("end", name)
        if select:
            self.parcel_listbox.selection_clear(0, "end")
            self.parcel_listbox.selection_set("end")
            self._on_select_parcel()

    def _selected_parcel_index(self):
        sel = self.parcel_listbox.curselection()
        return sel[0] if sel else None

    def _on_select_parcel(self, _event=None):
        idx = self._selected_parcel_index()
        if idx is None:
            return
        self.current_parcel = self.parcels[idx]
        self._refresh_points_tree()

    def _rename_parcel(self):
        idx = self._selected_parcel_index()
        if idx is None:
            messagebox.showinfo("Rename parcel", "Select a parcel first.")
            return
        parcel = self.parcels[idx]

        dialog = tk.Toplevel(self)
        dialog.title("Rename parcel")
        dialog.transient(self)
        ttk.Label(dialog, text="New name:").pack(padx=10, pady=(10, 0))
        name_var = tk.StringVar(value=parcel.name)
        entry = ttk.Entry(dialog, textvariable=name_var, width=30)
        entry.pack(padx=10, pady=5)
        entry.focus_set()

        def confirm():
            ok, reason = validate_parcel_name(name_var.get().strip())
            if not ok:
                messagebox.showerror("Invalid name", f"That doesn't look right ({reason}).", parent=dialog)
                return
            parcel.name = name_var.get().strip()
            self.parcel_listbox.delete(idx)
            self.parcel_listbox.insert(idx, parcel.name)
            self.parcel_listbox.selection_set(idx)
            dialog.destroy()

        ttk.Button(dialog, text="Save", command=confirm).pack(pady=(0, 10))
        dialog.bind("<Return>", lambda _e: confirm())
        dialog.grab_set()

    def _delete_parcel(self):
        idx = self._selected_parcel_index()
        if idx is None:
            return
        if len(self.parcels) == 1:
            messagebox.showinfo("Delete parcel", "At least one parcel is required — clear its points instead.")
            return
        if not messagebox.askyesno("Delete parcel", f"Delete '{self.parcels[idx].name}'?"):
            return
        del self.parcels[idx]
        self.parcel_listbox.delete(idx)
        new_idx = min(idx, len(self.parcels) - 1)
        self.parcel_listbox.selection_set(new_idx)
        self._on_select_parcel()

    # -------------------------------------------------------------- points

    def _add_point(self):
        if self.current_parcel is None:
            return
        label = self.point_label_var.get().strip()
        ok, reason = is_valid_label(label)
        if not ok:
            messagebox.showerror("Invalid label", f"That doesn't look right ({reason}).")
            return
        if any(p["label"] == label for p in self.current_parcel.points):
            messagebox.showerror("Duplicate label", f"Point '{label}' already exists in this parcel.")
            return
        try:
            easting = float(self.point_easting_var.get().strip())
            northing = float(self.point_northing_var.get().strip())
        except ValueError:
            messagebox.showerror("Invalid coordinates", "Easting and Northing must be numbers (e.g. 381002.320).")
            return

        self.current_parcel.points.append({"label": label, "easting": easting, "northing": northing})
        self.point_label_var.set("")
        self.point_easting_var.set("")
        self.point_northing_var.set("")
        self._refresh_points_tree()

    def _selected_point_index(self):
        sel = self.points_tree.selection()
        if not sel:
            return None
        return self.points_tree.index(sel[0])

    def _remove_point(self):
        idx = self._selected_point_index()
        if idx is None or self.current_parcel is None:
            return
        del self.current_parcel.points[idx]
        self._refresh_points_tree()

    def _move_point(self, direction):
        idx = self._selected_point_index()
        if idx is None or self.current_parcel is None:
            return
        new_idx = idx + direction
        pts = self.current_parcel.points
        if not (0 <= new_idx < len(pts)):
            return
        pts[idx], pts[new_idx] = pts[new_idx], pts[idx]
        self._refresh_points_tree()
        children = self.points_tree.get_children()
        self.points_tree.selection_set(children[new_idx])

    def _refresh_points_tree(self):
        self.points_tree.delete(*self.points_tree.get_children())
        if self.current_parcel is None:
            return
        for p in self.current_parcel.points:
            self.points_tree.insert("", "end", values=(p["label"], p["easting"], p["northing"]))

        n = len(self.current_parcel.points)
        if n < 3:
            self.summary_label.configure(text=f"Need at least 3 points to form a boundary ({n} so far).")
        else:
            peri = self.current_parcel.perimeter()
            ar = self.current_parcel.area()
            self.summary_label.configure(
                text=f"{n} points   Perimeter: {peri:.2f} m   Area: {ar:.2f} m² ({ar / 10000:.4f} ha)"
            )
        self._draw_preview()

    def _draw_preview(self):
        self.canvas.delete("all")
        if self.current_parcel is None or len(self.current_parcel.points) < 2:
            return
        pts = self.current_parcel.points
        eastings = [p["easting"] for p in pts]
        northings = [p["northing"] for p in pts]
        min_e, max_e = min(eastings), max(eastings)
        min_n, max_n = min(northings), max(northings)
        span_e = max(max_e - min_e, 1e-9)
        span_n = max(max_n - min_n, 1e-9)

        w = int(self.canvas["width"])
        h = int(self.canvas["height"])
        pad = 30
        scale = min((w - 2 * pad) / span_e, (h - 2 * pad) / span_n)

        def to_canvas(e, n):
            x = pad + (e - min_e) * scale
            # Northing increases "up"; canvas y grows downward, so invert.
            y = h - pad - (n - min_n) * scale
            return x, y

        coords = [to_canvas(p["easting"], p["northing"]) for p in pts]
        if len(coords) >= 3:
            flat = [c for xy in coords for c in xy]
            self.canvas.create_polygon(flat, outline="#2a6fdb", fill="#cfe0fb", width=2)
        else:
            self.canvas.create_line(*coords[0], *coords[1], fill="#2a6fdb", width=2)

        for p, (x, y) in zip(pts, coords):
            self.canvas.create_oval(x - 3, y - 3, x + 3, y + 3, fill="#2a6fdb", outline="")
            self.canvas.create_text(x + 8, y - 8, text=p["label"], anchor="w")

    # ---------------------------------------------------------------- save

    def _save_kml(self):
        epsg, country_hint, error = self._selected_epsg()
        if error:
            messagebox.showerror("Coordinate system", error)
            return

        incomplete = [p.name for p in self.parcels if len(p.points) < 3]
        if incomplete:
            messagebox.showerror(
                "Not enough points",
                "These parcels need at least 3 points before saving:\n" + "\n".join(incomplete),
            )
            return

        try:
            transformer, transform_info = build_transformer(epsg, country_hint)
        except Exception as exc:  # pragma: no cover - guarded by is_valid_epsg already
            messagebox.showerror("Coordinate system", f"Could not use {epsg}: {exc}")
            return

        parcels_for_kml = []
        for parcel in self.parcels:
            converted_points = []
            for p in parcel.points:
                lon, lat = convert_point(transformer, p["easting"], p["northing"])
                converted_points.append({**p, "lon": lon, "lat": lat})
            parcels_for_kml.append((parcel.name, converted_points))

        path = filedialog.asksaveasfilename(
            title="Save KML",
            defaultextension=".kml",
            filetypes=[("KML files", "*.kml")],
            initialfile="survey_parcels.kml",
        )
        if not path:
            return

        build_and_save(parcels_for_kml, path)
        self.last_saved_path = path

        status, detail = open_in_google_earth(path)
        open_lines = describe_open_result(status, detail, path)

        info_lines = describe_transform_info(transform_info)
        info_block = ("\n\n" + "\n".join(info_lines)) if info_lines else ""
        messagebox.showinfo(
            "Saved",
            f"Saved: {path}\n\n" + "\n".join(open_lines) + info_block,
        )

    def _view_kml(self):
        """Opens a KML in Google Earth (or the system's .kml handler) without
        re-saving — the last file saved this session, or one picked from
        disk if nothing's been saved yet."""
        path = self.last_saved_path
        if path is None or not os.path.isfile(path):
            path = filedialog.askopenfilename(
                title="Open KML in Google Earth",
                filetypes=[("KML files", "*.kml"), ("All files", "*.*")],
            )
            if not path:
                return

        status, detail = open_in_google_earth(path)
        messagebox.showinfo("View in Google Earth", "\n".join(describe_open_result(status, detail, path)))


def _offer_update():
    """Checks GitHub for a newer commit and, if found, offers to pull it in
    before the main window opens. No-op if this isn't a git clone or
    there's no network."""
    root = os.path.dirname(os.path.abspath(__file__))
    status, detail = check_for_update(root)
    if status != "update_available":
        return

    prompt_root = tk.Tk()
    prompt_root.withdraw()
    do_update = messagebox.askyesno(
        "Update available",
        f"A new version is available ({detail} commit(s) behind).\nUpdate now?",
        parent=prompt_root,
    )
    if do_update:
        ok, msg = apply_update(root)
        if ok:
            messagebox.showinfo("Updated", "Updated successfully. Please restart the app.", parent=prompt_root)
            prompt_root.destroy()
            sys.exit(0)
        messagebox.showwarning(
            "Update failed", f"Could not update ({msg}). Continuing with the current version.", parent=prompt_root
        )
    prompt_root.destroy()


if __name__ == "__main__":
    _offer_update()
    App().mainloop()
