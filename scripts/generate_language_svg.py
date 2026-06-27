"""
Generate a unified language distribution SVG chart set from GitHub repositories.

Donut chart  → languages.svg          (all repos)
Bar chart    → top_languages_bar.svg  (repos active in last 90 days)

Design system
─────────────
• Shared CSS variables, pattern defs, and type scale across both SVGs.
• Light mode  : white  (#ffffff) canvas
• Dark  mode  : black  (#0b0b0b) canvas   (prefers-color-scheme)
• Color-blind safe: every slice / bar is filled with color + hatch overlay.
• Font         : system-ui / sans-serif, 13 px body, 11 px secondary.
• Stroke width : 0.5 px for all borders.
• Accessible   : role="img", <title>, <desc>, tabindex="0" on interactive shapes.

Note / 表記:
This script was created or updated with the assistance of an AI model.
このスクリプトは AI の支援により作成または更新されました。
"""

from __future__ import annotations
import html
import math
import os
from collections import defaultdict
from datetime import datetime, timedelta

try:
    import requests as _requests
except ImportError:
    _requests = None

# ── paths ──────────────────────────────────────────────────────────────────────
GH_TOKEN   = os.environ.get("GH_TOKEN")
REPO_ROOT  = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUTPUT_DONUT = os.path.join(REPO_ROOT, "languages.svg")
OUTPUT_BAR   = os.path.join(REPO_ROOT, "top_languages_bar.svg")

# ── language colors (github-linguist palette) ──────────────────────────────────
LANG_COLORS: dict[str, str] = {
    "Python":           "#3776AB",
    "Jupyter Notebook": "#DA5B0B",
    "Go":               "#00ADD8",
    "JavaScript":       "#F7DF1E",
    "TypeScript":       "#3178C6",
    "Java":             "#ED8B00",
    "Kotlin":           "#7F52FF",
    "Swift":            "#F05138",
    "Scala":            "#DC322F",
    "Ruby":             "#CC342D",
    "Rust":             "#DEA584",
    "C":                "#555555",
    "C++":              "#00599C",
    "C/C++ Header":     "#6E4C13",
    "C++ Header":       "#00599C",
    "C#":               "#239120",
    "PHP":              "#777BB4",
    "Dart":             "#00B4AB",
    "Lua":              "#000080",
    "R":                "#276DC3",
    "Julia":            "#9558B2",
    "Haskell":          "#5D4F85",
    "Elm":              "#60B5CC",
    "Elixir":           "#6E4A7E",
    "Erlang":           "#B83998",
    "F#":               "#B845FC",
    "Fortran":          "#4D41B1",
    "Ada":              "#02F88C",
    "Pascal":           "#E3F171",
    "Visual Basic":     "#945DB7",
    "Groovy":           "#4298B8",
    "CoffeeScript":     "#244776",
    "Solidity":         "#AA6746",
    "VHDL":             "#ADB2CB",
    "Verilog":          "#B2B7F8",
    "SystemVerilog":    "#DAE1C2",
    "Assembly":         "#6E4C13",
    "Lisp":             "#3FB68B",
    "Common Lisp":      "#3FB68B",
    "Scheme":           "#1E4AEC",
    "OCaml":            "#EF7A08",
    "Perl":             "#0298C3",
    "Prolog":           "#74283C",
    "SQL":              "#E38C00",
    "Shell":            "#89E051",
    "PowerShell":       "#012456",
    "MATLAB":           "#e16737",
    "HTML":             "#E44D26",
    "CSS":              "#1572B6",
    "Markdown":         "#083FA1",
    "XML":              "#0060AC",
    "JSON":             "#292929",
    "YAML":             "#CB171E",
    "TOML":             "#9C4221",
    "INI":              "#D1DBE0",
    "Config":           "#AAAAAA",
    "Text":             "#888888",
    "SVG":              "#FFB13B",
    "LaTeX":            "#3D6117",
    "TeX":              "#3D6117",
    "BibTeX":           "#778899",
    "Other":            "#9CA3AF",
}

_FALLBACK_PALETTE = [
    "#0072b2", "#e69f00", "#009e73", "#cc79a7",
    "#56b4e9", "#d55e00", "#f0e442", "#999999",
    "#332288", "#88ccee",
]

# Hatch patterns (8×8 tile) — same set shared by both charts
_PATTERNS = [
    "",  # 0: solid
    '<line x1="0" y1="8" x2="8" y2="0" stroke="var(--ov)" stroke-width="1.4"/>',                      # 1: /
    '<line x1="0" y1="4" x2="8" y2="4" stroke="var(--ov)" stroke-width="1.4"/>',                      # 2: ─
    '<line x1="4" y1="0" x2="4" y2="8" stroke="var(--ov)" stroke-width="1.4"/>',                      # 3: │
    '<line x1="0" y1="8" x2="8" y2="0" stroke="var(--ov)" stroke-width="1.4"/>'
    '<line x1="0" y1="0" x2="8" y2="8" stroke="var(--ov)" stroke-width="1.4"/>',                      # 4: ×
    '<circle cx="4" cy="4" r="1.4" fill="var(--ov)"/>',                                               # 5: dots
    '<line x1="0" y1="0" x2="8" y2="8" stroke="var(--ov)" stroke-width="1.4"/>',                      # 6: \
    '<line x1="0" y1="2" x2="8" y2="2" stroke="var(--ov)" stroke-width="1.4"/>'
    '<line x1="0" y1="6" x2="8" y2="6" stroke="var(--ov)" stroke-width="1.4"/>',                      # 7: ══
    '<line x1="2" y1="0" x2="2" y2="8" stroke="var(--ov)" stroke-width="1.4"/>'
    '<line x1="6" y1="0" x2="6" y2="8" stroke="var(--ov)" stroke-width="1.4"/>',                      # 8: ║
    '<rect x="2" y="2" width="4" height="4" fill="none" stroke="var(--ov)" stroke-width="0.9"/>',     # 9: □
]


def _lang_color(lang: str, idx: int = 0) -> str:
    return LANG_COLORS.get(lang, _FALLBACK_PALETTE[idx % len(_FALLBACK_PALETTE)])


# ── shared SVG primitives ──────────────────────────────────────────────────────

# CSS injected into every SVG's <style> block.
# Keeps colors, typography, and spacing in sync between the two charts.
_SHARED_CSS = """
  :root {
    --bg:      #ffffff;
    --fg:      #0b0b0b;
    --fg2:     #444444;
    --fg3:     #777777;
    --edge:    rgba(0,0,0,0.08);
    --slice-border: #ffffff;
    --ov:      rgba(0,0,0,0.18);
    --bar-track: #e5e5e5;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --bg:      #0b0b0b;
      --fg:      #ffffff;
      --fg2:     #cccccc;
      --fg3:     #888888;
      --edge:    rgba(255,255,255,0.10);
      --slice-border: #0b0b0b;
      --ov:      rgba(255,255,255,0.15);
      --bar-track: #2a2a2a;
    }
  }
  svg { font-family: system-ui, sans-serif; }
  .label-main { font-size: 13px; fill: var(--fg);  }
  .label-sub  { font-size: 11px; fill: var(--fg3); }
  .label-bold { font-size: 13px; fill: var(--fg);  font-weight: 600; }
  .chart-title { font-size: 14px; fill: var(--fg); font-weight: 600; }
  .slice { cursor: pointer; }
  .slice:focus { outline: none; stroke: var(--fg); stroke-width: 2; }
"""


def _make_pattern_defs(items: list[tuple[str, int]], prefix: str = "p") -> str:
    """Return <defs> with one fill-pattern per language."""
    lines = ["<defs>"]
    for i, (lang, _) in enumerate(items):
        color   = _lang_color(lang, i)
        hatch   = _PATTERNS[i % len(_PATTERNS)]
        pid     = f"{prefix}{i}"
        lines.append(
            f'<pattern id="{pid}" patternUnits="userSpaceOnUse" width="8" height="8">'
            f'<rect width="8" height="8" fill="{color}"/>'
            f'{hatch}'
            f'</pattern>'
        )
    lines.append("</defs>")
    return "\n".join(lines)


# ── data helpers ───────────────────────────────────────────────────────────────

def _top_items(counter: dict, n: int = 8) -> list[tuple[str, int]]:
    """Return top-n languages (excluding 'Other'), then append an 'Other' bucket."""
    ranked = sorted(counter.items(), key=lambda x: x[1], reverse=True)
    top, rest = [], 0
    for lang, size in ranked:
        if lang != "Other" and len(top) < n:
            top.append((lang, size))
        else:
            rest += size
    if rest:
        top.append(("Other", rest))
    return top


# ── Donut chart ────────────────────────────────────────────────────────────────

def make_donut_svg(counter: dict, title: str, outpath: str) -> None:
    """
    Unified donut chart.

    Layout  : 560 × dynamic height
    Donut   : cx=175, r_outer=150, r_inner=70
    Legend  : right column, x=345
    """
    total = sum(counter.values())
    svg_id   = os.path.splitext(os.path.basename(outpath))[0]
    title_id = f"{svg_id}-title"
    desc_id  = f"{svg_id}-desc"

    # ── empty state ───────────────────────────────────────────────────────────
    if total == 0:
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="560" height="80" '
            f'role="img" aria-labelledby="{title_id} {desc_id}">\n'
            f'<style>{_SHARED_CSS}</style>\n'
            f'<rect width="560" height="80" fill="var(--bg)"/>\n'
            f'<title id="{title_id}">{html.escape(title)}</title>\n'
            f'<desc id="{desc_id}">No language data found.</desc>\n'
            f'<text x="280" y="44" text-anchor="middle" class="label-main">No data found.</text>\n'
            f'</svg>\n'
        )
        with open(outpath, "w") as f:
            f.write(svg)
        return

    top = _top_items(counter, n=10)
    n   = len(top)

    # ── layout constants ──────────────────────────────────────────────────────
    W           = 560
    cx, cy      = 175, 185       # donut centre
    r_out, r_in = 150, 70
    leg_x       = 345            # legend left edge
    leg_y0      = 30
    row_h       = 26
    H           = max(390, leg_y0 + n * row_h + 60)

    desc_text = f"{title}. " + ", ".join(
        f"{lang}: {size / total * 100:.1f}%" for lang, size in top
    )

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'role="img" aria-labelledby="{title_id} {desc_id}">',
        f'<title id="{title_id}">{html.escape(title)}</title>',
        f'<desc id="{desc_id}">{html.escape(desc_text)}</desc>',
        f'<style>{_SHARED_CSS}</style>',
        # white/black canvas
        f'<rect width="{W}" height="{H}" fill="var(--bg)"/>',
        _make_pattern_defs(top, prefix="dp"),
    ]

    # ── chart title ───────────────────────────────────────────────────────────
    parts.append(
        f'<text x="{cx}" y="22" text-anchor="middle" class="chart-title">'
        f'{html.escape(title)}</text>'
    )

    # ── donut slices ──────────────────────────────────────────────────────────
    angle = -math.pi / 2
    for i, (lang, size) in enumerate(top):
        frac  = size / total
        sweep = frac * 2 * math.pi
        end   = angle + sweep
        large = 1 if sweep > math.pi else 0

        ox1 = cx + r_out * math.cos(angle)
        oy1 = cy + r_out * math.sin(angle)
        ox2 = cx + r_out * math.cos(end)
        oy2 = cy + r_out * math.sin(end)
        ix1 = cx + r_in  * math.cos(end)
        iy1 = cy + r_in  * math.sin(end)
        ix2 = cx + r_in  * math.cos(angle)
        iy2 = cy + r_in  * math.sin(angle)

        d = (
            f"M {ox1:.2f} {oy1:.2f} "
            f"A {r_out} {r_out} 0 {large} 1 {ox2:.2f} {oy2:.2f} "
            f"L {ix1:.2f} {iy1:.2f} "
            f"A {r_in} {r_in} 0 {large} 0 {ix2:.2f} {iy2:.2f} Z"
        )
        pct   = f"{frac * 100:.1f}%"
        aria  = html.escape(f"{lang}: {pct}")
        parts.append(
            f'<path class="slice" d="{d}" fill="url(#dp{i})" '
            f'stroke="var(--slice-border)" stroke-width="1" '
            f'role="img" aria-label="{aria}" tabindex="0">'
            f'<title>{aria}</title></path>'
        )

        # percentage label inside slice (only if wide enough)
        if frac > 0.08:
            mid_a = angle + sweep / 2
            lr    = (r_out + r_in) / 2
            lx    = cx + lr * math.cos(mid_a)
            ly    = cy + lr * math.sin(mid_a)
            parts.append(
                f'<text x="{lx:.1f}" y="{ly:.1f}" font-size="11" '
                f'fill="#ffffff" text-anchor="middle" dominant-baseline="middle" '
                f'aria-hidden="true" font-weight="600">{html.escape(pct)}</text>'
            )

        angle = end

    # ── centre label ─────────────────────────────────────────────────────────
    parts.append(
        f'<circle cx="{cx}" cy="{cy}" r="{r_in}" fill="var(--bg)"/>'
        f'<text x="{cx}" y="{cy - 9}" text-anchor="middle" class="label-bold">'
        f'Languages</text>'
        f'<text x="{cx}" y="{cy + 10}" text-anchor="middle" class="label-sub">'
        f'{n} shown</text>'
    )

    # ── legend ────────────────────────────────────────────────────────────────
    MAX_LEGEND_CHARS = 22          # truncate long names to prevent overflow
    for i, (lang, size) in enumerate(top):
        frac  = size / total
        ly    = leg_y0 + i * row_h
        pct   = f"{frac * 100:.1f}%"
        name  = lang if len(lang) <= MAX_LEGEND_CHARS else lang[:MAX_LEGEND_CHARS - 1] + "…"
        parts.append(
            f'<rect x="{leg_x}" y="{ly + 1}" width="12" height="12" rx="2" '
            f'fill="url(#dp{i})" stroke="{_lang_color(lang, i)}" stroke-width="0.5" '
            f'aria-hidden="true"/>'
        )
        # language name
        parts.append(
            f'<text x="{leg_x + 18}" y="{ly + 12}" class="label-main" aria-hidden="true">'
            f'{html.escape(name)}</text>'
        )
        # percentage (right-aligned at W-8)
        parts.append(
            f'<text x="{W - 8}" y="{ly + 12}" text-anchor="end" '
            f'class="label-sub" aria-hidden="true">{html.escape(pct)}</text>'
        )

    # ── subtitle ─────────────────────────────────────────────────────────────
    parts.append(
        f'<text x="{leg_x}" y="{H - 12}" class="label-sub">'
        f'Measured by bytes of code</text>'
    )

    parts.append("</svg>")
    with open(outpath, "w") as f:
        f.write("\n".join(parts))


# ── Bar chart ──────────────────────────────────────────────────────────────────

def make_bar_chart_svg(counter: dict, outpath: str, days_back: int = 90) -> None:
    """
    Unified horizontal bar chart (top 5 languages, last N days).

    Layout  : 560 × dynamic height
    Bar area: x=160..520 (label 8px left margin, value label right)
    Pattern : same hatch set as the donut, consistent pattern IDs (bp0…bp4)
    """
    total = sum(counter.values())
    svg_id   = os.path.splitext(os.path.basename(outpath))[0]
    title_id = f"{svg_id}-title"
    desc_id  = f"{svg_id}-desc"

    chart_title = f"Top languages · last {days_back} days"

    if total == 0:
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="560" height="80" '
            f'role="img" aria-labelledby="{title_id} {desc_id}">\n'
            f'<style>{_SHARED_CSS}</style>\n'
            f'<rect width="560" height="80" fill="var(--bg)"/>\n'
            f'<title id="{title_id}">{html.escape(chart_title)}</title>\n'
            f'<desc id="{desc_id}">No language data found.</desc>\n'
            f'<text x="280" y="44" text-anchor="middle" class="label-main">No data found.</text>\n'
            f'</svg>\n'
        )
        with open(outpath, "w") as f:
            f.write(svg)
        return

    top = _top_items(counter, n=5)
    n   = len(top)

    # ── layout ────────────────────────────────────────────────────────────────
    W         = 560
    label_w   = 152         # reserved for language name (left)
    bar_x0    = label_w + 8 # bar starts here
    bar_max_w = W - bar_x0 - 56  # 56px right margin for pct label
    bar_h     = 22
    row_h     = 38           # bar_h + gap
    header_h  = 40
    footer_h  = 28
    H         = header_h + n * row_h + footer_h

    desc_text = f"{chart_title}. " + ", ".join(
        f"{lang}: {size / total * 100:.1f}%" for lang, size in top
    )

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'role="img" aria-labelledby="{title_id} {desc_id}">',
        f'<title id="{title_id}">{html.escape(chart_title)}</title>',
        f'<desc id="{desc_id}">{html.escape(desc_text)}</desc>',
        f'<style>{_SHARED_CSS}</style>',
        f'<rect width="{W}" height="{H}" fill="var(--bg)"/>',
        _make_pattern_defs(top, prefix="bp"),
    ]

    # ── chart title ───────────────────────────────────────────────────────────
    parts.append(
        f'<text x="8" y="24" class="chart-title">'
        f'{html.escape(chart_title)}</text>'
    )

    # ── bars ──────────────────────────────────────────────────────────────────
    MAX_NAME_CHARS = 20
    for i, (lang, size) in enumerate(top):
        frac   = size / total
        bar_w  = max(4, frac * bar_max_w)   # minimum 4px so bar is always visible
        by     = header_h + i * row_h + (row_h - bar_h) // 2
        pct    = f"{frac * 100:.1f}%"
        name   = lang if len(lang) <= MAX_NAME_CHARS else lang[:MAX_NAME_CHARS - 1] + "…"
        aria   = html.escape(f"{lang}: {pct}")

        # language name label (right-aligned, clipped to label area)
        parts.append(
            f'<text x="{label_w}" y="{by + bar_h // 2 + 1}" '
            f'text-anchor="end" dominant-baseline="middle" '
            f'class="label-main" aria-hidden="true" clip-path="none">'
            f'{html.escape(name)}</text>'
        )

        # track (background)
        parts.append(
            f'<rect x="{bar_x0}" y="{by}" width="{bar_max_w}" height="{bar_h}" '
            f'rx="4" fill="var(--bar-track)" aria-hidden="true"/>'
        )

        # colored + hatched bar
        parts.append(
            f'<rect x="{bar_x0}" y="{by}" width="{bar_w:.1f}" height="{bar_h}" '
            f'rx="4" fill="url(#bp{i})" stroke="{_lang_color(lang, i)}" '
            f'stroke-width="0.5" role="img" aria-label="{aria}" tabindex="0">'
            f'<title>{aria}</title></rect>'
        )

        # small color swatch (left edge of bar) for quick color ID
        swatch_w = min(4, bar_w)
        parts.append(
            f'<rect x="{bar_x0}" y="{by}" width="{swatch_w:.1f}" height="{bar_h}" '
            f'rx="4" fill="{_lang_color(lang, i)}" aria-hidden="true"/>'
        )

        # percentage label right of bar
        pct_x = bar_x0 + bar_w + 6
        # guard: if bar is very long, keep pct inside chart width
        if pct_x + 36 > W:
            pct_x = W - 44
        parts.append(
            f'<text x="{pct_x:.1f}" y="{by + bar_h // 2 + 1}" '
            f'dominant-baseline="middle" class="label-sub" aria-hidden="true">'
            f'{html.escape(pct)}</text>'
        )

    # ── pattern legend ────────────────────────────────────────────────────────
    # Small inline swatches so readers can match bar to legend entry
    leg_y = H - footer_h + 10
    lx    = 8
    for i, (lang, _) in enumerate(top):
        name  = lang if len(lang) <= 14 else lang[:13] + "…"
        parts.append(
            f'<rect x="{lx}" y="{leg_y}" width="10" height="10" rx="2" '
            f'fill="url(#bp{i})" stroke="{_lang_color(lang, i)}" stroke-width="0.5" '
            f'aria-hidden="true"/>'
        )
        parts.append(
            f'<text x="{lx + 14}" y="{leg_y + 9}" class="label-sub" aria-hidden="true">'
            f'{html.escape(name)}</text>'
        )
        # estimate text width: ~6.5px per char + 14px swatch + 10px gap
        lx += 14 + len(name) * 6.5 + 12
        if lx > W - 60:   # wrap guard — skip remaining items
            break

    parts.append("</svg>")
    with open(outpath, "w") as f:
        f.write("\n".join(parts))


# ── GitHub API ─────────────────────────────────────────────────────────────────

def _gh_headers() -> dict:
    return {
        "Authorization": f"Bearer {GH_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _list_repos() -> list[dict]:
    req     = _requests
    headers = _gh_headers()
    repos, page = [], 1
    while True:
        r = req.get(
            "https://api.github.com/user/repos",
            headers=headers,
            params={"per_page": 100, "page": page,
                    "affiliation": "owner,collaborator,organization_member"},
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
        if not data:
            break
        repos.extend(data)
        page += 1
    return repos


def _aggregate_languages(repos: list[dict]) -> dict:
    headers = _gh_headers()
    totals: dict = defaultdict(int)
    for repo in repos:
        fn = repo.get("full_name")
        if not fn:
            continue
        r = _requests.get(
            f"https://api.github.com/repos/{fn}/languages",
            headers=headers, timeout=30,
        )
        if r.status_code == 200:
            for lang, cnt in r.json().items():
                totals[lang] += cnt
    return dict(totals)


def fetch_all_repo_languages() -> dict:
    r = _requests.get("https://api.github.com/user", headers=_gh_headers(), timeout=30)
    r.raise_for_status()
    print(f"Authenticated as: {r.json().get('login', '?')}")
    repos = _list_repos()
    print(f"Found {len(repos)} accessible repositories")
    return _aggregate_languages(repos)


def fetch_recent_repo_languages(days_back: int = 90) -> dict:
    repos  = _list_repos()
    cutoff = datetime.utcnow() - timedelta(days=days_back)
    recent = []
    for repo in repos:
        pushed = repo.get("pushed_at", "")
        try:
            dt = datetime.fromisoformat(pushed.replace("Z", "+00:00"))
            if dt.replace(tzinfo=None) >= cutoff:
                recent.append(repo)
        except (ValueError, AttributeError):
            continue
    print(f"Filtered to {len(recent)} repos active in last {days_back} days")
    return _aggregate_languages(recent)


# ── Local fallback ─────────────────────────────────────────────────────────────

EXT_LANG: dict[str, str] = {
    ".py": "Python", ".pyw": "Python", ".ipynb": "Jupyter Notebook",
    ".go": "Go",
    ".js": "JavaScript", ".mjs": "JavaScript", ".cjs": "JavaScript", ".jsx": "JavaScript",
    ".ts": "TypeScript", ".tsx": "TypeScript",
    ".java": "Java", ".kt": "Kotlin", ".kts": "Kotlin",
    ".swift": "Swift", ".scala": "Scala",
    ".rb": "Ruby", ".rs": "Rust",
    ".cpp": "C++", ".cc": "C++", ".cxx": "C++",
    ".c": "C", ".h": "C/C++ Header", ".hpp": "C++ Header",
    ".cs": "C#", ".php": "PHP",
    ".dart": "Dart", ".lua": "Lua", ".r": "R", ".jl": "Julia",
    ".m": "MATLAB",
    ".hs": "Haskell", ".elm": "Elm",
    ".ex": "Elixir", ".exs": "Elixir", ".erl": "Erlang", ".hrl": "Erlang",
    ".fs": "F#", ".fsx": "F#",
    ".f": "Fortran", ".f90": "Fortran", ".f95": "Fortran",
    ".pas": "Pascal",
    ".vb": "Visual Basic", ".groovy": "Groovy", ".coffee": "CoffeeScript",
    ".sol": "Solidity",
    ".vhd": "VHDL", ".vhdl": "VHDL", ".v": "Verilog", ".sv": "SystemVerilog",
    ".s": "Assembly", ".asm": "Assembly",
    ".lisp": "Lisp", ".cl": "Common Lisp", ".scm": "Scheme",
    ".ml": "OCaml", ".pl": "Perl",
    ".sql": "SQL",
    ".sh": "Shell", ".bash": "Shell", ".zsh": "Shell",
    ".ps1": "PowerShell",
    ".html": "HTML", ".htm": "HTML", ".css": "CSS",
    ".md": "Markdown", ".xml": "XML", ".json": "JSON",
    ".yml": "YAML", ".yaml": "YAML", ".toml": "TOML",
    ".ini": "INI", ".txt": "Text", ".svg": "SVG",
    ".tex": "LaTeX", ".sty": "LaTeX", ".cls": "LaTeX", ".bib": "BibTeX",
}

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", ".github"}


def scan_bytes(root: str) -> dict:
    counts: dict = defaultdict(int)
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            try:
                full = os.path.join(dirpath, fn)
                size = os.path.getsize(full)
            except OSError:
                continue
            ext  = os.path.splitext(fn)[1].lower()
            lang = EXT_LANG.get(ext, "Other")
            counts[lang] += size
    return dict(counts)


# ── entry point ────────────────────────────────────────────────────────────────

DAYS_BACK = 90

if __name__ == "__main__":
    if GH_TOKEN and _requests is not None:
        print("Fetching language stats from GitHub API …")
        counts_all    = fetch_all_repo_languages()
        counts_recent = fetch_recent_repo_languages(days_back=DAYS_BACK)
    else:
        print("GH_TOKEN not set or `requests` unavailable — scanning local repo …")
        counts_all    = scan_bytes(REPO_ROOT)
        counts_recent = counts_all

    make_donut_svg(counts_all, "Language distribution", OUTPUT_DONUT)
    print("Wrote", OUTPUT_DONUT)

    make_bar_chart_svg(counts_recent, OUTPUT_BAR, days_back=DAYS_BACK)
    print("Wrote", OUTPUT_BAR)
