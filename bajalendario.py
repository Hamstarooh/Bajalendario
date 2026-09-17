"""Bajalendario - Dutch maternity/parental leave planner.

Desktop app (Tkinter, no external dependencies) to mark leave days for Mother
and Father on a calendar, see how many days/weeks have been used against the
Dutch legal limits (paid vs. unpaid, and the deadlines by which each type must
be used), and export the plan to share with HR.

Run with:  python bajalendario.py
Data is saved automatically to bajalendario_data.json, next to this file.
"""

import calendar
import csv
import datetime
import html
import json
import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bajalendario_data.json")

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]

# Leave types under Dutch law (indicative values - always double-check your
# exact entitlement with your employer / the UWV).
#
# "weeks" is the legal entitlement, used together with the person's working
# days/week setting to compute a hard day limit that the app will not let you
# exceed. "deadline" is (unit, amount): how long after the estimated due date
# (used as a stand-in for the birth date) the leave must be used by - the app
# blocks any day placed after that date. None means no deadline is enforced.
LEAVE_TYPES = {
    "MAMA_ZWANGER": {
        "label": "Pregnancy & Maternity Leave",
        "short": "Preg/Mat",
        "person": "mama",
        "color": "#f8bbd0",
        "weeks": 16,
        "paid": "100% (employer/UWV)",
        "deadline": None,
        "info": "Zwangerschaps- en bevallingsverlof: 16 weeks in total "
                "(up to 6 weeks before the due date, at least 10 weeks after), paid 100% by the UWV.",
    },
    "MAMA_PARENTAL_PAID": {
        "label": "Parental Leave - Paid (Mother)",
        "short": "Par.Paid",
        "person": "mama",
        "color": "#f06292",
        "weeks": 9,
        "paid": "70% (UWV)",
        "deadline": ("years", 1),
        "info": "Ouderschapsverlof, first 9 weeks: paid at 70% by the UWV, but only if taken "
                "before the child's 1st birthday. After that they become unpaid.",
    },
    "MAMA_PARENTAL_UNPAID": {
        "label": "Parental Leave - Unpaid (Mother)",
        "short": "Par.Unpd",
        "person": "mama",
        "color": "#880e4f",
        "weeks": 17,
        "paid": "Unpaid",
        "deadline": ("years", 8),
        "info": "Ouderschapsverlof, remaining 17 weeks: unpaid (unless your employer offers "
                "extra pay). Can be used until the child turns 8.",
    },
    "PAPA_GEBOORTE": {
        "label": "Birth Leave (1st week)",
        "short": "Birth",
        "person": "papa",
        "color": "#bbdefb",
        "weeks": 1,
        "paid": "100% (employer)",
        "deadline": ("weeks", 4),
        "info": "Geboorteverlof: 1 week, paid 100% by the employer. "
                "Must be taken within the first 4 weeks after birth.",
    },
    "PAPA_AANVULLEND": {
        "label": "Additional Partner Leave",
        "short": "Extra",
        "person": "papa",
        "color": "#42a5f5",
        "weeks": 5,
        "paid": "70% (UWV)",
        "deadline": ("months", 6),
        "info": "Aanvullend geboorteverlof: up to 5 more weeks, paid at 70% (UWV). "
                "Must be taken within the first 6 months of the baby's life.",
    },
    "PAPA_PARENTAL_PAID": {
        "label": "Parental Leave - Paid (Father)",
        "short": "Par.Paid",
        "person": "papa",
        "color": "#1976d2",
        "weeks": 9,
        "paid": "70% (UWV)",
        "deadline": ("years", 1),
        "info": "Ouderschapsverlof, first 9 weeks: paid at 70% by the UWV, but only if taken "
                "before the child's 1st birthday. After that they become unpaid.",
    },
    "PAPA_PARENTAL_UNPAID": {
        "label": "Parental Leave - Unpaid (Father)",
        "short": "Par.Unpd",
        "person": "papa",
        "color": "#0d47a1",
        "weeks": 17,
        "paid": "Unpaid",
        "deadline": ("years", 8),
        "info": "Ouderschapsverlof, remaining 17 weeks: unpaid (unless your employer offers "
                "extra pay). Can be used until the child turns 8.",
    },
}

# Old (pre-split) keys, kept so a data file saved by an earlier version of the
# app still loads instead of crashing.
LEGACY_KEY_MAP = {
    "MAMA_PARENTAL": "MAMA_PARENTAL_UNPAID",
    "PAPA_PARENTAL": "PAPA_PARENTAL_UNPAID",
}

PERSON_LABELS = {"mama": "Mother", "papa": "Father"}
CLEAR_LABEL = "(Clear this person's leave)"

EMPTY_COLOR = "#f5f5f5"
OUT_OF_MONTH_COLOR = "#e0e0e0"
TODAY_BORDER = "#ff7043"
DUE_DATE_BORDER = "#8e24aa"


def dark_text_for(bg_color):
    """Return black/white text color that reads well on top of bg_color."""
    bg_color = bg_color.lstrip("#")
    r, g, b = (int(bg_color[i:i + 2], 16) for i in (0, 2, 4))
    brightness = (r * 299 + g * 587 + b * 114) / 1000
    return "#000000" if brightness > 150 else "#ffffff"


def add_months(d, months):
    month_index = d.month - 1 + months
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return datetime.date(year, month, day)


def add_years(d, years):
    try:
        return d.replace(year=d.year + years)
    except ValueError:
        # 29 Feb on a birth year that isn't a leap year N years later
        return d.replace(month=2, day=28, year=d.year + years)


def parse_date(raw):
    return datetime.datetime.strptime(raw.strip(), "%d/%m/%Y").date()


class ToolTip:
    """Small info box that appears when hovering over a widget.

    `text_provider` can be a fixed string or a zero-argument callable that
    returns the text to show at that moment (or None to show nothing).
    """

    def __init__(self, widget, text_provider, delay=450):
        self.widget = widget
        self.text_provider = text_provider
        self.delay = delay
        self.after_id = None
        self.tipwindow = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, event=None):
        self._unschedule()
        self.after_id = self.widget.after(self.delay, self._show)

    def _unschedule(self):
        if self.after_id:
            self.widget.after_cancel(self.after_id)
            self.after_id = None

    def _show(self):
        text = self.text_provider() if callable(self.text_provider) else self.text_provider
        if not text or self.tipwindow:
            return
        x = self.widget.winfo_rootx() + 12
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        try:
            tw.wm_attributes("-topmost", True)
        except tk.TclError:
            pass
        tw.wm_geometry(f"+{x}+{y}")
        tk.Label(
            tw, text=text, justify="left", background="#ffffe0", relief="solid",
            borderwidth=1, font=("Segoe UI", 9), wraplength=320, padx=6, pady=4,
        ).pack()

    def _hide(self, event=None):
        self._unschedule()
        if self.tipwindow:
            self.tipwindow.destroy()
            self.tipwindow = None


class RangeEditor(tk.Toplevel):
    """Dialog to mark (or clear) a whole date range at once for one person/leave type."""

    def __init__(self, app, on_add, initial_person=None, initial_start=None, default_weekdays_only=True):
        super().__init__(app)
        self.app = app
        self.title("Add leave period")
        self.resizable(False, False)
        self.transient(app)
        self.grab_set()

        self.on_add = on_add
        self.type_by_label = {}

        frm = ttk.Frame(self, padding=12)
        frm.grid(row=0, column=0, sticky="nsew")

        ttk.Label(frm, text="Person:").grid(row=0, column=0, sticky="w", pady=4)
        self.person_var = tk.StringVar(value=initial_person or "Mother")
        person_combo = ttk.Combobox(frm, textvariable=self.person_var, values=["Mother", "Father"],
                                     state="readonly", width=34)
        person_combo.grid(row=0, column=1, pady=4, padx=6)
        person_combo.bind("<<ComboboxSelected>>", self._update_type_options)

        ttk.Label(frm, text="Leave type:").grid(row=1, column=0, sticky="w", pady=4)
        self.type_var = tk.StringVar()
        self.type_combo = ttk.Combobox(frm, textvariable=self.type_var, state="readonly", width=34)
        self.type_combo.grid(row=1, column=1, pady=4, padx=6)
        self.type_combo.bind("<<ComboboxSelected>>", self._on_type_change)

        ttk.Label(frm, text="Start date (dd/mm/yyyy):").grid(row=2, column=0, sticky="w", pady=4)
        start_text = initial_start.strftime("%d/%m/%Y") if initial_start else ""
        self.start_var = tk.StringVar(value=start_text)
        ttk.Entry(frm, textvariable=self.start_var, width=14).grid(row=2, column=1, pady=4, padx=6, sticky="w")

        ttk.Label(frm, text="End date (dd/mm/yyyy):").grid(row=3, column=0, sticky="w", pady=4)
        end_frame = ttk.Frame(frm)
        end_frame.grid(row=3, column=1, pady=4, padx=6, sticky="w")
        self.end_var = tk.StringVar(value=start_text)
        ttk.Entry(end_frame, textvariable=self.end_var, width=14).pack(side="left")
        add_week_btn = ttk.Button(end_frame, text="+1 week", width=8, command=self._add_week)
        add_week_btn.pack(side="left", padx=(6, 0))
        ToolTip(add_week_btn, "Extends the end date by 7 days each time you click it - "
                               "handy for adding whole weeks quickly.")

        self.weekdays_only_var = tk.BooleanVar(value=default_weekdays_only)
        self.weekdays_chk = ttk.Checkbutton(
            frm, text="Only mark working days (uses the working days/week setting)",
            variable=self.weekdays_only_var,
        )
        self.weekdays_chk.grid(row=4, column=0, columnspan=2, sticky="w", pady=(2, 4))

        self.weeks_left_var = tk.StringVar(value="")
        ttk.Label(frm, textvariable=self.weeks_left_var, foreground="#555555",
                  wraplength=360, justify="left").grid(row=5, column=0, columnspan=2, sticky="w", pady=(0, 8))

        btns = ttk.Frame(frm)
        btns.grid(row=6, column=0, columnspan=2, sticky="e")
        ttk.Button(btns, text="Cancel", command=self.destroy).pack(side="right", padx=4)
        ttk.Button(btns, text="Add", command=self._add).pack(side="right", padx=4)

        self.bind("<Return>", lambda e: self._add())
        self.bind("<Escape>", lambda e: self.destroy())

        self._update_type_options()

    def _update_type_options(self, event=None):
        person_key = "mama" if self.person_var.get() == "Mother" else "papa"
        self.type_by_label = {v["label"]: k for k, v in LEAVE_TYPES.items() if v["person"] == person_key}
        labels = list(self.type_by_label.keys()) + [CLEAR_LABEL]
        self.type_by_label[CLEAR_LABEL] = "__CLEAR__"
        self.type_combo.config(values=labels)
        if self.type_var.get() not in labels:
            self.type_var.set(labels[0])
        self._on_type_change()

    def _on_type_change(self, event=None):
        type_key = self.type_by_label.get(self.type_var.get())
        self.weekdays_chk.config(state="disabled" if type_key == "__CLEAR__" else "normal")
        self._update_weeks_left()

    def _update_weeks_left(self):
        type_key = self.type_by_label.get(self.type_var.get())
        if not type_key or type_key == "__CLEAR__":
            self.weeks_left_var.set("")
            return
        info = LEAVE_TYPES[type_key]
        working_days = self.app._working_days_for(info["person"])
        limit_days = info["weeks"] * working_days
        used_days = self.app._count_type_excluding(type_key, set())
        remaining_days = max(0, limit_days - used_days)
        remaining_weeks = remaining_days / working_days if working_days else 0
        text = (f"{remaining_weeks:.1f} of {info['weeks']} week(s) left for this leave type "
                f"({remaining_days} of {limit_days} working days).")
        deadline = self.app._deadline_for(type_key)
        if deadline:
            text += f" Must be used by {deadline.strftime('%d/%m/%Y')}."
        self.weeks_left_var.set(text)

    def _add_week(self):
        try:
            start = parse_date(self.start_var.get())
        except ValueError:
            messagebox.showerror("Bajalendario", "Enter a valid start date first.", parent=self)
            return
        try:
            current_end = parse_date(self.end_var.get())
        except ValueError:
            current_end = start - datetime.timedelta(days=1)
        new_end = current_end + datetime.timedelta(days=7)
        self.end_var.set(new_end.strftime("%d/%m/%Y"))

    def _add(self):
        try:
            start = parse_date(self.start_var.get())
            end = parse_date(self.end_var.get())
        except ValueError:
            messagebox.showerror("Bajalendario", "Enter both dates as dd/mm/yyyy.", parent=self)
            return
        if start > end:
            messagebox.showerror("Bajalendario", "The start date must not be after the end date.", parent=self)
            return

        type_key = self.type_by_label.get(self.type_var.get())
        if not type_key:
            messagebox.showerror("Bajalendario", "Choose a leave type.", parent=self)
            return

        person_key = "mama" if self.person_var.get() == "Mother" else "papa"
        self.on_add(person_key, type_key, start, end, self.weekdays_only_var.get())
        self.destroy()


class FillDayEditor(tk.Toplevel):
    """Dialog to mark a recurring weekday pattern (e.g. every Friday) from a date onward."""

    WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    def __init__(self, app, person, on_fill):
        super().__init__(app)
        self.app = app
        self.person = person
        self.on_fill = on_fill
        self.title(f"Fill {PERSON_LABELS[person]} Day(s)")
        self.resizable(False, False)
        self.transient(app)
        self.grab_set()

        self.type_by_label = {v["label"]: k for k, v in LEAVE_TYPES.items() if v["person"] == person}

        frm = ttk.Frame(self, padding=12)
        frm.grid(row=0, column=0, sticky="nsew")

        ttk.Label(frm, text="Leave type:").grid(row=0, column=0, sticky="w", pady=4)
        self.type_var = tk.StringVar(value=next(iter(self.type_by_label)))
        type_combo = ttk.Combobox(frm, textvariable=self.type_var, values=list(self.type_by_label.keys()),
                                   state="readonly", width=34)
        type_combo.grid(row=0, column=1, columnspan=2, pady=4, padx=6, sticky="w")
        type_combo.bind("<<ComboboxSelected>>", lambda e: self._update_weeks_left())

        ttk.Label(frm, text="Repeat on:").grid(row=1, column=0, sticky="nw", pady=4)
        days_frame = ttk.Frame(frm)
        days_frame.grid(row=1, column=1, columnspan=2, sticky="w", pady=4)
        self.weekday_vars = []
        for i, name in enumerate(self.WEEKDAY_NAMES):
            var = tk.BooleanVar(value=(i == 4))  # Friday checked by default (classic "papadag")
            ttk.Checkbutton(days_frame, text=name[:3], variable=var).grid(row=0, column=i, padx=2)
            self.weekday_vars.append(var)

        ttk.Label(frm, text="Start date (dd/mm/yyyy):").grid(row=2, column=0, sticky="w", pady=4)
        self.start_var = tk.StringVar()
        ttk.Entry(frm, textvariable=self.start_var, width=14).grid(row=2, column=1, pady=4, padx=6, sticky="w")

        ttk.Label(frm, text="End date (optional):").grid(row=3, column=0, sticky="w", pady=4)
        self.end_var = tk.StringVar()
        end_entry = ttk.Entry(frm, textvariable=self.end_var, width=14)
        end_entry.grid(row=3, column=1, pady=4, padx=6, sticky="w")
        ToolTip(end_entry, "Leave empty to fill automatically until the legal limit or the "
                            "deadline for this leave type is reached.")

        self.weeks_left_var = tk.StringVar(value="")
        ttk.Label(frm, textvariable=self.weeks_left_var, foreground="#555555",
                  wraplength=380, justify="left").grid(row=4, column=0, columnspan=3, sticky="w", pady=(4, 8))

        btns = ttk.Frame(frm)
        btns.grid(row=5, column=0, columnspan=3, sticky="e")
        ttk.Button(btns, text="Cancel", command=self.destroy).pack(side="right", padx=4)
        ttk.Button(btns, text="Fill", command=self._fill).pack(side="right", padx=4)

        self.bind("<Return>", lambda e: self._fill())
        self.bind("<Escape>", lambda e: self.destroy())

        self._update_weeks_left()

    def _update_weeks_left(self):
        type_key = self.type_by_label.get(self.type_var.get())
        if not type_key:
            self.weeks_left_var.set("")
            return
        info = LEAVE_TYPES[type_key]
        working_days = self.app._working_days_for(self.person)
        limit_days = info["weeks"] * working_days
        used_days = self.app._count_type_excluding(type_key, set())
        remaining_days = max(0, limit_days - used_days)
        remaining_weeks = remaining_days / working_days if working_days else 0
        text = (f"{remaining_weeks:.1f} of {info['weeks']} week(s) left for this leave type "
                f"({remaining_days} of {limit_days} working days).")
        deadline = self.app._deadline_for(type_key)
        if deadline:
            text += f" Must be used by {deadline.strftime('%d/%m/%Y')}."
        self.weeks_left_var.set(text)

    def _fill(self):
        try:
            start = parse_date(self.start_var.get())
        except ValueError:
            messagebox.showerror("Bajalendario", "Enter a valid start date (dd/mm/yyyy).", parent=self)
            return

        end = None
        raw_end = self.end_var.get().strip()
        if raw_end:
            try:
                end = parse_date(raw_end)
            except ValueError:
                messagebox.showerror("Bajalendario", "Enter a valid end date (dd/mm/yyyy) or leave it empty.",
                                      parent=self)
                return
            if end < start:
                messagebox.showerror("Bajalendario", "The end date must not be before the start date.", parent=self)
                return

        weekdays = {i for i, var in enumerate(self.weekday_vars) if var.get()}
        if not weekdays:
            messagebox.showerror("Bajalendario", "Select at least one day of the week.", parent=self)
            return

        type_key = self.type_by_label.get(self.type_var.get())
        if not type_key:
            messagebox.showerror("Bajalendario", "Choose a leave type.", parent=self)
            return

        self.on_fill(self.person, type_key, start, end, weekdays)
        self.destroy()


class BajalendarioApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Bajalendario - Leave Planner")
        self.geometry("1200x840")
        self.minsize(1040, 720)

        today = datetime.date.today()
        self.current_year = today.year
        self.current_month = today.month
        self._cached_due_date = None

        self.data = self._load_data()

        self._build_menu()
        self._build_top_bar()
        self._build_settings_bar()
        self._build_preload_bar()
        self._build_quickfill_bar()
        self._build_calendar_area()
        self._build_summary_area()

        self.render_month()
        self.update_summary()

    # ---------- Persistence ----------

    def _load_data(self):
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                data.setdefault("leaves", {})
                data.setdefault("settings", {})
                data["settings"].setdefault("working_days_mama", 5)
                data["settings"].setdefault("working_days_papa", 5)
                data["settings"].setdefault("due_date", "")
                data["settings"].setdefault("weeks_before_due", 4)
                self._migrate_legacy_keys(data)
                return data
            except (json.JSONDecodeError, OSError):
                messagebox.showwarning(
                    "Bajalendario",
                    "Could not read the existing data file; starting from scratch.",
                )
        return {
            "leaves": {},
            "settings": {
                "working_days_mama": 5,
                "working_days_papa": 5,
                "due_date": "",
                "weeks_before_due": 4,
            },
        }

    @staticmethod
    def _migrate_legacy_keys(data):
        for entry in data["leaves"].values():
            for person in ("mama", "papa"):
                key = entry.get(person)
                if key in LEGACY_KEY_MAP:
                    entry[person] = LEGACY_KEY_MAP[key]

    def _save_data(self):
        try:
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except OSError as exc:
            messagebox.showerror("Bajalendario", f"Could not save the data:\n{exc}")

    # ---------- UI construction ----------

    def _build_menu(self):
        menubar = tk.Menu(self)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Add leave period...", command=self._open_range_editor)
        file_menu.add_command(label="Fill Mother's day(s)...", command=lambda: self._open_fill_editor("mama"))
        file_menu.add_command(label="Fill Father's day(s)...", command=lambda: self._open_fill_editor("papa"))
        file_menu.add_separator()
        file_menu.add_command(label="Export leave plan for HR...", command=self._export_plan)
        file_menu.add_separator()
        file_menu.add_command(label="Reset all leave days...", command=self._reset_leaves)
        menubar.add_cascade(label="File", menu=file_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="About leave types", command=self._show_help)
        menubar.add_cascade(label="Help", menu=help_menu)

        self.config(menu=menubar)

    def _build_top_bar(self):
        bar = ttk.Frame(self, padding=(10, 8))
        bar.pack(side="top", fill="x")

        ttk.Button(bar, text="◀", width=3, command=self.prev_month).pack(side="left")
        self.month_label = ttk.Label(bar, text="", font=("Segoe UI", 14, "bold"), width=15, anchor="center")
        self.month_label.pack(side="left", padx=10)
        ttk.Button(bar, text="▶", width=3, command=self.next_month).pack(side="left")
        ttk.Button(bar, text="Today", command=self.goto_today).pack(side="left", padx=(12, 0))

        range_btn = ttk.Button(bar, text="Add leave period...", command=self._open_range_editor)
        range_btn.pack(side="left", padx=(12, 0))
        ToolTip(range_btn, "Mark a whole date range at once for one person and leave type. "
                            "Tip: clicking any day in the calendar opens this dialog pre-filled "
                            "with that day.")

        export_btn = ttk.Button(bar, text="Export for HR...", command=self._export_plan)
        export_btn.pack(side="left", padx=(8, 0))
        ToolTip(export_btn, "Export the current leave plan as an HTML report or CSV file, "
                             "ready to share with HR.")

        reset_btn = ttk.Button(bar, text="Reset leaves...", command=self._reset_leaves)
        reset_btn.pack(side="left", padx=(8, 0))
        ToolTip(reset_btn, "Removes ALL marked leave days for both Mother and Father. "
                            "Settings (working days, due date) are kept. Asks for confirmation first.")

        jump = ttk.Frame(bar)
        jump.pack(side="right")
        ttk.Label(jump, text="Jump to month/year:").pack(side="left", padx=(0, 4))
        self.jump_month_var = tk.StringVar(value=str(self.current_month))
        self.jump_year_var = tk.StringVar(value=str(self.current_year))
        ttk.Spinbox(jump, from_=1, to=12, width=3, textvariable=self.jump_month_var).pack(side="left")
        ttk.Spinbox(jump, from_=2020, to=2040, width=6, textvariable=self.jump_year_var).pack(side="left", padx=4)
        ttk.Button(jump, text="Go", command=self._jump_to).pack(side="left")

    def _build_settings_bar(self):
        bar = ttk.Frame(self, padding=(10, 0, 10, 8))
        bar.pack(side="top", fill="x")

        ttk.Label(bar, text="Working days/week — Mother:").pack(side="left")
        self.wd_mama_var = tk.StringVar(value=str(self.data["settings"]["working_days_mama"]))
        wd_mama = ttk.Spinbox(bar, from_=1, to=7, width=3, textvariable=self.wd_mama_var,
                               command=self._on_working_days_change)
        wd_mama.pack(side="left", padx=(4, 16))
        wd_mama.bind("<FocusOut>", lambda e: self._on_working_days_change())

        ttk.Label(bar, text="Father:").pack(side="left")
        self.wd_papa_var = tk.StringVar(value=str(self.data["settings"]["working_days_papa"]))
        wd_papa = ttk.Spinbox(bar, from_=1, to=7, width=3, textvariable=self.wd_papa_var,
                               command=self._on_working_days_change)
        wd_papa.pack(side="left", padx=4)
        wd_papa.bind("<FocusOut>", lambda e: self._on_working_days_change())

        # Legend (hover for details, incl. remaining days and deadline)
        legend = ttk.Frame(bar)
        legend.pack(side="right")
        for key, info in LEAVE_TYPES.items():
            chip = tk.Label(legend, text=info["short"], bg=info["color"], fg=dark_text_for(info["color"]),
                             padx=6, pady=1, font=("Segoe UI", 8))
            chip.pack(side="left", padx=3)
            ToolTip(chip, (lambda k=key: self._info_tooltip_text(k)))

    def _build_preload_bar(self):
        bar = ttk.Frame(self, padding=(10, 0, 10, 8))
        bar.pack(side="top", fill="x")

        ttk.Label(bar, text="Estimated due date (dd/mm/yyyy):").pack(side="left")
        self.due_date_var = tk.StringVar(value=self.data["settings"].get("due_date", ""))
        due_entry = ttk.Entry(bar, textvariable=self.due_date_var, width=12)
        due_entry.pack(side="left", padx=(4, 16))
        due_entry.bind("<FocusOut>", lambda e: self._on_due_date_change())
        ToolTip(due_entry, "Used as the reference birth date for all deadlines, and highlighted "
                            "with a purple border on the calendar.")

        ttk.Label(bar, text="Weeks before due date:").pack(side="left")
        self.weeks_before_var = tk.StringVar(value=str(self.data["settings"].get("weeks_before_due", 4)))
        wb_spin = ttk.Spinbox(bar, from_=4, to=6, width=3, textvariable=self.weeks_before_var)
        wb_spin.pack(side="left", padx=(4, 16))
        ToolTip(wb_spin, "How many weeks before the due date the mother wants to start her leave "
                          "(by law, between 4 and 6 weeks before).")

        preload_btn = ttk.Button(bar, text="Preload Mother's leave", command=self._preload_mama)
        preload_btn.pack(side="left")
        ToolTip(preload_btn, "Automatically marks the 16 weeks of Pregnancy & Maternity Leave "
                              "on the calendar, starting from the estimated due date.\n"
                              "Does not overwrite days that already have a leave type set for the mother.")

    def _build_quickfill_bar(self):
        bar = ttk.Frame(self, padding=(10, 0, 10, 8))
        bar.pack(side="top", fill="x")

        ttk.Label(bar, text="Quick fill a weekly pattern (e.g. \"every Friday\"):").pack(side="left")

        fill_mama_btn = ttk.Button(bar, text="Fill Mother Day(s)...", command=lambda: self._open_fill_editor("mama"))
        fill_mama_btn.pack(side="left", padx=(8, 4))
        ToolTip(fill_mama_btn, "Automatically mark specific weekdays (e.g. every Thursday and "
                                "Friday) from a start date onward, using the leave type you choose.")

        fill_papa_btn = ttk.Button(bar, text="Fill Father Day(s)...", command=lambda: self._open_fill_editor("papa"))
        fill_papa_btn.pack(side="left", padx=4)
        ToolTip(fill_papa_btn, "Automatically mark specific weekdays (e.g. every Friday) from a "
                                "start date onward, using the leave type you choose. Stops on its "
                                "own once the legal limit or deadline is reached.")

    def _build_calendar_area(self):
        self.cal_frame = ttk.Frame(self, padding=(10, 0, 10, 10))
        self.cal_frame.pack(side="top", fill="both", expand=True)

        for c in range(7):
            self.cal_frame.columnconfigure(c, weight=1, uniform="col")
        for r in range(7):
            self.cal_frame.rowconfigure(r, weight=1)

        for c, name in enumerate(WEEKDAYS):
            ttk.Label(self.cal_frame, text=name, anchor="center", font=("Segoe UI", 9, "bold")).grid(
                row=0, column=c, sticky="nsew", pady=(0, 4)
            )

        self.day_cells = []  # list of cell widget-dicts, up to 6 rows x 7 columns
        for r in range(1, 7):
            row_cells = []
            for c in range(7):
                cell = self._make_day_cell(r, c)
                row_cells.append(cell)
            self.day_cells.append(row_cells)

    def _make_day_cell(self, row, col):
        outer = tk.Frame(self.cal_frame, bg=EMPTY_COLOR, highlightthickness=1, highlightbackground="#cfcfcf")
        outer.grid(row=row, column=col, sticky="nsew", padx=2, pady=2)

        day_num_lbl = tk.Label(outer, text="", bg=EMPTY_COLOR, anchor="e", font=("Segoe UI", 9))
        day_num_lbl.pack(side="top", fill="x", padx=4, pady=(2, 0))

        mama_lbl = tk.Label(outer, text=" ", anchor="center", font=("Segoe UI", 8), bg=EMPTY_COLOR)
        mama_lbl.pack(side="top", fill="x", padx=4, pady=1)

        papa_lbl = tk.Label(outer, text=" ", anchor="center", font=("Segoe UI", 8), bg=EMPTY_COLOR)
        papa_lbl.pack(side="top", fill="x", padx=4, pady=(1, 3))

        widgets = {
            "outer": outer, "num": day_num_lbl, "mama": mama_lbl, "papa": papa_lbl,
            "date": None, "mama_key": None, "papa_key": None,
        }

        for w in (outer, day_num_lbl, mama_lbl, papa_lbl):
            w.bind("<Button-1>", lambda e, cell=widgets: self._on_day_click(cell))

        def mama_tip(cell=widgets):
            key = cell.get("mama_key")
            return self._info_tooltip_text(key) if key else None

        def papa_tip(cell=widgets):
            key = cell.get("papa_key")
            return self._info_tooltip_text(key) if key else None

        def num_tip(cell=widgets):
            d = cell.get("date")
            if d is not None and self._cached_due_date is not None and d == self._cached_due_date:
                return "Estimated due date"
            return None

        ToolTip(mama_lbl, mama_tip)
        ToolTip(papa_lbl, papa_tip)
        ToolTip(day_num_lbl, num_tip)

        return widgets

    def _build_summary_area(self):
        self.summary_frame = ttk.LabelFrame(self, text="Leave days summary", padding=10)
        self.summary_frame.pack(side="bottom", fill="x", padx=10, pady=(0, 10))

        self.summary_rows = {}
        for i, (key, info) in enumerate(LEAVE_TYPES.items()):
            row = ttk.Frame(self.summary_frame)
            row.pack(side="top", fill="x", pady=1)

            chip = tk.Label(row, text=info["label"], bg=info["color"], fg=dark_text_for(info["color"]),
                             width=30, anchor="w", padx=6, pady=2)
            chip.pack(side="left")

            pbar = ttk.Progressbar(row, length=220, maximum=100)
            pbar.pack(side="left", padx=10)

            value_lbl = ttk.Label(row, text="", width=42, anchor="w")
            value_lbl.pack(side="left")

            first_btn = ttk.Button(row, text="First day", width=9, command=lambda k=key: self._goto_first(k))
            first_btn.pack(side="left", padx=(6, 2))
            ToolTip(first_btn, "Jump the calendar to the first marked day of this leave type.")

            last_btn = ttk.Button(row, text="Last day", width=9, command=lambda k=key: self._goto_last(k))
            last_btn.pack(side="left", padx=2)
            ToolTip(last_btn, "Jump the calendar to the last marked day of this leave type.")

            reset_btn = ttk.Button(row, text="Reset", width=7, command=lambda k=key: self._reset_type(k))
            reset_btn.pack(side="left", padx=(2, 0))
            ToolTip(reset_btn, "Clears every day marked with this specific leave type. "
                                "Other leave types are left untouched. Asks for confirmation first.")

            self.summary_rows[key] = {"bar": pbar, "label": value_lbl}

    # ---------- Navigation ----------

    def prev_month(self):
        self.current_month -= 1
        if self.current_month == 0:
            self.current_month = 12
            self.current_year -= 1
        self.render_month()

    def next_month(self):
        self.current_month += 1
        if self.current_month == 13:
            self.current_month = 1
            self.current_year += 1
        self.render_month()

    def goto_today(self):
        today = datetime.date.today()
        self.current_year, self.current_month = today.year, today.month
        self.render_month()

    def _goto_date(self, date_obj):
        self.current_year, self.current_month = date_obj.year, date_obj.month
        self.render_month()

    def _type_date_bounds(self, type_key):
        person = LEAVE_TYPES[type_key]["person"]
        dates = [datetime.date.fromisoformat(iso) for iso, e in self.data["leaves"].items() if e.get(person) == type_key]
        if not dates:
            return None, None
        return min(dates), max(dates)

    def _goto_first(self, type_key):
        first, _ = self._type_date_bounds(type_key)
        if first is None:
            messagebox.showinfo("Bajalendario", "No days marked for this leave type yet.")
            return
        self._goto_date(first)

    def _goto_last(self, type_key):
        _, last = self._type_date_bounds(type_key)
        if last is None:
            messagebox.showinfo("Bajalendario", "No days marked for this leave type yet.")
            return
        self._goto_date(last)

    def _jump_to(self):
        try:
            month = int(self.jump_month_var.get())
            year = int(self.jump_year_var.get())
            if not (1 <= month <= 12):
                raise ValueError
        except ValueError:
            messagebox.showerror("Bajalendario", "Invalid month or year.")
            return
        self.current_month, self.current_year = month, year
        self.render_month()

    # ---------- Settings ----------

    def _on_working_days_change(self):
        try:
            wd_mama = max(1, min(7, int(self.wd_mama_var.get())))
            wd_papa = max(1, min(7, int(self.wd_papa_var.get())))
        except ValueError:
            return
        self.data["settings"]["working_days_mama"] = wd_mama
        self.data["settings"]["working_days_papa"] = wd_papa
        self._save_data()
        self.update_summary()

    def _on_due_date_change(self):
        raw = self.due_date_var.get().strip()
        if raw:
            try:
                datetime.datetime.strptime(raw, "%d/%m/%Y")
            except ValueError:
                return  # leave the stored value untouched until it's a valid date
        self.data["settings"]["due_date"] = raw
        self._save_data()
        self.render_month()
        self.update_summary()

    def _working_days_for(self, person):
        return self.data["settings"]["working_days_mama"] if person == "mama" else self.data["settings"]["working_days_papa"]

    def _preload_mama(self):
        raw = self.due_date_var.get().strip()
        try:
            due_date = parse_date(raw)
        except ValueError:
            messagebox.showerror("Bajalendario", "Enter the estimated due date as dd/mm/yyyy.")
            return

        try:
            weeks_before = int(self.weeks_before_var.get())
        except ValueError:
            weeks_before = 4
        weeks_before = max(4, min(6, weeks_before))
        self.weeks_before_var.set(str(weeks_before))

        self.data["settings"]["due_date"] = raw
        self.data["settings"]["weeks_before_due"] = weeks_before

        total_weeks = LEAVE_TYPES["MAMA_ZWANGER"]["weeks"]
        working_days = self.data["settings"]["working_days_mama"]
        start_date = due_date - datetime.timedelta(weeks=weeks_before)
        end_date = start_date + datetime.timedelta(days=total_weeks * 7 - 1)

        marked = 0
        skipped = 0
        d = start_date
        while d <= end_date:
            if d.weekday() < working_days:
                iso = d.isoformat()
                entry = self.data["leaves"].get(iso, {"mama": None, "papa": None})
                if entry.get("mama"):
                    skipped += 1
                else:
                    entry["mama"] = "MAMA_ZWANGER"
                    self.data["leaves"][iso] = entry
                    marked += 1
            d += datetime.timedelta(days=1)

        self._save_data()
        self.current_year, self.current_month = start_date.year, start_date.month
        self.render_month()
        self.update_summary()

        msg = (
            f"Pregnancy & Maternity Leave preloaded from {start_date.strftime('%d/%m/%Y')} "
            f"to {end_date.strftime('%d/%m/%Y')} ({total_weeks} weeks, {marked} working days marked)."
        )
        if skipped:
            msg += f"\n{skipped} day(s) were left untouched because they already had a leave type set for the mother."
        messagebox.showinfo("Bajalendario", msg)

    # ---------- Reset ----------

    def _reset_type(self, type_key):
        info = LEAVE_TYPES[type_key]
        person = info["person"]
        isos_to_clear = [iso for iso, entry in self.data["leaves"].items() if entry.get(person) == type_key]

        if not isos_to_clear:
            messagebox.showinfo("Bajalendario", f"There are no days marked for {info['label']}.")
            return

        confirmed = messagebox.askyesno(
            "Bajalendario",
            f"This will clear all {len(isos_to_clear)} day(s) marked as {info['label']} "
            f"({PERSON_LABELS[person]}). Other leave types are not affected.\n\nThis cannot be undone. Continue?",
            icon="warning",
        )
        if not confirmed:
            return

        for iso in isos_to_clear:
            entry = self.data["leaves"][iso]
            entry[person] = None
            if not entry.get("mama") and not entry.get("papa"):
                del self.data["leaves"][iso]

        self._save_data()
        self.render_month()
        self.update_summary()
        messagebox.showinfo("Bajalendario", f"Cleared {len(isos_to_clear)} day(s) of {info['label']}.")

    def _reset_leaves(self):
        if not self.data["leaves"]:
            messagebox.showinfo("Bajalendario", "There are no leave days to reset.")
            return
        confirmed = messagebox.askyesno(
            "Bajalendario",
            "This will remove ALL marked leave days for both Mother and Father.\n"
            "Settings (working days/week, due date) are kept.\n\nThis cannot be undone. Continue?",
            icon="warning",
        )
        if not confirmed:
            return
        self.data["leaves"] = {}
        self._save_data()
        self.render_month()
        self.update_summary()
        messagebox.showinfo("Bajalendario", "All leave days have been cleared.")

    # ---------- Adding a date range ----------

    def _open_range_editor(self):
        RangeEditor(self, self._on_range_add)

    def _on_day_click(self, cell):
        date_obj = cell["date"]
        if date_obj is None:
            return
        RangeEditor(self, self._on_range_add, initial_start=date_obj, default_weekdays_only=False)

    def _on_range_add(self, person, type_key, start, end, weekdays_only):
        if type_key == "__CLEAR__":
            self._clear_range(person, start, end)
            return

        working_days = self._working_days_for(person)
        dates = []
        d = start
        while d <= end:
            if not weekdays_only or d.weekday() < working_days:
                dates.append(d)
            d += datetime.timedelta(days=1)

        if not dates:
            messagebox.showinfo("Bajalendario", "No matching days were found in that range.")
            return

        ok, msg = self._validate_assignment(type_key, dates)
        if not ok:
            messagebox.showerror("Bajalendario", msg)
            return

        for d in dates:
            iso = d.isoformat()
            entry = self.data["leaves"].get(iso, {"mama": None, "papa": None})
            entry[person] = type_key
            self.data["leaves"][iso] = entry

        self._save_data()
        self.current_year, self.current_month = start.year, start.month
        self.render_month()
        self.update_summary()

        info = LEAVE_TYPES[type_key]
        messagebox.showinfo(
            "Bajalendario",
            f"Added {len(dates)} day(s) of {info['label']} for the "
            f"{PERSON_LABELS[person].lower()}, from {start.strftime('%d/%m/%Y')} to {end.strftime('%d/%m/%Y')}.",
        )

    def _clear_range(self, person, start, end):
        cleared = 0
        d = start
        while d <= end:
            iso = d.isoformat()
            entry = self.data["leaves"].get(iso)
            if entry and entry.get(person):
                entry[person] = None
                if not entry.get("mama") and not entry.get("papa"):
                    del self.data["leaves"][iso]
                cleared += 1
            d += datetime.timedelta(days=1)

        if cleared == 0:
            messagebox.showinfo("Bajalendario", "There was nothing to clear in that range.")
            return

        self._save_data()
        self.current_year, self.current_month = start.year, start.month
        self.render_month()
        self.update_summary()
        messagebox.showinfo(
            "Bajalendario",
            f"Cleared {cleared} day(s) for the {PERSON_LABELS[person].lower()}, "
            f"from {start.strftime('%d/%m/%Y')} to {end.strftime('%d/%m/%Y')}.",
        )

    # ---------- Filling a recurring weekday pattern ----------

    def _open_fill_editor(self, person):
        FillDayEditor(self, person, self._on_fill)

    def _on_fill(self, person, type_key, start, end, weekdays):
        info = LEAVE_TYPES[type_key]
        working_days = self._working_days_for(person)
        limit_days = info["weeks"] * working_days
        deadline = self._deadline_for(type_key)

        hard_end = end
        clipped_to_deadline = False
        if deadline is not None and (hard_end is None or hard_end > deadline):
            clipped_to_deadline = hard_end is not None
            hard_end = deadline
        if hard_end is None:
            hard_end = start + datetime.timedelta(days=365 * 10)  # safety cap: no end date, no deadline

        baseline = self._count_type_excluding(type_key, set())
        added = 0
        conflicts = 0
        first_added = None
        last_added = None
        stopped_for_limit = False

        d = start
        while d <= hard_end:
            if d.weekday() in weekdays:
                iso = d.isoformat()
                entry = self.data["leaves"].get(iso, {"mama": None, "papa": None})
                current = entry.get(person)
                if current == type_key:
                    pass
                elif current:
                    conflicts += 1
                else:
                    if baseline + added >= limit_days:
                        stopped_for_limit = True
                        break
                    entry[person] = type_key
                    self.data["leaves"][iso] = entry
                    added += 1
                    first_added = first_added or d
                    last_added = d
            d += datetime.timedelta(days=1)

        if added == 0:
            if conflicts:
                messagebox.showinfo(
                    "Bajalendario",
                    f"No days were added: all {conflicts} matching day(s) in that range already "
                    "have a different leave type set.",
                )
            elif baseline >= limit_days:
                messagebox.showinfo(
                    "Bajalendario",
                    f"No days were added: {info['label']} is already at its {limit_days}-day limit.",
                )
            else:
                messagebox.showinfo("Bajalendario", "No matching days were found in that range.")
            return

        self._save_data()
        self.current_year, self.current_month = start.year, start.month
        self.render_month()
        self.update_summary()

        weekday_names = ", ".join(WEEKDAYS[i] for i in sorted(weekdays))
        msg = (
            f"Added {added} day(s) ({weekday_names}) of {info['label']} for the "
            f"{PERSON_LABELS[person].lower()}, from {first_added.strftime('%d/%m/%Y')} "
            f"to {last_added.strftime('%d/%m/%Y')}."
        )
        if stopped_for_limit:
            msg += f"\nStopped because the {limit_days}-day limit for this leave type was reached."
        elif deadline is not None and (end is None or clipped_to_deadline):
            msg += f"\nStopped at the deadline for this leave type ({deadline.strftime('%d/%m/%Y')})."
        if conflicts:
            msg += f"\n{conflicts} day(s) were skipped because they already had a different leave type set."
        messagebox.showinfo("Bajalendario", msg)

    # ---------- Limit & deadline validation ----------

    def _deadline_for(self, type_key):
        raw = self.data["settings"].get("due_date", "").strip()
        if not raw:
            return None
        try:
            due_date = parse_date(raw)
        except ValueError:
            return None
        rule = LEAVE_TYPES[type_key].get("deadline")
        if not rule:
            return None
        unit, amount = rule
        if unit == "weeks":
            return due_date + datetime.timedelta(weeks=amount)
        if unit == "months":
            return add_months(due_date, amount)
        if unit == "years":
            return add_years(due_date, amount)
        return None

    def _count_type_excluding(self, type_key, excluded_isos):
        person = LEAVE_TYPES[type_key]["person"]
        count = 0
        for iso, entry in self.data["leaves"].items():
            if iso in excluded_isos:
                continue
            if entry.get(person) == type_key:
                count += 1
        return count

    def _validate_assignment(self, type_key, dates):
        """Check a proposed set of dates for type_key against the day limit and the deadline.

        `dates` are the calendar days that would end up marked as type_key
        once the change is applied (regardless of what they were before).
        Returns (True, "") if the change is allowed, otherwise (False, reason).
        """
        info = LEAVE_TYPES[type_key]
        working_days = self._working_days_for(info["person"])
        limit_days = info["weeks"] * working_days

        excluded_isos = {d.isoformat() for d in dates}
        other_count = self._count_type_excluding(type_key, excluded_isos)
        final_count = other_count + len(dates)

        if final_count > limit_days:
            remaining = max(0, limit_days - other_count)
            return False, (
                f"{info['label']} only allows {limit_days} working days ({info['weeks']} weeks). "
                f"{other_count} day(s) are already used, so at most {remaining} more can be added "
                f"(you're trying to add {len(dates)})."
            )

        deadline = self._deadline_for(type_key)
        if deadline:
            late_dates = sorted(d for d in dates if d > deadline)
            if late_dates:
                return False, (
                    f"{info['label']} must be used by {deadline.strftime('%d/%m/%Y')} "
                    f"(based on the estimated due date). {len(late_dates)} of the selected day(s) fall "
                    f"after that date, e.g. {late_dates[0].strftime('%d/%m/%Y')}."
                )

        return True, ""

    def _info_tooltip_text(self, type_key):
        info = LEAVE_TYPES[type_key]
        working_days = self._working_days_for(info["person"])
        limit_days = info["weeks"] * working_days
        used = self._count_type_excluding(type_key, set())

        text = f"{info['label']} ({PERSON_LABELS[info['person']]})\n{info['info']}"
        text += f"\nPay: {info['paid']}."
        text += f"\nLimit: {limit_days} working days ({info['weeks']} weeks) - {used} used so far."

        deadline = self._deadline_for(type_key)
        if deadline:
            text += f"\nMust be used by: {deadline.strftime('%d/%m/%Y')} (based on the due date)."
        return text

    # ---------- Calendar rendering ----------

    def render_month(self):
        self.month_label.config(text=f"{MONTHS[self.current_month - 1]} {self.current_year}")
        self.jump_month_var.set(str(self.current_month))
        self.jump_year_var.set(str(self.current_year))

        raw_due = self.data["settings"].get("due_date", "").strip()
        try:
            self._cached_due_date = parse_date(raw_due) if raw_due else None
        except ValueError:
            self._cached_due_date = None

        cal = calendar.Calendar(firstweekday=0)
        month_dates = list(cal.itermonthdates(self.current_year, self.current_month))
        # itermonthdates always returns full weeks (multiples of 7)
        weeks = [month_dates[i:i + 7] for i in range(0, len(month_dates), 7)]

        today = datetime.date.today()

        for r in range(6):
            for c in range(7):
                cell = self.day_cells[r][c]
                if r < len(weeks):
                    date_obj = weeks[r][c]
                else:
                    date_obj = None

                if date_obj is None:
                    cell["outer"].grid_remove()
                    continue
                cell["outer"].grid()

                in_month = date_obj.month == self.current_month
                cell["date"] = date_obj if in_month else None

                if not in_month:
                    cell["mama_key"] = None
                    cell["papa_key"] = None
                    self._paint_cell(cell, OUT_OF_MONTH_COLOR, "", "", "")
                    continue

                entry = self.data["leaves"].get(date_obj.isoformat(), {})
                mama_key = entry.get("mama")
                papa_key = entry.get("papa")
                cell["mama_key"] = mama_key
                cell["papa_key"] = papa_key

                mama_color = LEAVE_TYPES[mama_key]["color"] if mama_key in LEAVE_TYPES else EMPTY_COLOR
                mama_text = LEAVE_TYPES[mama_key]["short"] if mama_key in LEAVE_TYPES else ""
                papa_color = LEAVE_TYPES[papa_key]["color"] if papa_key in LEAVE_TYPES else EMPTY_COLOR
                papa_text = LEAVE_TYPES[papa_key]["short"] if papa_key in LEAVE_TYPES else ""

                is_due_date = self._cached_due_date is not None and date_obj == self._cached_due_date
                if is_due_date:
                    border, thickness = DUE_DATE_BORDER, 3
                elif date_obj == today:
                    border, thickness = TODAY_BORDER, 2
                else:
                    border, thickness = "#cfcfcf", 1
                cell["outer"].config(highlightbackground=border, highlightthickness=thickness)

                num_text = f"{date_obj.day} \U0001F476" if is_due_date else str(date_obj.day)
                cell["num"].config(text=num_text, bg=EMPTY_COLOR)
                cell["outer"].config(bg=EMPTY_COLOR)
                cell["mama"].config(text=mama_text or " ", bg=mama_color,
                                     fg=dark_text_for(mama_color) if mama_text else "#9e9e9e")
                cell["papa"].config(text=papa_text or " ", bg=papa_color,
                                     fg=dark_text_for(papa_color) if papa_text else "#9e9e9e")

    def _paint_cell(self, cell, color, num_text, mama_text, papa_text):
        cell["outer"].config(bg=color, highlightbackground="#cfcfcf", highlightthickness=1)
        cell["num"].config(text=num_text, bg=color)
        cell["mama"].config(text=mama_text or " ", bg=color, fg=color)
        cell["papa"].config(text=papa_text or " ", bg=color, fg=color)

    # ---------- Summary ----------

    def update_summary(self):
        counts = self._counts_by_type()

        for key, info in LEAVE_TYPES.items():
            working_days = self._working_days_for(info["person"])
            limit_days = info["weeks"] * working_days
            used_days = counts[key]
            used_weeks = used_days / working_days if working_days else 0
            pct = min(100, (used_days / limit_days * 100) if limit_days else 0)

            text = f"{used_days}/{limit_days} days ({used_weeks:.1f}/{info['weeks']} wk) - {info['paid']}"
            deadline = self._deadline_for(key)
            if deadline:
                text += f" - use by {deadline.strftime('%d/%m/%Y')}"

            row = self.summary_rows[key]
            row["bar"].config(value=pct)
            row["label"].config(text=text)

    def _counts_by_type(self):
        counts = {key: 0 for key in LEAVE_TYPES}
        for entry in self.data["leaves"].values():
            for person in ("mama", "papa"):
                key = entry.get(person)
                if key in counts:
                    counts[key] += 1
        return counts

    # ---------- Export for HR ----------

    def _collect_ranges(self):
        """Group marked days into contiguous leave periods per leave type.

        A gap is still considered "contiguous" when it is no longer than the
        person's usual non-working stretch (e.g. a normal weekend), so a
        continuous block of leave doesn't get split into one row per week.
        """
        per_type_dates = {}
        for iso, entry in self.data["leaves"].items():
            try:
                date_obj = datetime.date.fromisoformat(iso)
            except ValueError:
                continue
            for person in ("mama", "papa"):
                key = entry.get(person)
                if key in LEAVE_TYPES:
                    per_type_dates.setdefault(key, []).append(date_obj)

        ranges = []
        for key, dates in per_type_dates.items():
            info = LEAVE_TYPES[key]
            working_days = self._working_days_for(info["person"])
            allowed_gap = (7 - working_days) + 1
            dates.sort()
            start = prev = dates[0]
            count = 1
            for d in dates[1:]:
                if (d - prev).days <= allowed_gap:
                    count += 1
                else:
                    ranges.append({"type": key, "start": start, "end": prev, "days": count})
                    start = d
                    count = 1
                prev = d
            ranges.append({"type": key, "start": start, "end": prev, "days": count})

        ranges.sort(key=lambda r: r["start"])
        return ranges

    def _export_plan(self):
        ranges = self._collect_ranges()
        if not ranges:
            messagebox.showinfo("Bajalendario", "There are no leave days marked yet.")
            return

        path = filedialog.asksaveasfilename(
            title="Export leave plan for HR",
            defaultextension=".html",
            filetypes=[("HTML report", "*.html"), ("CSV file", "*.csv")],
            initialfile="bajalendario_leave_plan",
        )
        if not path:
            return

        base, ext = os.path.splitext(path)
        mama_ranges = [r for r in ranges if LEAVE_TYPES[r["type"]]["person"] == "mama"]
        papa_ranges = [r for r in ranges if LEAVE_TYPES[r["type"]]["person"] == "papa"]
        is_csv = path.lower().endswith(".csv")
        writer_fn = self._write_csv if is_csv else self._write_html

        jobs = [(path, ranges, None, "Combined")]
        if mama_ranges:
            jobs.append((f"{base}_mother{ext}", mama_ranges, "mama", "Mother"))
        if papa_ranges:
            jobs.append((f"{base}_father{ext}", papa_ranges, "papa", "Father"))

        written = []
        try:
            for job_path, job_ranges, person_filter, title_suffix in jobs:
                writer_fn(job_path, job_ranges, person_filter, title_suffix)
                written.append(job_path)
        except OSError as exc:
            messagebox.showerror("Bajalendario", f"Could not export the file:\n{exc}")
            return

        messagebox.showinfo("Bajalendario", "Leave plan exported to:\n" + "\n".join(written))

    def _write_csv(self, path, ranges, person_filter, title_suffix):
        counts = self._counts_by_type()
        types_to_show = [k for k, v in LEAVE_TYPES.items() if person_filter is None or v["person"] == person_filter]

        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([f"Bajalendario - Leave plan ({title_suffix})"])
            writer.writerow([])
            writer.writerow(["Person", "Leave type", "Pay", "Start date", "End date", "Working days", "Weeks"])
            for r in ranges:
                info = LEAVE_TYPES[r["type"]]
                working_days = self._working_days_for(info["person"])
                writer.writerow([
                    PERSON_LABELS[info["person"]],
                    info["label"],
                    info["paid"],
                    r["start"].strftime("%d/%m/%Y"),
                    r["end"].strftime("%d/%m/%Y"),
                    r["days"],
                    round(r["days"] / working_days, 1) if working_days else 0,
                ])

            writer.writerow([])
            writer.writerow(["Summary vs. legal entitlement"])
            writer.writerow(["Leave type", "Pay", "Days used", "Days available", "Weeks used", "Weeks available",
                              "Use by"])
            for key in types_to_show:
                info = LEAVE_TYPES[key]
                working_days = self._working_days_for(info["person"])
                limit_days = info["weeks"] * working_days
                used_days = counts[key]
                deadline = self._deadline_for(key)
                writer.writerow([
                    info["label"], info["paid"], used_days, limit_days,
                    round(used_days / working_days, 1) if working_days else 0, info["weeks"],
                    deadline.strftime("%d/%m/%Y") if deadline else "",
                ])

    def _mini_calendar_html(self, ranges, person_filter):
        if not ranges:
            return "<p>No leave days to show.</p>"

        boundary_dates = set()
        for r in ranges:
            boundary_dates.add(r["start"])
            boundary_dates.add(r["end"])

        start_date = min(r["start"] for r in ranges)
        end_date = max(r["end"] for r in ranges)

        months = []
        y, m = start_date.year, start_date.month
        while (y, m) <= (end_date.year, end_date.month):
            months.append((y, m))
            m += 1
            if m == 13:
                m = 1
                y += 1

        cal = calendar.Calendar(firstweekday=0)
        blocks = []
        for (year, month) in months:
            month_dates = list(cal.itermonthdates(year, month))
            weeks = [month_dates[i:i + 7] for i in range(0, len(month_dates), 7)]

            rows = []
            for week in weeks:
                cells = []
                for date_obj in week:
                    if date_obj.month != month:
                        cells.append('<td class="mini-cal-out"></td>')
                        continue

                    entry = self.data["leaves"].get(date_obj.isoformat(), {})
                    mama_key = entry.get("mama")
                    papa_key = entry.get("papa")
                    mama_color = LEAVE_TYPES[mama_key]["color"] if mama_key in LEAVE_TYPES else None
                    papa_color = LEAVE_TYPES[papa_key]["color"] if papa_key in LEAVE_TYPES else None

                    style = ""
                    if person_filter == "mama":
                        bg = mama_color
                    elif person_filter == "papa":
                        bg = papa_color
                    elif mama_color and papa_color:
                        bg = None
                        style += f"background:linear-gradient(to bottom, {mama_color} 50%, {papa_color} 50%);"
                    else:
                        bg = mama_color or papa_color

                    if bg:
                        style += f"background:{bg};color:{dark_text_for(bg)};"
                    if date_obj in boundary_dates:
                        style += "outline:2px solid #222;outline-offset:-2px;font-weight:700;"

                    cells.append(f'<td style="{style}">{date_obj.day}</td>')
                rows.append("<tr>" + "".join(cells) + "</tr>")

            blocks.append(
                '<div class="mini-cal">'
                f'<div class="mini-cal-title">{MONTHS[month - 1]} {year}</div>'
                '<table class="mini-cal-table"><tr>'
                + "".join(f"<th>{wd[0]}</th>" for wd in WEEKDAYS)
                + "</tr>" + "".join(rows) + "</table></div>"
            )

        return '<div class="mini-cal-grid">' + "".join(blocks) + "</div>"

    def _write_html(self, path, ranges, person_filter, title_suffix):
        counts = self._counts_by_type()
        types_to_show = [k for k, v in LEAVE_TYPES.items() if person_filter is None or v["person"] == person_filter]

        period_rows = []
        for r in ranges:
            info = LEAVE_TYPES[r["type"]]
            working_days = self._working_days_for(info["person"])
            weeks = r["days"] / working_days if working_days else 0
            period_rows.append(
                "<tr>"
                f"<td>{html.escape(PERSON_LABELS[info['person']])}</td>"
                f"<td><span class=\"chip\" style=\"background:{info['color']};"
                f"color:{dark_text_for(info['color'])}\">{html.escape(info['label'])}</span></td>"
                f"<td>{html.escape(info['paid'])}</td>"
                f"<td>{r['start'].strftime('%d/%m/%Y')}</td>"
                f"<td>{r['end'].strftime('%d/%m/%Y')}</td>"
                f"<td>{r['days']}</td>"
                f"<td>{weeks:.1f}</td>"
                "</tr>"
            )

        summary_rows = []
        for key in types_to_show:
            info = LEAVE_TYPES[key]
            working_days = self._working_days_for(info["person"])
            limit_days = info["weeks"] * working_days
            used_days = counts[key]
            used_weeks = used_days / working_days if working_days else 0
            deadline = self._deadline_for(key)
            summary_rows.append(
                "<tr>"
                f"<td><span class=\"chip\" style=\"background:{info['color']};"
                f"color:{dark_text_for(info['color'])}\">{html.escape(info['label'])}</span></td>"
                f"<td>{html.escape(info['paid'])}</td>"
                f"<td>{used_days}</td><td>{limit_days}</td>"
                f"<td>{used_weeks:.1f}</td><td>{info['weeks']}</td>"
                f"<td>{deadline.strftime('%d/%m/%Y') if deadline else '-'}</td>"
                "</tr>"
            )

        due_date = html.escape(self.data["settings"].get("due_date") or "-")
        mini_calendar = self._mini_calendar_html(ranges, person_filter)
        title = f"Bajalendario - Leave plan ({html.escape(title_suffix)})"

        html_doc = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Bajalendario - Leave plan</title>
<style>
  body {{ font-family: "Segoe UI", Arial, sans-serif; margin: 24px; color: #222; }}
  h1 {{ margin-bottom: 4px; }}
  .subtitle {{ color: #666; margin-top: 0; }}
  table {{ border-collapse: collapse; width: 100%; margin-bottom: 28px; }}
  th, td {{ border: 1px solid #ddd; padding: 6px 10px; text-align: left; font-size: 14px; }}
  th {{ background: #f0f0f0; }}
  .chip {{ padding: 2px 8px; border-radius: 4px; font-size: 13px; }}
  .footnote {{ color: #666; font-size: 12px; }}
  .mini-cal-grid {{ display: flex; flex-wrap: wrap; gap: 16px; margin-bottom: 28px; }}
  .mini-cal {{ border: 1px solid #ddd; border-radius: 6px; padding: 8px; }}
  .mini-cal-title {{ font-weight: 600; margin-bottom: 6px; font-size: 12px; text-align: center; }}
  .mini-cal-table {{ border-collapse: collapse; }}
  .mini-cal-table th, .mini-cal-table td {{
    width: 22px; height: 20px; text-align: center; font-size: 10px; border: 1px solid #eee; padding: 0;
  }}
  .mini-cal-table th {{ background: #fafafa; color: #888; font-weight: 400; }}
  .mini-cal-out {{ background: #fafafa; }}
  @media print {{ body {{ margin: 8px; }} }}
</style>
</head>
<body>
  <h1>{title}</h1>
  <p class="subtitle">
    Generated on {datetime.date.today().strftime('%d/%m/%Y')} &middot; Estimated due date: {due_date}
    &middot; Netherlands parental &amp; maternity leave
  </p>

  <h2>Planned leave periods</h2>
  <table>
    <tr><th>Person</th><th>Leave type</th><th>Pay</th><th>Start date</th><th>End date</th>
        <th>Working days</th><th>Weeks</th></tr>
    {''.join(period_rows)}
  </table>

  <h2>Calendar overview</h2>
  <p class="subtitle">Start and end days of each period are outlined in bold.</p>
  {mini_calendar}

  <h2>Summary vs. legal entitlement</h2>
  <table>
    <tr><th>Leave type</th><th>Pay</th><th>Days used</th><th>Days available</th>
        <th>Weeks used</th><th>Weeks available</th><th>Use by</th></tr>
    {''.join(summary_rows)}
  </table>

  <p class="footnote">Figures are indicative and based on standard Dutch entitlements; please confirm the
  exact dates and amounts with your employer's HR department and/or the UWV.</p>
</body>
</html>"""

        with open(path, "w", encoding="utf-8") as f:
            f.write(html_doc)

    # ---------- Help ----------

    def _show_help(self):
        lines = []
        for info in LEAVE_TYPES.values():
            lines.append(f"• {info['label']} ({info['paid']}): {info['info']}")
        messagebox.showinfo(
            "Leave types (Netherlands)",
            "These figures are indicative; always confirm the exact numbers with your "
            "employer, the UWV, or the Dutch government.\n\n" + "\n\n".join(lines),
        )


if __name__ == "__main__":
    app = BajalendarioApp()
    app.mainloop()
