"""
FDA 483 Citation Analysis Report Generator
==========================================
Interactive CLI script that loads FDA 483 citation & inspection CSVs,
lets the user pick which analyses to run, then generates a self-contained
HTML report with embedded charts and data tables.

State machine
-------------
  MENU  →  user picks analyses  →  LOAD  →  ANALYZE  →  RENDER  →  DONE

Analysis modules (user-selectable)
----------------------------------
  1. Top CFR Violations         – bar chart + ranked table
  2. Most-Cited Firms           – bar chart + ranked table
  3. Citations Over Time        – monthly time-series line chart
  4. Program Area Breakdown     – donut chart
  5. Co-Occurrence Analysis     – heatmap of violations that appear together
  6. Repeat Offender Analysis   – firms with multiple inspections ranked by severity
  7. All of the above
"""

import os
import io
import sys
import base64
from datetime import datetime
from collections import Counter
from itertools import combinations

import pandas as pd
import matplotlib
matplotlib.use("Agg")  # headless backend – no GUI window
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import seaborn as sns

# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------
SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR  = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "outputs"))

CITATIONS_CSV   = os.path.join(OUTPUT_DIR, "drugs_483_citations_2025.csv")
INSPECTIONS_CSV = os.path.join(OUTPUT_DIR, "drugs_483_inspections_2025.csv")

# ---------------------------------------------------------------------------
# Chart style constants  (dark theme matching the GUI palette)
# ---------------------------------------------------------------------------
BG_DARK   = "#1a1b2e"
BG_CARD   = "#232440"
FG_TEXT   = "#e0e0f0"
ACCENT    = "#6c63ff"
ACCENT2   = "#8b83ff"
GRID_CLR  = "#3a3b5c"
PALETTE   = ["#6c63ff", "#8b83ff", "#2ecc71", "#e74c3c", "#f39c12",
             "#1abc9c", "#3498db", "#e67e22", "#9b59b6", "#e84393"]

plt.rcParams.update({
    "figure.facecolor": BG_DARK,
    "axes.facecolor":   BG_CARD,
    "axes.edgecolor":   GRID_CLR,
    "axes.labelcolor":  FG_TEXT,
    "text.color":       FG_TEXT,
    "xtick.color":      FG_TEXT,
    "ytick.color":      FG_TEXT,
    "grid.color":       GRID_CLR,
    "grid.alpha":       0.4,
    "font.family":      "sans-serif",
    "font.size":        10,
})


# ═══════════════════════════════════════════════════════════════════════════
# Helper utilities
# ═══════════════════════════════════════════════════════════════════════════

def fig_to_base64(fig: plt.Figure) -> str:
    """Render a matplotlib figure to a base64-encoded PNG string."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")


def make_html_table(df: pd.DataFrame) -> str:
    """Convert a DataFrame to a styled HTML <table> string."""
    rows = []
    rows.append("<table>")
    rows.append("<thead><tr>" +
                "".join(f"<th>{c}</th>" for c in df.columns) +
                "</tr></thead>")
    rows.append("<tbody>")
    for _, row in df.iterrows():
        rows.append("<tr>" +
                    "".join(f"<td>{v}</td>" for v in row) +
                    "</tr>")
    rows.append("</tbody></table>")
    return "\n".join(rows)


# ═══════════════════════════════════════════════════════════════════════════
# Analysis functions  –  each returns an HTML section string
# ═══════════════════════════════════════════════════════════════════════════

def analyze_top_violations(df: pd.DataFrame, top_n: int = 15) -> str:
    """Section 1 – Top CFR Violations bar chart + table."""
    counts = df["ActCFRNumber"].value_counts().head(top_n)

    # Bar chart
    fig, ax = plt.subplots(figsize=(10, 5))
    bars = ax.barh(counts.index[::-1], counts.values[::-1], color=PALETTE[0],
                   edgecolor=ACCENT2, linewidth=0.5)
    ax.set_xlabel("Number of Citations")
    ax.set_title(f"Top {top_n} CFR Violations", fontsize=14, fontweight="bold")
    ax.grid(axis="x", linestyle="--")
    for bar in bars:
        ax.text(bar.get_width() + 5, bar.get_y() + bar.get_height() / 2,
                f"{int(bar.get_width())}", va="center", fontsize=8, color=FG_TEXT)
    img = fig_to_base64(fig)

    # Table
    tbl_df = counts.reset_index()
    tbl_df.columns = ["CFR Number", "Citation Count"]
    tbl_df["Rank"] = range(1, len(tbl_df) + 1)
    tbl_df = tbl_df[["Rank", "CFR Number", "Citation Count"]]

    return f"""
    <section>
      <h2>1. Top {top_n} CFR Violations</h2>
      <p>The most frequently cited Code of Federal Regulations sections across
         all inspections in the dataset.</p>
      <img src="data:image/png;base64,{img}" alt="Top CFR Violations" />
      {make_html_table(tbl_df)}
    </section>"""


def analyze_most_cited_firms(df: pd.DataFrame, top_n: int = 15) -> str:
    """Section 2 – Most-cited firms bar chart + table."""
    counts = df["LegalName"].value_counts().head(top_n)

    fig, ax = plt.subplots(figsize=(10, 5))
    bars = ax.barh(counts.index[::-1], counts.values[::-1], color=PALETTE[2],
                   edgecolor="#27ae60", linewidth=0.5)
    ax.set_xlabel("Number of Citations")
    ax.set_title(f"Top {top_n} Most-Cited Firms", fontsize=14, fontweight="bold")
    ax.grid(axis="x", linestyle="--")
    for bar in bars:
        ax.text(bar.get_width() + 2, bar.get_y() + bar.get_height() / 2,
                f"{int(bar.get_width())}", va="center", fontsize=8, color=FG_TEXT)
    img = fig_to_base64(fig)

    tbl_df = counts.reset_index()
    tbl_df.columns = ["Firm Name", "Citation Count"]
    tbl_df["Rank"] = range(1, len(tbl_df) + 1)
    tbl_df = tbl_df[["Rank", "Firm Name", "Citation Count"]]

    return f"""
    <section>
      <h2>2. Top {top_n} Most-Cited Firms</h2>
      <p>Firms receiving the highest number of 483 citations across all
         inspections in the dataset.</p>
      <img src="data:image/png;base64,{img}" alt="Most-Cited Firms" />
      {make_html_table(tbl_df)}
    </section>"""


def analyze_citations_over_time(df: pd.DataFrame) -> str:
    """Section 3 – Monthly citation volume time-series line chart."""
    tmp = df.copy()
    tmp["InspectionEndDate"] = pd.to_datetime(tmp["InspectionEndDate"],
                                               errors="coerce")
    tmp = tmp.dropna(subset=["InspectionEndDate"])
    tmp["YearMonth"] = tmp["InspectionEndDate"].dt.to_period("M")

    monthly = tmp.groupby("YearMonth").size()
    # Filter to only include periods with reasonable data
    monthly = monthly[monthly.index >= "2020-01"]

    fig, ax = plt.subplots(figsize=(12, 4.5))
    x_labels = [str(p) for p in monthly.index]
    ax.plot(x_labels, monthly.values, color=ACCENT, linewidth=2, marker="o",
            markersize=3, markerfacecolor=ACCENT2)
    ax.fill_between(x_labels, monthly.values, alpha=0.15, color=ACCENT)
    ax.set_xlabel("Month")
    ax.set_ylabel("Citations")
    ax.set_title("483 Citations Over Time (Monthly)", fontsize=14,
                 fontweight="bold")
    ax.grid(axis="y", linestyle="--")
    # Show every 3rd label to avoid crowding
    for i, label in enumerate(ax.get_xticklabels()):
        if i % 3 != 0:
            label.set_visible(False)
    plt.xticks(rotation=45, ha="right", fontsize=8)
    img = fig_to_base64(fig)

    # Summary stats
    total = monthly.sum()
    avg_monthly = monthly.mean()
    peak_month = monthly.idxmax()
    peak_val = monthly.max()

    return f"""
    <section>
      <h2>3. Citations Over Time</h2>
      <p>Monthly citation volume from 2020 onward.</p>
      <img src="data:image/png;base64,{img}" alt="Citations Over Time" />
      <div class="stats-row">
        <div class="stat-card"><span class="stat-value">{total:,}</span>
          <span class="stat-label">Total Citations (2020+)</span></div>
        <div class="stat-card"><span class="stat-value">{avg_monthly:.0f}</span>
          <span class="stat-label">Avg / Month</span></div>
        <div class="stat-card"><span class="stat-value">{peak_month}</span>
          <span class="stat-label">Peak Month ({peak_val:,})</span></div>
      </div>
    </section>"""


def analyze_program_areas(df: pd.DataFrame) -> str:
    """Section 4 – Program area donut chart."""
    counts = df["ProgramArea"].value_counts()

    fig, ax = plt.subplots(figsize=(7, 7))
    wedges, texts, autotexts = ax.pie(
        counts.values, labels=None, autopct="%1.1f%%",
        colors=PALETTE[:len(counts)], startangle=140,
        pctdistance=0.82, wedgeprops=dict(width=0.4, edgecolor=BG_DARK))
    for t in autotexts:
        t.set_fontsize(9)
        t.set_color(FG_TEXT)
    ax.legend(counts.index, loc="center left", bbox_to_anchor=(1, 0.5),
              fontsize=9, frameon=False)
    ax.set_title("Citations by Program Area", fontsize=14, fontweight="bold")
    img = fig_to_base64(fig)

    tbl_df = counts.reset_index()
    tbl_df.columns = ["Program Area", "Count"]
    tbl_df["Percent"] = (tbl_df["Count"] / tbl_df["Count"].sum() * 100
                         ).round(1).astype(str) + "%"

    return f"""
    <section>
      <h2>4. Program Area Breakdown</h2>
      <p>Distribution of citations across FDA program areas.</p>
      <img src="data:image/png;base64,{img}" alt="Program Area Breakdown" />
      {make_html_table(tbl_df)}
    </section>"""


def analyze_co_occurrence(df: pd.DataFrame, top_n: int = 12) -> str:
    """Section 5 – Co-occurrence heatmap of top violations within inspections."""
    # Get the top N CFR numbers for the matrix
    top_cfrs = df["ActCFRNumber"].value_counts().head(top_n).index.tolist()

    # Build co-occurrence counts per inspection
    grouped = df[df["ActCFRNumber"].isin(top_cfrs)].groupby("InspectionID")
    cooc = Counter()
    for _, grp in grouped:
        cfrs = sorted(grp["ActCFRNumber"].unique())
        for a, b in combinations(cfrs, 2):
            cooc[(a, b)] += 1

    # Build matrix
    matrix = pd.DataFrame(0, index=top_cfrs, columns=top_cfrs)
    for (a, b), cnt in cooc.items():
        matrix.loc[a, b] = cnt
        matrix.loc[b, a] = cnt

    # Shorten labels for readability
    short = [c.replace("21 CFR ", "") for c in top_cfrs]

    fig, ax = plt.subplots(figsize=(9, 7))
    sns.heatmap(matrix.values, annot=True, fmt="d", cmap="Purples",
                xticklabels=short, yticklabels=short, linewidths=0.5,
                linecolor=BG_DARK, ax=ax, cbar_kws={"shrink": 0.7})
    ax.set_title(f"Co-Occurrence of Top {top_n} CFR Violations\n"
                 "(within the same inspection)",
                 fontsize=13, fontweight="bold")
    plt.xticks(rotation=45, ha="right", fontsize=8)
    plt.yticks(fontsize=8)
    img = fig_to_base64(fig)

    # Find top pairs
    top_pairs = sorted(cooc.items(), key=lambda x: -x[1])[:10]
    pair_df = pd.DataFrame(
        [(a, b, c) for (a, b), c in top_pairs],
        columns=["Violation A", "Violation B", "Co-Occurrences"]
    )

    return f"""
    <section>
      <h2>5. Co-Occurrence Analysis</h2>
      <p>How often the top {top_n} CFR violations appear <em>together</em>
         within the same inspection. Higher numbers indicate violations that
         frequently accompany each other.</p>
      <img src="data:image/png;base64,{img}" alt="Co-Occurrence Heatmap" />
      <h3>Top 10 Violation Pairs</h3>
      {make_html_table(pair_df)}
    </section>"""


def analyze_repeat_offenders(df: pd.DataFrame, top_n: int = 15) -> str:
    """Section 6 – Repeat offender analysis: firms with multiple inspections."""
    firm_stats = df.groupby("LegalName").agg(
        Inspections=("InspectionID", "nunique"),
        Citations=("CitationID", "count"),
        UniqueCFRs=("ActCFRNumber", "nunique"),
    ).reset_index()
    firm_stats["Citations / Inspection"] = (
        firm_stats["Citations"] / firm_stats["Inspections"]
    ).round(1)
    # Filter to firms with more than 1 inspection
    repeaters = firm_stats[firm_stats["Inspections"] > 1].sort_values(
        "Citations", ascending=False
    ).head(top_n)

    fig, ax = plt.subplots(figsize=(10, 5))
    x = range(len(repeaters))
    bars1 = ax.bar(x, repeaters["Inspections"], width=0.35, label="Inspections",
                   color=PALETTE[0], edgecolor=ACCENT2, linewidth=0.5)
    bars2 = ax.bar([i + 0.35 for i in x], repeaters["Citations / Inspection"],
                   width=0.35, label="Citations / Inspection",
                   color=PALETTE[3], edgecolor="#c0392b", linewidth=0.5)
    ax.set_xticks([i + 0.175 for i in x])
    ax.set_xticklabels(repeaters["LegalName"], rotation=45, ha="right",
                       fontsize=7)
    ax.set_title(f"Top {top_n} Repeat Offenders", fontsize=14,
                 fontweight="bold")
    ax.legend(frameon=False)
    ax.grid(axis="y", linestyle="--")
    img = fig_to_base64(fig)

    tbl_df = repeaters[["LegalName", "Inspections", "Citations",
                        "UniqueCFRs", "Citations / Inspection"]].copy()
    tbl_df.columns = ["Firm Name", "Inspections", "Total Citations",
                      "Unique CFRs", "Citations / Insp."]
    tbl_df.insert(0, "Rank", range(1, len(tbl_df) + 1))

    return f"""
    <section>
      <h2>6. Repeat Offender Analysis</h2>
      <p>Firms with <strong>multiple inspections</strong>, ranked by total
         citation volume. The "Citations / Inspection" ratio indicates
         severity per visit.</p>
      <img src="data:image/png;base64,{img}" alt="Repeat Offenders" />
      {make_html_table(tbl_df)}
    </section>"""


# ═══════════════════════════════════════════════════════════════════════════
# Report assembly
# ═══════════════════════════════════════════════════════════════════════════

HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>FDA 483 Citation Analysis Report</title>
<style>
  /* ---------- Reset & base ---------- */
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
    background: {bg_dark};
    color: {fg_text};
    line-height: 1.6;
    padding: 0 24px 60px;
  }}
  a {{ color: {accent}; }}

  /* ---------- Header ---------- */
  header {{
    text-align: center;
    padding: 48px 0 24px;
    border-bottom: 1px solid {grid};
    margin-bottom: 36px;
  }}
  header h1 {{
    font-size: 2rem;
    background: linear-gradient(135deg, {accent}, {accent2});
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
  }}
  header .subtitle {{ color: #8888aa; font-size: 0.95rem; margin-top: 6px; }}
  header .meta {{ color: #8888aa; font-size: 0.85rem; margin-top: 12px; }}

  /* ---------- Sections ---------- */
  section {{
    max-width: 1000px;
    margin: 0 auto 48px;
    background: {bg_card};
    border-radius: 12px;
    padding: 28px 32px;
    box-shadow: 0 4px 24px rgba(0,0,0,0.3);
  }}
  section h2 {{
    color: {accent};
    font-size: 1.4rem;
    margin-bottom: 12px;
    border-bottom: 2px solid {grid};
    padding-bottom: 8px;
  }}
  section h3 {{
    color: {accent2};
    font-size: 1.1rem;
    margin: 20px 0 8px;
  }}
  section p {{
    margin-bottom: 18px;
    color: #c0c0d8;
  }}
  section img {{
    display: block;
    max-width: 100%;
    margin: 12px auto 24px;
    border-radius: 8px;
    border: 1px solid {grid};
  }}

  /* ---------- Tables ---------- */
  table {{
    width: 100%;
    border-collapse: collapse;
    margin: 12px 0;
    font-size: 0.9rem;
  }}
  th {{
    background: {bg_dark};
    color: {accent};
    padding: 10px 14px;
    text-align: left;
    border-bottom: 2px solid {grid};
    position: sticky;
    top: 0;
  }}
  td {{
    padding: 8px 14px;
    border-bottom: 1px solid {grid};
  }}
  tr:hover td {{ background: rgba(108, 99, 255, 0.08); }}

  /* ---------- Stat cards ---------- */
  .stats-row {{
    display: flex;
    gap: 16px;
    flex-wrap: wrap;
    margin-top: 16px;
  }}
  .stat-card {{
    flex: 1;
    min-width: 150px;
    background: {bg_dark};
    border-radius: 8px;
    padding: 16px 20px;
    text-align: center;
    border: 1px solid {grid};
  }}
  .stat-value {{
    display: block;
    font-size: 1.5rem;
    font-weight: 700;
    color: {accent};
  }}
  .stat-label {{
    display: block;
    font-size: 0.82rem;
    color: #8888aa;
    margin-top: 4px;
  }}

  /* ---------- Print ---------- */
  @media print {{
    body {{ background: #fff; color: #222; padding: 0; }}
    section {{ box-shadow: none; border: 1px solid #ddd; }}
    th {{ background: #f5f5f5; color: #333; }}
    td {{ color: #333; }}
    header h1 {{
      -webkit-text-fill-color: {accent};
      background: none;
    }}
  }}
</style>
</head>
<body>

<header>
  <h1>🔬 FDA 483 Citation Analysis Report</h1>
  <div class="subtitle">{subtitle}</div>
  <div class="meta">Generated {timestamp} &nbsp;|&nbsp;
       {total_citations:,} citations &nbsp;|&nbsp;
       {total_firms:,} firms &nbsp;|&nbsp;
       {total_inspections:,} inspections</div>
</header>

{sections}

<footer style="text-align:center; color:#666; font-size:0.8rem;
               padding:24px 0; border-top:1px solid {grid}; max-width:1000px;
               margin:0 auto;">
  Report generated by analyze_report.py
</footer>

</body>
</html>
"""


def build_report(sections_html: list, df: pd.DataFrame) -> str:
    """Assemble the final HTML string from rendered section blocks."""
    return HTML_TEMPLATE.format(
        bg_dark=BG_DARK,
        bg_card=BG_CARD,
        fg_text=FG_TEXT,
        accent=ACCENT,
        accent2=ACCENT2,
        grid=GRID_CLR,
        subtitle="Comprehensive analysis of FDA 483 inspection citations",
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M"),
        total_citations=len(df),
        total_firms=df["LegalName"].nunique(),
        total_inspections=df["InspectionID"].nunique(),
        sections="\n".join(sections_html),
    )


# ═══════════════════════════════════════════════════════════════════════════
# Interactive menu (CLI)
# ═══════════════════════════════════════════════════════════════════════════

ANALYSIS_OPTIONS = {
    "1": ("Top CFR Violations",    analyze_top_violations),
    "2": ("Most-Cited Firms",      analyze_most_cited_firms),
    "3": ("Citations Over Time",   analyze_citations_over_time),
    "4": ("Program Area Breakdown",analyze_program_areas),
    "5": ("Co-Occurrence Analysis", analyze_co_occurrence),
    "6": ("Repeat Offender Analysis", analyze_repeat_offenders),
}


def show_menu():
    """Display the interactive menu and return list of selected keys."""
    print("\n" + "=" * 60)
    print("  FDA 483 Citation Analysis Report Generator")
    print("=" * 60)
    print("\nSelect the analyses to include in your report:\n")
    for key, (name, _) in ANALYSIS_OPTIONS.items():
        print(f"  [{key}]  {name}")
    print(f"\n  [7]  All of the above")
    print(f"  [0]  Quit\n")

    raw = input("Enter your choices (e.g. 1,3,5  or  7 for all): ").strip()
    if raw == "0":
        return []
    if "7" in raw:
        return list(ANALYSIS_OPTIONS.keys())

    selected = [c.strip() for c in raw.replace(" ", ",").split(",")
                if c.strip() in ANALYSIS_OPTIONS]
    return selected


# ═══════════════════════════════════════════════════════════════════════════
# Main entry point
# ═══════════════════════════════════════════════════════════════════════════

def main():
    # ── MENU state ──
    selected = show_menu()
    if not selected:
        print("No analyses selected. Exiting.")
        return

    print(f"\n[OK] Selected: {', '.join(ANALYSIS_OPTIONS[k][0] for k in selected)}")

    # ── LOAD state ──
    print(f"\nLoading citations from {CITATIONS_CSV} …")
    if not os.path.exists(CITATIONS_CSV):
        print(f"ERROR: File not found: {CITATIONS_CSV}")
        print("Run fda_483s.py or fda_483s_gui.py first to generate the data.")
        return
    df = pd.read_csv(CITATIONS_CSV)
    print(f"  -> {len(df):,} citation records loaded.")

    # ── ANALYZE state ──
    sections_html = []
    for key in selected:
        name, func = ANALYSIS_OPTIONS[key]
        print(f"  Analyzing: {name} ...")
        section = func(df)
        sections_html.append(section)

    # ── RENDER state ──
    print("\nAssembling report ...")
    html = build_report(sections_html, df)

    report_path = os.path.join(OUTPUT_DIR, "fda_483_analysis_report.html")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\n{'=' * 60}")
    print(f"  [OK] Report saved to: {report_path}")
    print(f"  Open in a browser to view.  Print to PDF if needed.")
    print(f"{'=' * 60}\n")

    # ── DONE state ──


if __name__ == "__main__":
    main()
