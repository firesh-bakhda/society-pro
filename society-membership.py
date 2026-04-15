import calendar
import datetime
import importlib
import math
import os
import re
import sqlite3
import tkinter as tk
import webbrowser
from tkinter import filedialog, messagebox, ttk

import customtkinter as ctk
from fpdf import FPDF

try:
    from tkcalendar import Calendar, DateEntry
except ImportError:
    Calendar = None
    DateEntry = None

BUTTON_BLUE = "#2563eb"
BUTTON_BLUE_HOVER = "#1d4ed8"
BUTTON_GREEN = "#16a34a"
BUTTON_GREEN_HOVER = "#15803d"
BUTTON_RED = "#b91c1c"
BUTTON_RED_HOVER = "#991b1b"

# --- DATABASE INITIALIZATION ---
def init_db():
    conn = sqlite3.connect('society_pro_v2.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS members 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                       name TEXT NOT NULL, age INTEGER, profession TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS payments 
                      (pay_id INTEGER PRIMARY KEY AUTOINCREMENT,
                       member_id INTEGER, fee_type TEXT, fee_paid REAL, 
                       pay_date TEXT, ref_no TEXT, pay_method TEXT,
                       FOREIGN KEY(member_id) REFERENCES members(id))''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS fee_config 
                      (type TEXT PRIMARY KEY, amount REAL)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS member_types
                      (type TEXT PRIMARY KEY)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS admin_settings 
                      (key TEXT PRIMARY KEY, value TEXT)''')

    # Add newer member profile columns for older databases.
    existing_columns = {
        row[1] for row in cursor.execute("PRAGMA table_info(members)").fetchall()
    }
    if "global_id_no" not in existing_columns:
        cursor.execute("ALTER TABLE members ADD COLUMN global_id_no TEXT")
    if "global_mobile_no" not in existing_columns:
        cursor.execute("ALTER TABLE members ADD COLUMN global_mobile_no TEXT")
    if "global_home_no" not in existing_columns:
        cursor.execute("ALTER TABLE members ADD COLUMN global_home_no TEXT")
    if "address" not in existing_columns:
        cursor.execute("ALTER TABLE members ADD COLUMN address TEXT")
    if "member_type" not in existing_columns:
        cursor.execute("ALTER TABLE members ADD COLUMN member_type TEXT")
    if "revoked" not in existing_columns:
        cursor.execute("ALTER TABLE members ADD COLUMN revoked INTEGER DEFAULT 0")
    if "revoked_at" not in existing_columns:
        cursor.execute("ALTER TABLE members ADD COLUMN revoked_at TEXT")
    if "membership_added_at" not in existing_columns:
        cursor.execute("ALTER TABLE members ADD COLUMN membership_added_at TEXT")

    # Backfill missing timestamps for legacy rows.
    cursor.execute(
        "UPDATE members SET membership_added_at=datetime('now','localtime') WHERE COALESCE(membership_added_at, '')=''"
    )
    
    # Defaults
    cursor.executemany("INSERT OR IGNORE INTO fee_config VALUES (?, ?)", 
                       [('Entrance Fee', 25.0), ('Annual Subscription', 48.0), ('Life Membership', 2500.0)])
    cursor.executemany(
        "INSERT OR IGNORE INTO member_types(type) VALUES (?)",
        [('Standard',), ('Associate',), ('Life Member',)],
    )
    cursor.executemany("INSERT OR IGNORE INTO admin_settings VALUES (?, ?)", 
                       [('society_name', 'My Society'), 
                        ('bank_account', 'Maybank 1234567890'), 
                        ('logo_path', '')])

    # Migrate legacy defaults to new defaults without overriding user-customized values.
    cursor.execute(
        "UPDATE admin_settings SET value=? WHERE key='society_name' AND value=?",
        ('My Society', 'My Malaysian Society'),
    )
    cursor.execute(
        "UPDATE fee_config SET amount=? WHERE type='Entrance Fee' AND amount=?",
        (25.0, 50.0),
    )
    cursor.execute(
        "UPDATE fee_config SET amount=? WHERE type='Annual Subscription' AND amount=?",
        (48.0, 100.0),
    )
    cursor.execute(
        "UPDATE fee_config SET amount=? WHERE type='Life Membership' AND amount=?",
        (2500.0, 500.0),
    )

    # Migrate legacy single default member type to the new baseline defaults.
    existing_member_types = [
        row[0] for row in cursor.execute("SELECT type FROM member_types").fetchall()
    ]
    if existing_member_types == ['Regular']:
        cursor.execute("DELETE FROM member_types")
        cursor.executemany(
            "INSERT INTO member_types(type) VALUES (?)",
            [('Standard',), ('Associate',), ('Life Member',)],
        )

    conn.commit()
    conn.close()


class FallbackCalendarDateInput(ctk.CTkFrame):
    def __init__(self, parent, width=500):
        super().__init__(parent, fg_color="transparent")
        self._selected_date = datetime.date.today()
        self._current_year = self._selected_date.year
        self._current_month = self._selected_date.month
        self._date_var = tk.StringVar(value=self._selected_date.strftime("%d/%m/%Y"))

        entry_width = max(width - 94, 120)
        self._entry = ctk.CTkEntry(self, textvariable=self._date_var, width=entry_width)
        self._entry.pack(side="left", padx=(0, 8))
        self._button = ctk.CTkButton(
            self,
            text="Pick",
            width=86,
            fg_color=BUTTON_BLUE,
            hover_color=BUTTON_BLUE_HOVER,
            command=self._open_calendar,
        )
        self._button.pack(side="left")

    def get(self):
        return self._date_var.get()

    def _open_calendar(self):
        self._popup = ctk.CTkToplevel(self)
        self._popup.title("Choose Date")
        self._popup.geometry("320x340")
        self._popup.resizable(False, False)
        self._popup.transient(self.winfo_toplevel())
        self._popup.grab_set()

        # Use tkcalendar widget when available, while keeping a CTk-styled entry field.
        if Calendar is not None:
            cal = Calendar(
                self._popup,
                selectmode="day",
                date_pattern="dd/mm/yyyy",
                year=self._current_year,
                month=self._current_month,
                day=self._selected_date.day,
            )
            cal.pack(fill="both", expand=True, padx=12, pady=(12, 8))

            action_row = ctk.CTkFrame(self._popup, fg_color="transparent")
            action_row.pack(fill="x", padx=12, pady=(0, 12))
            ctk.CTkButton(
                action_row,
                text="Cancel",
                width=120,
                fg_color=BUTTON_BLUE,
                hover_color=BUTTON_BLUE_HOVER,
                command=self._popup.destroy,
            ).pack(side="left")
            ctk.CTkButton(
                action_row,
                text="Use Date",
                width=120,
                fg_color=BUTTON_GREEN,
                hover_color=BUTTON_GREEN_HOVER,
                command=lambda: self._pick_calendar_date(cal),
            ).pack(side="right")
            return

        nav = ctk.CTkFrame(self._popup, fg_color="transparent")
        nav.pack(fill="x", padx=10, pady=(10, 5))

        ctk.CTkButton(
            nav,
            text="<",
            width=35,
            fg_color=BUTTON_BLUE,
            hover_color=BUTTON_BLUE_HOVER,
            command=lambda: self._change_month(-1),
        ).pack(side="left")
        self._month_lbl = ctk.CTkLabel(nav, text="", font=("Arial", 14, "bold"))
        self._month_lbl.pack(side="left", expand=True)
        ctk.CTkButton(
            nav,
            text=">",
            width=35,
            fg_color=BUTTON_BLUE,
            hover_color=BUTTON_BLUE_HOVER,
            command=lambda: self._change_month(1),
        ).pack(side="right")

        self._days_frame = ctk.CTkFrame(self._popup, fg_color="transparent")
        self._days_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self._render_calendar()

    def _change_month(self, delta):
        month = self._current_month + delta
        year = self._current_year
        if month < 1:
            month = 12
            year -= 1
        elif month > 12:
            month = 1
            year += 1

        self._current_month = month
        self._current_year = year
        self._render_calendar()

    def _render_calendar(self):
        self._month_lbl.configure(text=f"{calendar.month_name[self._current_month]} {self._current_year}")

        for child in self._days_frame.winfo_children():
            child.destroy()

        weekdays = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
        for col, day_name in enumerate(weekdays):
            ctk.CTkLabel(self._days_frame, text=day_name).grid(row=0, column=col, padx=2, pady=2)

        month_rows = calendar.monthcalendar(self._current_year, self._current_month)
        for row_index, week in enumerate(month_rows, start=1):
            for col_index, day in enumerate(week):
                if day == 0:
                    ctk.CTkLabel(self._days_frame, text=" ").grid(row=row_index, column=col_index, padx=2, pady=2)
                    continue

                ctk.CTkButton(
                    self._days_frame,
                    text=str(day),
                    width=34,
                    height=26,
                    fg_color=BUTTON_BLUE,
                    hover_color=BUTTON_BLUE_HOVER,
                    command=lambda d=day: self._pick_day(d),
                ).grid(row=row_index, column=col_index, padx=2, pady=2)

    def _pick_day(self, day):
        self._selected_date = datetime.date(self._current_year, self._current_month, day)
        self._date_var.set(self._selected_date.strftime("%d/%m/%Y"))
        self._popup.destroy()

    def _pick_calendar_date(self, cal_widget):
        try:
            selected = datetime.datetime.strptime(cal_widget.get_date(), "%d/%m/%Y").date()
            self._selected_date = selected
            self._current_year = selected.year
            self._current_month = selected.month
            self._date_var.set(selected.strftime("%d/%m/%Y"))
        except Exception:
            pass
        self._popup.destroy()

class SocietyApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Society Pro - Admin & Billing System")
        self.geometry("1200x1000")
        init_db()

        self.banks = ["Maybank", "CIMB", "Public Bank", "RHB", "Hong Leong", "AmBank", "TNG eWallet", "GrabPay", "DuitNow QR", "Cash"]
        self.profs = ["Private Sector", "Government", "Self-Employed", "Student", "Retiree", "Engineer", "Teacher", "Doctor"]
        self.global_regions = [
            "Malaysia",
            "Singapore",
            "Indonesia",
            "Thailand",
            "India",
            "United States",
            "United Kingdom",
            "Australia",
            "Other",
        ]
        self.region_id_prefix = {
            "Malaysia": "MY-",
            "Singapore": "SG-",
            "Indonesia": "ID-",
            "Thailand": "TH-",
            "India": "IN-",
            "United States": "US-",
            "United Kingdom": "UK-",
            "Australia": "AU-",
            "Other": "ID-",
        }
        self.region_phone_prefix = {
            "Malaysia": "+60",
            "Singapore": "+65",
            "Indonesia": "+62",
            "Thailand": "+66",
            "India": "+91",
            "United States": "+1",
            "United Kingdom": "+44",
            "Australia": "+61",
            "Other": "+",
        }

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)

        # Sidebar
        self.sidebar = ctk.CTkFrame(self, width=220, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        ctk.CTkLabel(self.sidebar, text="SOCIETY PRO", font=ctk.CTkFont(size=20, weight="bold")).pack(pady=20)

        self.sidebar_top = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.sidebar_top.pack(fill="x", padx=12, pady=(0, 8))
        self.sidebar_bottom = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.sidebar_bottom.pack(side="bottom", fill="x", padx=12, pady=(8, 14))

        ctk.CTkButton(self.sidebar_top, text="👤 Register Member", anchor="w", fg_color=BUTTON_BLUE, hover_color=BUTTON_BLUE_HOVER, command=self.show_register).pack(pady=6, padx=8, fill="x")
        ctk.CTkButton(self.sidebar_top, text="💳 Renew / Pay Fees", anchor="w", fg_color=BUTTON_BLUE, hover_color=BUTTON_BLUE_HOVER, command=self.show_renewal).pack(pady=6, padx=8, fill="x")
        ctk.CTkButton(self.sidebar_top, text="📇 View Member Details", anchor="w", fg_color=BUTTON_BLUE, hover_color=BUTTON_BLUE_HOVER, command=self.show_member_details).pack(pady=6, padx=8, fill="x")
        ctk.CTkButton(self.sidebar_top, text="🧾 Generate Receipts", anchor="w", fg_color=BUTTON_BLUE, hover_color=BUTTON_BLUE_HOVER, command=self.show_receipt_menu).pack(pady=6, padx=8, fill="x")
        ctk.CTkButton(self.sidebar_top, text="📚 Payment Records", anchor="w", fg_color=BUTTON_BLUE, hover_color=BUTTON_BLUE_HOVER, command=self.show_records).pack(pady=6, padx=8, fill="x")
        ctk.CTkButton(self.sidebar_top, text="📊 Statistics", anchor="w", fg_color=BUTTON_BLUE, hover_color=BUTTON_BLUE_HOVER, command=self.show_statistics).pack(pady=6, padx=8, fill="x")

        ctk.CTkButton(self.sidebar_bottom, text="⚙ Admin Settings", anchor="w", fg_color=BUTTON_BLUE, hover_color=BUTTON_BLUE_HOVER, command=self.show_admin_settings).pack(pady=(0, 6), padx=8, fill="x")
        ctk.CTkButton(self.sidebar_bottom, text="ℹ About", anchor="w", fg_color=BUTTON_BLUE, hover_color=BUTTON_BLUE_HOVER, command=self.show_about).pack(pady=(0, 2), padx=8, fill="x")

        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=30, pady=20)

        self.footer_bar = ctk.CTkFrame(self, corner_radius=0, height=38)
        self.footer_bar.grid(row=1, column=0, columnspan=2, sticky="ew")
        self.footer_bar.grid_columnconfigure(0, weight=1)
        self.footer_bar.grid_propagate(False)
        self.footer_label = ctk.CTkLabel(
            self.footer_bar,
            text="Copyright (R) 2026   |   Firesh Bakhda   |   Community Edition",
            font=("Arial", 12, "bold"),
            anchor="center",
        )
        self.footer_label.grid(row=0, column=0, sticky="ew", padx=12, pady=8)

        self.style = ttk.Style()
        self.style.theme_use("default")
        self.style.configure("Treeview", background="#2a2d2e", foreground="white", fieldbackground="#2a2d2e", rowheight=30)
        self.style.map("Treeview", background=[('selected', '#1f538d')])

        # Shared layout values for cleaner alignment across forms.
        self.form_field_width = 540
        self.form_section_width = 620
        self._toast_widget = None
        self._toast_after_id = None

        self.show_register()

    def _create_date_input(self, parent, width=500):
        # Unified styled date field for consistent look and alignment.
        return FallbackCalendarDateInput(parent, width=width)

    def _add_field_label(self, parent, text, width=None):
        ctk.CTkLabel(
            parent,
            text=text,
            anchor="w",
            width=width or self.form_field_width,
            font=("Arial", 13, "bold"),
        ).pack(pady=(3, 1))

    def get_admin_setting(self, key):
        conn = sqlite3.connect('society_pro_v2.db')
        res = conn.execute("SELECT value FROM admin_settings WHERE key=?", (key,)).fetchone()
        conn.close()
        return res[0] if res else ""

    def get_member_types(self):
        conn = sqlite3.connect('society_pro_v2.db')
        rows = conn.execute(
            """SELECT type
               FROM member_types
               ORDER BY CASE type
                   WHEN 'Standard' THEN 1
                   WHEN 'Associate' THEN 2
                   WHEN 'Life Member' THEN 3
                   ELSE 99
               END,
               type"""
        ).fetchall()
        conn.close()
        types = [r[0] for r in rows if r[0] and str(r[0]).strip()]
        return types or ["Standard", "Associate", "Life Member"]

    def clear_main(self):
        for widget in self.main_frame.winfo_children():
            widget.destroy()

    def _create_bottom_action_bar(self):
        bar = ctk.CTkFrame(self.main_frame, fg_color=("#d9dde3", "#1f242b"), height=42, corner_radius=8)
        bar.pack(side="bottom", fill="x", pady=(6, 0), padx=(2, 2))
        bar.pack_propagate(False)
        return bar

    def _show_notification(self, message, level="info", duration_ms=5000):
        palette = {
            "success": {"bg": "#0f766e", "title": "Success"},
            "warning": {"bg": "#b45309", "title": "Warning"},
            "error": {"bg": "#b91c1c", "title": "Error"},
            "info": {"bg": "#2563eb", "title": "Info"},
        }
        style = palette.get(level, palette["info"])

        if self._toast_after_id is not None:
            self.after_cancel(self._toast_after_id)
            self._toast_after_id = None

        if self._toast_widget is not None and self._toast_widget.winfo_exists():
            self._toast_widget.destroy()

        self.update_idletasks()
        toast_width = 360
        x_pad = 18
        y_pad = 18
        x_pos = max(self.winfo_width() - toast_width - x_pad, x_pad)

        self._toast_widget = ctk.CTkFrame(
            self,
            fg_color=style["bg"],
            corner_radius=12,
            border_width=1,
            border_color=("#e5e7eb", "#1f2937"),
            width=toast_width,
            height=88,
        )
        self._toast_widget.place(x=x_pos, y=y_pad)
        self._toast_widget.pack_propagate(False)

        ctk.CTkLabel(
            self._toast_widget,
            text=style["title"],
            text_color="white",
            font=("Arial", 14, "bold"),
            anchor="w",
        ).pack(fill="x", padx=14, pady=(10, 2))
        ctk.CTkLabel(
            self._toast_widget,
            text=message,
            text_color="white",
            font=("Arial", 12),
            justify="left",
            anchor="w",
            wraplength=330,
        ).pack(fill="x", padx=14, pady=(0, 10))

        self._toast_widget.lift()
        self._toast_after_id = self.after(duration_ms, self._hide_notification)

    def _hide_notification(self):
        if self._toast_widget is not None and self._toast_widget.winfo_exists():
            self._toast_widget.destroy()
        self._toast_widget = None
        self._toast_after_id = None

    def _export_treeview_to_xlsx(self, tree, default_filename):
        try:
            openpyxl_module = importlib.import_module("openpyxl")
            workbook = openpyxl_module.Workbook()
        except Exception:
            self._show_notification("Excel export requires openpyxl. Install it to continue.", level="error")
            return

        file_path = filedialog.asksaveasfilename(
            title="Export to Excel",
            defaultextension=".xlsx",
            initialfile=default_filename,
            filetypes=[("Excel Workbook", "*.xlsx")],
        )
        if not file_path:
            return

        sheet = workbook.active
        sheet.title = "Export"

        columns = tree["columns"]
        headers = [tree.heading(col).get("text") or str(col) for col in columns]
        sheet.append(headers)

        for item_id in tree.get_children():
            row_vals = tree.item(item_id).get("values", [])
            sheet.append(list(row_vals))

        try:
            workbook.save(file_path)
            self._show_notification(f"Exported {len(tree.get_children())} rows to Excel.", level="success")
        except Exception as exc:
            self._show_notification(f"Excel export failed: {exc}", level="error")

    def _set_region_prefill(self, entry_widget, region, is_id=False):
        if is_id:
            entry_widget.delete(0, "end")
            entry_widget.insert(0, self.region_id_prefix.get(region, "ID-"))
            return

        entry_widget.delete(0, "end")
        entry_widget.insert(0, self.region_phone_prefix.get(region, "+"))

    def _on_id_region_change(self, region):
        self._set_region_prefill(self.ent_global_id, region, is_id=True)

    def _on_mobile_region_change(self, region):
        self._set_region_prefill(self.ent_global_mobile, region)

    def _on_home_region_change(self, region):
        self._set_region_prefill(self.ent_global_home, region)

    def _split_global_contact(self, stored_value, is_id=False):
        value = str(stored_value or "").strip()
        if not value:
            return "Malaysia", ""

        country = "Malaysia"
        number = value
        if ":" in value:
            possible_country, remainder = value.split(":", 1)
            possible_country = possible_country.strip()
            if possible_country in self.global_regions:
                country = possible_country
            number = remainder.strip()

        if not number:
            number = self.region_id_prefix.get(country, "ID-") if is_id else self.region_phone_prefix.get(country, "+")
        return country, number

    def _add_member_type_row(self, value=""):
        row = ctk.CTkFrame(self.member_type_container, fg_color="transparent")
        row.pack(fill="x", pady=(0, 6))
        ent = ctk.CTkEntry(row, width=420, placeholder_text="Member Type")
        if value:
            ent.insert(0, value)
        ent.pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            row,
            text="Remove",
            width=90,
            fg_color=BUTTON_RED,
            hover_color=BUTTON_RED_HOVER,
            command=lambda r=row: self._remove_member_type_row(r),
        ).pack(side="left")
        self.member_type_rows.append((row, ent))

    def _remove_member_type_row(self, row_widget):
        if len(self.member_type_rows) <= 1:
            self._show_notification("At least one member type is required.", level="warning")
            return
        self.member_type_rows = [pair for pair in self.member_type_rows if pair[0] != row_widget]
        row_widget.destroy()

    # --- STATISTICS DASHBOARD ---
    def _parse_payment_date(self, value):
        if not value:
            return None
        value = str(value).strip()
        formats = ["%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"]
        for fmt in formats:
            try:
                return datetime.datetime.strptime(value, fmt).date()
            except Exception:
                continue
        return None

    def _short_text(self, text, max_len=14):
        text = str(text)
        if len(text) <= max_len:
            return text
        return text[: max_len - 3] + "..."

    def _currency(self, value):
        try:
            return f"RM {float(value):,.2f}"
        except Exception:
            return "RM 0.00"

    def _build_statistics_payload(self):
        payload = {
            "total_members": 0,
            "total_payments": 0,
            "total_revenue": 0.0,
            "avg_payment": 0.0,
            "life_members": 0,
            "active_members_90": 0,
            "last_payment_date": "-",
            "member_type": [],
            "fee_type": [],
            "pay_method": [],
            "profession": [],
            "age_bucket": [],
            "region": [],
            "monthly_revenue": [],
            "weekday_revenue": [],
            "top_members": [],
            "recent": [],
        }

        conn = sqlite3.connect('society_pro_v2.db')
        cur = conn.cursor()

        total_members = cur.execute("SELECT COUNT(*) FROM members").fetchone()[0] or 0
        total_payments = cur.execute("SELECT COUNT(*) FROM payments").fetchone()[0] or 0
        total_revenue = cur.execute("SELECT COALESCE(SUM(fee_paid), 0) FROM payments").fetchone()[0] or 0.0
        life_members = cur.execute("SELECT COUNT(*) FROM members WHERE member_type='Life Member'").fetchone()[0] or 0

        payload["total_members"] = total_members
        payload["total_payments"] = total_payments
        payload["total_revenue"] = float(total_revenue)
        payload["avg_payment"] = float(total_revenue) / total_payments if total_payments else 0.0
        payload["life_members"] = life_members

        payload["member_type"] = cur.execute(
            "SELECT COALESCE(member_type, 'Unspecified'), COUNT(*) FROM members GROUP BY COALESCE(member_type, 'Unspecified') ORDER BY COUNT(*) DESC"
        ).fetchall()
        payload["fee_type"] = cur.execute(
            "SELECT fee_type, COALESCE(SUM(fee_paid),0) FROM payments GROUP BY fee_type ORDER BY SUM(fee_paid) DESC"
        ).fetchall()
        payload["pay_method"] = cur.execute(
            "SELECT COALESCE(pay_method, 'Unknown'), COUNT(*) FROM payments GROUP BY COALESCE(pay_method, 'Unknown') ORDER BY COUNT(*) DESC"
        ).fetchall()
        payload["profession"] = cur.execute(
            "SELECT COALESCE(profession, 'Unspecified'), COUNT(*) FROM members GROUP BY COALESCE(profession, 'Unspecified') ORDER BY COUNT(*) DESC"
        ).fetchall()
        payload["top_members"] = cur.execute(
            """SELECT m.name, COALESCE(SUM(p.fee_paid), 0) AS total_paid
               FROM members m
               LEFT JOIN payments p ON p.member_id = m.id
               GROUP BY m.id, m.name
               ORDER BY total_paid DESC, m.name ASC
               LIMIT 10"""
        ).fetchall()
        payload["recent"] = cur.execute(
            """SELECT m.name, p.fee_type, p.fee_paid, p.pay_date, p.pay_method
               FROM payments p
               JOIN members m ON p.member_id = m.id
               ORDER BY p.pay_id DESC
               LIMIT 12"""
        ).fetchall()

        ages = [
            row[0]
            for row in cur.execute("SELECT age FROM members WHERE age IS NOT NULL").fetchall()
            if str(row[0]).strip().isdigit()
        ]
        age_buckets = {
            "<25": 0,
            "25-34": 0,
            "35-44": 0,
            "45-54": 0,
            "55-64": 0,
            "65+": 0,
        }
        for age in ages:
            a = int(age)
            if a < 25:
                age_buckets["<25"] += 1
            elif a < 35:
                age_buckets["25-34"] += 1
            elif a < 45:
                age_buckets["35-44"] += 1
            elif a < 55:
                age_buckets["45-54"] += 1
            elif a < 65:
                age_buckets["55-64"] += 1
            else:
                age_buckets["65+"] += 1
        payload["age_bucket"] = list(age_buckets.items())

        region_counts = {}
        for value, in cur.execute("SELECT COALESCE(global_mobile_no, '') FROM members").fetchall():
            label = "Unknown"
            if ":" in value:
                possible = value.split(":", 1)[0].strip()
                if possible:
                    label = possible
            region_counts[label] = region_counts.get(label, 0) + 1
        payload["region"] = sorted(region_counts.items(), key=lambda x: x[1], reverse=True)

        month_totals = {}
        weekday_totals = {"Mon": 0.0, "Tue": 0.0, "Wed": 0.0, "Thu": 0.0, "Fri": 0.0, "Sat": 0.0, "Sun": 0.0}
        last_payment = None
        active_cutoff = datetime.date.today() - datetime.timedelta(days=90)
        active_member_ids = set()
        for member_id, fee_paid, pay_date in cur.execute("SELECT member_id, fee_paid, pay_date FROM payments").fetchall():
            d = self._parse_payment_date(pay_date)
            if d is None:
                continue
            month_key = d.strftime("%Y-%m")
            month_totals[month_key] = month_totals.get(month_key, 0.0) + float(fee_paid or 0)
            weekday_key = d.strftime("%a")
            if weekday_key in weekday_totals:
                weekday_totals[weekday_key] += float(fee_paid or 0)
            if last_payment is None or d > last_payment:
                last_payment = d
            if d >= active_cutoff:
                active_member_ids.add(member_id)

        payload["monthly_revenue"] = sorted(month_totals.items(), key=lambda x: x[0])
        payload["weekday_revenue"] = list(weekday_totals.items())
        payload["active_members_90"] = len(active_member_ids)
        payload["last_payment_date"] = last_payment.strftime("%d/%m/%Y") if last_payment else "-"

        conn.close()
        return payload

    def _chart_panel(self, parent, title, subtitle="", height=280):
        panel = ctk.CTkFrame(parent, corner_radius=12)
        panel.pack(side="left", fill="both", expand=True, padx=6, pady=6)
        ctk.CTkLabel(panel, text=title, anchor="w", font=("Arial", 16, "bold")).pack(fill="x", padx=12, pady=(10, 0))
        if subtitle:
            ctk.CTkLabel(panel, text=subtitle, anchor="w", text_color=("#4b5563", "#9ca3af"), font=("Arial", 11)).pack(fill="x", padx=12, pady=(2, 0))
        canvas = tk.Canvas(panel, height=height, highlightthickness=0, bg="#111827")
        canvas.pack(fill="both", expand=True, padx=12, pady=(8, 12))
        return panel, canvas

    def _draw_stat_card(self, parent, title, value, accent="#2563eb", subtext=""):
        card = ctk.CTkFrame(parent, corner_radius=12)
        card.pack(side="left", fill="both", expand=True, padx=6, pady=6)
        ctk.CTkFrame(card, fg_color=accent, height=4, corner_radius=4).pack(fill="x", padx=10, pady=(10, 8))
        ctk.CTkLabel(card, text=title, anchor="w", font=("Arial", 12), text_color=("#334155", "#cbd5e1")).pack(fill="x", padx=12)
        ctk.CTkLabel(card, text=value, anchor="w", font=("Arial", 22, "bold")).pack(fill="x", padx=12, pady=(2, 4))
        if subtext:
            ctk.CTkLabel(card, text=subtext, anchor="w", font=("Arial", 11), text_color=("#475569", "#94a3b8")).pack(fill="x", padx=12, pady=(0, 10))

    def _draw_bar_chart(self, canvas, data, bar_color="#2563eb", value_prefix="", max_items=8):
        canvas.update_idletasks()
        canvas.delete("all")
        width = max(canvas.winfo_width(), 480)
        height = max(canvas.winfo_height(), 260)
        canvas.configure(bg="#0f172a")

        if not data:
            canvas.create_text(width / 2, height / 2, text="No data available", fill="#cbd5e1", font=("Arial", 13, "bold"))
            return

        entries = data[:max_items]
        labels = [self._short_text(x[0], 13) for x in entries]
        values = [float(x[1]) for x in entries]
        max_val = max(values) if values else 1
        max_val = max(max_val, 1)

        left_pad = 54
        right_pad = 14
        top_pad = 20
        bottom_pad = 46
        chart_w = width - left_pad - right_pad
        chart_h = height - top_pad - bottom_pad

        for i in range(5):
            y = top_pad + (chart_h * i / 4)
            canvas.create_line(left_pad, y, width - right_pad, y, fill="#1f2937")
            val = max_val * (1 - i / 4)
            label = f"{value_prefix}{val:,.0f}" if max_val >= 10 else f"{value_prefix}{val:.1f}"
            canvas.create_text(left_pad - 8, y, text=label, fill="#94a3b8", anchor="e", font=("Arial", 8))

        count = len(values)
        slot = chart_w / max(count, 1)
        bar_w = min(46, slot * 0.65)

        for idx, (label, val) in enumerate(zip(labels, values)):
            x_center = left_pad + (idx + 0.5) * slot
            x0 = x_center - bar_w / 2
            x1 = x_center + bar_w / 2
            y1 = top_pad + chart_h
            bar_h = (val / max_val) * chart_h
            y0 = y1 - bar_h
            canvas.create_rectangle(x0, y0, x1, y1, fill=bar_color, outline="")
            canvas.create_text(x_center, y0 - 10, text=f"{value_prefix}{val:,.0f}", fill="#e2e8f0", font=("Arial", 8))
            canvas.create_text(x_center, y1 + 14, text=label, fill="#cbd5e1", font=("Arial", 8))

    def _draw_line_chart(self, canvas, data, line_color="#10b981", value_prefix="RM "):
        canvas.update_idletasks()
        canvas.delete("all")
        width = max(canvas.winfo_width(), 480)
        height = max(canvas.winfo_height(), 260)
        canvas.configure(bg="#111827")

        if not data:
            canvas.create_text(width / 2, height / 2, text="No trend data yet", fill="#cbd5e1", font=("Arial", 13, "bold"))
            return

        labels = [x[0] for x in data]
        values = [float(x[1]) for x in data]
        max_val = max(values) if values else 1
        min_val = min(values) if values else 0
        span = max(max_val - min_val, 1)

        left_pad, right_pad, top_pad, bottom_pad = 58, 16, 20, 44
        chart_w = width - left_pad - right_pad
        chart_h = height - top_pad - bottom_pad

        for i in range(5):
            y = top_pad + chart_h * i / 4
            canvas.create_line(left_pad, y, width - right_pad, y, fill="#1f2937")
            v = max_val - (span * i / 4)
            canvas.create_text(left_pad - 8, y, text=f"{value_prefix}{v:,.0f}", fill="#94a3b8", anchor="e", font=("Arial", 8))

        points = []
        x_step = chart_w / max(len(values) - 1, 1)
        for i, v in enumerate(values):
            x = left_pad + i * x_step
            y = top_pad + (max_val - v) / span * chart_h
            points.extend([x, y])

        if len(points) >= 4:
            canvas.create_line(points, fill=line_color, width=3, smooth=True)

        for i, v in enumerate(values):
            x = left_pad + i * x_step
            y = top_pad + (max_val - v) / span * chart_h
            canvas.create_oval(x - 4, y - 4, x + 4, y + 4, fill="#f8fafc", outline=line_color, width=2)
            if len(values) <= 12 or i % 2 == 0:
                canvas.create_text(x, height - 18, text=self._short_text(labels[i], 8), fill="#cbd5e1", font=("Arial", 8))

    def _draw_pie_chart(self, canvas, data, colors=None, max_items=8):
        canvas.update_idletasks()
        canvas.delete("all")
        width = max(canvas.winfo_width(), 480)
        height = max(canvas.winfo_height(), 260)
        canvas.configure(bg="#0f172a")

        if not data:
            canvas.create_text(width / 2, height / 2, text="No distribution data", fill="#cbd5e1", font=("Arial", 13, "bold"))
            return

        entries = data[:max_items]
        labels = [str(x[0]) for x in entries]
        values = [float(x[1]) for x in entries]
        total = sum(values)
        if total <= 0:
            canvas.create_text(width / 2, height / 2, text="No values to plot", fill="#cbd5e1", font=("Arial", 13, "bold"))
            return

        palette = colors or [
            "#60a5fa", "#34d399", "#f59e0b", "#f87171", "#a78bfa", "#22d3ee", "#f472b6", "#94a3b8", "#4ade80", "#fb923c"
        ]

        cx = width * 0.32
        cy = height * 0.52
        radius = min(width, height) * 0.33
        x0, y0, x1, y1 = cx - radius, cy - radius, cx + radius, cy + radius

        start = 0
        for i, (label, val) in enumerate(zip(labels, values)):
            extent = (val / total) * 360
            color = palette[i % len(palette)]
            canvas.create_arc(x0, y0, x1, y1, start=start, extent=extent, fill=color, outline="#0b1220", width=1)
            start += extent

        legend_x = width * 0.58
        legend_y = 24
        for i, (label, val) in enumerate(zip(labels, values)):
            color = palette[i % len(palette)]
            pct = (val / total) * 100
            y = legend_y + i * 24
            canvas.create_rectangle(legend_x, y, legend_x + 12, y + 12, fill=color, outline="")
            canvas.create_text(
                legend_x + 18,
                y + 6,
                text=f"{self._short_text(label, 18)}  {pct:.1f}%",
                fill="#e2e8f0",
                anchor="w",
                font=("Arial", 9),
            )

    def _draw_donut_chart(self, canvas, data):
        self._draw_pie_chart(canvas, data, max_items=6)
        width = max(canvas.winfo_width(), 480)
        height = max(canvas.winfo_height(), 260)
        cx = width * 0.32
        cy = height * 0.52
        radius = min(width, height) * 0.16
        canvas.create_oval(cx - radius, cy - radius, cx + radius, cy + radius, fill="#0f172a", outline="#0f172a")
        total = sum(float(v) for _, v in data)
        canvas.create_text(cx, cy - 6, text="Total", fill="#94a3b8", font=("Arial", 9, "bold"))
        canvas.create_text(cx, cy + 10, text=f"{int(total)}", fill="#f8fafc", font=("Arial", 12, "bold"))

    def _draw_radar_like_chart(self, canvas, data, fill="#38bdf8"):
        canvas.update_idletasks()
        canvas.delete("all")
        width = max(canvas.winfo_width(), 480)
        height = max(canvas.winfo_height(), 260)
        canvas.configure(bg="#111827")

        if not data:
            canvas.create_text(width / 2, height / 2, text="No segment data", fill="#cbd5e1", font=("Arial", 13, "bold"))
            return

        entries = data[:7]
        labels = [self._short_text(x[0], 10) for x in entries]
        values = [float(x[1]) for x in entries]
        max_val = max(values) if values else 1
        max_val = max(max_val, 1)

        cx, cy = width * 0.5, height * 0.53
        radius = min(width, height) * 0.31
        sides = len(entries)

        for layer in range(1, 5):
            r = radius * layer / 4
            pts = []
            for i in range(sides):
                ang = (2 * math.pi * i / sides) - math.pi / 2
                pts.extend([cx + r * math.cos(ang), cy + r * math.sin(ang)])
            canvas.create_polygon(pts, outline="#1f2937", fill="", width=1)

        for i, label in enumerate(labels):
            ang = (2 * math.pi * i / sides) - math.pi / 2
            x = cx + radius * math.cos(ang)
            y = cy + radius * math.sin(ang)
            canvas.create_line(cx, cy, x, y, fill="#1f2937")
            canvas.create_text(cx + (radius + 18) * math.cos(ang), cy + (radius + 18) * math.sin(ang), text=label, fill="#cbd5e1", font=("Arial", 8))

        poly = []
        for i, value in enumerate(values):
            r = radius * (value / max_val)
            ang = (2 * math.pi * i / sides) - math.pi / 2
            poly.extend([cx + r * math.cos(ang), cy + r * math.sin(ang)])
        canvas.create_polygon(poly, fill=fill, outline="#e2e8f0", width=2, stipple="gray50")

    def show_statistics(self):
        self.clear_main()
        action_bar = self._create_bottom_action_bar()

        title_row = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        title_row.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(title_row, text="Statistics Dashboard", font=("Arial", 24, "bold")).pack(side="left")
        ctk.CTkLabel(
            title_row,
            text=f"Updated: {datetime.datetime.now().strftime('%d %b %Y %H:%M')}",
            text_color=("#475569", "#94a3b8"),
            font=("Arial", 12),
        ).pack(side="right")

        payload = self._build_statistics_payload()

        cards = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        cards.pack(fill="x", pady=(0, 4))
        self._draw_stat_card(cards, "Total Members", f"{payload['total_members']}", accent="#2563eb", subtext="Registered members")
        self._draw_stat_card(cards, "Total Revenue", self._currency(payload["total_revenue"]), accent="#0891b2", subtext="All-time collections")
        self._draw_stat_card(cards, "Payment Transactions", f"{payload['total_payments']}", accent="#16a34a", subtext="Successful entries")
        self._draw_stat_card(cards, "Avg Payment", self._currency(payload["avg_payment"]), accent="#d97706", subtext="Mean per transaction")

        cards2 = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        cards2.pack(fill="x", pady=(0, 6))
        self._draw_stat_card(cards2, "Life Members", f"{payload['life_members']}", accent="#7c3aed", subtext="Current Life Member count")
        self._draw_stat_card(cards2, "Active (Last 90 Days)", f"{payload['active_members_90']}", accent="#0f766e", subtext="Members with recent payment")
        self._draw_stat_card(cards2, "Last Payment Date", payload["last_payment_date"], accent="#be123c", subtext="Most recent transaction")
        member_share = (payload["active_members_90"] / payload["total_members"] * 100) if payload["total_members"] else 0.0
        self._draw_stat_card(cards2, "Engagement", f"{member_share:.1f}%", accent="#1d4ed8", subtext="Active members ratio")

        dashboard = ctk.CTkScrollableFrame(self.main_frame, fg_color="transparent")
        dashboard.pack(fill="both", expand=True, pady=(2, 4))

        row1 = ctk.CTkFrame(dashboard, fg_color="transparent")
        row1.pack(fill="x", expand=True)
        _, c1 = self._chart_panel(row1, "Revenue by Fee Type", "Shows which fee categories drive income")
        self._draw_bar_chart(c1, payload["fee_type"], bar_color="#0284c7", value_prefix="RM ")
        _, c2 = self._chart_panel(row1, "Monthly Revenue Trend", "Chronological collection pattern")
        self._draw_line_chart(c2, payload["monthly_revenue"], line_color="#22c55e", value_prefix="RM ")

        row2 = ctk.CTkFrame(dashboard, fg_color="transparent")
        row2.pack(fill="x", expand=True)
        _, c3 = self._chart_panel(row2, "Member Type Distribution", "Composition of your membership base")
        self._draw_donut_chart(c3, payload["member_type"])
        _, c4 = self._chart_panel(row2, "Payment Method Mix", "How members prefer to pay")
        self._draw_pie_chart(c4, payload["pay_method"])

        row3 = ctk.CTkFrame(dashboard, fg_color="transparent")
        row3.pack(fill="x", expand=True)
        _, c5 = self._chart_panel(row3, "Profession Breakdown", "Top professional backgrounds")
        self._draw_bar_chart(c5, payload["profession"], bar_color="#a855f7", value_prefix="")
        _, c6 = self._chart_panel(row3, "Age Segment Radar", "Audience profile by age bucket")
        self._draw_radar_like_chart(c6, payload["age_bucket"], fill="#06b6d4")

        row4 = ctk.CTkFrame(dashboard, fg_color="transparent")
        row4.pack(fill="x", expand=True)
        _, c7 = self._chart_panel(row4, "Global Reach", "Members by selected mobile region")
        self._draw_bar_chart(c7, payload["region"], bar_color="#f97316", value_prefix="")
        _, c8 = self._chart_panel(row4, "Weekday Collection Pulse", "Revenue generated by weekday")
        self._draw_bar_chart(c8, payload["weekday_revenue"], bar_color="#14b8a6", value_prefix="RM ", max_items=7)

        table_row = ctk.CTkFrame(dashboard, fg_color="transparent")
        table_row.pack(fill="both", expand=True)

        top_panel = ctk.CTkFrame(table_row, corner_radius=12)
        top_panel.pack(side="left", fill="both", expand=True, padx=6, pady=6)
        ctk.CTkLabel(top_panel, text="Top 10 Members by Contribution", anchor="w", font=("Arial", 16, "bold")).pack(fill="x", padx=12, pady=(10, 4))
        top_tree = ttk.Treeview(top_panel, columns=("Rank", "Member", "Total"), show="headings", height=9)
        top_tree.heading("Rank", text="Rank")
        top_tree.heading("Member", text="Member")
        top_tree.heading("Total", text="Total Paid (RM)")
        top_tree.column("Rank", anchor="center", width=60)
        top_tree.column("Member", anchor="w", width=220)
        top_tree.column("Total", anchor="center", width=140)
        top_tree.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        for idx, row in enumerate(payload["top_members"], start=1):
            top_tree.insert("", "end", values=(idx, row[0], f"{float(row[1]):.2f}"))

        recent_panel = ctk.CTkFrame(table_row, corner_radius=12)
        recent_panel.pack(side="left", fill="both", expand=True, padx=6, pady=6)
        ctk.CTkLabel(recent_panel, text="Latest 12 Payments", anchor="w", font=("Arial", 16, "bold")).pack(fill="x", padx=12, pady=(10, 4))
        recent_tree = ttk.Treeview(recent_panel, columns=("Member", "Fee", "Amount", "Date", "Method"), show="headings", height=9)
        recent_tree.heading("Member", text="Member")
        recent_tree.heading("Fee", text="Fee Type")
        recent_tree.heading("Amount", text="Amount (RM)")
        recent_tree.heading("Date", text="Date")
        recent_tree.heading("Method", text="Method")
        recent_tree.column("Member", anchor="w", width=160)
        recent_tree.column("Fee", anchor="w", width=130)
        recent_tree.column("Amount", anchor="center", width=100)
        recent_tree.column("Date", anchor="center", width=90)
        recent_tree.column("Method", anchor="center", width=110)
        recent_tree.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        for row in payload["recent"]:
            recent_tree.insert("", "end", values=(row[0], row[1], f"{float(row[2]):.2f}", row[3], row[4]))

        ctk.CTkButton(
            action_bar,
            text="Refresh Dashboard",
            fg_color=BUTTON_GREEN,
            hover_color=BUTTON_GREEN_HOVER,
            width=220,
            height=80,
            command=self.show_statistics,
        ).pack(side="right", padx=6, pady=6)

    # --- 1. ADMIN SETTINGS (NEW) ---
    def show_admin_settings(self):
        self.clear_main()
        action_bar = self._create_bottom_action_bar()
        ctk.CTkLabel(self.main_frame, text="Admin & Society Settings", font=("Arial", 22, "bold")).pack(pady=(2, 8))
        content = ctk.CTkFrame(self.main_frame, width=780, fg_color="transparent")
        content.pack(fill="both", expand=True, pady=(0, 4))

        # Society information section
        society_section = ctk.CTkFrame(content, corner_radius=10)
        society_section.pack(fill="x", padx=6, pady=(0, 10))
        ctk.CTkLabel(society_section, text="Society Information", font=("Arial", 16, "bold")).pack(anchor="w", padx=16, pady=(10, 4))

        self._add_field_label(society_section, "Society Name", width=self.form_field_width)
        self.ent_soc_name = ctk.CTkEntry(society_section, placeholder_text="Society Name", width=self.form_field_width)
        self.ent_soc_name.insert(0, self.get_admin_setting('society_name'))
        self.ent_soc_name.pack(pady=(0, 4))

        self._add_field_label(society_section, "Bank Account Information", width=self.form_field_width)
        self.ent_soc_bank = ctk.CTkEntry(society_section, placeholder_text="Bank Account Info", width=self.form_field_width)
        self.ent_soc_bank.insert(0, self.get_admin_setting('bank_account'))
        self.ent_soc_bank.pack(pady=(0, 6))

        # Logo Upload
        self._add_field_label(society_section, "Society Logo", width=self.form_field_width)
        logo_frame = ctk.CTkFrame(society_section, fg_color="transparent", width=self.form_field_width)
        logo_frame.pack(pady=(0, 12))
        self.lbl_logo = ctk.CTkLabel(logo_frame, text=f"Logo Path: {self.get_admin_setting('logo_path')}")
        self.lbl_logo.pack(side="left", padx=(4, 10))
        ctk.CTkButton(
            logo_frame,
            text="Upload Logo (32x32)",
            fg_color=BUTTON_BLUE,
            hover_color=BUTTON_BLUE_HOVER,
            command=self.upload_logo,
        ).pack(side="left")

        # Fee and member type section
        fee_section = ctk.CTkFrame(content, corner_radius=10)
        fee_section.pack(fill="x", padx=6, pady=(0, 4))
        ctk.CTkLabel(fee_section, text="Fee Structure Settings", font=("Arial", 16, "bold")).pack(anchor="w", padx=16, pady=(10, 4))

        conn = sqlite3.connect('society_pro_v2.db')
        fees = conn.execute("SELECT * FROM fee_config").fetchall(); conn.close()
        self.fee_ents = {}
        fee_table = ctk.CTkFrame(fee_section, fg_color="transparent", width=self.form_field_width)
        fee_table.pack(fill="x", padx=16, pady=(0, 8))
        for t, a in fees:
            f = ctk.CTkFrame(fee_table, fg_color="transparent", width=self.form_field_width)
            f.pack(fill="x", pady=(0, 4))
            f.grid_columnconfigure(0, minsize=300)
            f.grid_columnconfigure(1, minsize=220)
            ctk.CTkLabel(f, text=str(t), anchor="w").grid(row=0, column=0, sticky="w", pady=0)
            e = ctk.CTkEntry(f, width=220)
            e.insert(0, str(a))
            e.grid(row=0, column=1, sticky="w", pady=0)
            self.fee_ents[t] = e

        member_type_header = ctk.CTkFrame(fee_section, fg_color="transparent")
        member_type_header.pack(fill="x", padx=16, pady=(2, 6))
        ctk.CTkLabel(member_type_header, text="Member Types", font=("Arial", 16, "bold")).pack(side="left")
        ctk.CTkButton(
            member_type_header,
            text="+ Add Member Type",
            width=180,
            fg_color=BUTTON_BLUE,
            hover_color=BUTTON_BLUE_HOVER,
            command=lambda: self._add_member_type_row(""),
        ).pack(side="right")

        self.member_type_container = ctk.CTkFrame(fee_section, fg_color="transparent")
        self.member_type_container.pack(fill="x", padx=16, pady=(0, 12))
        self.member_type_rows = []

        for m_type in self.get_member_types():
            self._add_member_type_row(m_type)

        ctk.CTkButton(
            action_bar,
            text="Save All Settings",
            fg_color=BUTTON_GREEN,
            hover_color=BUTTON_GREEN_HOVER,
            height=80,
            command=self.save_admin_settings,
        ).pack(side="right", padx=6, pady=6)

    def upload_logo(self):
        path = filedialog.askopenfilename(filetypes=[("Image files", "*.png *.jpg *.jpeg")])
        if path:
            self.lbl_logo.configure(text=f"Logo Path: {path}")
            self.new_logo_path = path

    def save_admin_settings(self):
        conn = sqlite3.connect('society_pro_v2.db')
        conn.execute("UPDATE admin_settings SET value=? WHERE key='society_name'", (self.ent_soc_name.get(),))
        conn.execute("UPDATE admin_settings SET value=? WHERE key='bank_account'", (self.ent_soc_bank.get(),))
        if hasattr(self, 'new_logo_path'):
            conn.execute("UPDATE admin_settings SET value=? WHERE key='logo_path'", (self.new_logo_path,))
        
        for t, e in self.fee_ents.items():
            conn.execute("UPDATE fee_config SET amount=? WHERE type=?", (e.get(), t))

        raw_types = [ent.get().strip() for _, ent in self.member_type_rows]
        member_types = []
        seen = set()
        for m_type in raw_types:
            if not m_type:
                continue
            key = m_type.lower()
            if key in seen:
                continue
            seen.add(key)
            member_types.append(m_type)
        if not member_types:
            member_types = ["Standard", "Associate", "Life Member"]

        conn.execute("DELETE FROM member_types")
        conn.executemany("INSERT INTO member_types(type) VALUES (?)", [(m_type,) for m_type in member_types])
        
        conn.commit(); conn.close()
        self._show_notification("All settings updated.", level="success")

    def _normalize_text(self, value):
        return str(value or "").strip().casefold()

    def _resolve_choice_case_insensitive(self, raw_value, options, default_value=""):
        cleaned = str(raw_value or "").strip()
        if not cleaned:
            return default_value
        option_map = {self._normalize_text(opt): opt for opt in options}
        return option_map.get(self._normalize_text(cleaned), cleaned)

    def _format_import_global_contact(self, country_raw, value_raw, is_id=False):
        # Keep imported storage aligned with manual UI format: "Country: Value".
        country = str(country_raw or "").strip()
        value = str(value_raw or "").strip()
        if not value:
            return ""

        country_map = {self._normalize_text(r): r for r in self.global_regions}

        # Backward compatibility: if spreadsheet provides "Country: Value" in one column.
        if not country and ":" in value:
            maybe_country, remainder = value.split(":", 1)
            canonical = country_map.get(self._normalize_text(maybe_country))
            if canonical:
                country = canonical
                value = remainder.strip()

        if country:
            country = country_map.get(self._normalize_text(country), country)

        if is_id:
            expected_prefix = self.region_id_prefix.get(country, "ID-") if country else ""
            if expected_prefix:
                upper_value = value.upper()
                if not upper_value.startswith(expected_prefix.upper()) and not re.match(r"^[A-Z]{2}-", upper_value):
                    value = f"{expected_prefix}{value}"
        else:
            expected_prefix = self.region_phone_prefix.get(country, "+") if country else ""
            if expected_prefix and not value.startswith(expected_prefix) and not value.startswith("+"):
                value = f"{expected_prefix}{value}"

        return f"{country}: {value}" if country else value

    def _get_member_import_template_path(self):
        base_dir = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
        return os.path.join(base_dir, "member_import_template.xlsx")

    def _ensure_member_import_template(self):
        try:
            openpyxl_module = importlib.import_module("openpyxl")
        except Exception:
            self._show_notification("Template creation requires openpyxl. Install it to continue.", level="error")
            return None

        template_path = self._get_member_import_template_path()
        workbook = openpyxl_module.Workbook()
        sheet = workbook.active
        sheet.title = "Members"
        headers = [
            "Name",
            "Age",
            "Profession",
            "Member Type",
            "Address",
            "ID Country",
            "Global ID",
            "Mobile Country",
            "Global Mobile",
            "Home Country",
            "Global Home",
        ]
        sheet.append(headers)
        sheet.append([
            "Jane Doe",
            33,
            "Engineer",
            "Standard",
            "12 Example Street, Kuala Lumpur",
            "Malaysia",
            "900101145678",
            "Malaysia",
            "0123456789",
            "Malaysia",
            "0123456789",
        ])

        # Hidden list sheet drives strict dropdown choices for template users.
        list_sheet = workbook.create_sheet("Lists")
        list_sheet["A1"] = "Profession"
        list_sheet["B1"] = "Member Type"
        list_sheet["C1"] = "Country"

        member_types = self.get_member_types()
        max_rows = max(len(self.profs), len(member_types), len(self.global_regions))
        for idx in range(max_rows):
            if idx < len(self.profs):
                list_sheet.cell(row=idx + 2, column=1, value=self.profs[idx])
            if idx < len(member_types):
                list_sheet.cell(row=idx + 2, column=2, value=member_types[idx])
            if idx < len(self.global_regions):
                list_sheet.cell(row=idx + 2, column=3, value=self.global_regions[idx])

        last_prof_row = len(self.profs) + 1
        last_member_type_row = len(member_types) + 1
        last_country_row = len(self.global_regions) + 1

        DataValidation = openpyxl_module.worksheet.datavalidation.DataValidation
        prof_validation = DataValidation(
            type="list",
            formula1=f"=Lists!$A$2:$A${last_prof_row}",
            allow_blank=True,
            showDropDown=False,
            showErrorMessage=True,
            errorStyle="stop",
            errorTitle="Invalid Profession",
            error="Choose a Profession from the dropdown list only.",
        )
        member_type_validation = DataValidation(
            type="list",
            formula1=f"=Lists!$B$2:$B${last_member_type_row}",
            allow_blank=True,
            showDropDown=False,
            showErrorMessage=True,
            errorStyle="stop",
            errorTitle="Invalid Member Type",
            error="Choose a Member Type from the dropdown list only.",
        )
        country_validation = DataValidation(
            type="list",
            formula1=f"=Lists!$C$2:$C${last_country_row}",
            allow_blank=True,
            showDropDown=False,
            showErrorMessage=True,
            errorStyle="stop",
            errorTitle="Invalid Country",
            error="Choose a Country from the dropdown list only.",
        )

        sheet.add_data_validation(prof_validation)
        sheet.add_data_validation(member_type_validation)
        sheet.add_data_validation(country_validation)
        prof_validation.add("C2:C5000")
        member_type_validation.add("D2:D5000")
        country_validation.add("F2:F5000")
        country_validation.add("H2:H5000")
        country_validation.add("J2:J5000")

        list_sheet.sheet_state = "hidden"
        workbook.save(template_path)
        return template_path

    def open_member_import_template(self):
        template_path = self._ensure_member_import_template()
        if not template_path:
            return

        try:
            if hasattr(os, "startfile"):
                os.startfile(template_path)
            else:
                webbrowser.open(f"file://{template_path}")
            self._show_notification("Import template opened.", level="success")
        except Exception as exc:
            self._show_notification(f"Unable to open template: {exc}", level="error")

    def import_members_from_excel(self):
        try:
            openpyxl_module = importlib.import_module("openpyxl")
        except Exception:
            self._show_notification("Member import requires openpyxl. Install it to continue.", level="error")
            return

        file_path = filedialog.askopenfilename(
            title="Import Member Basic Details",
            filetypes=[("Excel Workbook", "*.xlsx *.xlsm")],
        )
        if not file_path:
            return

        try:
            workbook = openpyxl_module.load_workbook(file_path, data_only=True)
            sheet = workbook.active
        except Exception as exc:
            self._show_notification(f"Failed to read Excel file: {exc}", level="error")
            return

        header_row = next(sheet.iter_rows(min_row=1, max_row=1, values_only=True), None)
        if not header_row:
            self._show_notification("Import file is empty.", level="warning")
            return

        def keyify(value):
            return re.sub(r"[^a-z0-9]", "", str(value or "").strip().casefold())

        alias_to_field = {
            "name": "name",
            "fullname": "name",
            "membername": "name",
            "age": "age",
            "profession": "profession",
            "job": "profession",
            "membertype": "member_type",
            "type": "member_type",
            "address": "address",
            "idcountry": "global_id_country",
            "globalidcountry": "global_id_country",
            "idregion": "global_id_country",
            "globalidregion": "global_id_country",
            "globalid": "global_id_no",
            "globalidno": "global_id_no",
            "id": "global_id_no",
            "mobilecountry": "global_mobile_country",
            "globalmobilecountry": "global_mobile_country",
            "mobileregion": "global_mobile_country",
            "globalmobileregion": "global_mobile_country",
            "globalmobile": "global_mobile_no",
            "globalmobileno": "global_mobile_no",
            "mobile": "global_mobile_no",
            "mobileno": "global_mobile_no",
            "phone": "global_mobile_no",
            "homecountry": "global_home_country",
            "globalhomecountry": "global_home_country",
            "homeregion": "global_home_country",
            "globalhomeregion": "global_home_country",
            "globalhome": "global_home_no",
            "globalhomeno": "global_home_no",
            "home": "global_home_no",
            "homeno": "global_home_no",
        }

        header_index_map = {}
        for idx, header in enumerate(header_row):
            normalized = keyify(header)
            field_name = alias_to_field.get(normalized)
            if field_name and field_name not in header_index_map:
                header_index_map[field_name] = idx

        if "name" not in header_index_map:
            self._show_notification("Import requires at least a Name column.", level="error")
            return

        member_types = self.get_member_types()
        profession_choices = list(self.profs)

        conn = sqlite3.connect('society_pro_v2.db')
        cur = conn.cursor()
        existing_rows = cur.execute(
            """SELECT COALESCE(name, ''), COALESCE(global_id_no, ''), COALESCE(global_mobile_no, ''), COALESCE(global_home_no, '')
               FROM members
               WHERE COALESCE(revoked, 0) = 0"""
        ).fetchall()

        existing_names = {self._normalize_text(r[0]) for r in existing_rows if self._normalize_text(r[0])}
        existing_ids = {self._normalize_text(r[1]) for r in existing_rows if self._normalize_text(r[1])}
        existing_mobile = {self._normalize_text(r[2]) for r in existing_rows if self._normalize_text(r[2])}
        existing_home = {self._normalize_text(r[3]) for r in existing_rows if self._normalize_text(r[3])}

        inserted_count = 0
        skipped_count = 0
        invalid_choice_count = 0

        profession_map = {self._normalize_text(v): v for v in profession_choices}
        member_type_map = {self._normalize_text(v): v for v in member_types}

        for row in sheet.iter_rows(min_row=2, values_only=True):
            if not row:
                continue

            def get_value(field_name):
                col_idx = header_index_map.get(field_name)
                if col_idx is None or col_idx >= len(row):
                    return ""
                raw = row[col_idx]
                return "" if raw is None else str(raw).strip()

            name = get_value("name")
            if not name:
                skipped_count += 1
                continue

            age_raw = get_value("age")
            age_digits = re.sub(r"[^0-9]", "", age_raw)
            age_value = int(age_digits) if age_digits else None

            profession_raw = get_value("profession")
            if profession_raw:
                profession = profession_map.get(self._normalize_text(profession_raw))
                if not profession:
                    skipped_count += 1
                    invalid_choice_count += 1
                    continue
            else:
                profession = ""

            member_type_raw = get_value("member_type")
            default_member_type = "Standard" if "Standard" in member_types else member_types[0]
            if member_type_raw:
                member_type = member_type_map.get(self._normalize_text(member_type_raw))
                if not member_type:
                    skipped_count += 1
                    invalid_choice_count += 1
                    continue
            else:
                member_type = default_member_type

            address = get_value("address")
            global_id_country = get_value("global_id_country")
            global_mobile_country = get_value("global_mobile_country")
            global_home_country = get_value("global_home_country")

            global_id = self._format_import_global_contact(
                global_id_country,
                get_value("global_id_no"),
                is_id=True,
            )
            global_mobile = self._format_import_global_contact(
                global_mobile_country,
                get_value("global_mobile_no"),
                is_id=False,
            )
            global_home = self._format_import_global_contact(
                global_home_country,
                get_value("global_home_no"),
                is_id=False,
            )

            norm_name = self._normalize_text(name)
            norm_id = self._normalize_text(global_id)
            norm_mobile = self._normalize_text(global_mobile)
            norm_home = self._normalize_text(global_home)

            duplicate = (
                (norm_name and norm_name in existing_names)
                or (norm_id and norm_id in existing_ids)
                or (norm_mobile and norm_mobile in existing_mobile)
                or (norm_home and norm_home in existing_home)
            )
            if duplicate:
                skipped_count += 1
                continue

            cur.execute(
                "INSERT INTO members (name, age, profession, member_type, global_id_no, global_mobile_no, global_home_no, address, membership_added_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    name,
                    age_value,
                    profession,
                    member_type,
                    global_id,
                    global_mobile,
                    global_home,
                    address,
                    datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                ),
            )
            inserted_count += 1

            if norm_name:
                existing_names.add(norm_name)
            if norm_id:
                existing_ids.add(norm_id)
            if norm_mobile:
                existing_mobile.add(norm_mobile)
            if norm_home:
                existing_home.add(norm_home)

        conn.commit()
        conn.close()

        if invalid_choice_count:
            self._show_notification(
                f"Import done. Added: {inserted_count}, Skipped: {skipped_count}. Invalid Profession/Member Type rows: {invalid_choice_count}.",
                level="success" if inserted_count else "warning",
            )
        else:
            self._show_notification(
                f"Import done. Added: {inserted_count}, Skipped existing/invalid: {skipped_count}.",
                level="success" if inserted_count else "info",
            )

    # --- 2. REGISTRATION ---
    def show_register(self):
        self.clear_main()
        action_bar = self._create_bottom_action_bar()
        ctk.CTkLabel(self.main_frame, text="New Membership Registration", font=("Arial", 22, "bold")).pack(pady=(2, 6))
        form = ctk.CTkFrame(self.main_frame, width=self.form_section_width, fg_color="transparent")
        form.pack(fill="both", expand=True, pady=(0, 3))

        self._add_field_label(form, "Full Name")
        self.ent_name = ctk.CTkEntry(form, placeholder_text="Full Name", width=self.form_field_width)
        self.ent_name.pack()
        self._add_field_label(form, "Age")
        self.ent_age = ctk.CTkEntry(form, placeholder_text="Age", width=self.form_field_width)
        self.ent_age.pack()
        self._add_field_label(form, "Profession")
        self.opt_prof = ctk.CTkOptionMenu(form, values=self.profs, width=self.form_field_width)
        self.opt_prof.pack()

        self._add_field_label(form, "Member Type")
        self.member_type_options = self.get_member_types()
        self.opt_member_type = ctk.CTkOptionMenu(form, values=self.member_type_options, width=self.form_field_width)
        self.opt_member_type.set("Standard" if "Standard" in self.member_type_options else self.member_type_options[0])
        self.opt_member_type.pack()

        self._add_field_label(form, "Address")
        self.ent_address = ctk.CTkTextbox(form, width=self.form_field_width, height=80)
        self.ent_address.pack(pady=(0, 2))

        ctk.CTkLabel(form, text="Global Identification Number", anchor="w", width=self.form_field_width, font=("Arial", 13, "bold")).pack(pady=(2, 1))
        self.id_row = ctk.CTkFrame(form, fg_color="transparent", width=self.form_field_width, height=34)
        self.id_row.pack(pady=(0, 1))
        self.id_row.pack_propagate(False)
        self.opt_id_region = ctk.CTkOptionMenu(self.id_row, values=self.global_regions, width=170, command=self._on_id_region_change)
        self.opt_id_region.set("Malaysia")
        self.opt_id_region.pack(side="left", padx=(0, 8))
        self.ent_global_id = ctk.CTkEntry(self.id_row, placeholder_text="Identification Number", width=362)
        self.ent_global_id.insert(0, "MY-")
        self.ent_global_id.pack(side="left")

        ctk.CTkLabel(form, text="Global Mobile Number", anchor="w", width=self.form_field_width, font=("Arial", 13, "bold")).pack(pady=(2, 1))
        self.mobile_row = ctk.CTkFrame(form, fg_color="transparent", width=self.form_field_width, height=34)
        self.mobile_row.pack(pady=(0, 1))
        self.mobile_row.pack_propagate(False)
        self.opt_mobile_region = ctk.CTkOptionMenu(self.mobile_row, values=self.global_regions, width=170, command=self._on_mobile_region_change)
        self.opt_mobile_region.set("Malaysia")
        self.opt_mobile_region.pack(side="left", padx=(0, 8))
        self.ent_global_mobile = ctk.CTkEntry(self.mobile_row, placeholder_text="Mobile Number", width=362)
        self.ent_global_mobile.insert(0, "+60")
        self.ent_global_mobile.pack(side="left")

        ctk.CTkLabel(form, text="Global Home Number", anchor="w", width=self.form_field_width, font=("Arial", 13, "bold")).pack(pady=(2, 1))
        self.home_row = ctk.CTkFrame(form, fg_color="transparent", width=self.form_field_width, height=34)
        self.home_row.pack(pady=(0, 1))
        self.home_row.pack_propagate(False)
        self.opt_home_region = ctk.CTkOptionMenu(self.home_row, values=self.global_regions, width=170, command=self._on_home_region_change)
        self.opt_home_region.set("Malaysia")
        self.opt_home_region.pack(side="left", padx=(0, 8))
        self.ent_global_home = ctk.CTkEntry(self.home_row, placeholder_text="Home Number", width=362)
        self.ent_global_home.insert(0, "+60")
        self.ent_global_home.pack(side="left")

        ctk.CTkLabel(form, text="Initial Payment Selection", font=("Arial", 15, "bold")).pack(pady=(3, 1))
        conn = sqlite3.connect('society_pro_v2.db'); fees = conn.execute("SELECT type, amount FROM fee_config").fetchall(); conn.close()
        fee_map = {f_t: f_a for f_t, f_a in fees}

        self.init_payment_choice = ctk.StringVar(value="entrance")
        option_entrance = f"Entrance Fee only (RM{fee_map.get('Entrance Fee', 0):.2f})"
        option_entrance_annual = (
            f"Entrance Fee + Annual Subscription "
            f"(RM{fee_map.get('Entrance Fee', 0) + fee_map.get('Annual Subscription', 0):.2f})"
        )
        option_life = f"Life Membership only (RM{fee_map.get('Life Membership', 0):.2f})"

        self.payment_options = {
            option_entrance: "entrance",
            option_entrance_annual: "entrance_annual",
            option_life: "life",
        }
        self.init_payment_menu = ctk.CTkOptionMenu(
            form,
            values=list(self.payment_options.keys()),
            width=self.form_field_width,
        )
        self.init_payment_menu.set(option_entrance)
        self.init_payment_menu.pack(pady=(0, 1))

        self.register_fee_map = fee_map

        self._add_field_label(form, "Payment Date")
        self.ent_pay_date = self._create_date_input(form, width=self.form_field_width)
        self.ent_pay_date.pack()
        self._add_field_label(form, "Reference Number")
        self.ent_ref = ctk.CTkEntry(form, placeholder_text="Bank Ref No.", width=self.form_field_width)
        self.ent_ref.pack()
        self._add_field_label(form, "Payment Method")
        self.opt_method = ctk.CTkOptionMenu(form, values=self.banks, width=self.form_field_width)
        self.opt_method.pack()

        import_help = ctk.CTkFrame(form, fg_color="transparent")
        import_help.pack(fill="x", pady=(6, 0))
        ctk.CTkLabel(import_help, text="Bulk Import:", font=("Arial", 12, "bold")).pack(side="left", padx=(0, 6))
        template_link = ctk.CTkLabel(
            import_help,
            text="Open Basic Excel Template",
            text_color=BUTTON_BLUE,
            cursor="hand2",
            font=("Arial", 12, "underline"),
        )
        template_link.pack(side="left")
        template_link.bind("<Button-1>", lambda _event: self.open_member_import_template())

        ctk.CTkButton(
            action_bar,
            text="Import Members (Excel)",
            fg_color=BUTTON_BLUE,
            hover_color=BUTTON_BLUE_HOVER,
            width=210,
            height=80,
            command=self.import_members_from_excel,
        ).pack(side="right", padx=6, pady=6)

        ctk.CTkButton(
            action_bar,
            text="Register & Print Receipt",
            fg_color=BUTTON_GREEN,
            hover_color=BUTTON_GREEN_HOVER,
            width=240,
            height=80,
            command=self.save_reg,
        ).pack(side="right", padx=6, pady=6)

    def save_reg(self):
        name = self.ent_name.get().strip()
        age, prof, date, ref, method = self.ent_age.get(), self.opt_prof.get(), self.ent_pay_date.get(), self.ent_ref.get() or "N/A", self.opt_method.get()
        member_type = self.opt_member_type.get()
        address = self.ent_address.get("1.0", "end").strip()
        global_id = f"{self.opt_id_region.get()}: {self.ent_global_id.get().strip()}"
        global_mobile = f"{self.opt_mobile_region.get()}: {self.ent_global_mobile.get().strip()}"
        global_home = f"{self.opt_home_region.get()}: {self.ent_global_home.get().strip()}"
        payment_choice = self.payment_options.get(self.init_payment_menu.get(), "entrance")

        if payment_choice == "entrance":
            selected = [("Entrance Fee", self.register_fee_map.get("Entrance Fee", 0.0))]
        elif payment_choice == "entrance_annual":
            selected = [
                ("Entrance Fee", self.register_fee_map.get("Entrance Fee", 0.0)),
                ("Annual Subscription", self.register_fee_map.get("Annual Subscription", 0.0)),
            ]
        elif payment_choice == "life":
            selected = [("Life Membership", self.register_fee_map.get("Life Membership", 0.0))]
        else:
            selected = []

        if name and age and selected:
            conn = sqlite3.connect('society_pro_v2.db'); cur = conn.cursor()
            membership_added_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cur.execute(
                "INSERT INTO members (name, age, profession, member_type, global_id_no, global_mobile_no, global_home_no, address, membership_added_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (name, age, prof, member_type, global_id, global_mobile, global_home, address, membership_added_at),
            )
            m_id = cur.lastrowid
            total = 0; receipt_items = []
            for f_t, f_a in selected:
                cur.execute("INSERT INTO payments (member_id, fee_type, fee_paid, pay_date, ref_no, pay_method) VALUES (?,?,?,?,?,?)", (m_id, f_t, f_a, date, ref, method))
                total += f_a; receipt_items.append((f_t, f_a, date, ref, method))
            conn.commit(); conn.close()
            self.generate_professional_pdf(name, receipt_items, total)
            self._show_notification(f"Member {name} registered.", level="success")
        else:
            self._show_notification("Check Name, Age, and Fees.", level="warning")

    # --- 3. RENEWAL ---
    def show_renewal(self):
        self.clear_main()
        action_bar = self._create_bottom_action_bar()
        ctk.CTkLabel(self.main_frame, text="Renewal Payment", font=("Arial", 22, "bold")).pack(pady=(2, 6))
        form = ctk.CTkFrame(self.main_frame, width=self.form_section_width, fg_color="transparent")
        form.pack(fill="both", expand=True, pady=(0, 3))

        conn = sqlite3.connect('society_pro_v2.db')
        m_rows = conn.execute(
            """SELECT id, name
               FROM members
               WHERE COALESCE(revoked, 0) = 0
             AND LOWER(COALESCE(member_type, '')) != 'life member'
               ORDER BY id"""
        ).fetchall()
        f_rows = conn.execute("SELECT type, amount FROM fee_config WHERE type != 'Entrance Fee'").fetchall()
        conn.close()

        if not m_rows:
            self._show_notification("No eligible members for renewal (revoked/life members are excluded).", level="info")
            return
        m_list = [f"{r[0]} - {r[1]}" for r in m_rows]
        self._add_field_label(form, "Member")
        self.opt_member = ctk.CTkOptionMenu(form, values=m_list, width=self.form_field_width)
        self.opt_member.pack()
        
        self.renew_fee_var = ctk.StringVar()
        ctk.CTkLabel(form, text="Renewal Fee Type", font=("Arial", 15, "bold")).pack(pady=(6, 3))
        fee_frame = ctk.CTkFrame(form, fg_color="transparent", width=self.form_field_width)
        fee_frame.pack(pady=(0, 2))
        fee_frame.pack_propagate(False)
        for f_t, f_a in f_rows:
            ctk.CTkRadioButton(fee_frame, text=f"{f_t} (RM{f_a:.2f})", variable=self.renew_fee_var, value=f_t).pack(pady=1, anchor="w", padx=6)

        self._add_field_label(form, "Payment Date")
        self.ent_r_date = self._create_date_input(form, width=self.form_field_width)
        self.ent_r_date.pack()
        self._add_field_label(form, "Reference Number")
        self.ent_r_ref = ctk.CTkEntry(form, placeholder_text="Ref No.", width=self.form_field_width)
        self.ent_r_ref.pack()
        self._add_field_label(form, "Payment Method")
        self.opt_r_method = ctk.CTkOptionMenu(form, values=self.banks, width=self.form_field_width)
        self.opt_r_method.pack()
        ctk.CTkButton(
            action_bar,
            text="Process Payment",
            fg_color=BUTTON_GREEN,
            hover_color=BUTTON_GREEN_HOVER,
            width=220,
            height=80,
            command=self.save_renewal,
        ).pack(side="right", padx=6, pady=6)

    def save_renewal(self):
        m_id = self.opt_member.get().split(" - ")[0]
        m_name = self.opt_member.get().split(" - ")[1]
        f_type = self.renew_fee_var.get()
        conn = sqlite3.connect('society_pro_v2.db'); amt = conn.execute("SELECT amount FROM fee_config WHERE type=?", (f_type,)).fetchone()[0]
        conn.execute("INSERT INTO payments (member_id, fee_type, fee_paid, pay_date, ref_no, pay_method) VALUES (?,?,?,?,?,?)", (m_id, f_type, amt, self.ent_r_date.get(), self.ent_r_ref.get() or "N/A", self.opt_r_method.get()))
        conn.commit(); conn.close()
        self.generate_professional_pdf(m_name, [(f_type, amt, self.ent_r_date.get(), self.ent_r_ref.get() or "N/A", self.opt_r_method.get())], amt)
        self._show_notification("Payment recorded.", level="success")

    # --- 4. RECEIPT DASHBOARD ---
    def show_receipt_menu(self):
        self.clear_main()
        action_bar = self._create_bottom_action_bar()
        header = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        header.pack(fill="x", pady=(0, 20))
        self.rec_search = ctk.StringVar(); self.rec_search.trace_add("write", lambda *args: self.refresh_receipt_table())
        ctk.CTkEntry(header, placeholder_text="Search Name...", width=300, textvariable=self.rec_search).pack(side="right")

        f = ctk.CTkFrame(self.main_frame); f.pack(fill="both", expand=True)
        cols = ("ID", "Name", "Type", "Amount", "Method", "Date", "Ref")
        self.rec_table = ttk.Treeview(f, columns=cols, show="headings", selectmode="extended")
        for col in cols: self.rec_table.heading(col, text=col); self.rec_table.column(col, anchor="center", width=110)
        self.rec_table.pack(side="left", fill="both", expand=True)

        ctk.CTkButton(
            action_bar,
            text="Print Consolidated Receipt",
            fg_color=BUTTON_GREEN,
            hover_color=BUTTON_GREEN_HOVER,
            height=80,
            command=self.bulk_receipt,
        ).pack(side="right", padx=6, pady=6)
        self.refresh_receipt_table()

    def refresh_receipt_table(self):
        for i in self.rec_table.get_children(): self.rec_table.delete(i)
        q = f"%{self.rec_search.get()}%"
        conn = sqlite3.connect('society_pro_v2.db')
        data = conn.execute('''SELECT p.pay_id, m.name, p.fee_type, p.fee_paid, p.pay_method, p.pay_date, p.ref_no FROM payments p JOIN members m ON p.member_id = m.id WHERE m.name LIKE ? ORDER BY p.pay_id DESC''', (q,)).fetchall(); conn.close()
        for r in data: self.rec_table.insert("", "end", values=r)

    def bulk_receipt(self):
        items = self.rec_table.selection()
        if not items: return
        rows = [self.rec_table.item(i)['values'] for i in items]
        # (ID, Name, Type, Amt, Method, Date, Ref)
        pdf_rows = [(r[2], r[3], r[5], r[6], r[4]) for r in rows]
        total = sum(float(r[3]) for r in rows)
        self.generate_professional_pdf(rows[0][1], pdf_rows, total)
        self._show_notification("Consolidated receipt generated.", level="success")

    # --- 5. PROFESSIONAL PDF ENGINE (LOGO + BANK + FULL TABLE) ---
    def generate_professional_pdf(self, name, items, total):
        try:
            soc_name = self.get_admin_setting('society_name')
            bank_info = self.get_admin_setting('bank_account')
            logo_path = self.get_admin_setting('logo_path')
            filename = f"{re.sub(r'[^a-zA-Z0-9]', '', str(name)).lower()}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

            pdf = FPDF()
            pdf.add_page()
            
            # Header with Logo
            if logo_path and os.path.exists(logo_path):
                pdf.image(logo_path, 10, 8, 20)
            
            pdf.set_font("Helvetica", 'B', 16)
            pdf.cell(0, 10, soc_name.upper(), ln=True, align='C')
            pdf.set_font("Helvetica", size=10)
            pdf.cell(0, 5, f"Account: {bank_info}", ln=True, align='C')
            pdf.ln(10)
            pdf.set_font("Helvetica", 'B', 14)
            pdf.cell(0, 10, "OFFICIAL PAYMENT RECEIPT", ln=True, align='C')
            pdf.ln(5)
            
            pdf.set_font("Helvetica", 'B', 11)
            pdf.cell(0, 10, f"Member: {name}", ln=True)
            
            # Full Detailed Table
            pdf.set_font("Helvetica", 'B', 9)
            pdf.cell(50, 8, "Fee Type", 1); pdf.cell(30, 8, "Date", 1); pdf.cell(40, 8, "Ref No", 1); pdf.cell(35, 8, "Method", 1); pdf.cell(35, 8, "Amount (RM)", 1, ln=True)
            
            pdf.set_font("Helvetica", size=9)
            for f_t, f_a, f_d, f_r, f_m in items:
                pdf.cell(50, 8, str(f_t), 1); pdf.cell(30, 8, str(f_d), 1); pdf.cell(40, 8, str(f_r), 1); pdf.cell(35, 8, str(f_m), 1); pdf.cell(35, 8, f"{float(f_a):.2f}", 1, ln=True)
            
            pdf.set_font("Helvetica", 'B', 10)
            pdf.cell(155, 10, "GRAND TOTAL", 1, align='R'); pdf.cell(35, 10, f"RM {float(total):.2f}", 1, ln=True, align='C')
            
            pdf.ln(10)
            pdf.set_font("Helvetica", 'I', 8)
            pdf.cell(0, 5, "This is a computer-generated receipt. Please keep for your records.", align='C')
            
            pdf.output(filename)
        except Exception as e:
            self._show_notification(f"PDF generation failed: {e}", level="error")

    # --- MEMBER DETAILS & RECORDS ---
    def show_member_details(self):
        self.clear_main()
        action_bar = self._create_bottom_action_bar()
        header = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        header.pack(fill="x", pady=(0, 10))
        self.mem_search = ctk.StringVar(); self.mem_search.trace_add("write", lambda *args: self.refresh_member_table())
        ctk.CTkEntry(header, placeholder_text="Search Name...", width=400, textvariable=self.mem_search).pack(side="right")
        f = ctk.CTkFrame(self.main_frame); f.pack(fill="both", expand=True)
        cols = (
            "ID",
            "Name",
            "Age",
            "Profession",
            "Member Type",
            "Address",
            "Global ID",
            "Global Mobile",
            "Global Home",
            "Revoked",
            "Revoked At",
            "Membership Added At",
            "Payments",
            "Total Paid (RM)",
            "Last Payment",
        )
        self.mem_table = ttk.Treeview(f, columns=cols, show="headings")
        for c in cols:
            self.mem_table.heading(c, text=c)

        self.mem_table.column("ID", anchor="center", width=60)
        self.mem_table.column("Name", anchor="w", width=150)
        self.mem_table.column("Age", anchor="center", width=60)
        self.mem_table.column("Profession", anchor="w", width=130)
        self.mem_table.column("Member Type", anchor="w", width=120)
        self.mem_table.column("Address", anchor="w", width=220)
        self.mem_table.column("Global ID", anchor="w", width=130)
        self.mem_table.column("Global Mobile", anchor="w", width=130)
        self.mem_table.column("Global Home", anchor="w", width=130)
        self.mem_table.column("Revoked", anchor="center", width=80)
        self.mem_table.column("Revoked At", anchor="center", width=140)
        self.mem_table.column("Membership Added At", anchor="center", width=160)
        self.mem_table.column("Payments", anchor="center", width=80)
        self.mem_table.column("Total Paid (RM)", anchor="center", width=110)
        self.mem_table.column("Last Payment", anchor="center", width=110)
        self.mem_table.pack(side="left", fill="both", expand=True)
        ctk.CTkButton(
            action_bar,
            text="Export to Excel",
            fg_color=BUTTON_GREEN,
            hover_color=BUTTON_GREEN_HOVER,
            width=180,
            height=80,
            command=lambda: self._export_treeview_to_xlsx(self.mem_table, "member_details.xlsx"),
        ).pack(side="right", padx=6, pady=6)
        ctk.CTkButton(
            action_bar,
            text="Edit Member Details",
            fg_color=BUTTON_BLUE,
            hover_color=BUTTON_BLUE_HOVER,
            width=190,
            height=80,
            command=self.edit_selected_member,
        ).pack(side="right", padx=6, pady=6)
        ctk.CTkButton(
            action_bar,
            text="Revoke Membership",
            fg_color=BUTTON_RED,
            hover_color=BUTTON_RED_HOVER,
            width=190,
            height=80,
            command=self.revoke_selected_member,
        ).pack(side="right", padx=6, pady=6)
        self.refresh_member_table()

    def revoke_selected_member(self):
        selected_items = self.mem_table.selection()
        if not selected_items:
            self._show_notification("Select one member to revoke.", level="warning")
            return

        item_values = self.mem_table.item(selected_items[0]).get("values", [])
        if not item_values:
            self._show_notification("Unable to read selected member.", level="error")
            return

        member_id = item_values[0]
        member_name = item_values[1] if len(item_values) > 1 else "Selected member"
        is_revoked = str(item_values[9]).strip().lower() == "yes" if len(item_values) > 9 else False

        if is_revoked:
            self._show_notification("Selected member is already revoked.", level="info")
            return

        confirmed = messagebox.askyesno(
            "Confirm Revoke",
            f"Revoke membership for {member_name}?",
            parent=self,
        )
        if not confirmed:
            return

        revoked_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = sqlite3.connect('society_pro_v2.db')
        conn.execute(
            "UPDATE members SET revoked=1, revoked_at=? WHERE id=?",
            (revoked_at, member_id),
        )
        conn.commit()
        conn.close()

        self.refresh_member_table()
        self._show_notification(f"Membership revoked for {member_name}.", level="success")

    def edit_selected_member(self):
        selected_items = self.mem_table.selection()
        if not selected_items:
            self._show_notification("Select one member to edit.", level="warning")
            return

        item_values = self.mem_table.item(selected_items[0]).get("values", [])
        if not item_values:
            self._show_notification("Unable to read selected member.", level="error")
            return

        member_id = item_values[0]
        conn = sqlite3.connect('society_pro_v2.db')
        row = conn.execute(
            """SELECT id, name, age, profession, COALESCE(member_type, ''), COALESCE(address, ''),
                      COALESCE(global_id_no, ''), COALESCE(global_mobile_no, ''), COALESCE(global_home_no, '')
               FROM members WHERE id=?""",
            (member_id,),
        ).fetchone()
        conn.close()

        if not row:
            self._show_notification("Member not found.", level="error")
            return

        _, name, age, profession, member_type, address, global_id, global_mobile, global_home = row

        edit_win = ctk.CTkToplevel(self)
        edit_win.title(f"Edit Member - {name}")
        edit_win.geometry("760x760")
        edit_win.transient(self)
        edit_win.grab_set()

        container = ctk.CTkFrame(edit_win, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=14, pady=14)

        ctk.CTkLabel(container, text="Edit Member Details", font=("Arial", 22, "bold")).pack(pady=(2, 8))

        def add_label(text):
            ctk.CTkLabel(
                container,
                text=text,
                anchor="w",
                width=650,
                font=("Arial", 13, "bold"),
            ).pack(pady=(2, 1))

        add_label("Full Name")
        ent_name = ctk.CTkEntry(container, width=650)
        ent_name.insert(0, str(name or ""))
        ent_name.pack()

        add_label("Age")
        ent_age = ctk.CTkEntry(container, width=650)
        ent_age.insert(0, str(age or ""))
        ent_age.pack()

        add_label("Profession")
        profession_options = list(self.profs)
        if profession and profession not in profession_options:
            profession_options.append(profession)
        opt_prof = ctk.CTkOptionMenu(container, values=profession_options, width=650)
        opt_prof.set(profession if profession else profession_options[0])
        opt_prof.pack()

        add_label("Member Type")
        member_types = self.get_member_types()
        if member_type and member_type not in member_types:
            member_types.append(member_type)
        opt_member_type = ctk.CTkOptionMenu(container, values=member_types, width=650)
        opt_member_type.set(member_type if member_type else member_types[0])
        opt_member_type.pack()

        add_label("Address")
        txt_address = ctk.CTkTextbox(container, width=650, height=90)
        txt_address.insert("1.0", str(address or ""))
        txt_address.pack(pady=(0, 2))

        id_country, id_value = self._split_global_contact(global_id, is_id=True)
        mobile_country, mobile_value = self._split_global_contact(global_mobile, is_id=False)
        home_country, home_value = self._split_global_contact(global_home, is_id=False)

        add_label("Global Identification Number")
        id_row = ctk.CTkFrame(container, fg_color="transparent", width=650, height=34)
        id_row.pack(pady=(0, 1))
        id_row.pack_propagate(False)
        opt_id_country = ctk.CTkOptionMenu(id_row, values=self.global_regions, width=200)
        opt_id_country.set(id_country)
        opt_id_country.pack(side="left", padx=(0, 8))
        ent_id = ctk.CTkEntry(id_row, width=442)
        ent_id.insert(0, id_value)
        ent_id.pack(side="left")

        add_label("Global Mobile Number")
        mobile_row = ctk.CTkFrame(container, fg_color="transparent", width=650, height=34)
        mobile_row.pack(pady=(0, 1))
        mobile_row.pack_propagate(False)
        opt_mobile_country = ctk.CTkOptionMenu(mobile_row, values=self.global_regions, width=200)
        opt_mobile_country.set(mobile_country)
        opt_mobile_country.pack(side="left", padx=(0, 8))
        ent_mobile = ctk.CTkEntry(mobile_row, width=442)
        ent_mobile.insert(0, mobile_value)
        ent_mobile.pack(side="left")

        add_label("Global Home Number")
        home_row = ctk.CTkFrame(container, fg_color="transparent", width=650, height=34)
        home_row.pack(pady=(0, 1))
        home_row.pack_propagate(False)
        opt_home_country = ctk.CTkOptionMenu(home_row, values=self.global_regions, width=200)
        opt_home_country.set(home_country)
        opt_home_country.pack(side="left", padx=(0, 8))
        ent_home = ctk.CTkEntry(home_row, width=442)
        ent_home.insert(0, home_value)
        ent_home.pack(side="left")

        btn_row = ctk.CTkFrame(container, fg_color="transparent")
        btn_row.pack(fill="x", pady=(10, 8))

        def save_member_update():
            upd_name = ent_name.get().strip()
            upd_age = ent_age.get().strip()
            upd_prof = opt_prof.get()
            upd_member_type = opt_member_type.get()
            upd_address = txt_address.get("1.0", "end").strip()

            if not upd_name:
                self._show_notification("Member name is required.", level="warning")
                return

            upd_global_id = f"{opt_id_country.get()}: {ent_id.get().strip()}" if ent_id.get().strip() else ""
            upd_global_mobile = f"{opt_mobile_country.get()}: {ent_mobile.get().strip()}" if ent_mobile.get().strip() else ""
            upd_global_home = f"{opt_home_country.get()}: {ent_home.get().strip()}" if ent_home.get().strip() else ""

            conn_local = sqlite3.connect('society_pro_v2.db')
            conn_local.execute(
                """UPDATE members
                   SET name=?, age=?, profession=?, member_type=?, address=?,
                       global_id_no=?, global_mobile_no=?, global_home_no=?
                   WHERE id=?""",
                (
                    upd_name,
                    upd_age if upd_age else None,
                    upd_prof,
                    upd_member_type,
                    upd_address,
                    upd_global_id,
                    upd_global_mobile,
                    upd_global_home,
                    member_id,
                ),
            )
            conn_local.commit()
            conn_local.close()

            edit_win.destroy()
            self.refresh_member_table()
            self._show_notification("Member details updated.", level="success")

        ctk.CTkButton(
            btn_row,
            text="Cancel",
            width=160,
            fg_color=BUTTON_RED,
            hover_color=BUTTON_RED_HOVER,
            command=edit_win.destroy,
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            btn_row,
            text="Save Changes",
            width=180,
            fg_color=BUTTON_GREEN,
            hover_color=BUTTON_GREEN_HOVER,
            command=save_member_update,
        ).pack(side="right")

    def refresh_member_table(self):
        for i in self.mem_table.get_children():
            self.mem_table.delete(i)

        q = f"%{self.mem_search.get()}%"
        conn = sqlite3.connect('society_pro_v2.db')
        data = conn.execute(
            '''SELECT m.id,
                      m.name,
                      m.age,
                      m.profession,
                      COALESCE(m.member_type, ''),
                      COALESCE(m.address, ''),
                      COALESCE(m.global_id_no, ''),
                      COALESCE(m.global_mobile_no, ''),
                      COALESCE(m.global_home_no, ''),
                      COALESCE(m.revoked, 0),
                      COALESCE(m.revoked_at, ''),
                                            COALESCE(m.membership_added_at, ''),
                      COUNT(p.pay_id) AS payment_count,
                      COALESCE(SUM(p.fee_paid), 0) AS total_paid,
                      COALESCE(MAX(p.pay_date), '') AS last_payment
               FROM members m
               LEFT JOIN payments p ON p.member_id = m.id
               WHERE m.name LIKE ?
               GROUP BY m.id, m.name, m.age, m.profession, m.member_type, m.address,
                                                m.global_id_no, m.global_mobile_no, m.global_home_no, m.revoked, m.revoked_at, m.membership_added_at
               ORDER BY m.id DESC''',
            (q,),
        ).fetchall()
        conn.close()

        for r in data:
            row = list(r)
            row[9] = "Yes" if int(row[9] or 0) else "No"
            row[13] = f"{float(row[13]):.2f}"
            self.mem_table.insert("", "end", values=row)

    def show_records(self):
        self.clear_main()
        action_bar = self._create_bottom_action_bar()
        header = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        header.pack(fill="x", pady=(0, 10))
        self.log_search = ctk.StringVar(); self.log_search.trace_add("write", lambda *args: self.refresh_records_table())
        ctk.CTkEntry(header, placeholder_text="Search Log...", width=400, textvariable=self.log_search).pack(side="right")
        f = ctk.CTkFrame(self.main_frame); f.pack(fill="both", expand=True)
        cols = ("ID", "Member", "Type", "Amount", "Date", "Method", "Ref")
        self.log_table = ttk.Treeview(f, columns=cols, show="headings")
        for c in cols: self.log_table.heading(c, text=c); self.log_table.column(c, anchor="center")
        self.log_table.pack(side="left", fill="both", expand=True)
        ctk.CTkButton(
            action_bar,
            text="Export to Excel",
            fg_color=BUTTON_GREEN,
            hover_color=BUTTON_GREEN_HOVER,
            width=180,
            height=80,
            command=lambda: self._export_treeview_to_xlsx(self.log_table, "payment_records.xlsx"),
        ).pack(side="right", padx=6, pady=6)
        self.refresh_records_table()

    def refresh_records_table(self):
        for i in self.log_table.get_children(): self.log_table.delete(i)
        q = f"%{self.log_search.get()}%"; conn = sqlite3.connect('society_pro_v2.db')
        data = conn.execute('''SELECT p.pay_id, m.name, p.fee_type, p.fee_paid, p.pay_date, p.pay_method, p.ref_no 
                               FROM payments p JOIN members m ON p.member_id = m.id WHERE m.name LIKE ?''', (q,)).fetchall(); conn.close()
        for r in data: self.log_table.insert("", "end", values=r)

    def show_config(self): self.show_admin_settings()

    def _open_license_file(self):
        base_dir = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
        license_path = os.path.join(base_dir, "LICENSE")

        if not os.path.exists(license_path):
            self._show_notification("license.md not found in app folder.", level="warning")
            return

        try:
            if hasattr(os, "startfile"):
                os.startfile(license_path)
            else:
                webbrowser.open(f"file://{license_path}")
        except Exception as exc:
            self._show_notification(f"Unable to open license file: {exc}", level="error")

    def _open_paypal_donation(self):
        try:
            webbrowser.open("https://paypal.me/fbakhda")
        except Exception as exc:
            self._show_notification(f"Unable to open PayPal donation link: {exc}", level="error")

    def _find_touchngo_image_path(self):
        base_dir = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
        preferred_names = [
            "touchngo_qr.jpeg",
            ]

        for name in preferred_names:
            candidate = os.path.join(base_dir, name)
            if os.path.exists(candidate):
                return candidate

        for name in os.listdir(base_dir):
            lowered = name.lower()
            if not lowered.endswith((".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif")):
                continue
            if "touchngo" in lowered or "tng" in lowered or "whatsapp image" in lowered:
                return os.path.join(base_dir, name)

        return None

    def _show_touchngo_donation_image(self):
        image_path = self._find_touchngo_image_path()
        if not image_path:
            self._show_notification("TouchNGo donation image not found in app folder.", level="warning")
            return

        try:
            pil_image_module = importlib.import_module("PIL.Image")
            pil_imagetk_module = importlib.import_module("PIL.ImageTk")
            image_obj = pil_image_module.open(image_path)
            image_obj.thumbnail((420, 520))
            preview_image = pil_imagetk_module.PhotoImage(image_obj)
            self._touchngo_preview_image = preview_image

            popup = ctk.CTkToplevel(self)
            popup.title("Donate via TouchNGo")
            popup.geometry("470x620")
            popup.transient(self)
            popup.grab_set()

            ctk.CTkLabel(popup, text="Donate via TouchNGo", font=("Arial", 18, "bold")).pack(pady=(10, 8))
            img_label = tk.Label(popup, image=preview_image, bg="white")
            img_label.pack(padx=12, pady=(0, 8))
            ctk.CTkLabel(popup, text=os.path.basename(image_path), font=("Arial", 11)).pack(pady=(0, 10))
        except Exception:
            try:
                if hasattr(os, "startfile"):
                    os.startfile(image_path)
                else:
                    webbrowser.open(f"file://{image_path}")
            except Exception as exc:
                self._show_notification(f"Unable to open TouchNGo image: {exc}", level="error")

    def show_about(self):
        self.clear_main()

        build_date = "Unknown"
        try:
            script_path = os.path.abspath(__file__) if "__file__" in globals() else os.path.abspath("society-membership.py")
            build_date = datetime.datetime.fromtimestamp(os.path.getmtime(script_path)).strftime("%d %b %Y")
        except Exception:
            pass

        ctk.CTkLabel(self.main_frame, text="About", font=("Arial", 24, "bold")).pack(pady=(8, 10))

        card = ctk.CTkFrame(self.main_frame, corner_radius=12, width=700)
        card.pack(fill="x", padx=20, pady=(0, 10))

        ctk.CTkLabel(card, text="Product: Society Pro - Community Edition", anchor="w", font=("Arial", 15, "bold")).pack(fill="x", padx=20, pady=(18, 6))
        ctk.CTkLabel(card, text=f"Build Date: {build_date}", anchor="w", font=("Arial", 14)).pack(fill="x", padx=20, pady=4)
        ctk.CTkLabel(card, text="Author: Firesh Kishor Kumar @ Firesh Bakhda", anchor="w", font=("Arial", 14)).pack(fill="x", padx=20, pady=4)
        ctk.CTkLabel(card, text="Author Email: firesh@gmail.com", anchor="w", font=("Arial", 14)).pack(fill="x", padx=20, pady=4)

        donate_row = ctk.CTkFrame(card, fg_color="transparent")
        donate_row.pack(fill="x", padx=20, pady=(8, 0))
        ctk.CTkLabel(donate_row, text="Support:", font=("Arial", 14, "bold")).pack(side="left")
        ctk.CTkButton(
            donate_row,
            text="Donate via PayPal",
            width=160,
            fg_color=BUTTON_BLUE,
            hover_color=BUTTON_BLUE_HOVER,
            command=self._open_paypal_donation,
        ).pack(side="left", padx=(10, 0))
        ctk.CTkButton(
            donate_row,
            text="Donate via TouchNGo",
            width=180,
            fg_color=BUTTON_GREEN,
            hover_color=BUTTON_GREEN_HOVER,
            command=self._show_touchngo_donation_image,
        ).pack(side="left", padx=(10, 0))

        link_row = ctk.CTkFrame(card, fg_color="transparent")
        link_row.pack(fill="x", padx=20, pady=(8, 18))
        ctk.CTkLabel(link_row, text="License:", font=("Arial", 14, "bold")).pack(side="left")
        ctk.CTkButton(
            link_row,
            text="Open license.md",
            width=160,
            fg_color=BUTTON_GREEN,
            hover_color=BUTTON_GREEN_HOVER,
            command=self._open_license_file,
        ).pack(side="left", padx=(10, 0))

if __name__ == "__main__":
    app = SocietyApp()
    app.mainloop()
