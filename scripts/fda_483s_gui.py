"""
FDA 483 Inspection Explorer – GUI
=================================
Tkinter front-end that wraps fda_483s.py.

Features:
  • Date-range pickers (From / To)
  • Product-type dropdown (Drugs, Devices, Biologics, etc.)
  • Classification checkboxes (NAI, VAI, OAI)
  • Selectable inspection & citation column lists
  • Toggle to also fetch 483 observation citations
  • Output-format radio buttons (CSV, JSON, or both)
  • Output-directory chooser
  • Live scrolling log panel
  • Background-threaded API calls to keep the UI responsive

State-machine for the Run button:
  IDLE  → user clicks Run → RUNNING (button disabled, progress bar active)
  RUNNING → fetch completes → IDLE (button re-enabled, results logged)
  RUNNING → error occurs    → IDLE (button re-enabled, error logged)
"""

import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime

# ---------------------------------------------------------------------------
# Import the core API helpers from the sibling module
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fda_483s as api

# ---------------------------------------------------------------------------
# Constants – column options surfaced in the GUI
# ---------------------------------------------------------------------------
ALL_INSPECTION_COLUMNS = [
    "FEINumber", "LegalName", "AddressLine1", "City", "StateCode",
    "CountryName", "InspectionID", "InspectionEndDate", "FiscalYear",
    "Classification", "ClassificationCode", "ProductType",
    "PostedCitations", "ProjectArea", "FirmProfile",
]

ALL_CITATION_COLUMNS = [
    "FEINumber", "LegalName", "InspectionID", "InspectionEndDate",
    "CitationID", "ActCFRNumber", "ShortDescription", "LongDescription",
    "ProgramArea",
]

PRODUCT_TYPES = ["Drugs", "Devices", "Biologics", "Tobacco", "Veterinary", "Food"]
CLASSIFICATION_CODES = ["NAI", "VAI", "OAI"]

# ---------------------------------------------------------------------------
# Color palette & style tokens
# ---------------------------------------------------------------------------
BG_DARK      = "#1a1b2e"
BG_CARD      = "#232440"
BG_INPUT     = "#2c2d50"
FG_TEXT       = "#e0e0f0"
FG_DIM        = "#8888aa"
ACCENT        = "#6c63ff"
ACCENT_HOVER  = "#8b83ff"
ACCENT_ACTIVE = "#5046e0"
SUCCESS       = "#2ecc71"
ERROR_CLR     = "#e74c3c"
BORDER        = "#3a3b5c"
HIGHLIGHT     = "#3d3e66"


# ═══════════════════════════════════════════════════════════════════════════
# Main Application Window
# ═══════════════════════════════════════════════════════════════════════════
class FDAExplorerApp(tk.Tk):
    """Top-level window for the FDA 483 Explorer GUI."""

    def __init__(self):
        super().__init__()

        self.title("FDA 483 Inspection Explorer")
        self.configure(bg=BG_DARK)
        self.minsize(960, 740)
        self.geometry("1060x820")

        # ---- State variables ----
        self.date_from_var = tk.StringVar(value="2025-01-01")
        self.date_to_var   = tk.StringVar(value="2025-12-31")
        self.product_var   = tk.StringVar(value="Drugs")
        self.fetch_citations_var = tk.BooleanVar(value=True)
        self.output_format_var   = tk.StringVar(value="both")
        self.output_dir_var = tk.StringVar(
            value=os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'outputs'))
        )

        # Classification checkbox vars
        self.class_vars = {}
        for code in CLASSIFICATION_CODES:
            v = tk.BooleanVar(value=(code in ("VAI", "OAI")))
            self.class_vars[code] = v

        # Column checkbox vars
        self.insp_col_vars = {c: tk.BooleanVar(value=True) for c in ALL_INSPECTION_COLUMNS}
        self.cite_col_vars = {c: tk.BooleanVar(value=True) for c in ALL_CITATION_COLUMNS}

        self._running = False

        # ---- Build the UI ----
        self._apply_styles()
        self._build_ui()

    # ------------------------------------------------------------------
    # Styling
    # ------------------------------------------------------------------
    def _apply_styles(self):
        """Configure ttk styles for the dark theme."""
        style = ttk.Style(self)
        style.theme_use("clam")

        style.configure(".", background=BG_DARK, foreground=FG_TEXT,
                         fieldbackground=BG_INPUT, bordercolor=BORDER,
                         darkcolor=BG_DARK, lightcolor=BG_DARK,
                         troughcolor=BG_CARD, selectbackground=ACCENT,
                         selectforeground="#ffffff", font=("Segoe UI", 10))

        style.configure("TFrame", background=BG_DARK)
        style.configure("Card.TFrame", background=BG_CARD, relief="flat")
        style.configure("TLabel", background=BG_DARK, foreground=FG_TEXT,
                         font=("Segoe UI", 10))
        style.configure("Card.TLabel", background=BG_CARD)
        style.configure("Header.TLabel", font=("Segoe UI Semibold", 12),
                         foreground=ACCENT, background=BG_CARD)
        style.configure("Title.TLabel", font=("Segoe UI Bold", 16),
                         foreground="#ffffff", background=BG_DARK)
        style.configure("Dim.TLabel", foreground=FG_DIM, background=BG_DARK)

        style.configure("TCheckbutton", background=BG_CARD, foreground=FG_TEXT,
                         font=("Segoe UI", 9))
        style.map("TCheckbutton",
                   background=[("active", HIGHLIGHT)],
                   foreground=[("disabled", FG_DIM)])

        style.configure("TRadiobutton", background=BG_CARD, foreground=FG_TEXT,
                         font=("Segoe UI", 9))
        style.map("TRadiobutton", background=[("active", HIGHLIGHT)])

        style.configure("TEntry", fieldbackground=BG_INPUT, foreground=FG_TEXT,
                         insertcolor=FG_TEXT, bordercolor=BORDER,
                         lightcolor=BORDER, darkcolor=BORDER)

        style.configure("TCombobox", fieldbackground=BG_INPUT, foreground=FG_TEXT,
                         selectbackground=ACCENT, arrowcolor=ACCENT)
        style.map("TCombobox", fieldbackground=[("readonly", BG_INPUT)])

        # Accent button
        style.configure("Accent.TButton", background=ACCENT, foreground="#ffffff",
                         font=("Segoe UI Semibold", 11), padding=(20, 10),
                         bordercolor=ACCENT)
        style.map("Accent.TButton",
                   background=[("active", ACCENT_HOVER), ("disabled", BORDER)],
                   foreground=[("disabled", FG_DIM)])

        # Small utility button
        style.configure("Small.TButton", background=BG_INPUT, foreground=FG_TEXT,
                         font=("Segoe UI", 9), padding=(8, 4))
        style.map("Small.TButton", background=[("active", HIGHLIGHT)])

        # Progress bar
        style.configure("Accent.Horizontal.TProgressbar",
                         troughcolor=BG_CARD, background=ACCENT, bordercolor=BG_CARD)

        style.configure("TLabelframe", background=BG_CARD, foreground=ACCENT,
                         bordercolor=BORDER)
        style.configure("TLabelframe.Label", background=BG_CARD, foreground=ACCENT,
                         font=("Segoe UI Semibold", 10))

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------
    def _build_ui(self):
        """Assemble all GUI sections."""
        # Title bar
        title_frame = ttk.Frame(self)
        title_frame.pack(fill="x", padx=16, pady=(14, 4))
        ttk.Label(title_frame, text="🔬  FDA 483 Inspection Explorer",
                  style="Title.TLabel").pack(side="left")
        ttk.Label(title_frame, text="Query the FDA Data Dashboard API",
                  style="Dim.TLabel").pack(side="left", padx=(12, 0))

        # Main content area (scrollable via canvas is overkill; use pack)
        content = ttk.Frame(self)
        content.pack(fill="both", expand=True, padx=16, pady=8)

        # Top row: Filters | Options
        top = ttk.Frame(content)
        top.pack(fill="x", pady=(0, 8))
        top.columnconfigure(0, weight=1)
        top.columnconfigure(1, weight=1)

        self._build_filters_card(top).grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        self._build_options_card(top).grid(row=0, column=1, sticky="nsew", padx=(6, 0))

        # Middle row: Column selectors
        mid = ttk.Frame(content)
        mid.pack(fill="x", pady=(0, 8))
        mid.columnconfigure(0, weight=1)
        mid.columnconfigure(1, weight=1)

        self._build_column_card(
            mid, "Inspection Columns", self.insp_col_vars, ALL_INSPECTION_COLUMNS
        ).grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        self._build_column_card(
            mid, "Citation Columns", self.cite_col_vars, ALL_CITATION_COLUMNS
        ).grid(row=0, column=1, sticky="nsew", padx=(6, 0))

        # Run button + progress
        run_frame = ttk.Frame(content)
        run_frame.pack(fill="x", pady=(0, 8))

        self.run_btn = ttk.Button(run_frame, text="▶  Run Query",
                                  style="Accent.TButton", command=self._on_run)
        self.run_btn.pack(side="left")

        self.progress = ttk.Progressbar(run_frame, mode="indeterminate",
                                        style="Accent.Horizontal.TProgressbar",
                                        length=260)
        self.progress.pack(side="left", padx=(16, 0), fill="x", expand=True)

        self.status_label = ttk.Label(run_frame, text="Ready", style="Dim.TLabel")
        self.status_label.pack(side="right", padx=(12, 0))

        # Log panel
        log_frame = ttk.LabelFrame(content, text="  Log  ")
        log_frame.pack(fill="both", expand=True)

        self.log_text = tk.Text(
            log_frame, bg=BG_INPUT, fg=FG_TEXT, font=("Consolas", 9),
            insertbackground=FG_TEXT, relief="flat", wrap="word",
            highlightthickness=0, padx=8, pady=6, state="disabled",
        )
        log_scroll = ttk.Scrollbar(log_frame, orient="vertical",
                                    command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scroll.set)
        log_scroll.pack(side="right", fill="y")
        self.log_text.pack(fill="both", expand=True)

        # Configure log text tags for color-coded messages
        self.log_text.tag_configure("info",    foreground=FG_TEXT)
        self.log_text.tag_configure("success", foreground=SUCCESS)
        self.log_text.tag_configure("error",   foreground=ERROR_CLR)
        self.log_text.tag_configure("accent",  foreground=ACCENT)

    # ------------------------------------------------------------------
    # Card builders
    # ------------------------------------------------------------------
    def _card(self, parent):
        """Create a rounded-look card frame."""
        card = ttk.Frame(parent, style="Card.TFrame", padding=12)
        return card

    def _build_filters_card(self, parent):
        """Date range, product type, classifications."""
        card = self._card(parent)

        ttk.Label(card, text="Filters", style="Header.TLabel").grid(
            row=0, column=0, columnspan=4, sticky="w", pady=(0, 8))

        # Date from
        ttk.Label(card, text="Date From:", style="Card.TLabel").grid(
            row=1, column=0, sticky="e", padx=(0, 6))
        ttk.Entry(card, textvariable=self.date_from_var, width=14).grid(
            row=1, column=1, sticky="w")

        # Date to
        ttk.Label(card, text="Date To:", style="Card.TLabel").grid(
            row=1, column=2, sticky="e", padx=(16, 6))
        ttk.Entry(card, textvariable=self.date_to_var, width=14).grid(
            row=1, column=3, sticky="w")

        # Product type
        ttk.Label(card, text="Product Type:", style="Card.TLabel").grid(
            row=2, column=0, sticky="e", padx=(0, 6), pady=(8, 0))
        combo = ttk.Combobox(card, textvariable=self.product_var,
                             values=PRODUCT_TYPES, state="readonly", width=16)
        combo.grid(row=2, column=1, sticky="w", pady=(8, 0))

        # Classifications
        ttk.Label(card, text="Classifications:", style="Card.TLabel").grid(
            row=3, column=0, sticky="ne", padx=(0, 6), pady=(8, 0))
        cls_frame = ttk.Frame(card, style="Card.TFrame")
        cls_frame.grid(row=3, column=1, columnspan=3, sticky="w", pady=(8, 0))
        for code in CLASSIFICATION_CODES:
            ttk.Checkbutton(cls_frame, text=code, variable=self.class_vars[code]
                            ).pack(side="left", padx=(0, 14))

        return card

    def _build_options_card(self, parent):
        """Citations toggle, output format, output directory."""
        card = self._card(parent)

        ttk.Label(card, text="Options", style="Header.TLabel").grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 8))

        # Fetch citations
        ttk.Checkbutton(card, text="Also fetch 483 citations",
                         variable=self.fetch_citations_var).grid(
            row=1, column=0, columnspan=3, sticky="w")

        # Output format
        ttk.Label(card, text="Output Format:", style="Card.TLabel").grid(
            row=2, column=0, sticky="w", pady=(10, 0))
        fmt_frame = ttk.Frame(card, style="Card.TFrame")
        fmt_frame.grid(row=2, column=1, columnspan=2, sticky="w", pady=(10, 0))
        for val, lbl in [("csv", "CSV"), ("json", "JSON"), ("both", "Both")]:
            ttk.Radiobutton(fmt_frame, text=lbl, variable=self.output_format_var,
                             value=val).pack(side="left", padx=(0, 14))

        # Output directory
        ttk.Label(card, text="Output Dir:", style="Card.TLabel").grid(
            row=3, column=0, sticky="w", pady=(10, 0))
        dir_entry = ttk.Entry(card, textvariable=self.output_dir_var, width=28)
        dir_entry.grid(row=3, column=1, sticky="we", pady=(10, 0), padx=(0, 6))
        ttk.Button(card, text="Browse…", style="Small.TButton",
                   command=self._browse_dir).grid(
            row=3, column=2, sticky="w", pady=(10, 0))

        card.columnconfigure(1, weight=1)
        return card

    def _build_column_card(self, parent, title, var_dict, col_list):
        """Checkbox list with Select All / Clear All buttons."""
        card = self._card(parent)

        header = ttk.Frame(card, style="Card.TFrame")
        header.pack(fill="x")
        ttk.Label(header, text=title, style="Header.TLabel").pack(side="left")

        btn_frame = ttk.Frame(header, style="Card.TFrame")
        btn_frame.pack(side="right")
        ttk.Button(btn_frame, text="All", style="Small.TButton",
                   command=lambda: self._set_all(var_dict, True)).pack(
            side="left", padx=(0, 4))
        ttk.Button(btn_frame, text="None", style="Small.TButton",
                   command=lambda: self._set_all(var_dict, False)).pack(side="left")

        cols_frame = ttk.Frame(card, style="Card.TFrame")
        cols_frame.pack(fill="x", pady=(6, 0))

        # Lay out in two sub-columns for compactness
        mid = len(col_list) // 2 + len(col_list) % 2
        left = ttk.Frame(cols_frame, style="Card.TFrame")
        right = ttk.Frame(cols_frame, style="Card.TFrame")
        left.pack(side="left", fill="x", expand=True)
        right.pack(side="left", fill="x", expand=True)

        for i, col in enumerate(col_list):
            target = left if i < mid else right
            ttk.Checkbutton(target, text=col, variable=var_dict[col]).pack(
                anchor="w", pady=1)

        return card

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _set_all(var_dict, value):
        for v in var_dict.values():
            v.set(value)

    def _browse_dir(self):
        d = filedialog.askdirectory(initialdir=self.output_dir_var.get())
        if d:
            self.output_dir_var.set(d)

    def _log(self, msg, tag="info"):
        """Append a line to the log panel (thread-safe via after())."""
        def _append():
            self.log_text.configure(state="normal")
            self.log_text.insert("end", msg + "\n", tag)
            self.log_text.see("end")
            self.log_text.configure(state="disabled")
        self.after(0, _append)

    def _set_status(self, text):
        self.after(0, lambda: self.status_label.configure(text=text))

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    def _validate_inputs(self):
        """Return True if all user inputs are valid, else show error."""
        # Date format check
        for label, var in [("Date From", self.date_from_var),
                           ("Date To", self.date_to_var)]:
            try:
                datetime.strptime(var.get().strip(), "%Y-%m-%d")
            except ValueError:
                messagebox.showerror("Invalid Date",
                    f"{label} must be in YYYY-MM-DD format.")
                return False

        # At least one classification selected
        if not any(v.get() for v in self.class_vars.values()):
            messagebox.showerror("No Classification",
                "Select at least one classification code.")
            return False

        # At least one inspection column
        if not any(v.get() for v in self.insp_col_vars.values()):
            messagebox.showerror("No Columns",
                "Select at least one inspection column.")
            return False

        # If fetching citations, need at least one citation column
        if self.fetch_citations_var.get() and not any(v.get() for v in self.cite_col_vars.values()):
            messagebox.showerror("No Citation Columns",
                "Select at least one citation column, or disable citation fetching.")
            return False

        return True

    # ------------------------------------------------------------------
    # Run logic (background thread)
    # ------------------------------------------------------------------
    def _on_run(self):
        """Validate inputs and kick off the API fetch on a background thread."""
        if self._running:
            return
        if not self._validate_inputs():
            return

        self._running = True
        self.run_btn.configure(state="disabled")
        self.progress.start(14)
        self._set_status("Fetching…")
        self._log("=" * 60, "accent")
        self._log(f"Starting query at {datetime.now():%Y-%m-%d %H:%M:%S}", "accent")

        threading.Thread(target=self._run_query, daemon=True).start()

    def _run_query(self):
        """Execute the API calls (runs on a background thread)."""
        try:
            date_from = self.date_from_var.get().strip()
            date_to   = self.date_to_var.get().strip()
            product   = self.product_var.get()
            out_dir   = self.output_dir_var.get()
            fmt       = self.output_format_var.get()

            classifications = [c for c, v in self.class_vars.items() if v.get()]
            insp_cols = [c for c, v in self.insp_col_vars.items() if v.get()]
            cite_cols = [c for c, v in self.cite_col_vars.items() if v.get()]

            # Temporarily override module-level column lists
            orig_insp = api.INSPECTION_COLUMNS[:]
            orig_cite = api.CITATION_COLUMNS[:]
            api.INSPECTION_COLUMNS = insp_cols
            api.CITATION_COLUMNS = cite_cols

            # -- Step 1: Fetch inspections --
            self._log(f"Product type : {product}")
            self._log(f"Date range   : {date_from} → {date_to}")
            self._log(f"Classifications: {classifications}")
            self._log(f"Inspection columns: {len(insp_cols)} selected")

            self._set_status("Fetching inspections…")
            inspections = api.fetch_inspections(
                date_from=date_from,
                date_to=date_to,
                product_type=product,
                classifications=classifications,
            )
            self._log(f"✓ {len(inspections)} inspection records fetched.", "success")

            # Build a year-tag for filenames
            year_tag = date_from[:4]
            prefix = product.lower()

            # Save inspections
            if inspections:
                base = os.path.join(out_dir, f"{prefix}_483_inspections_{year_tag}")
                if fmt in ("json", "both"):
                    api.save_to_json(inspections, base + ".json")
                    self._log(f"  Saved → {base}.json", "success")
                if fmt in ("csv", "both"):
                    api.save_to_csv(inspections, base + ".csv")
                    self._log(f"  Saved → {base}.csv", "success")
            else:
                self._log("No inspection records returned.", "error")

            # -- Step 2: Optionally fetch citations --
            if self.fetch_citations_var.get() and inspections:
                self._set_status("Fetching citations…")
                # Need PostedCitations in results to filter; fall back to all FEIs
                feis = list({
                    r["FEINumber"] for r in inspections
                    if r.get("PostedCitations") not in (None, "", "0", 0, False)
                })
                if not feis:
                    # If PostedCitations wasn't in selected columns, use all FEIs
                    feis = list({r.get("FEINumber") for r in inspections if r.get("FEINumber")})

                self._log(f"\n{len(feis)} unique FEIs with posted citations.", "info")
                self._log(f"Citation columns: {len(cite_cols)} selected")

                citations = api.fetch_citations(feis)
                self._log(f"✓ {len(citations)} citation records fetched.", "success")

                if citations:
                    base = os.path.join(out_dir, f"{prefix}_483_citations_{year_tag}")
                    if fmt in ("json", "both"):
                        api.save_to_json(citations, base + ".json")
                        self._log(f"  Saved → {base}.json", "success")
                    if fmt in ("csv", "both"):
                        api.save_to_csv(citations, base + ".csv")
                        self._log(f"  Saved → {base}.csv", "success")
                else:
                    self._log("No citation records returned.", "error")

            # Restore original column lists
            api.INSPECTION_COLUMNS = orig_insp
            api.CITATION_COLUMNS = orig_cite

            self._log(f"\nDone at {datetime.now():%H:%M:%S}.", "accent")
            self._set_status("Done ✓")

        except Exception as exc:
            self._log(f"\n✗ ERROR: {exc}", "error")
            self._set_status("Error")
        finally:
            self.after(0, self._finish_run)

    def _finish_run(self):
        """Re-enable controls after the background task completes."""
        self._running = False
        self.progress.stop()
        self.run_btn.configure(state="normal")


# ═══════════════════════════════════════════════════════════════════════════
# Entry point
# ═══════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    app = FDAExplorerApp()
    app.mainloop()
