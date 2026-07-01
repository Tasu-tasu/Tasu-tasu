"""
Generate a unified language distribution SVG chart from GitHub repositories.
Concept: Academic Editorial (minimalist, booktabs-style lines, refined typography, smooth animations)

Output: languages.svg (800 × 360 px)
- Left: Overall language distribution (donut chart + legend)
- Right: Recent language distribution (horizontal bar chart + grid)

Design system:
- Font: Georgia/Serif for headers/notes, system-ui/monospace for data.
- Light/Dark mode via prefers-color-scheme.
- Refined unified color palette.

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
GH_TOKEN = os.environ.get("GH_TOKEN")
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUTPUT_SVG = os.path.join(REPO_ROOT, "languages.svg")

# ── settings ───────────────────────────────────────────────────────────────────
# フォークリポジトリを含めるか (True = 含める)
INCLUDE_FORKS = False
# 集計から除外するリポジトリの full_name リスト
EXCLUDE_REPOS: list[str] = []  # 例: ["tasu-tasuku/tasu-tasuku"]

# ── language colors (Academic Editorial palette) ────────────────────────────────
LANG_COLORS: dict[str, str] = {
    # プログラミング言語（既存）
    "Python":           "#3f6a8a",  # Steel Blue
    "Jupyter Notebook": "#b85a1c",  # Terracotta
    "Go":               "#2a8f9d",  # Sage Teal
    "JavaScript":       "#c2ab25",  # Muted Ochre
    "TypeScript":       "#2b5b84",  # Slate Blue
    "Java":             "#a86c1e",  # Amber
    "Kotlin":           "#5a3fa8",  # Muted Purple
    "Swift":            "#bd3b24",  # Rust Red
    "C":                "#6b7280",  # Cool Grey
    "C++":              "#2a4e7c",  # Classic Navy
    "MATLAB":           "#bd532b",  # Burnt Orange
    
    # ドキュメント言語
    "HTML":             "#b83e23",  # Terracotta Red
    "CSS":              "#216a94",  # Ocean Blue
    "Markdown":         "#1e3b70",  # Deep Indigo
    "LaTeX":            "#5b4a8a",  # 学術的な紫（TeX系）
    "ReStructuredText": "#5a7c8c",  # 青灰色（rst）
    
    # プログラミング言語（Wikipedia追加）
    "Ruby":             "#cc342d",  # ルビレッド（公式ロゴ色）
    "PHP":              "#777bb3",  # PHP紫（公式ロゴ色）
    "Rust":             "#ce5a1e",  # Rust褐色（公式ロゴ色）
    "R":                "#276dc3",  # R水色（公式ロゴ色）
    "Scala":            "#c22d40",  # Scala赤褐色（公式ロゴ色）
    "Clojure":          "#63b132",  # Clojure緑（公式ロゴ色）
    "Haskell":          "#5e5086",  # Haskell紫（公式ロゴ色）
    "Lua":              "#2c3e70",  # Lua濃紺（公式ロゴ色）
    "Elixir":           "#4b275f",  # Elixir紫（公式ロゴ色）
    "F#":               "#378bba",  # F#青（公式ロゴ色）
    "C#":               "#239120",  # C#緑（Microsoft色）
    "VB.NET":           "#0078d4",  # VB.NET青（Microsoft色）
    "Perl":             "#0073b8",  # Perl青（公式ロゴ色）
    "Groovy":           "#4298b8",  # Groovy水色（公式ロゴ色）
    "Dart":             "#01579b",  # Dart濃青（Google色）
    "Kotlin":           "#5a3fa8",  # Kotlin紫（JetBrains色）
    
    # その他
    "Other":            "#718096",  # Slate Grey
}
_FALLBACK_PALETTE = [
    "#3f6a8a", "#a86c1e", "#2a8f9d", "#bd532b", "#5a3fa8",
    "#6b7280", "#216a94", "#bd3b24", "#718096", "#c2ab25"
]

def _lang_color(lang: str, idx: int = 0) -> str:
    return LANG_COLORS.get(lang, _FALLBACK_PALETTE[idx % len(_FALLBACK_PALETTE)])

def _top_items(counter: dict, n: int = 5) -> list[tuple[str, int]]:
    """Return top-n languages, grouping the rest into 'Other'."""
    ranked = sorted(counter.items(), key=lambda x: x[1], reverse=True)
    top, rest = [], 0
    for lang, size in ranked:
        if lang != "Other" and len(top) < n:
            top.append((lang, size))
        else:
            rest += size
    if rest > 0:
        top.append(("Other", rest))
    return top


def _label_lines(lang: str, max_chars: int = 12) -> list[str]:
    """Break a language name into at most 2 display lines at a word boundary."""
    if len(lang) <= max_chars:
        return [lang]
    idx = lang[:max_chars + 1].rfind(' ')
    if idx <= 0:
        return [lang[:max_chars] + '\u2026']  # no space — hard truncate
    return [lang[:idx], lang[idx + 1:]]


def _add_frame(parts: list, H: int, footer_line2_y: int):
    """Simple frame: outer border + section dividers."""
    
    # ── Outer frame ──────────────────────────────────────────────────
    # Main border
    parts.append(f'<rect x="12" y="8" width="776" height="{H - 16}" fill="none" '
                 f'stroke="var(--border)" stroke-width="2" />')
    
    # ── Title / content separator ──────────────────────────────────
    parts.append(f'<line x1="12" y1="48" x2="788" y2="48" stroke="var(--border)" stroke-width="1" />')
    
    # ── Vertical divider (center) ──────────────────────────────────
    parts.append(f'<line x1="400" y1="48" x2="400" y2="{footer_line2_y}" '
                 f'stroke="var(--border)" stroke-width="0.75" opacity="0.5" />')
    
    # ── Footer separator ──────────────────────────────────────────
    parts.append(f'<line x1="12" y1="{footer_line2_y}" x2="788" y2="{footer_line2_y}" '
                 f'stroke="var(--border)" stroke-width="1" />')


def make_unified_svg(counts_all: dict, counts_recent: dict, outpath: str, days_back: int = 90) -> None:
    total_all = sum(counts_all.values())
    total_recent = sum(counts_recent.values())

    if total_all == 0:
        # Empty state
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="800" height="360" role="img">\n'
            f'<style>\n'
            f'  :root {{ --bg: #faf9f6; --fg: #1a1a1a; }}\n'
            f'  @media (prefers-color-scheme: dark) {{ :root {{ --bg: #0f0f11; --fg: #f0f0f0; }} }}\n'
            f'  rect {{ fill: var(--bg); }}\n'
            f'  text {{ font-family: Georgia, serif; fill: var(--fg); font-size: 14px; text-anchor: middle; }}\n'
            f'</style>\n'
            f'<rect width="800" height="360"/>\n'
            f'<text x="400" y="180">No language data found.</text>\n'
            f'</svg>\n'
        )
        with open(outpath, "w") as f:
            f.write(svg)
        return

    top_all = _top_items(counts_all, n=5)
    top_recent = _top_items(counts_recent, n=5)

    # ── Layout constants ──────────────────────────────────────────
    LEG_MAX_CHARS = 12   # max chars per line in donut legend
    BAR_MAX_CHARS = 9    # max chars per line in bar chart label (narrower column)
    LEG_ROW_H_1 = 28     # legend single-line row height
    LEG_ROW_H_2 = 38     # legend two-line row height
    BAR_ROW_H_1 = 38     # bar single-line row height
    BAR_ROW_H_2 = 50     # bar two-line row height
    leg_x   = 265        # legend left edge x
    leg_y0  = 90         # legend first row top-y
    bar_y0  = 92         # bar first row top-y
    grid_x0 = 520        # bar chart start x
    grid_w  = 200        # bar chart max bar width
    cx, cy  = 150, 185   # donut centre

    def _leg_rh(lang: str) -> int:
        return LEG_ROW_H_2 if len(_label_lines(lang, LEG_MAX_CHARS)) > 1 else LEG_ROW_H_1

    def _bar_rh(lang: str) -> int:
        return BAR_ROW_H_2 if len(_label_lines(lang, BAR_MAX_CHARS)) > 1 else BAR_ROW_H_1

    leg_bottom     = leg_y0 + sum(_leg_rh(l) for l, _ in top_all)
    bar_bottom     = bar_y0 + sum(_bar_rh(l) for l, _ in top_recent)
    content_bottom = max(leg_bottom, bar_bottom, 270)
    H              = max(370, content_bottom + 75)

    footer_line1_y = content_bottom + 15
    note_y         = footer_line1_y + 18
    footer_line2_y = footer_line1_y + 31

    # ── SVG & CSS Generation ──────────────────────────────────────────────────
    svg_id = "language-analysis"
    title_text = "PROGRAMMING LANGUAGE ANALYSIS & RECENT ACTIVITY"
    desc_text = f"Donut chart shows overall language usage. Bar chart shows activity in the last {days_back} days."

    # Generate animations dynamically
    donut_css = []
    donut_circumference = 2 * math.pi * 75 # r = 75 -> ~471.2389
    
    for i, (lang, size) in enumerate(top_all):
        pct = size / total_all
        length = pct * donut_circumference
        offset = donut_circumference - length
        donut_css.append(f"""
@keyframes draw-slice-{i} {{
  from {{ stroke-dashoffset: {donut_circumference:.4f}; }}
  to {{ stroke-dashoffset: {offset:.4f}; }}
}}
.slice-{i} {{
  stroke: {_lang_color(lang, i)};
  stroke-dasharray: {donut_circumference:.4f};
  stroke-dashoffset: {donut_circumference:.4f};
  animation: draw-slice-{i} 1.2s cubic-bezier(0.25, 1, 0.5, 1) forwards;
}}""")

    bar_css = []
    for i, (lang, size) in enumerate(top_recent):
        bar_css.append(f"""
@keyframes grow-bar-{i} {{
  from {{ transform: scaleX(0); }}
  to {{ transform: scaleX(1); }}
}}
.bar-{i} {{
  fill: {_lang_color(lang, i)};
  animation: grow-bar-{i} 1.2s cubic-bezier(0.25, 1, 0.5, 1) forwards;
}}""")

    css = f"""
  :root {{
    --bg: #faf9f6;
    --fg: #1a1a1a;
    --fg-muted: #555555;
    --text-muted: #777777;
    --border: #222222;
    --grid: rgba(0, 0, 0, 0.05);
    --slice-border: #faf9f6;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      --bg: #0f0f11;
      --fg: #f0f0f0;
      --fg-muted: #a0a0a0;
      --text-muted: #888888;
      --border: #cccccc;
      --grid: rgba(255, 255, 255, 0.06);
      --slice-border: #0f0f11;
    }}
  }}
  
  svg {{
    background-color: var(--bg);
  }}
  
  .font-serif {{
    font-family: Georgia, Cambria, "Times New Roman", Times, serif;
  }}
  .font-sans {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
  }}
  .font-mono {{
    font-family: ui-monospace, SFMono-Regular, SF Mono, Menlo, Consolas, Liberation Mono, monospace;
  }}
  
  .main-title {{
    font-size: 13px;
    font-weight: bold;
    fill: var(--fg);
    letter-spacing: 0.06em;
  }}
  
  .sub-title {{
    font-size: 11px;
    font-weight: bold;
    fill: var(--fg-muted);
    letter-spacing: 0.05em;
  }}
  
  .label-text {{
    font-size: 12px;
    fill: var(--fg);
  }}
  
  .val-text {{
    font-size: 11px;
    fill: var(--fg-muted);
  }}
  
  .note-text {{
    font-size: 9.5px;
    fill: var(--text-muted);
  }}
  
  .bar {{
    transform-origin: 520px 0;
  }}
  
  /* Animations */
  @keyframes fade-in {{
    from {{ opacity: 0; }}
    to {{ opacity: 1; }}
  }}
  
  .fade-in {{
    opacity: 0;
    animation: fade-in 0.8s ease-out 0.6s forwards;
  }}
  
  {"".join(donut_css)}
  {"".join(bar_css)}
"""

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="800" height="{H}" viewBox="0 0 800 {H}" role="img" aria-labelledby="{svg_id}-title {svg_id}-desc">',
        f'<title id="{svg_id}-title">{html.escape(title_text)}</title>',
        f'<desc id="{svg_id}-desc">{html.escape(desc_text)}</desc>',
        f'<style>{css}</style>',
        f'<rect width="100%" height="100%" fill="var(--bg)"/>',
    ]

    # ── Frame ──────────────────────────────────────────────────────
    _add_frame(parts, H, footer_line2_y)

    # ── Title ──────────────────────────────────────────────────────
    parts.append(f'<text x="400" y="29" text-anchor="middle" class="font-serif main-title">{html.escape(title_text)}</text>')

    # ── Left Column: Donut Chart ───────────────────────────────────────────────────────
    parts.append(f'<text x="40" y="68" class="font-serif sub-title">I. OVERALL LANGUAGE USAGE</text>')
    
    # Donut Slices (r=75, stroke-width=30, cx=150, cy=185)
    accumulated_pct = 0.0
    for i, (lang, size) in enumerate(top_all):
        pct = size / total_all
        angle = -90.0 + (accumulated_pct * 360.0)
        aria = html.escape(f"{lang}: {pct*100:.1f}%")
        parts.append(
            f'<circle class="slice-{i}" cx="{cx}" cy="{cy}" r="75" fill="none" '
            f'stroke-width="26" stroke-linecap="butt" '
            f'transform="rotate({angle:.2f} {cx} {cy})" '
            f'role="img" aria-label="{aria}" tabindex="0">'
            f'<title>{aria}</title>'
            f'</circle>'
        )
        accumulated_pct += pct

    parts.append(f'<circle cx="{cx}" cy="{cy}" r="88" fill="none" stroke="var(--slice-border)" stroke-width="1.5"/>')
    parts.append(f'<circle cx="{cx}" cy="{cy}" r="62" fill="none" stroke="var(--slice-border)" stroke-width="1.5"/>')

    # Donut Center Label
    parts.append(
        f'<g class="fade-in">'
        f'<text x="{cx}" y="{cy - 5}" text-anchor="middle" class="font-serif label-text" style="font-weight: bold;">Languages</text>'
        f'<text x="{cx}" y="{cy + 12}" text-anchor="middle" class="font-serif val-text" style="font-style: italic;">All-Time</text>'
        f'</g>'
    )

    # Donut Legend (wrapped labels, cumulative y)
    cumulative_ly = leg_y0
    for i, (lang, size) in enumerate(top_all):
        pct   = size / total_all
        lines = _label_lines(lang, LEG_MAX_CHARS)
        rh    = LEG_ROW_H_2 if len(lines) > 1 else LEG_ROW_H_1
        ly    = cumulative_ly
        color = _lang_color(lang, i)

        if len(lines) == 1:
            swatch_y  = ly + 4
            label_el  = f'<text x="{leg_x + 18}" y="{ly + 13}" class="font-sans label-text">{html.escape(lines[0])}</text>'
            pct_y     = ly + 13
        else:
            swatch_y  = ly + 10
            label_el  = (
                f'<text class="font-sans label-text">'
                f'<tspan x="{leg_x + 18}" y="{ly + 9}">{html.escape(lines[0])}</tspan>'
                f'<tspan x="{leg_x + 18}" y="{ly + 22}">{html.escape(lines[1])}</tspan>'
                f'</text>'
            )
            pct_y     = ly + 15

        parts.append(
            f'<g class="fade-in">'
            f'<rect x="{leg_x}" y="{swatch_y}" width="10" height="10" rx="1" fill="{color}" stroke="var(--slice-border)" stroke-width="0.5" />'
            + label_el +
            f'<text x="385" y="{pct_y}" text-anchor="end" class="font-mono val-text">{pct*100:.1f}%</text>'
            f'</g>'
        )
        cumulative_ly += rh

    # ── Right Column: Recent Activity ─────────────────────────────────────────────────
    parts.append(f'<text x="420" y="68" class="font-serif sub-title">II. RECENT ACTIVITY (LAST {days_back} DAYS)</text>')

    # Grid Lines (dynamic content height)
    for p in [0.0, 0.25, 0.50, 0.75, 1.0]:
        gx = grid_x0 + grid_w * p
        parts.append(f'<line x1="{gx}" y1="82" x2="{gx}" y2="{content_bottom + 5}" stroke="var(--grid)" stroke-width="0.75" />')
        if p in [0.0, 0.5, 1.0]:
            parts.append(f'<text x="{gx}" y="77" text-anchor="middle" class="font-mono val-text" style="font-size: 9px;">{int(p*100)}%</text>')

    # Bars with wrapped labels (cumulative y)
    cumulative_by = bar_y0
    for i, (lang, size) in enumerate(top_recent):
        pct   = size / total_recent
        lines = _label_lines(lang, BAR_MAX_CHARS)
        rh    = BAR_ROW_H_2 if len(lines) > 1 else BAR_ROW_H_1
        by    = cumulative_by
        bw    = max(2, pct * grid_w)
        aria  = html.escape(f"{lang}: {pct*100:.1f}%")

        if len(lines) == 1:
            bar_rect_y = by + 13
            label_el   = f'<text x="510" y="{by + 22}" text-anchor="end" class="font-sans label-text">{html.escape(lines[0])}</text>'
        else:
            bar_rect_y = by + 19
            label_el   = (
                f'<text text-anchor="end" class="font-sans label-text">'
                f'<tspan x="510" y="{by + 13}">{html.escape(lines[0])}</tspan>'
                f'<tspan x="510" y="{by + 27}">{html.escape(lines[1])}</tspan>'
                f'</text>'
            )

        parts.append(
            f'<g>'
            + label_el +
            f'<rect class="bar bar-{i}" x="{grid_x0}" y="{bar_rect_y}" width="{bw:.2f}" height="12" rx="1" '
            f'role="img" aria-label="{aria}" tabindex="0">'
            f'<title>{aria}</title>'
            f'</rect>'
            f'<text x="{grid_x0 + bw + 8}" y="{bar_rect_y + 10}" class="font-mono val-text fade-in">{pct*100:.1f}%</text>'
            f'</g>'
        )
        cumulative_by += rh

    # ── Footer ────────────────────────────────────────────────────────────────
    note_txt = f"* Note: All-time language distribution is measured by bytes of code. Recent activity is based on commits over the last {days_back} days."
    parts.append(f'<text x="15" y="{note_y}" class="font-serif note-text" style="font-style: italic;">{html.escape(note_txt)}</text>')
    parts.append(f'<text x="785" y="{note_y}" text-anchor="end" class="font-serif note-text">Source: GitHub API</text>')

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
    req = _requests
    headers = _gh_headers()
    repos, page = [], 1
    while True:
        r = req.get(
            "https://api.github.com/user/repos",
            headers=headers,
            params={
                "per_page": 100,
                "page": page,
                "affiliation": "owner,collaborator,organization_member",
                "visibility": "all",  # public + private 両方
            },
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
        if not data:
            break
        repos.extend(data)
        print(f"  Page {page}: {len(data)} repos fetched (cumulative: {len(repos)})")
        page += 1

    # フォーク除外
    if not INCLUDE_FORKS:
        before = len(repos)
        repos = [r for r in repos if not r.get("fork", False)]
        print(f"  Excluded {before - len(repos)} forked repos (INCLUDE_FORKS=False)")

    # 明示的除外リスト
    if EXCLUDE_REPOS:
        repos = [r for r in repos if r.get("full_name") not in EXCLUDE_REPOS]
        print(f"  Applied EXCLUDE_REPOS filter: {EXCLUDE_REPOS}")

    print(f"  → Total repos to analyze: {len(repos)}")
    for repo in repos:
        print(f"    - {repo.get('full_name')} (fork={repo.get('fork')}, private={repo.get('private')})")
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
    user_info = r.json()
    print(f"Authenticated as: {user_info.get('login', '?')}")
    print(f"Token scopes: checking via rate_limit endpoint...")
    rl = _requests.get("https://api.github.com/rate_limit", headers=_gh_headers(), timeout=30)
    if "X-OAuth-Scopes" in rl.headers:
        print(f"  OAuth scopes: {rl.headers['X-OAuth-Scopes']}")
    print("Listing all accessible repositories...")
    repos = _list_repos()
    print(f"Aggregating languages from {len(repos)} repositories...")
    return _aggregate_languages(repos)

def fetch_recent_repo_languages(days_back: int = 90) -> dict:
    repos = _list_repos()
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
            ext = os.path.splitext(fn)[1].lower()
            lang = EXT_LANG.get(ext, "Other")
            counts[lang] += size
    return dict(counts)

# ── entry point ────────────────────────────────────────────────────────────────

DAYS_BACK = 90

if __name__ == "__main__":
    if GH_TOKEN and _requests is not None:
        print("Fetching language stats from GitHub API …")
        counts_all = fetch_all_repo_languages()
        counts_recent = fetch_recent_repo_languages(days_back=DAYS_BACK)
    else:
        print("GH_TOKEN not set or `requests` unavailable — scanning local repo …")
        counts_all = scan_bytes(REPO_ROOT)
        # For local scanning fallback, mock recent as having slightly different ratios or identical
        counts_recent = counts_all

    make_unified_svg(counts_all, counts_recent, OUTPUT_SVG, days_back=DAYS_BACK)
    print("Wrote", OUTPUT_SVG)