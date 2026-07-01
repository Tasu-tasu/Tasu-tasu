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
INCLUDE_FORKS = False
EXCLUDE_REPOS: list[str] = []

# ── language colors (Academic Editorial palette) ────────────────────────────────
LANG_COLORS: dict[str, str] = {
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
    "HTML":             "#b83e23",  # Terracotta Red
    "CSS":              "#216a94",  # Ocean Blue
    "Markdown":         "#1e3b70",  # Deep Indigo
    "LaTeX":            "#5b4a8a",  # Academic Purple
    "ReStructuredText": "#5a7c8c",  # Blue Grey
    "Ruby":             "#cc342d",
    "PHP":              "#777bb3",
    "Rust":             "#ce5a1e",
    "R":                "#276dc3",
    "Scala":            "#c22d40",
    "Clojure":          "#63b132",
    "Haskell":          "#5e5086",
    "Lua":              "#2c3e70",
    "Elixir":           "#4b275f",
    "F#":               "#378bba",
    "C#":               "#239120",
    "VB.NET":           "#0078d4",
    "Perl":             "#0073b8",
    "Groovy":           "#4298b8",
    "Dart":             "#01579b",
    "Other":            "#718096",
}

_FALLBACK_PALETTE = [
    "#3f6a8a", "#a86c1e", "#2a8f9d", "#bd532b", "#5a3fa8",
    "#6b7280", "#216a94", "#bd3b24", "#718096", "#c2ab25"
]

def _lang_color(lang: str, idx: int = 0) -> str:
    return LANG_COLORS.get(lang, _FALLBACK_PALETTE[idx % len(_FALLBACK_PALETTE)])

def _top_items(counter: dict, n: int = 5) -> list[tuple[str, int]]:
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

def make_unified_svg(counts_all: dict, counts_recent: dict, outpath: str, days_back: int = 90) -> None:
    total_all = sum(counts_all.values())
    total_recent = sum(counts_recent.values())

    if total_all == 0:
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

    svg_id = "language-analysis"
    title_text = "PROGRAMMING LANGUAGE ANALYSIS & RECENT ACTIVITY"
    desc_text = f"Donut chart shows overall language usage. Bar chart shows activity in the last {days_back} days."

    donut_css = []
    donut_circumference = 2 * math.pi * 75  # ~471.2389
    
    for i, (lang, size) in enumerate(top_all):
        pct = size / total_all
        length = pct * donut_circumference
        offset = donut_circumference - length
        color = _lang_color(lang, i)
        donut_css.append(f"""
@keyframes draw-slice-{i} {{
  from {{ stroke-dashoffset: {donut_circumference:.4f}; }}
  to {{ stroke-dashoffset: {offset:.4f}; }}
}}
.slice-{i} {{
  stroke: {color} !important;
  stroke-dasharray: {donut_circumference:.4f};
  stroke-dashoffset: {donut_circumference:.4f};
  animation: draw-slice-{i} 1.2s cubic-bezier(0.25, 1, 0.5, 1) forwards;
}}""")

    # 右側コンポーネント用 (開始位置の修正に追従)
    grid_x0 = 540
    grid_w = 180

    bar_css = []
    for i, (lang, size) in enumerate(top_recent):
        color = _lang_color(lang, i)
        bar_css.append(f"""
@keyframes grow-bar-{i} {{
  from {{ transform: scaleX(0); }}
  to {{ transform: scaleX(1); }}
}}
.bar-{i} {{
  fill: {color} !important;
  transform-origin: {grid_x0}px 0;
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
        f'<svg xmlns="http://www.w3.org/2000/svg" width="800" height="360" viewBox="0 0 800 360" role="img" aria-labelledby="{svg_id}-title {svg_id}-desc">',
        f'<title id="{svg_id}-title">{html.escape(title_text)}</title>',
        f'<desc id="{svg_id}-desc">{html.escape(desc_text)}</desc>',
        f'<style>{css}</style>',
        f'<rect width="100%" height="100%" fill="var(--bg)"/>',
    ]

    # ── Header ────────────────────────────────────────────────────────────────
    parts.append(f'<line x1="15" y1="12" x2="785" y2="12" stroke="var(--border)" stroke-width="1.5" />')
    parts.append(f'<text x="15" y="29" class="font-serif main-title">{html.escape(title_text)}</text>')
    parts.append(f'<line x1="15" y1="40" x2="785" y2="40" stroke="var(--border)" stroke-width="0.75" />')

    # ── Left Column: Donut Chart ──────────────────────────────────────────────
    parts.append(f'<text x="40" y="68" class="font-serif sub-title">I. OVERALL LANGUAGE USAGE</text>')
    
    cx, cy = 150, 185
    accumulated_pct = 0.0
    for i, (lang, size) in enumerate(top_all):
        pct = size / total_all
        angle = -90.0 + (accumulated_pct * 360.0)
        aria = html.escape(f"{lang}: {pct*100:.1f}%")
        color = _lang_color(lang, i)
        parts.append(
            f'<circle class="slice-{i}" cx="{cx}" cy="{cy}" r="75" fill="none" '
            f'stroke="{color}" stroke-width="26" stroke-linecap="butt" '
            f'transform="rotate({angle:.2f} {cx} {cy})" '
            f'role="img" aria-label="{aria}" tabindex="0">'
            f'<title>{aria}</title>'
            f'</circle>'
        )
        accumulated_pct += pct

    parts.append(f'<circle cx="{cx}" cy="{cy}" r="88" fill="none" stroke="var(--slice-border)" stroke-width="1.5"/>')
    parts.append(f'<circle cx="{cx}" cy="{cy}" r="62" fill="none" stroke="var(--slice-border)" stroke-width="1.5"/>')

    parts.append(
        f'<g class="fade-in">'
        f'<text x="{cx}" y="{cy - 5}" text-anchor="middle" class="font-serif label-text" style="font-weight: bold;">Languages</text>'
        f'<text x="{cx}" y="{cy + 12}" text-anchor="middle" class="font-serif val-text" style="font-style: italic;">All-Time</text>'
        f'</g>'
    )

    # 凡例の位置調整（文字被り対策）
    leg_x = 255
    leg_y0 = 98
    for i, (lang, size) in enumerate(top_all):
        pct = size / total_all
        ly = leg_y0 + i * 26
        color = _lang_color(lang, i)
        parts.append(
            f'<g class="fade-in">'
            f'<rect x="{leg_x}" y="{ly + 2}" width="10" height="10" rx="1" fill="{color}" stroke="var(--slice-border)" stroke-width="0.5" />'
            f'<text x="{leg_x + 18}" y="{ly + 11}" class="font-sans label-text">{html.escape(lang)}</text>'
            f'<text x="390" y="{ly + 11}" text-anchor="end" class="font-mono val-text">{pct*100:.1f}%</text>'
            f'</g>'
        )

    # ── Vertical Divider ──────────────────────────────────────────────────────
    parts.append(f'<line x1="400" y1="55" x2="400" y2="295" stroke="var(--border)" stroke-width="0.5" stroke-dasharray="3,3" />')

    # ── Right Column: Recent Activity ─────────────────────────────────────────
    parts.append(f'<text x="420" y="68" class="font-serif sub-title">II. RECENT ACTIVITY (LAST {days_back} DAYS)</text>')

    # グリッドの描画 (grid_x0 = 540 に更新)
    for p in [0.0, 0.25, 0.50, 0.75, 1.0]:
        gx = grid_x0 + grid_w * p
        parts.append(f'<line x1="{gx}" y1="85" x2="{gx}" y2="292" stroke="var(--grid)" stroke-width="0.75" />')
        if p in [0.0, 0.5, 1.0]:
            parts.append(f'<text x="{gx}" y="80" text-anchor="middle" class="font-mono val-text" style="font-size: 9px;">{int(p*100)}%</text>')

    # バーの描画 (ラベルの右寄せ位置を530にし、テキスト被りを完全に排除)
    bar_y0 = 102
    row_h = 36
    bar_h = 12
    for i, (lang, size) in enumerate(top_recent):
        pct = size / total_recent
        by = bar_y0 + i * row_h
        bw = max(2, pct * grid_w)
        aria = html.escape(f"{lang}: {pct*100:.1f}%")
        color = _lang_color(lang, i)
        parts.append(
            f'<g>'
            f'<text x="530" y="{by + 10}" text-anchor="end" class="font-sans label-text">{html.escape(lang)}</text>'
            f'<rect class="bar-{i}" x="{grid_x0}" y="{by}" width="{bw:.2f}" height="{bar_h}" rx="1" fill="{color}" '
            f'role="img" aria-label="{aria}" tabindex="0">'
            f'<title>{aria}</title>'
            f'</rect>'
            f'<text x="{grid_x0 + bw + 8}" y="{by + 10}" class="font-mono val-text fade-in">{pct*100:.1f}%</text>'
            f'</g>'
        )

    # ── Footer ────────────────────────────────────────────────────────────────
    parts.append(f'<line x1="15" y1="315" x2="785" y2="315" stroke="var(--border)" stroke-width="0.75" />')
    note_txt = f"* Note: All-time language distribution is measured by bytes of code. Recent activity is based on commits over the last {days_back} days."
    parts.append(f'<text x="15" y="333" class="font-serif note-text" style="font-style: italic;">{html.escape(note_txt)}</text>')
    parts.append(f'<text x="785" y="333" text-anchor="end" class="font-serif note-text">Source: GitHub API</text>')
    parts.append(f'<line x1="15" y1="346" x2="785" y2="346" stroke="var(--border)" stroke-width="1.5" />')

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
                "visibility": "all",
            },
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
        if not data:
            break
        repos.extend(data)
        page += 1

    if not INCLUDE_FORKS:
        repos = [r for r in repos if not r.get("fork", False)]

    if EXCLUDE_REPOS:
        repos = [r for r in repos if r.get("full_name") not in EXCLUDE_REPOS]

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
    repos = _list_repos()
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
        counts_recent = counts_all

    make_unified_svg(counts_all, counts_recent, OUTPUT_SVG, days_back=DAYS_BACK)
    print("Wrote", OUTPUT_SVG)