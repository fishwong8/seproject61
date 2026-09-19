import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
import os
import hashlib
from datetime import datetime

DB_FILE = "election_central.sqlite"

# ---------- Theme & Icons ----------
COLORS = {
    "bg":          "#1e1e2e",
    "surface":     "#2a2a3c",
    "surface_alt": "#32324a",
    "primary":     "#7c3aed",
    "primary_hi":  "#8b5cf6",
    "success":     "#10b981",
    "danger":      "#ef4444",
    "warning":     "#f59e0b",
    "info":        "#3b82f6",
    "pink":        "#ec4899",
    "text":        "#e5e7eb",
    "text_dim":    "#9ca3af",
    "border":      "#3f3f5a",
}

ICONS = {
    "app": "🗳", "admin": "👤", "users": "👥", "lock": "🔒", "key": "🔑",
    "login": "🔐", "logout": "⎋", "add": "➕", "edit": "✏", "delete": "🗑",
    "save": "💾", "cancel": "✖", "search": "🔍", "refresh": "⟳",
    "settings": "⚙", "home": "🏠", "vote": "✅", "stats": "📊",
    "calendar": "📅", "shield": "🛡", "register": "📝", "ballot": "📩",
    "candidate": "🎖", "poll": "📍", "count": "🧮", "record": "📋",
    "station": "🏢", "complaint": "⚠", "log": "📜", "backup": "🔄",
    "back": "⬅", "arrow": "➜", "db": "🗄",
}


# ============================================================
#                  DATABASE LAYER
# ============================================================

def hash_password(password: str) -> str:
    """Simple SHA-256 hashing for demo. Use bcrypt/argon2 in production."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def get_connection():
    """Open a connection with foreign keys enabled."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Create schema, indexes, triggers and seed data if missing."""
    conn = get_connection()
    cur = conn.cursor()

    # ---------------- Schema ----------------
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS admin_users (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          username TEXT UNIQUE NOT NULL,
          password TEXT NOT NULL,
          full_name TEXT,
          role TEXT NOT NULL DEFAULT 'admin',
          is_active INTEGER NOT NULL DEFAULT 1,
          created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS polling_stations (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT NOT NULL,
          location TEXT,
          code TEXT UNIQUE,
          opening_time TEXT,
          closing_time TEXT,
          is_active INTEGER NOT NULL DEFAULT 1,
          is_backup_enabled INTEGER NOT NULL DEFAULT 0,
          created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS elections (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT NOT NULL,
          description TEXT,
          start_datetime TEXT,
          end_datetime TEXT,
          status TEXT NOT NULL DEFAULT 'scheduled',
          created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS voters (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          national_id TEXT UNIQUE,
          full_name TEXT NOT NULL,
          date_of_birth TEXT,
          address TEXT,
          email TEXT,
          phone TEXT,
          is_eligible INTEGER NOT NULL DEFAULT 1,
          station_id INTEGER,
          created_at TEXT NOT NULL DEFAULT (datetime('now')),
          FOREIGN KEY (station_id) REFERENCES polling_stations(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS candidates (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          election_id INTEGER NOT NULL,
          voter_id INTEGER,
          name TEXT NOT NULL,
          party TEXT,
          position TEXT,
          bio TEXT,
          photo_url TEXT,
          created_at TEXT NOT NULL DEFAULT (datetime('now')),
          FOREIGN KEY (election_id) REFERENCES elections(id) ON DELETE CASCADE,
          FOREIGN KEY (voter_id) REFERENCES voters(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS ballots (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          election_id INTEGER NOT NULL,
          voter_id INTEGER NOT NULL,
          station_id INTEGER,
          issued_at TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'issued',
          serial_number TEXT UNIQUE,
          FOREIGN KEY (election_id) REFERENCES elections(id) ON DELETE CASCADE,
          FOREIGN KEY (voter_id) REFERENCES voters(id) ON DELETE CASCADE,
          FOREIGN KEY (station_id) REFERENCES polling_stations(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS votes (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          election_id INTEGER NOT NULL,
          ballot_id INTEGER,
          voter_id INTEGER,
          candidate_id INTEGER NOT NULL,
          station_id INTEGER,
          cast_at TEXT NOT NULL,
          FOREIGN KEY (election_id) REFERENCES elections(id) ON DELETE CASCADE,
          FOREIGN KEY (ballot_id) REFERENCES ballots(id) ON DELETE SET NULL,
          FOREIGN KEY (voter_id) REFERENCES voters(id) ON DELETE SET NULL,
          FOREIGN KEY (candidate_id) REFERENCES candidates(id) ON DELETE CASCADE,
          FOREIGN KEY (station_id) REFERENCES polling_stations(id) ON DELETE SET NULL,
          UNIQUE (election_id, voter_id)
        );

        CREATE TABLE IF NOT EXISTS complaints (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          election_id INTEGER,
          station_id INTEGER,
          voter_id INTEGER,
          complaint_type TEXT,
          description TEXT,
          created_at TEXT NOT NULL DEFAULT (datetime('now')),
          status TEXT NOT NULL DEFAULT 'open',
          FOREIGN KEY (election_id) REFERENCES elections(id) ON DELETE SET NULL,
          FOREIGN KEY (station_id) REFERENCES polling_stations(id) ON DELETE SET NULL,
          FOREIGN KEY (voter_id) REFERENCES voters(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS station_logs (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          station_id INTEGER NOT NULL,
          log_type TEXT NOT NULL,
          timestamp TEXT NOT NULL,
          detail TEXT,
          queue_length INTEGER,
          FOREIGN KEY (station_id) REFERENCES polling_stations(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS system_logs (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          admin_id INTEGER,
          action TEXT,
          detail TEXT,
          created_at TEXT NOT NULL DEFAULT (datetime('now')),
          FOREIGN KEY (admin_id) REFERENCES admin_users(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS results_summary (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          election_id INTEGER NOT NULL,
          candidate_id INTEGER NOT NULL,
          total_votes INTEGER NOT NULL DEFAULT 0,
          last_updated_at TEXT,
          FOREIGN KEY (election_id) REFERENCES elections(id) ON DELETE CASCADE,
          FOREIGN KEY (candidate_id) REFERENCES candidates(id) ON DELETE CASCADE,
          UNIQUE (election_id, candidate_id)
        );
        """
    )

    # ---------------- Indexes ----------------
    cur.executescript(
        """
        CREATE INDEX IF NOT EXISTS idx_voters_nid          ON voters(national_id);
        CREATE INDEX IF NOT EXISTS idx_voters_station      ON voters(station_id);
        CREATE INDEX IF NOT EXISTS idx_candidates_election ON candidates(election_id);
        CREATE INDEX IF NOT EXISTS idx_ballots_election    ON ballots(election_id);
        CREATE INDEX IF NOT EXISTS idx_ballots_voter       ON ballots(voter_id);
        CREATE INDEX IF NOT EXISTS idx_votes_election      ON votes(election_id);
        CREATE INDEX IF NOT EXISTS idx_votes_candidate     ON votes(candidate_id);
        CREATE INDEX IF NOT EXISTS idx_votes_station       ON votes(station_id);
        CREATE INDEX IF NOT EXISTS idx_votes_cast_at       ON votes(cast_at);
        CREATE INDEX IF NOT EXISTS idx_station_logs_sid    ON station_logs(station_id);
        CREATE INDEX IF NOT EXISTS idx_system_logs_admin   ON system_logs(admin_id);
        """
    )

    # ---------------- Triggers ----------------
    cur.executescript(
        """
        CREATE TRIGGER IF NOT EXISTS trg_ballot_serial
        AFTER INSERT ON ballots
        WHEN NEW.serial_number IS NULL
        BEGIN
          UPDATE ballots
             SET serial_number = 'B' || printf('%08d', NEW.id) ||
                                 '-' || strftime('%Y%m%d', NEW.issued_at)
           WHERE id = NEW.id;
        END;
        """
    )

    # ---------------- Seed data ----------------
    cur.execute("SELECT COUNT(*) AS c FROM admin_users")
    if cur.fetchone()["c"] == 0:
        cur.execute(
            "INSERT INTO admin_users (username, password, full_name, role, is_active) "
            "VALUES (?, ?, ?, ?, 1)",
            ("admin", hash_password("admin123"), "Default Admin", "superadmin"),
        )
        print("✓ Default admin created  →  admin / admin123")

    cur.execute("SELECT COUNT(*) AS c FROM polling_stations")
    if cur.fetchone()["c"] == 0:
        stations = [
            ("Central Polling Station", "1 Central Rd, Hong Kong", "CPS-001", "08:00", "18:00"),
            ("Kowloon Polling Station", "2 Nathan Rd, Kowloon",    "KPS-002", "08:00", "18:00"),
            ("New Territories Station", "3 Castle Peak Rd, NT",    "NTS-003", "08:30", "18:30"),
        ]
        cur.executemany(
            "INSERT INTO polling_stations (name, location, code, opening_time, closing_time) "
            "VALUES (?, ?, ?, ?, ?)",
            stations,
        )
        print(f"✓ {len(stations)} demo polling stations created")

    conn.commit()
    conn.close()


def log_system(admin_id, action, detail=""):
    """Insert a system_logs row (silent fail-safe)."""
    try:
        conn = get_connection()
        conn.execute(
            "INSERT INTO system_logs (admin_id, action, detail, created_at) "
            "VALUES (?, ?, ?, datetime('now'))",
            (admin_id, action, detail),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print("log_system error:", e)


def db_stats():
    """Return row counts for a small dashboard."""
    conn = get_connection()
    cur = conn.cursor()
    stats = {}
    for tbl in ("admin_users", "polling_stations", "elections",
                "voters", "candidates", "ballots", "votes",
                "complaints", "station_logs", "system_logs"):
        cur.execute(f"SELECT COUNT(*) AS c FROM {tbl}")
        stats[tbl] = cur.fetchone()["c"]
    conn.close()
    return stats


# ============================================================
#                  REUSABLE WIDGETS
# ============================================================

class Card(tk.Frame):
    def __init__(self, parent, title="", icon="", **kwargs):
        super().__init__(parent, bg=COLORS["surface"], **kwargs)
        self.configure(highlightbackground=COLORS["border"],
                       highlightthickness=1, bd=0)
        if title:
            header = tk.Frame(self, bg=COLORS["surface"])
            header.pack(fill="x", padx=16, pady=(14, 6))
            tk.Label(header, text=f"{icon}  {title}".strip(),
                     bg=COLORS["surface"], fg=COLORS["text"],
                     font=("Segoe UI", 12, "bold")).pack(side="left")


class IconButton(tk.Button):
    def __init__(self, parent, text="", icon="", command=None,
                 variant="primary", **kwargs):
        palette = {
            "primary": (COLORS["primary"],     COLORS["primary_hi"], "#ffffff"),
            "success": (COLORS["success"],     "#059669",            "#ffffff"),
            "danger":  (COLORS["danger"],      "#dc2626",            "#ffffff"),
            "warning": (COLORS["warning"],     "#d97706",            "#ffffff"),
            "ghost":   (COLORS["surface_alt"], COLORS["border"],     COLORS["text"]),
        }
        bg, hover, fg = palette.get(variant, palette["primary"])
        label = f"{icon}  {text}".strip() if icon else text
        super().__init__(parent, text=label, command=command,
                         bg=bg, fg=fg, activebackground=hover,
                         activeforeground=fg, relief="flat", bd=0,
                         font=("Segoe UI", 10, "bold"),
                         padx=12, pady=6, cursor="hand2", **kwargs)
        self._bg, self._hover = bg, hover
        self.bind("<Enter>", lambda e: self.configure(bg=self._hover))
        self.bind("<Leave>", lambda e: self.configure(bg=self._bg))


class LabeledEntry(tk.Frame):
    def __init__(self, parent, label, icon="", show=None, bg=None):
        _bg = bg or COLORS["surface"]
        super().__init__(parent, bg=_bg)
        tk.Label(self, text=f"{icon}  {label}".strip(),
                 bg=_bg, fg=COLORS["text_dim"],
                 font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 4))
        wrapper = tk.Frame(self, bg=COLORS["surface_alt"],
                           highlightbackground=COLORS["border"],
                           highlightthickness=1)
        wrapper.pack(fill="x")
        self.entry = tk.Entry(wrapper, bg=COLORS["surface_alt"],
                              fg=COLORS["text"], insertbackground=COLORS["text"],
                              relief="flat", bd=0, font=("Segoe UI", 10), show=show)
        self.entry.pack(fill="x", padx=10, pady=8)

    def get(self):     return self.entry.get()
    def set(self, v):  self.entry.delete(0, "end"); self.entry.insert(0, v)
    def focus(self):   self.entry.focus_set()


def style_treeview(root):
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    style.configure("EC.Treeview",
                    background=COLORS["surface_alt"],
                    fieldbackground=COLORS["surface_alt"],
                    foreground=COLORS["text"],
                    rowheight=28, borderwidth=0,
                    font=("Segoe UI", 10))
    style.configure("EC.Treeview.Heading",
                    background=COLORS["surface"],
                    foreground=COLORS["text_dim"],
                    font=("Segoe UI", 10, "bold"), relief="flat")
    style.map("EC.Treeview",
              background=[("selected", COLORS["primary"])],
              foreground=[("selected", "#ffffff")])
    style.map("EC.Treeview.Heading",
              background=[("active", COLORS["surface_alt"])])
    style.configure("EC.TNotebook", background=COLORS["bg"], borderwidth=0)
    style.configure("EC.TNotebook.Tab",
                    background=COLORS["surface"],
                    foreground=COLORS["text_dim"],
                    padding=[14, 8], font=("Segoe UI", 10, "bold"))
    style.map("EC.TNotebook.Tab",
              background=[("selected", COLORS["primary"])],
              foreground=[("selected", "#ffffff")])
    style.configure("TCombobox",
                    fieldbackground=COLORS["surface_alt"],
                    background=COLORS["surface_alt"],
                    foreground=COLORS["text"], arrowcolor=COLORS["text"])
    style.configure("TLabel", background=COLORS["surface"], foreground=COLORS["text"])
    style.configure("TFrame", background=COLORS["surface"])


def make_tree(parent, cols, widths, height=12):
    tree = ttk.Treeview(parent, columns=cols, show="headings",
                        style="EC.Treeview", height=height)
    for c, w in zip(cols, widths):
        tree.heading(c, text=c.replace("_", " ").title())
        tree.column(c, width=w, anchor="w")
    return tree


class TileButton(tk.Frame):
    def __init__(self, parent, icon, title, subtitle, color, command,
                 locked=False, **kwargs):
        super().__init__(parent, bg=COLORS["surface"],
                         highlightbackground=COLORS["border"],
                         highlightthickness=1, cursor="hand2", **kwargs)
        inner = tk.Frame(self, bg=COLORS["surface"])
        inner.pack(fill="both", expand=True, padx=20, pady=18)

        icon_bg = tk.Frame(inner, bg=color, width=56, height=56)
        icon_bg.pack(side="left", padx=(0, 16))
        icon_bg.pack_propagate(False)
        tk.Label(icon_bg, text=icon, bg=color, fg="#ffffff",
                 font=("Segoe UI Emoji", 22)).place(relx=0.5, rely=0.5, anchor="center")

        text_frame = tk.Frame(inner, bg=COLORS["surface"])
        text_frame.pack(side="left", fill="both", expand=True)

        row = tk.Frame(text_frame, bg=COLORS["surface"])
        row.pack(anchor="w")
        tk.Label(row, text=title, bg=COLORS["surface"], fg=COLORS["text"],
                 font=("Segoe UI", 13, "bold")).pack(side="left")
        if locked:
            tk.Label(row, text="  🔒 login required", bg=COLORS["surface"],
                     fg=COLORS["warning"], font=("Segoe UI", 8)).pack(side="left")

        tk.Label(text_frame, text=subtitle, bg=COLORS["surface"],
                 fg=COLORS["text_dim"], font=("Segoe UI", 9),
                 wraplength=320, justify="left").pack(anchor="w", pady=(4, 0))
        tk.Label(inner, text=ICONS["arrow"], bg=COLORS["surface"],
                 fg=color, font=("Segoe UI Emoji", 16)).pack(side="right")

        widgets = []
        def collect(w):
            widgets.append(w)
            for c in w.winfo_children():
                collect(c)
        collect(inner)

        def on_enter(_):
            for w in widgets:
                try:
                    if w.cget("bg") == COLORS["surface"]:
                        w.configure(bg=COLORS["surface_alt"])
                except Exception:
                    pass
        def on_leave(_):
            for w in widgets:
                try:
                    if w.cget("bg") == COLORS["surface_alt"]:
                        w.configure(bg=COLORS["surface"])
                except Exception:
                    pass

        def bind_all(w):
            w.bind("<Enter>", on_enter)
            w.bind("<Leave>", on_leave)
            w.bind("<Button-1>", lambda e: command())
            for c in w.winfo_children():
                bind_all(c)
        bind_all(self)


# ============================================================
#                  APP SHELL
# ============================================================

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Election Management & Voting System 選舉及投票系統")
        self.geometry("1180x780")
        self.minsize(1080, 700)
        self.configure(bg=COLORS["bg"])
        self._center()
        style_treeview(self)

        self.current_admin_id = None

        container = tk.Frame(self, bg=COLORS["bg"])
        container.pack(fill="both", expand=True)
        container.rowconfigure(0, weight=1)
        container.columnconfigure(0, weight=1)
        self.container = container
        self.frames = {}

        for F in (HomeFrame, LoginFrame, RegistrationFrame,
                  BallotIssueFrame, CandidatesFrame, PollingFrame,
                  CountingFrame, RecordFrame, SettingsFrame):
            frame = F(parent=container, app=self)
            self.frames[F.__name__] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        self.show_frame("HomeFrame")

    def _center(self):
        self.update_idletasks()
        w, h = 1180, 780
        x = (self.winfo_screenwidth()  - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

    def show_frame(self, name):
        frame = self.frames[name]
        if hasattr(frame, "refresh"):
            frame.refresh()
        if isinstance(frame, PageFrame):
            frame.refresh_header()
        frame.tkraise()

    def go_home(self):
        self.show_frame("HomeFrame")


# ============================================================
#                  HOME
# ============================================================

class HomeFrame(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=COLORS["bg"])
        self.app = app

        header = tk.Frame(self, bg=COLORS["surface"], height=90)
        header.pack(fill="x")
        header.pack_propagate(False)

        hleft = tk.Frame(header, bg=COLORS["surface"])
        hleft.pack(side="left", padx=24, pady=16)
        tk.Label(hleft, text=ICONS["app"], bg=COLORS["surface"],
                 fg=COLORS["primary_hi"], font=("Segoe UI Emoji", 26)).pack(side="left")
        hl2 = tk.Frame(hleft, bg=COLORS["surface"])
        hl2.pack(side="left", padx=10)
        tk.Label(hl2, text="Election Central 中央選舉管理平台",
                 bg=COLORS["surface"], fg=COLORS["text"],
                 font=("Segoe UI", 16, "bold")).pack(anchor="w")
        tk.Label(hl2, text="Election Management & Voting System",
                 bg=COLORS["surface"], fg=COLORS["text_dim"],
                 font=("Segoe UI", 9)).pack(anchor="w")

        hright = tk.Frame(header, bg=COLORS["surface"])
        hright.pack(side="right", padx=24)
        self.db_label = tk.Label(hright, text="", bg=COLORS["surface"],
                                 fg=COLORS["text_dim"], font=("Segoe UI", 9))
        self.db_label.pack(side="left", padx=10)
        self.status_label = tk.Label(hright, text="", bg=COLORS["surface"],
                                     fg=COLORS["text_dim"], font=("Segoe UI", 10))
        self.status_label.pack(side="left", padx=10)

        body = tk.Frame(self, bg=COLORS["bg"])
        body.pack(fill="both", expand=True, padx=40, pady=20)

        tk.Label(body, text="Select a Module 選擇功能",
                 bg=COLORS["bg"], fg=COLORS["text"],
                 font=("Segoe UI", 15, "bold")).pack(anchor="w", pady=(0, 4))
        tk.Label(body, text="Click any card below to enter that section.",
                 bg=COLORS["bg"], fg=COLORS["text_dim"],
                 font=("Segoe UI", 10)).pack(anchor="w", pady=(0, 16))

        grid = tk.Frame(body, bg=COLORS["bg"])
        grid.pack(fill="both", expand=True)
        for i in range(2):
            grid.columnconfigure(i, weight=1, uniform="tile")
        for i in range(4):
            grid.rowconfigure(i, weight=1, uniform="tile")

        tiles = [
            (ICONS["login"],   "1. Login 登入",
             "管理員登入以使用其他功能", COLORS["primary"],
             lambda: self.app.show_frame("LoginFrame")),
            (ICONS["register"],"2. 選票登記系統 Registration",
             "新增選舉、登記投票人、管理選民資料", COLORS["success"],
             lambda: self._guarded("RegistrationFrame")),
            (ICONS["ballot"],  "3. 發票櫃枱 Issue Counter",
             "發出選票、標記損壞或未使用選票", COLORS["warning"],
             lambda: self._guarded("BallotIssueFrame")),
            (ICONS["candidate"],"4. 候選人系統 Candidates",
             "新增及管理各選舉的候選人", COLORS["info"],
             lambda: self._guarded("CandidatesFrame")),
            (ICONS["poll"],    "5. Polling 投票及統計",
             "投票、每小時統計、投訴個案", COLORS["pink"],
             lambda: self._guarded("PollingFrame")),
            (ICONS["count"],   "6. Counting 點票",
             "各候選人得票點算結果", COLORS["danger"],
             lambda: self._guarded("CountingFrame")),
            (ICONS["record"],  "7. Record 投票站紀錄",
             "開站/關站/排隊/事件紀錄", COLORS["success"],
             lambda: self._guarded("RecordFrame")),
            (ICONS["settings"],"8. Settings 設定",
             "投票站、後備模式、帳戶、系統紀錄", COLORS["text_dim"],
             lambda: self._guarded("SettingsFrame")),
        ]

        for idx, (icon, title, subtitle, color, cmd) in enumerate(tiles):
            r, c = divmod(idx, 2)
            is_login = (idx == 0)
            tile = TileButton(grid, icon=icon, title=title, subtitle=subtitle,
                              color=color, command=cmd, locked=not is_login)
            tile.grid(row=r, column=c, sticky="nsew",
                      padx=(0 if c == 0 else 8, 8 if c == 0 else 0),
                      pady=(0 if r == 0 else 6, 6 if r == 3 else 0))

    def _guarded(self, frame_name):
        if not self.app.current_admin_id:
            if messagebox.askyesno(
                "Login required 需要登入",
                "You need to log in first.\n需要先登入。\n\nGo to Login now?"):
                self.app.show_frame("LoginFrame")
            return
        self.app.show_frame(frame_name)

    def refresh(self):
        try:
            s = db_stats()
            self.db_label.config(
                text=f"{ICONS['db']}  DB: {os.path.basename(DB_FILE)}  |  "
                     f"Voters {s['voters']}  •  Elections {s['elections']}  •  "
                     f"Votes {s['votes']}")
        except Exception:
            self.db_label.config(text=f"{ICONS['db']}  {os.path.basename(DB_FILE)}")

        if self.app.current_admin_id:
            self.status_label.config(
                text=f"{ICONS['admin']}  Logged in  |  Admin ID {self.app.current_admin_id}",
                fg=COLORS["success"])
        else:
            self.status_label.config(
                text=f"{ICONS['lock']}  Not logged in  |  未登入",
                fg=COLORS["warning"])


# ============================================================
#                  PAGE BASE
# ============================================================

class PageFrame(tk.Frame):
    page_title = "Page"
    page_icon  = "🏠"

    def __init__(self, parent, app):
        super().__init__(parent, bg=COLORS["bg"])
        self.app = app

        top = tk.Frame(self, bg=COLORS["surface"], height=64)
        top.pack(fill="x")
        top.pack_propagate(False)

        left = tk.Frame(top, bg=COLORS["surface"])
        left.pack(side="left", padx=16)
        IconButton(left, text="Home 主頁", icon=ICONS["back"],
                   variant="ghost",
                   command=lambda: self.app.go_home()).pack(side="left")
        tk.Label(left, text=f"{self.page_icon}  {self.page_title}",
                 bg=COLORS["surface"], fg=COLORS["text"],
                 font=("Segoe UI", 14, "bold")).pack(side="left", padx=16)

        right = tk.Frame(top, bg=COLORS["surface"])
        right.pack(side="right", padx=16)
        self.admin_label = tk.Label(
            right, text=f"{ICONS['admin']}  Admin", bg=COLORS["surface"],
            fg=COLORS["text_dim"], font=("Segoe UI", 10))
        self.logout_button = IconButton(
            right, text="Logout 登出", icon=ICONS["logout"],
            variant="danger", command=self._logout)

        self.body = tk.Frame(self, bg=COLORS["bg"])
        self.body.pack(fill="both", expand=True)

    def refresh_header(self):
        """Only show session controls when an administrator is logged in."""
        if self.app.current_admin_id:
            self.admin_label.pack(side="left", padx=8)
            self.logout_button.pack(side="left")
        else:
            self.admin_label.pack_forget()
            self.logout_button.pack_forget()

    def _logout(self):
        if self.app.current_admin_id:
            log_system(self.app.current_admin_id, "logout")
        self.app.current_admin_id = None
        self.app.show_frame("HomeFrame")


# ============================================================
#                  LOGIN
# ============================================================

class LoginFrame(PageFrame):
    page_title = "Login 登入"
    page_icon  = ICONS["login"]

    def __init__(self, parent, app):
        super().__init__(parent, app)

        outer = tk.Frame(self.body, bg=COLORS["bg"])
        outer.pack(fill="both", expand=True, padx=40, pady=40)
        outer.columnconfigure(0, weight=1, uniform="cols")
        outer.columnconfigure(1, weight=1, uniform="cols")
        outer.rowconfigure(0, weight=1)

        brand = tk.Frame(outer, bg=COLORS["primary"])
        brand.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        tk.Label(brand, text=ICONS["app"], bg=COLORS["primary"],
                 fg="#ffffff", font=("Segoe UI Emoji", 72)).pack(pady=(80, 10))
        tk.Label(brand, text="Election Central", bg=COLORS["primary"],
                 fg="#ffffff", font=("Segoe UI", 24, "bold")).pack()
        tk.Label(brand, text="選舉及投票管理系統", bg=COLORS["primary"],
                 fg="#e9d5ff", font=("Segoe UI", 12)).pack(pady=(4, 0))
        tk.Label(brand, text=f"{ICONS['shield']}  Authorized Personnel Only",
                 bg=COLORS["primary"], fg="#e9d5ff",
                 font=("Segoe UI", 9)).pack(side="bottom", pady=24)

        card = Card(outer)
        card.grid(row=0, column=1, sticky="nsew", padx=(12, 0))
        form = tk.Frame(card, bg=COLORS["surface"])
        form.pack(fill="both", expand=True, padx=40, pady=40)

        tk.Label(form, text=f"{ICONS['login']}  Admin Login",
                 bg=COLORS["surface"], fg=COLORS["text"],
                 font=("Segoe UI", 20, "bold")).pack(anchor="w")
        tk.Label(form, text="管理員登入 — Enter your credentials to continue.",
                 bg=COLORS["surface"], fg=COLORS["text_dim"],
                 font=("Segoe UI", 9)).pack(anchor="w", pady=(4, 28))

        self.username_entry = LabeledEntry(form, "Username 帳戶", icon=ICONS["admin"])
        self.username_entry.pack(fill="x", pady=(0, 14))
        self.password_entry = LabeledEntry(form, "Password 密碼", icon=ICONS["lock"], show="*")
        self.password_entry.pack(fill="x", pady=(0, 20))

        IconButton(form, text="Login 登入", icon=ICONS["login"],
                   variant="primary", command=self.do_login).pack(fill="x")

        tk.Frame(form, bg=COLORS["border"], height=1).pack(fill="x", pady=20)
        tk.Label(form, text=f"{ICONS['key']}  Default: admin / admin123",
                 bg=COLORS["surface"], fg=COLORS["text_dim"],
                 font=("Segoe UI", 8)).pack()

        self.password_entry.entry.bind("<Return>", lambda e: self.do_login())

    def refresh(self):
        self.username_entry.set("")
        self.password_entry.set("")
        self.username_entry.focus()

    def do_login(self):
        username = self.username_entry.get().strip()
        password = self.password_entry.get()

        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM admin_users WHERE username=? AND is_active=1",
            (username,),
        )
        user = cur.fetchone()
        conn.close()

        if user and user["password"] == hash_password(password):
            self.app.current_admin_id = user["id"]
            log_system(user["id"], "login", f"username={username}")
            messagebox.showinfo("Login", "Login successful.")
            self.app.go_home()
        else:
            log_system(None, "login_failed", f"username={username}")
            messagebox.showerror("Login", "Invalid username or password.")


# ============================================================
#                  REGISTRATION
# ============================================================

class RegistrationFrame(PageFrame):
    page_title = "選票登記系統 Registration"
    page_icon  = ICONS["register"]

    def __init__(self, parent, app):
        super().__init__(parent, app)

        wrap = tk.Frame(self.body, bg=COLORS["bg"])
        wrap.pack(fill="both", expand=True, padx=10, pady=10)

        left_card = Card(wrap, title="Elections 選舉", icon=ICONS["vote"])
        left_card.pack(side="left", fill="y", padx=(0, 5))

        left_body = tk.Frame(left_card, bg=COLORS["surface"])
        left_body.pack(fill="both", expand=True, padx=16, pady=(4, 12))

        list_wrap = tk.Frame(left_body, bg=COLORS["surface_alt"],
                             highlightbackground=COLORS["border"], highlightthickness=1)
        list_wrap.pack(fill="both", expand=True)

        self.election_list = tk.Listbox(
            list_wrap, width=42, height=20,
            bg=COLORS["surface_alt"], fg=COLORS["text"],
            selectbackground=COLORS["primary"], selectforeground="#ffffff",
            relief="flat", bd=0, font=("Segoe UI", 10),
            highlightthickness=0, activestyle="none")
        self.election_list.pack(side="left", fill="both", expand=True, padx=6, pady=6)

        sb = tk.Scrollbar(list_wrap, orient="vertical", command=self.election_list.yview)
        sb.pack(side="right", fill="y")
        self.election_list.config(yscrollcommand=sb.set)

        IconButton(left_body, text="New Election 新增選舉", icon=ICONS["add"],
                   variant="primary",
                   command=self.create_election_dialog).pack(fill="x", pady=(12, 0))

        right_card = Card(wrap, title="Voter Registration 投票人登記", icon=ICONS["register"])
        right_card.pack(side="left", fill="both", expand=True, padx=(5, 0))

        form = tk.Frame(right_card, bg=COLORS["surface"])
        form.pack(fill="both", expand=True, padx=24, pady=16)

        self.v_station = tk.StringVar()
        self.e_nid = LabeledEntry(form, "National ID 身份證號碼", icon=ICONS["admin"])
        self.e_nid.pack(fill="x", pady=6)
        self.e_name = LabeledEntry(form, "Full name 姓名", icon=ICONS["admin"])
        self.e_name.pack(fill="x", pady=6)

        tk.Label(form, text=f"{ICONS['station']}  Station 投票站",
                 bg=COLORS["surface"], fg=COLORS["text_dim"],
                 font=("Segoe UI", 9)).pack(anchor="w", pady=(6, 4))
        self.station_combo = ttk.Combobox(form, textvariable=self.v_station, state="readonly")
        self.station_combo.pack(fill="x")

        IconButton(form, text="Register voter 登記投票人", icon=ICONS["save"],
                   variant="success",
                   command=self.register_voter).pack(anchor="w", pady=(20, 0))

    def refresh(self):
        self.load_elections()
        self.load_stations()

    def load_elections(self):
        self.election_list.delete(0, tk.END)
        conn = get_connection()
        rows = conn.execute("SELECT * FROM elections ORDER BY id").fetchall()
        conn.close()
        for r in rows:
            self.election_list.insert(tk.END, f"{r['id']}: {r['name']} (status={r['status']})")

    def load_stations(self):
        conn = get_connection()
        rows = conn.execute(
            "SELECT * FROM polling_stations WHERE is_active=1 ORDER BY id").fetchall()
        conn.close()
        vals = [f"{r['id']} - {r['name']}" for r in rows]
        self.station_combo["values"] = vals
        if vals:
            self.station_combo.current(0)
        else:
            self.station_combo.set("")

    def create_election_dialog(self):
        dialog = tk.Toplevel(self)
        dialog.title("New Election 新增選舉")
        dialog.configure(bg=COLORS["surface"])
        dialog.geometry("460x320")
        dialog.transient(self); dialog.grab_set()

        tk.Label(dialog, text=f"{ICONS['add']}  Create New Election",
                 bg=COLORS["surface"], fg=COLORS["text"],
                 font=("Segoe UI", 13, "bold")).pack(pady=(20, 10), padx=20, anchor="w")

        form = tk.Frame(dialog, bg=COLORS["surface"])
        form.pack(fill="both", expand=True, padx=20)
        e_name = LabeledEntry(form, "Name 名稱", icon=ICONS["vote"]);   e_name.pack(fill="x", pady=6)
        e_desc = LabeledEntry(form, "Description 描述", icon=ICONS["edit"]); e_desc.pack(fill="x", pady=6)

        def save():
            name = e_name.get().strip(); desc = e_desc.get().strip()
            if not name:
                messagebox.showerror("Error", "Name required."); return
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("INSERT INTO elections (name, description, status) VALUES (?, ?, ?)",
                        (name, desc, "scheduled"))
            conn.commit(); conn.close()
            log_system(self.app.current_admin_id, "create_election", f"name={name}")
            dialog.destroy(); self.load_elections()

        btns = tk.Frame(dialog, bg=COLORS["surface"]); btns.pack(fill="x", padx=20, pady=20)
        IconButton(btns, text="Cancel", icon=ICONS["cancel"], variant="ghost",
                   command=dialog.destroy).pack(side="right", padx=6)
        IconButton(btns, text="Save 儲存", icon=ICONS["save"], variant="primary",
                   command=save).pack(side="right")

    def register_voter(self):
        nid = self.e_nid.get().strip()
        name = self.e_name.get().strip()
        station_val = self.v_station.get()

        if not nid or not name:
            messagebox.showerror("Error", "National ID and name required."); return

        station_id = None
        if station_val:
            try:    station_id = int(station_val.split(" - ")[0])
            except Exception: station_id = None

        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO voters (national_id, full_name, is_eligible, station_id) "
                "VALUES (?, ?, 1, ?)",
                (nid, name, station_id))
            conn.commit()
            log_system(self.app.current_admin_id, "register_voter", f"nid={nid}")
            messagebox.showinfo("OK", "Voter registered.")
            self.e_nid.set(""); self.e_name.set("")
        except sqlite3.IntegrityError:
            messagebox.showerror("Error", "National ID already exists.")
        finally:
            conn.close()


# ============================================================
#                  BALLOT ISSUE
# ============================================================

class BallotIssueFrame(PageFrame):
    page_title = "發票櫃枱 Issue Counter"
    page_icon  = ICONS["ballot"]

    def __init__(self, parent, app):
        super().__init__(parent, app)

        wrap = tk.Frame(self.body, bg=COLORS["bg"])
        wrap.pack(fill="both", expand=True, padx=10, pady=10)

        form_card = Card(wrap, title="Issue Ballot 發出選票", icon=ICONS["ballot"])
        form_card.pack(fill="x", pady=(0, 8))
        form = tk.Frame(form_card, bg=COLORS["surface"])
        form.pack(fill="x", padx=24, pady=16)
        form.columnconfigure(1, weight=1)

        self.election_var = tk.StringVar()
        self.station_var = tk.StringVar()
        self.voter_nid_var = tk.StringVar()

        rows = [
            (f"{ICONS['vote']}  Election 選舉:", self.election_var, "combo"),
            (f"{ICONS['station']}  Station 投票站:", self.station_var, "combo"),
            (f"{ICONS['admin']}  Voter ID 身份證號碼:", self.voter_nid_var, "entry"),
        ]
        for i, (lbl, var, kind) in enumerate(rows):
            tk.Label(form, text=lbl, bg=COLORS["surface"], fg=COLORS["text_dim"],
                     font=("Segoe UI", 9)).grid(row=i, column=0, padx=5, pady=6, sticky="e")
            if kind == "combo":
                w = ttk.Combobox(form, textvariable=var, state="readonly")
            else:
                w = tk.Entry(form, textvariable=var, bg=COLORS["surface_alt"],
                             fg=COLORS["text"], insertbackground=COLORS["text"],
                             relief="flat", bd=0, font=("Segoe UI", 10))
            w.grid(row=i, column=1, padx=5, pady=6, sticky="ew", ipady=4)
            if i == 0: self.election_combo = w
            if i == 1: self.station_combo = w

        IconButton(form, text="Issue ballot 發出選票", icon=ICONS["ballot"],
                   variant="success", command=self.issue_ballot
                   ).grid(row=3, column=0, columnspan=2, pady=(12, 0), sticky="w")

        list_card = Card(wrap, title="Recent Ballots 最近選票", icon=ICONS["record"])
        list_card.pack(fill="both", expand=True)
        body = tk.Frame(list_card, bg=COLORS["surface"])
        body.pack(fill="both", expand=True, padx=16, pady=(4, 12))

        bar = tk.Frame(body, bg=COLORS["surface"]); bar.pack(fill="x", pady=(0, 10))
        IconButton(bar, text="Mark spoiled 損壞", icon=ICONS["delete"],
                   variant="danger", command=self.mark_spoiled).pack(side="left", padx=(0, 8))
        IconButton(bar, text="Mark unused 未用", icon=ICONS["cancel"],
                   variant="warning", command=self.mark_unused).pack(side="left", padx=(0, 8))
        IconButton(bar, text="Refresh", icon=ICONS["refresh"],
                   variant="ghost", command=self.load_recent_ballots).pack(side="left")

        self.tree = make_tree(body,
                              ("id", "serial", "election", "voter", "station", "issued_at", "status"),
                              (50, 130, 200, 180, 160, 160, 90), height=12)
        self.tree.pack(fill="both", expand=True)

    def refresh(self):
        self.load_elections(); self.load_stations(); self.load_recent_ballots()

    def load_elections(self):
        conn = get_connection()
        rows = conn.execute("SELECT * FROM elections ORDER BY id").fetchall()
        conn.close()
        vals = [f"{r['id']} - {r['name']}" for r in rows]
        self.election_combo["values"] = vals
        if vals: self.election_combo.current(0)

    def load_stations(self):
        conn = get_connection()
        rows = conn.execute(
            "SELECT * FROM polling_stations WHERE is_active=1 ORDER BY id").fetchall()
        conn.close()
        vals = [f"{r['id']} - {r['name']}" for r in rows]
        self.station_combo["values"] = vals
        if vals: self.station_combo.current(0)

    def get_ids(self):
        eid = sid = None
        if self.election_var.get():
            try: eid = int(self.election_var.get().split(" - ")[0])
            except Exception: eid = None
        if self.station_var.get():
            try: sid = int(self.station_var.get().split(" - ")[0])
            except Exception: sid = None
        return eid, sid

    def issue_ballot(self):
        eid, sid = self.get_ids()
        nid = self.voter_nid_var.get().strip()
        if not eid or not sid or not nid:
            messagebox.showerror("Error", "Election, station, and voter ID required."); return

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM voters WHERE national_id=? AND is_eligible=1", (nid,))
        voter = cur.fetchone()
        if not voter:
            conn.close(); messagebox.showerror("Error", "Voter not found or not eligible."); return

        issued_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cur.execute(
            "INSERT INTO ballots (election_id, voter_id, station_id, issued_at, status) "
            "VALUES (?, ?, ?, ?, ?)",
            (eid, voter["id"], sid, issued_at, "issued"))
        conn.commit()
        log_system(self.app.current_admin_id, "issue_ballot",
                   f"voter_nid={nid}, election={eid}, station={sid}")
        conn.close()
        messagebox.showinfo("OK", "Ballot issued.")
        self.voter_nid_var.set("")
        self.load_recent_ballots()

    def load_recent_ballots(self):
        self.tree.delete(*self.tree.get_children())
        conn = get_connection()
        rows = conn.execute(
            """
            SELECT b.id, b.serial_number, e.name AS election, v.full_name AS voter,
                   s.name AS station, b.issued_at, b.status
            FROM ballots b
            LEFT JOIN elections e ON b.election_id = e.id
            LEFT JOIN voters v ON b.voter_id = v.id
            LEFT JOIN polling_stations s ON b.station_id = s.id
            ORDER BY b.id DESC LIMIT 100
            """
        ).fetchall()
        conn.close()
        for r in rows:
            self.tree.insert("", tk.END, values=(
                r["id"], r["serial_number"] or "-", r["election"], r["voter"],
                r["station"], r["issued_at"], r["status"]))

    def _get_selected_ballot_id(self):
        sel = self.tree.selection()
        if not sel: return None
        try: return int(self.tree.item(sel[0], "values")[0])
        except Exception: return None

    def mark_spoiled(self):
        bid = self._get_selected_ballot_id()
        if not bid: messagebox.showerror("Error", "Select a ballot first."); return
        conn = get_connection()
        conn.execute("UPDATE ballots SET status='spoiled' WHERE id=?", (bid,))
        conn.commit(); conn.close()
        log_system(self.app.current_admin_id, "mark_spoiled", f"ballot_id={bid}")
        self.load_recent_ballots()

    def mark_unused(self):
        bid = self._get_selected_ballot_id()
        if not bid: messagebox.showerror("Error", "Select a ballot first."); return
        conn = get_connection()
        conn.execute("UPDATE ballots SET status='unused' WHERE id=?", (bid,))
        conn.commit(); conn.close()
        log_system(self.app.current_admin_id, "mark_unused", f"ballot_id={bid}")
        self.load_recent_ballots()


# ============================================================
#                  CANDIDATES
# ============================================================

class CandidatesFrame(PageFrame):
    page_title = "候選人系統 Candidates"
    page_icon  = ICONS["candidate"]

    def __init__(self, parent, app):
        super().__init__(parent, app)

        wrap = tk.Frame(self.body, bg=COLORS["bg"])
        wrap.pack(fill="both", expand=True, padx=10, pady=10)

        card = Card(wrap, title="Candidates Management 候選人系統", icon=ICONS["candidate"])
        card.pack(fill="both", expand=True)
        body = tk.Frame(card, bg=COLORS["surface"])
        body.pack(fill="both", expand=True, padx=16, pady=(4, 12))

        top = tk.Frame(body, bg=COLORS["surface"]); top.pack(fill="x", pady=(0, 10))
        tk.Label(top, text=f"{ICONS['vote']}  Election 選舉:",
                 bg=COLORS["surface"], fg=COLORS["text_dim"],
                 font=("Segoe UI", 9)).pack(side="left")
        self.election_var = tk.StringVar()
        self.election_combo = ttk.Combobox(top, textvariable=self.election_var,
                                            state="readonly", width=40)
        self.election_combo.pack(side="left", padx=8)
        self.election_combo.bind("<<ComboboxSelected>>", lambda e: self.load_candidates())

        IconButton(top, text="Add candidate 新增候選人", icon=ICONS["add"],
                   variant="primary",
                   command=self.add_candidate_dialog).pack(side="right")
        IconButton(top, text="Refresh", icon=ICONS["refresh"],
                   variant="ghost", command=self.refresh).pack(side="right", padx=8)

        self.tree = make_tree(body, ("id", "name", "party", "position"),
                              (60, 320, 260, 240), height=14)
        self.tree.pack(fill="both", expand=True)

    def refresh(self):
        conn = get_connection()
        rows = conn.execute("SELECT * FROM elections ORDER BY id").fetchall()
        conn.close()
        vals = [f"{r['id']} - {r['name']}" for r in rows]
        self.election_combo["values"] = vals
        if vals: self.election_combo.current(0)
        self.load_candidates()

    def get_election_id(self):
        val = self.election_var.get()
        if not val: return None
        try: return int(val.split(" - ")[0])
        except Exception: return None

    def load_candidates(self):
        self.tree.delete(*self.tree.get_children())
        eid = self.get_election_id()
        if not eid: return
        conn = get_connection()
        rows = conn.execute(
            "SELECT id, name, party, position FROM candidates WHERE election_id=?",
            (eid,)).fetchall()
        conn.close()
        for r in rows:
            self.tree.insert("", tk.END,
                             values=(r["id"], r["name"], r["party"], r["position"]))

    def add_candidate_dialog(self):
        eid = self.get_election_id()
        if not eid: messagebox.showerror("Error", "Select an election first."); return

        dialog = tk.Toplevel(self)
        dialog.title("Add Candidate 新增候選人")
        dialog.configure(bg=COLORS["surface"])
        dialog.geometry("440x380")
        dialog.transient(self); dialog.grab_set()

        tk.Label(dialog, text=f"{ICONS['candidate']}  Add New Candidate",
                 bg=COLORS["surface"], fg=COLORS["text"],
                 font=("Segoe UI", 13, "bold")).pack(pady=(20, 10), padx=20, anchor="w")

        form = tk.Frame(dialog, bg=COLORS["surface"])
        form.pack(fill="both", expand=True, padx=20)
        e_name  = LabeledEntry(form, "Name 名稱", icon=ICONS["candidate"]); e_name.pack(fill="x", pady=6)
        e_party = LabeledEntry(form, "Party 政黨", icon=ICONS["shield"]);    e_party.pack(fill="x", pady=6)
        e_pos   = LabeledEntry(form, "Position 職位/議席", icon=ICONS["admin"]); e_pos.pack(fill="x", pady=6)

        def save():
            name = e_name.get().strip(); party = e_party.get().strip(); pos = e_pos.get().strip()
            if not name:
                messagebox.showerror("Error", "Name required."); return
            conn = get_connection()
            conn.execute(
                "INSERT INTO candidates (election_id, name, party, position) VALUES (?, ?, ?, ?)",
                (eid, name, party, pos))
            conn.commit(); conn.close()
            log_system(self.app.current_admin_id, "add_candidate",
                       f"election={eid}, name={name}")
            dialog.destroy(); self.load_candidates()

        btns = tk.Frame(dialog, bg=COLORS["surface"]); btns.pack(fill="x", padx=20, pady=20)
        IconButton(btns, text="Cancel", icon=ICONS["cancel"], variant="ghost",
                   command=dialog.destroy).pack(side="right", padx=6)
        IconButton(btns, text="Save 儲存", icon=ICONS["save"], variant="primary",
                   command=save).pack(side="right")


# ============================================================
#                  POLLING
# ============================================================

class PollingFrame(PageFrame):
    page_title = "Polling 投票及統計"
    page_icon  = ICONS["poll"]

    def __init__(self, parent, app):
        super().__init__(parent, app)

        wrap = tk.Frame(self.body, bg=COLORS["bg"])
        wrap.pack(fill="both", expand=True, padx=10, pady=10)

        vote_card = Card(wrap, title="Voting 投票", icon=ICONS["vote"])
        vote_card.pack(fill="x", pady=(0, 8))
        form = tk.Frame(vote_card, bg=COLORS["surface"])
        form.pack(fill="x", padx=24, pady=16)
        form.columnconfigure(1, weight=1)

        self.vote_election_var  = tk.StringVar()
        self.vote_station_var   = tk.StringVar()
        self.vote_nid_var       = tk.StringVar()
        self.vote_candidate_var = tk.StringVar()

        rows = [
            (f"{ICONS['vote']}  Election 選舉:",         self.vote_election_var,  "combo"),
            (f"{ICONS['station']}  Station 投票站:",       self.vote_station_var,   "combo"),
            (f"{ICONS['admin']}  Voter ID 身份證號碼:",    self.vote_nid_var,       "entry"),
            (f"{ICONS['candidate']}  Candidate 候選人:",   self.vote_candidate_var, "combo"),
        ]
        for i, (lbl, var, kind) in enumerate(rows):
            tk.Label(form, text=lbl, bg=COLORS["surface"], fg=COLORS["text_dim"],
                     font=("Segoe UI", 9)).grid(row=i, column=0, padx=5, pady=6, sticky="e")
            if kind == "combo":
                w = ttk.Combobox(form, textvariable=var, state="readonly")
            else:
                w = tk.Entry(form, textvariable=var, bg=COLORS["surface_alt"],
                             fg=COLORS["text"], insertbackground=COLORS["text"],
                             relief="flat", bd=0, font=("Segoe UI", 10))
            w.grid(row=i, column=1, padx=5, pady=6, sticky="ew", ipady=4)
            if i == 0: self.vote_election_combo = w
            if i == 1: self.vote_station_combo = w
            if i == 3: self.vote_candidate_combo = w

        self.vote_election_combo.bind("<<ComboboxSelected>>",
                                      lambda e: self.load_candidates_for_vote())

        IconButton(form, text="Submit vote 提交選票", icon=ICONS["vote"],
                   variant="success", command=self.submit_vote
                   ).grid(row=4, column=0, columnspan=2, pady=(12, 0), sticky="w")

        bottom = tk.Frame(wrap, bg=COLORS["bg"])
        bottom.pack(fill="both", expand=True)
        bottom.columnconfigure(0, weight=1, uniform="cols")
        bottom.columnconfigure(1, weight=1, uniform="cols")

        stats_card = Card(bottom, title="Hourly Stats 每小時統計", icon=ICONS["stats"])
        stats_card.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        s_body = tk.Frame(stats_card, bg=COLORS["surface"])
        s_body.pack(fill="both", expand=True, padx=16, pady=(4, 12))
        IconButton(s_body, text="Refresh stats 重新整理", icon=ICONS["refresh"],
                   variant="ghost",
                   command=self.load_hourly_stats).pack(anchor="w", pady=(0, 8))
        self.stats_tree = make_tree(s_body, ("hour", "issued", "votes"),
                                    (220, 140, 140), height=9)
        self.stats_tree.pack(fill="both", expand=True)

        comp_card = Card(bottom, title="Complaints 投訴個案", icon=ICONS["complaint"])
        comp_card.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        c_body = tk.Frame(comp_card, bg=COLORS["surface"])
        c_body.pack(fill="both", expand=True, padx=16, pady=(4, 12))
        IconButton(c_body, text="New complaint 新增投訴", icon=ICONS["add"],
                   variant="primary",
                   command=self.add_complaint_dialog).pack(anchor="w", pady=(0, 8))
        self.complaints_tree = make_tree(
            c_body,
            ("id", "election", "station", "type", "status", "created_at"),
            (50, 140, 140, 130, 90, 150), height=9)
        self.complaints_tree.pack(fill="both", expand=True)

    def refresh(self):
        self.load_elections(); self.load_stations()
        self.load_candidates_for_vote()
        self.load_hourly_stats(); self.load_complaints()

    def load_elections(self):
        conn = get_connection()
        rows = conn.execute("SELECT * FROM elections ORDER BY id").fetchall()
        conn.close()
        vals = [f"{r['id']} - {r['name']}" for r in rows]
        self.vote_election_combo["values"] = vals
        if vals: self.vote_election_combo.current(0)

    def load_stations(self):
        conn = get_connection()
        rows = conn.execute(
            "SELECT * FROM polling_stations WHERE is_active=1 ORDER BY id").fetchall()
        conn.close()
        vals = [f"{r['id']} - {r['name']}" for r in rows]
        self.vote_station_combo["values"] = vals
        if vals: self.vote_station_combo.current(0)

    def get_vote_ids(self):
        eid = sid = None
        if self.vote_election_var.get():
            try: eid = int(self.vote_election_var.get().split(" - ")[0])
            except Exception: eid = None
        if self.vote_station_var.get():
            try: sid = int(self.vote_station_var.get().split(" - ")[0])
            except Exception: sid = None
        return eid, sid

    def load_candidates_for_vote(self):
        eid, _ = self.get_vote_ids()
        if not eid:
            self.vote_candidate_combo["values"] = []; return
        conn = get_connection()
        rows = conn.execute(
            "SELECT id, name, party FROM candidates WHERE election_id=?", (eid,)).fetchall()
        conn.close()
        vals = [f"{r['id']} - {r['name']} ({r['party']})" for r in rows]
        self.vote_candidate_combo["values"] = vals
        if vals: self.vote_candidate_combo.current(0)

    def get_candidate_id_for_vote(self):
        val = self.vote_candidate_var.get()
        if not val: return None
        try: return int(val.split(" - ")[0])
        except Exception: return None

    def submit_vote(self):
        eid, sid = self.get_vote_ids()
        cid = self.get_candidate_id_for_vote()
        nid = self.vote_nid_var.get().strip()

        if not eid or not sid or not cid or not nid:
            messagebox.showerror("Error",
                "Election, station, candidate, and voter ID required."); return

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM voters WHERE national_id=? AND is_eligible=1", (nid,))
        voter = cur.fetchone()
        if not voter:
            conn.close(); messagebox.showerror("Error",
                "Voter not found or not eligible."); return

        cur.execute("SELECT * FROM votes WHERE election_id=? AND voter_id=?",
                    (eid, voter["id"]))
        if cur.fetchone():
            conn.close(); messagebox.showerror("Error",
                "You have already voted in this election."); return

        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cur.execute(
            "INSERT INTO ballots (election_id, voter_id, station_id, issued_at, status) "
            "VALUES (?, ?, ?, ?, ?)",
            (eid, voter["id"], sid, ts, "used"))
        ballot_id = cur.lastrowid

        cur.execute(
            "INSERT INTO votes (election_id, ballot_id, voter_id, candidate_id, station_id, cast_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (eid, ballot_id, voter["id"], cid, sid, ts))
        conn.commit()
        log_system(self.app.current_admin_id, "submit_vote",
                   f"election={eid}, candidate={cid}, voter_nid={nid}")
        conn.close()
        messagebox.showinfo("OK", "Vote recorded.")
        self.vote_nid_var.set("")
        self.load_hourly_stats()

    def load_hourly_stats(self):
        self.stats_tree.delete(*self.stats_tree.get_children())
        eid, sid = self.get_vote_ids()
        if not eid or not sid: return

        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT strftime('%Y-%m-%d %H:00', issued_at) AS hour, COUNT(*) AS cnt
            FROM ballots
            WHERE election_id=? AND station_id=?
            GROUP BY hour ORDER BY hour
            """, (eid, sid))
        ballot_rows = {r["hour"]: r["cnt"] for r in cur.fetchall()}

        cur.execute(
            """
            SELECT strftime('%Y-%m-%d %H:00', cast_at) AS hour, COUNT(*) AS cnt
            FROM votes
            WHERE election_id=? AND station_id=?
            GROUP BY hour ORDER BY hour
            """, (eid, sid))
        vote_rows = {r["hour"]: r["cnt"] for r in cur.fetchall()}
        conn.close()

        hours = sorted(set(list(ballot_rows.keys()) + list(vote_rows.keys())))
        for h in hours:
            self.stats_tree.insert("", tk.END,
                values=(h, ballot_rows.get(h, 0), vote_rows.get(h, 0)))

    def load_complaints(self):
        self.complaints_tree.delete(*self.complaints_tree.get_children())
        conn = get_connection()
        rows = conn.execute(
            """
            SELECT c.id, e.name AS election, s.name AS station,
                   c.complaint_type, c.status, c.created_at
            FROM complaints c
            LEFT JOIN elections e ON c.election_id = e.id
            LEFT JOIN polling_stations s ON c.station_id = s.id
            ORDER BY c.id DESC LIMIT 100
            """
        ).fetchall()
        conn.close()
        for r in rows:
            self.complaints_tree.insert("", tk.END, values=(
                r["id"], r["election"], r["station"],
                r["complaint_type"], r["status"], r["created_at"]))

    def add_complaint_dialog(self):
        dialog = tk.Toplevel(self)
        dialog.title("New Complaint 新增投訴")
        dialog.configure(bg=COLORS["surface"])
        dialog.geometry("480x520")
        dialog.transient(self); dialog.grab_set()

        tk.Label(dialog, text=f"{ICONS['complaint']}  New Complaint",
                 bg=COLORS["surface"], fg=COLORS["text"],
                 font=("Segoe UI", 13, "bold")).pack(pady=(20, 10), padx=20, anchor="w")

        form = tk.Frame(dialog, bg=COLORS["surface"])
        form.pack(fill="both", expand=True, padx=20)
        e_eid  = LabeledEntry(form, "Election ID 選舉 (可空)", icon=ICONS["vote"]);  e_eid.pack(fill="x", pady=6)
        e_sid  = LabeledEntry(form, "Station ID 投票站 (可空)", icon=ICONS["station"]); e_sid.pack(fill="x", pady=6)
        e_vid  = LabeledEntry(form, "Voter ID 身份證 (可空)", icon=ICONS["admin"]);  e_vid.pack(fill="x", pady=6)
        e_type = LabeledEntry(form, "Type 類別", icon=ICONS["edit"]);               e_type.pack(fill="x", pady=6)
        e_desc = LabeledEntry(form, "Description 描述", icon=ICONS["edit"]);        e_desc.pack(fill="x", pady=6)

        def save():
            eid_s = e_eid.get().strip(); sid_s = e_sid.get().strip()
            vid_nid = e_vid.get().strip(); ctype = e_type.get().strip(); desc = e_desc.get().strip()
            if not ctype:
                messagebox.showerror("Error", "Complaint type required."); return

            eid_int = int(eid_s) if eid_s.isdigit() else None
            sid_int = int(sid_s) if sid_s.isdigit() else None
            voter_id = None
            if vid_nid:
                conn = get_connection()
                v = conn.execute("SELECT id FROM voters WHERE national_id=?",
                                 (vid_nid,)).fetchone()
                conn.close()
                if v: voter_id = v["id"]

            conn = get_connection()
            conn.execute(
                """
                INSERT INTO complaints (election_id, station_id, voter_id,
                                        complaint_type, description, created_at, status)
                VALUES (?, ?, ?, ?, ?, datetime('now'), 'open')
                """, (eid_int, sid_int, voter_id, ctype, desc))
            conn.commit(); conn.close()
            log_system(self.app.current_admin_id, "add_complaint", f"type={ctype}")
            dialog.destroy(); self.load_complaints()

        btns = tk.Frame(dialog, bg=COLORS["surface"]); btns.pack(fill="x", padx=20, pady=20)
        IconButton(btns, text="Cancel", icon=ICONS["cancel"], variant="ghost",
                   command=dialog.destroy).pack(side="right", padx=6)
        IconButton(btns, text="Save 儲存", icon=ICONS["save"], variant="primary",
                   command=save).pack(side="right")


# ============================================================
#                  COUNTING
# ============================================================

class CountingFrame(PageFrame):
    page_title = "Counting 點票"
    page_icon  = ICONS["count"]

    def __init__(self, parent, app):
        super().__init__(parent, app)

        wrap = tk.Frame(self.body, bg=COLORS["bg"])
        wrap.pack(fill="both", expand=True, padx=10, pady=10)

        card = Card(wrap, title="Counting 點票結果", icon=ICONS["count"])
        card.pack(fill="both", expand=True)
        body = tk.Frame(card, bg=COLORS["surface"])
        body.pack(fill="both", expand=True, padx=16, pady=(4, 12))

        top = tk.Frame(body, bg=COLORS["surface"]); top.pack(fill="x", pady=(0, 10))
        tk.Label(top, text=f"{ICONS['vote']}  Election 選舉:",
                 bg=COLORS["surface"], fg=COLORS["text_dim"],
                 font=("Segoe UI", 9)).pack(side="left")
        self.election_var = tk.StringVar()
        self.election_combo = ttk.Combobox(top, textvariable=self.election_var,
                                            state="readonly", width=40)
        self.election_combo.pack(side="left", padx=8)
        self.election_combo.bind("<<ComboboxSelected>>", lambda e: self.load_results())

        IconButton(top, text="Refresh 重新整理", icon=ICONS["refresh"],
                   variant="ghost", command=self.load_results).pack(side="right")

        self.tree = make_tree(body, ("candidate", "party", "votes"),
                              (400, 280, 160), height=14)
        self.tree.pack(fill="both", expand=True)

    def refresh(self):
        conn = get_connection()
        rows = conn.execute("SELECT * FROM elections ORDER BY id").fetchall()
        conn.close()
        vals = [f"{r['id']} - {r['name']}" for r in rows]
        self.election_combo["values"] = vals
        if vals: self.election_combo.current(0)
        self.load_results()

    def get_election_id(self):
        val = self.election_var.get()
        if not val: return None
        try: return int(val.split(" - ")[0])
        except Exception: return None

    def load_results(self):
        self.tree.delete(*self.tree.get_children())
        eid = self.get_election_id()
        if not eid: return
        conn = get_connection()
        rows = conn.execute(
            """
            SELECT c.name AS candidate_name, c.party, COUNT(v.id) AS votes
            FROM candidates c
            LEFT JOIN votes v
              ON v.candidate_id = c.id AND v.election_id = c.election_id
            WHERE c.election_id=?
            GROUP BY c.id
            ORDER BY votes DESC
            """, (eid,)).fetchall()
        conn.close()
        for r in rows:
            self.tree.insert("", tk.END,
                values=(r["candidate_name"], r["party"], r["votes"]))


# ============================================================
#                  RECORD
# ============================================================

class RecordFrame(PageFrame):
    page_title = "投票站紀錄 Station Records"
    page_icon  = ICONS["record"]

    def __init__(self, parent, app):
        super().__init__(parent, app)

        wrap = tk.Frame(self.body, bg=COLORS["bg"])
        wrap.pack(fill="both", expand=True, padx=10, pady=10)

        card = Card(wrap, title="Station Records 投票站紀錄", icon=ICONS["record"])
        card.pack(fill="both", expand=True)
        body = tk.Frame(card, bg=COLORS["surface"])
        body.pack(fill="both", expand=True, padx=16, pady=(4, 12))

        top = tk.Frame(body, bg=COLORS["surface"]); top.pack(fill="x", pady=(0, 10))
        tk.Label(top, text=f"{ICONS['station']}  Station 投票站:",
                 bg=COLORS["surface"], fg=COLORS["text_dim"],
                 font=("Segoe UI", 9)).pack(side="left")
        self.station_var = tk.StringVar()
        self.station_combo = ttk.Combobox(top, textvariable=self.station_var,
                                           state="readonly", width=40)
        self.station_combo.pack(side="left", padx=8)
        self.station_combo.bind("<<ComboboxSelected>>", lambda e: self.load_logs())

        IconButton(top, text="Log incident 事件", icon=ICONS["complaint"], variant="primary",
                   command=lambda: self.add_log("incident")).pack(side="right", padx=4)
        IconButton(top, text="Log queue 排隊", icon=ICONS["users"], variant="warning",
                   command=lambda: self.add_log("queue")).pack(side="right", padx=4)
        IconButton(top, text="Log close 關站", icon=ICONS["delete"], variant="danger",
                   command=lambda: self.add_log("close")).pack(side="right", padx=4)
        IconButton(top, text="Log open 開站", icon=ICONS["add"], variant="success",
                   command=lambda: self.add_log("open")).pack(side="right", padx=4)

        self.tree = make_tree(body, ("type", "timestamp", "detail", "queue"),
                              (140, 220, 400, 140), height=14)
        self.tree.pack(fill="both", expand=True)

    def refresh(self):
        conn = get_connection()
        rows = conn.execute("SELECT * FROM polling_stations ORDER BY id").fetchall()
        conn.close()
        vals = [f"{r['id']} - {r['name']}" for r in rows]
        self.station_combo["values"] = vals
        if vals: self.station_combo.current(0)
        self.load_logs()

    def get_station_id(self):
        val = self.station_var.get()
        if not val: return None
        try: return int(val.split(" - ")[0])
        except Exception: return None

    def load_logs(self):
        self.tree.delete(*self.tree.get_children())
        sid = self.get_station_id()
        if not sid: return
        conn = get_connection()
        rows = conn.execute(
            "SELECT * FROM station_logs WHERE station_id=? ORDER BY timestamp DESC LIMIT 100",
            (sid,)).fetchall()
        conn.close()
        for r in rows:
            self.tree.insert("", tk.END, values=(
                r["log_type"], r["timestamp"], r["detail"], r["queue_length"]))

    def add_log(self, log_type):
        sid = self.get_station_id()
        if not sid:
            messagebox.showerror("Error", "Select a station first."); return

        dialog = tk.Toplevel(self)
        dialog.title(f"New {log_type} log 新增紀錄")
        dialog.configure(bg=COLORS["surface"])
        dialog.geometry("440x280")
        dialog.transient(self); dialog.grab_set()

        tk.Label(dialog, text=f"{ICONS['record']}  New {log_type.upper()} Log",
                 bg=COLORS["surface"], fg=COLORS["text"],
                 font=("Segoe UI", 13, "bold")).pack(pady=(20, 10), padx=20, anchor="w")

        form = tk.Frame(dialog, bg=COLORS["surface"])
        form.pack(fill="both", expand=True, padx=20)
        e_detail = LabeledEntry(form, "Detail 詳情", icon=ICONS["edit"]); e_detail.pack(fill="x", pady=6)
        e_queue  = LabeledEntry(form, "Queue length 排隊人數 (queue 時使用)", icon=ICONS["users"])
        e_queue.pack(fill="x", pady=6)

        def save():
            detail = e_detail.get().strip()
            q_val = e_queue.get().strip()
            q_int = int(q_val) if q_val.isdigit() else None
            conn = get_connection()
            conn.execute(
                """
                INSERT INTO station_logs (station_id, log_type, timestamp, detail, queue_length)
                VALUES (?, ?, datetime('now'), ?, ?)
                """, (sid, log_type, detail, q_int))
            conn.commit(); conn.close()
            log_system(self.app.current_admin_id, f"station_log_{log_type}",
                       f"station_id={sid}")
            dialog.destroy(); self.load_logs()

        btns = tk.Frame(dialog, bg=COLORS["surface"]); btns.pack(fill="x", padx=20, pady=20)
        IconButton(btns, text="Cancel", icon=ICONS["cancel"], variant="ghost",
                   command=dialog.destroy).pack(side="right", padx=6)
        IconButton(btns, text="Save 儲存", icon=ICONS["save"], variant="primary",
                   command=save).pack(side="right")


# ============================================================
#                  SETTINGS
# ============================================================

class SettingsFrame(PageFrame):
    page_title = "Settings 設定"
    page_icon  = ICONS["settings"]

    def __init__(self, parent, app):
        super().__init__(parent, app)

        wrap = tk.Frame(self.body, bg=COLORS["bg"])
        wrap.pack(fill="both", expand=True, padx=10, pady=10)

        notebook = ttk.Notebook(wrap, style="EC.TNotebook")
        notebook.pack(fill="both", expand=True)

        self.stations_frame = StationSettingsFrame(notebook, app=app)
        self.accounts_frame = AccountSettingsFrame(notebook, app=app)
        self.logs_frame     = SystemLogsFrame(notebook)
        self.db_frame       = DatabaseInfoFrame(notebook)

        notebook.add(self.stations_frame, text=f"{ICONS['station']}  Stations 投票站")
        notebook.add(self.accounts_frame, text=f"{ICONS['admin']}  Accounts 帳戶")
        notebook.add(self.logs_frame,     text=f"{ICONS['log']}  System Logs 系統紀錄")
        notebook.add(self.db_frame,       text=f"{ICONS['db']}  Database 資料庫")

    def refresh(self):
        self.stations_frame.refresh()
        self.accounts_frame.refresh()
        self.logs_frame.refresh()
        self.db_frame.refresh()


class StationSettingsFrame(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=COLORS["bg"])
        self.app = app

        top = tk.Frame(self, bg=COLORS["bg"]); top.pack(fill="x", padx=10, pady=10)
        tk.Label(top, text=f"{ICONS['station']}  Polling Stations 投票站設定",
                 bg=COLORS["bg"], fg=COLORS["text"],
                 font=("Segoe UI", 12, "bold")).pack(side="left")
        IconButton(top, text="Toggle backup mode 後備模式", icon=ICONS["backup"],
                   variant="warning", command=self.toggle_backup_mode).pack(side="right", padx=4)
        IconButton(top, text="New station 新增投票站", icon=ICONS["add"],
                   variant="primary", command=self.add_station_dialog).pack(side="right", padx=4)

        body = tk.Frame(self, bg=COLORS["bg"]); body.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.tree = make_tree(
            body,
            ("id", "name", "location", "code", "open", "close", "active", "backup"),
            (50, 180, 180, 100, 130, 130, 80, 90), height=14)
        self.tree.pack(fill="both", expand=True)

    def refresh(self): self.load_stations()

    def load_stations(self):
        self.tree.delete(*self.tree.get_children())
        conn = get_connection()
        rows = conn.execute("SELECT * FROM polling_stations ORDER BY id").fetchall()
        conn.close()
        for r in rows:
            self.tree.insert("", tk.END, values=(
                r["id"], r["name"], r["location"], r["code"],
                r["opening_time"], r["closing_time"],
                r["is_active"], r["is_backup_enabled"]))

    def _get_selected_station_id(self):
        sel = self.tree.selection()
        if not sel: return None
        try: return int(self.tree.item(sel[0], "values")[0])
        except Exception: return None

    def add_station_dialog(self):
        dialog = tk.Toplevel(self)
        dialog.title("New Station 新增投票站")
        dialog.configure(bg=COLORS["surface"])
        dialog.geometry("440x360")
        dialog.transient(self); dialog.grab_set()

        tk.Label(dialog, text=f"{ICONS['station']}  New Polling Station",
                 bg=COLORS["surface"], fg=COLORS["text"],
                 font=("Segoe UI", 13, "bold")).pack(pady=(20, 10), padx=20, anchor="w")

        form = tk.Frame(dialog, bg=COLORS["surface"]); form.pack(fill="both", expand=True, padx=20)
        e_name = LabeledEntry(form, "Name 名稱", icon=ICONS["station"]); e_name.pack(fill="x", pady=6)
        e_loc  = LabeledEntry(form, "Location 地點", icon=ICONS["home"]); e_loc.pack(fill="x", pady=6)
        e_code = LabeledEntry(form, "Code 代碼", icon=ICONS["key"]); e_code.pack(fill="x", pady=6)

        def save():
            name = e_name.get().strip(); loc = e_loc.get().strip(); code = e_code.get().strip()
            if not name or not code:
                messagebox.showerror("Error", "Name and code required."); return
            conn = get_connection()
            try:
                conn.execute(
                    "INSERT INTO polling_stations (name, location, code, is_active) "
                    "VALUES (?, ?, ?, 1)", (name, loc, code))
                conn.commit()
                log_system(self.app.current_admin_id, "add_station",
                           f"name={name}, code={code}")
            except sqlite3.IntegrityError:
                messagebox.showerror("Error", "Station code already exists.")
            finally:
                conn.close()
                dialog.destroy()
                self.load_stations()

        btns = tk.Frame(dialog, bg=COLORS["surface"]); btns.pack(fill="x", padx=20, pady=20)
        IconButton(btns, text="Cancel", icon=ICONS["cancel"], variant="ghost",
                   command=dialog.destroy).pack(side="right", padx=6)
        IconButton(btns, text="Save 儲存", icon=ICONS["save"], variant="primary",
                   command=save).pack(side="right")

    def toggle_backup_mode(self):
        sid = self._get_selected_station_id()
        if not sid: messagebox.showerror("Error", "Select a station first."); return
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT is_backup_enabled FROM polling_stations WHERE id=?", (sid,))
        row = cur.fetchone()
        if not row: conn.close(); return
        new_val = 0 if row["is_backup_enabled"] else 1
        cur.execute("UPDATE polling_stations SET is_backup_enabled=? WHERE id=?",
                    (new_val, sid))
        conn.commit(); conn.close()
        log_system(self.app.current_admin_id, "toggle_backup",
                   f"station_id={sid}, new={new_val}")
        self.load_stations()


class AccountSettingsFrame(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=COLORS["bg"])
        self.app = app

        top = tk.Frame(self, bg=COLORS["bg"]); top.pack(fill="x", padx=10, pady=10)
        tk.Label(top, text=f"{ICONS['admin']}  Admin Accounts 帳戶設定",
                 bg=COLORS["bg"], fg=COLORS["text"],
                 font=("Segoe UI", 12, "bold")).pack(side="left")
        IconButton(top, text="Deactivate 啟用/停用", icon=ICONS["lock"],
                   variant="warning", command=self.toggle_active).pack(side="right", padx=4)
        IconButton(top, text="New admin 新增帳戶", icon=ICONS["add"],
                   variant="primary", command=self.add_admin_dialog).pack(side="right", padx=4)

        body = tk.Frame(self, bg=COLORS["bg"]); body.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.tree = make_tree(body,
                              ("id", "username", "full_name", "role", "active", "created_at"),
                              (50, 160, 220, 150, 80, 180), height=14)
        self.tree.pack(fill="both", expand=True)

    def refresh(self): self.load_admins()

    def load_admins(self):
        self.tree.delete(*self.tree.get_children())
        conn = get_connection()
        rows = conn.execute("SELECT * FROM admin_users ORDER BY id").fetchall()
        conn.close()
        for r in rows:
            self.tree.insert("", tk.END, values=(
                r["id"], r["username"], r["full_name"], r["role"],
                r["is_active"], r["created_at"]))

    def _get_selected_admin_id(self):
        sel = self.tree.selection()
        if not sel: return None
        try: return int(self.tree.item(sel[0], "values")[0])
        except Exception: return None

    def add_admin_dialog(self):
        dialog = tk.Toplevel(self)
        dialog.title("New Admin 新增帳戶")
        dialog.configure(bg=COLORS["surface"])
        dialog.geometry("460x440")
        dialog.transient(self); dialog.grab_set()

        tk.Label(dialog, text=f"{ICONS['admin']}  New Admin Account",
                 bg=COLORS["surface"], fg=COLORS["text"],
                 font=("Segoe UI", 13, "bold")).pack(pady=(20, 10), padx=20, anchor="w")

        form = tk.Frame(dialog, bg=COLORS["surface"]); form.pack(fill="both", expand=True, padx=20)
        e_u = LabeledEntry(form, "Username 帳戶", icon=ICONS["admin"]); e_u.pack(fill="x", pady=6)
        e_p = LabeledEntry(form, "Password 密碼", icon=ICONS["lock"], show="*"); e_p.pack(fill="x", pady=6)
        e_n = LabeledEntry(form, "Full name 姓名", icon=ICONS["admin"]); e_n.pack(fill="x", pady=6)
        e_r = LabeledEntry(form, "Role 角色", icon=ICONS["shield"]); e_r.pack(fill="x", pady=6)
        e_r.set("admin")

        def save():
            u = e_u.get().strip(); p = e_p.get().strip()
            n = e_n.get().strip(); r = e_r.get().strip()
            if not u or not p or not r:
                messagebox.showerror("Error", "Username, password, role required."); return
            conn = get_connection()
            try:
                conn.execute(
                    "INSERT INTO admin_users (username, password, full_name, role, is_active) "
                    "VALUES (?, ?, ?, ?, 1)",
                    (u, hash_password(p), n, r))
                conn.commit()
                log_system(self.app.current_admin_id, "create_admin", f"username={u}")
            except sqlite3.IntegrityError:
                messagebox.showerror("Error", "Username already exists.")
            finally:
                conn.close()
                dialog.destroy()
                self.load_admins()

        btns = tk.Frame(dialog, bg=COLORS["surface"]); btns.pack(fill="x", padx=20, pady=20)
        IconButton(btns, text="Cancel", icon=ICONS["cancel"], variant="ghost",
                   command=dialog.destroy).pack(side="right", padx=6)
        IconButton(btns, text="Save 儲存", icon=ICONS["save"], variant="primary",
                   command=save).pack(side="right")

    def toggle_active(self):
        aid = self._get_selected_admin_id()
        if not aid: messagebox.showerror("Error", "Select an admin first."); return
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT is_active FROM admin_users WHERE id=?", (aid,))
        row = cur.fetchone()
        if not row: conn.close(); return
        new_val = 0 if row["is_active"] else 1
        cur.execute("UPDATE admin_users SET is_active=? WHERE id=?", (new_val, aid))
        conn.commit(); conn.close()
        log_system(self.app.current_admin_id, "toggle_admin_active",
                   f"admin_id={aid}, new={new_val}")
        self.load_admins()


class SystemLogsFrame(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=COLORS["bg"])

        top = tk.Frame(self, bg=COLORS["bg"]); top.pack(fill="x", padx=10, pady=10)
        tk.Label(top, text=f"{ICONS['log']}  System Logs 系統紀錄",
                 bg=COLORS["bg"], fg=COLORS["text"],
                 font=("Segoe UI", 12, "bold")).pack(side="left")
        IconButton(top, text="Refresh", icon=ICONS["refresh"], variant="ghost",
                   command=self.refresh).pack(side="right")

        body = tk.Frame(self, bg=COLORS["bg"]); body.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.tree = make_tree(body,
                              ("id", "admin", "action", "detail", "created_at"),
                              (60, 140, 200, 380, 190), height=14)
        self.tree.pack(fill="both", expand=True)

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        conn = get_connection()
        rows = conn.execute(
            """
            SELECT l.id, a.username AS admin, l.action, l.detail, l.created_at
            FROM system_logs l
            LEFT JOIN admin_users a ON l.admin_id = a.id
            ORDER BY l.id DESC LIMIT 200
            """
        ).fetchall()
        conn.close()
        for r in rows:
            self.tree.insert("", tk.END, values=(
                r["id"], r["admin"] or "(anonymous)", r["action"],
                r["detail"], r["created_at"]))


class DatabaseInfoFrame(tk.Frame):
    """Shows DB path, table row counts, and quick actions."""
    def __init__(self, parent):
        super().__init__(parent, bg=COLORS["bg"])

        top = tk.Frame(self, bg=COLORS["bg"]); top.pack(fill="x", padx=10, pady=10)
        tk.Label(top, text=f"{ICONS['db']}  Database 資料庫",
                 bg=COLORS["bg"], fg=COLORS["text"],
                 font=("Segoe UI", 12, "bold")).pack(side="left")
        IconButton(top, text="Refresh", icon=ICONS["refresh"], variant="ghost",
                   command=self.refresh).pack(side="right")

        card = Card(self, title="SQLite Database Info", icon=ICONS["db"])
        card.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        body = tk.Frame(card, bg=COLORS["surface"])
        body.pack(fill="both", expand=True, padx=20, pady=16)

        self.path_label = tk.Label(body, text="", bg=COLORS["surface"],
                                   fg=COLORS["text"], font=("Consolas", 10))
        self.path_label.pack(anchor="w", pady=(0, 4))

        self.size_label = tk.Label(body, text="", bg=COLORS["surface"],
                                   fg=COLORS["text_dim"], font=("Segoe UI", 9))
        self.size_label.pack(anchor="w", pady=(0, 16))

        self.tree = make_tree(body, ("table", "rows"),
                              (320, 160), height=11)
        self.tree.pack(fill="x", expand=False)

    def refresh(self):
        self.path_label.config(text=f"{ICONS['db']}  {os.path.abspath(DB_FILE)}")
        try:
            size = os.path.getsize(DB_FILE)
            self.size_label.config(text=f"File size: {size:,} bytes "
                                        f"({size/1024:.1f} KB)")
        except OSError:
            self.size_label.config(text="File not found")

        self.tree.delete(*self.tree.get_children())
        for tbl, cnt in db_stats().items():
            self.tree.insert("", tk.END, values=(tbl, cnt))


# ============================================================
#                  MAIN
# ============================================================

if __name__ == "__main__":
    init_db()
    app = App()
    app.mainloop()
