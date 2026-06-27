"""
Generate a single language distribution donut-chart SVG from all GitHub repositories via the GitHub API.
Also generates a horizontal bar chart of the top 5 languages.
Falls back to scanning the local repository if GH_TOKEN is not set.
Writes: languages.svg and top_languages_bar.svg at the repo root.

Note / 表記:
This script was created or updated with the assistance of an AI model.
このスクリプトは AI の支援により作成または更新されました。
"""
import html
import math
import os
from collections import defaultdict
from datetime import datetime, timedelta

try:
    import requests as _requests
except ImportError:
    _requests = None

GH_TOKEN = os.environ.get('GH_TOKEN')
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
OUTPUT_DONUT = os.path.join(REPO_ROOT, 'languages.svg')
OUTPUT_BAR = os.path.join(REPO_ROOT, 'top_languages_bar.svg')

# Official / iconic language colors (sourced from github-linguist and community conventions)
LANG_COLORS: dict[str, str] = {
    'Python':            '#3776AB',
    'Jupyter Notebook':  '#DA5B0B',
    'Go':                '#00ADD8',
    'JavaScript':        '#F7DF1E',
    'TypeScript':        '#3178C6',
    'Java':              '#ED8B00',
    'Kotlin':            '#7F52FF',
    'Swift':             '#F05138',
    'Scala':             '#DC322F',
    'Ruby':              '#CC342D',
    'Rust':              '#DEA584',
    'C':                 '#555555',
    'C++':               '#00599C',
    'C/C++ Header':      '#6E4C13',
    'C++ Header':        '#00599C',
    'C#':                '#239120',
    'PHP':               '#777BB4',
    'Dart':              '#00B4AB',
    'Lua':               '#000080',
    'R':                 '#276DC3',
    'Julia':             '#9558B2',
    'Haskell':           '#5D4F85',
    'Elm':               '#60B5CC',
    'Elixir':            '#6E4A7E',
    'Erlang':            '#B83998',
    'F#':                '#B845FC',
    'Fortran':           '#4D41B1',
    'Ada':               '#02F88C',
    'Pascal':            '#E3F171',
    'Visual Basic':      '#945DB7',
    'Groovy':            '#4298B8',
    'CoffeeScript':      '#244776',
    'Solidity':          '#AA6746',
    'VHDL':              '#ADB2CB',
    'Verilog':           '#B2B7F8',
    'SystemVerilog':     '#DAE1C2',
    'Assembly':          '#6E4C13',
    'Lisp':              '#3FB68B',
    'Common Lisp':       '#3FB68B',
    'Scheme':            '#1E4AEC',
    'OCaml':             '#EF7A08',
    'Perl':              '#0298C3',
    'Prolog':            '#74283C',
    'SQL':               '#E38C00',
    'Shell':             '#89E051',
    'PowerShell':        '#012456',
    # Markup
    'HTML':              '#E44D26',
    'CSS':               '#1572B6',
    'Markdown':          '#083FA1',
    'XML':               '#0060AC',
    'JSON':              '#292929',
    'YAML':              '#CB171E',
    'TOML':              '#9C4221',
    'INI':               '#D1DBE0',
    'Config':            '#AAAAAA',
    'Text':              '#888888',
    'SVG':               '#FFB13B',
    'LaTeX':             '#3D6117',
    'TeX':               '#3D6117',
    'BibTeX':            '#778899',
    'Other':             '#9CA3AF',
}

# Fallback palette when a language has no registered color
_FALLBACK_PALETTE = [
    '#0072b2', '#e69f00', '#009e73', '#cc79a7',
    '#56b4e9', '#d55e00', '#f0e442', '#999999',
    '#332288', '#88ccee',
]

# Hatch patterns overlaid on slices for colorblind / print accessibility
_PATTERN_OVERLAYS = [
    '',                                                                  # 0: solid
    '<line x1="0" y1="8" x2="8" y2="0" stroke="var(--overlay-color)" stroke-width="1.5"/>',  # 1: diagonal /
    '<line x1="0" y1="4" x2="8" y2="4" stroke="var(--overlay-color)" stroke-width="1.5"/>',  # 2: horizontal
    '<line x1="4" y1="0" x2="4" y2="8" stroke="var(--overlay-color)" stroke-width="1.5"/>',  # 3: vertical
    '<line x1="0" y1="8" x2="8" y2="0" stroke="var(--overlay-color)" stroke-width="1.5"/>'
    '<line x1="0" y1="0" x2="8" y2="8" stroke="var(--overlay-color)" stroke-width="1.5"/>',  # 4: cross-diagonal
    '<circle cx="4" cy="4" r="1.5" fill="var(--overlay-color)"/>',          # 5: dots
    '<line x1="0" y1="0" x2="8" y2="8" stroke="var(--overlay-color)" stroke-width="1.5"/>',  # 6: diagonal \
    '<line x1="0" y1="2" x2="8" y2="2" stroke="var(--overlay-color)" stroke-width="1.5"/>'
    '<line x1="0" y1="6" x2="8" y2="6" stroke="var(--overlay-color)" stroke-width="1.5"/>',  # 7: double horizontal
    '<line x1="2" y1="0" x2="2" y2="8" stroke="var(--overlay-color)" stroke-width="1.5"/>'
    '<line x1="6" y1="0" x2="6" y2="8" stroke="var(--overlay-color)" stroke-width="1.5"/>',  # 8: double vertical
    '<rect x="2" y="2" width="4" height="4" fill="none" stroke="var(--overlay-color)" stroke-width="1"/>',  # 9: squares
]


def _color(lang: str, fallback_index: int = 0) -> str:
    return LANG_COLORS.get(lang, _FALLBACK_PALETTE[fallback_index % len(_FALLBACK_PALETTE)])


def _make_defs(items: list[tuple[str, int]]) -> str:
    """Return SVG <defs> with fill patterns per language (color + hatch overlay)."""
    lines = ['<defs>']
    for i, (lang, _) in enumerate(items):
        pid = f'p{i}'
        color = _color(lang, i)
        overlay = _PATTERN_OVERLAYS[i % len(_PATTERN_OVERLAYS)]
        lines.append(
            f'<pattern id="{pid}" patternUnits="userSpaceOnUse" width="8" height="8">'
            f'<rect width="8" height="8" fill="{color}"/>'
            f'{overlay}'
            f'</pattern>'
        )
    lines.append('</defs>')
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# GitHub API
# ---------------------------------------------------------------------------

def _gh_headers() -> dict:
    return {
        'Authorization': f'Bearer {GH_TOKEN}',
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
    }


def fetch_all_repo_languages() -> dict:
    """Aggregate language bytes across all repos accessible to the authenticated user token."""
    req = _requests
    headers = _gh_headers()

    # Verify token and get authenticated user info
    r = req.get('https://api.github.com/user', headers=headers, timeout=30)
    r.raise_for_status()
    username = r.json().get('login', '<unknown>')
    print(f'Authenticated as: {username}')

    repos, page = [], 1
    # Use the authenticated user's /user/repos endpoint to list all repos the token can access
    while True:
        r = req.get(
            'https://api.github.com/user/repos',
            headers=headers,
            params={'per_page': 100, 'page': page, 'affiliation': 'owner,collaborator,organization_member'},
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
        if not data:
            break
        repos.extend(data)
        page += 1
    print(f'Found {len(repos)} repositories accessible to token')

    totals: dict = defaultdict(int)
    for repo in repos:
        full_name = repo.get('full_name')
        if not full_name:
            continue
        r = req.get(
            f'https://api.github.com/repos/{full_name}/languages',
            headers=headers,
            timeout=30,
        )
        if r.status_code == 200:
            for lang, byte_count in r.json().items():
                totals[lang] += byte_count
    return dict(totals)


def fetch_recent_repo_languages(days_back: int = 90) -> dict:
    """
    Aggregate language bytes across repos updated in the last N days.
    Default: 90 days (approximately 3 months).
    """
    req = _requests
    headers = _gh_headers()

    repos, page = [], 1
    # Fetch all repos
    while True:
        r = req.get(
            'https://api.github.com/user/repos',
            headers=headers,
            params={'per_page': 100, 'page': page, 'affiliation': 'owner,collaborator,organization_member'},
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
        if not data:
            break
        repos.extend(data)
        page += 1

    # Filter repos by pushed_at timestamp (last N days)
    cutoff_date = datetime.utcnow() - timedelta(days=days_back)
    filtered_repos = []
    
    for repo in repos:
        pushed_at_str = repo.get('pushed_at')
        if not pushed_at_str:
            continue
        # Parse ISO 8601 timestamp (e.g., "2024-06-15T10:30:00Z")
        try:
            pushed_at = datetime.fromisoformat(pushed_at_str.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            continue
        
        if pushed_at >= cutoff_date:
            filtered_repos.append(repo)
    
    print(f'Filtered to {len(filtered_repos)} repositories updated in the last {days_back} days')

    totals: dict = defaultdict(int)
    for repo in filtered_repos:
        full_name = repo.get('full_name')
        if not full_name:
            continue
        r = req.get(
            f'https://api.github.com/repos/{full_name}/languages',
            headers=headers,
            timeout=30,
        )
        if r.status_code == 200:
            for lang, byte_count in r.json().items():
                totals[lang] += byte_count
    return dict(totals)


# ---------------------------------------------------------------------------
# Local fallback
# ---------------------------------------------------------------------------

EXT_LANG = {
    '.py': 'Python', '.pyw': 'Python', '.ipynb': 'Jupyter Notebook',
    '.go': 'Go',
    '.js': 'JavaScript', '.mjs': 'JavaScript', '.cjs': 'JavaScript', '.jsx': 'JavaScript',
    '.ts': 'TypeScript', '.tsx': 'TypeScript',
    '.java': 'Java', '.kt': 'Kotlin', '.kts': 'Kotlin',
    '.swift': 'Swift', '.scala': 'Scala',
    '.rb': 'Ruby', '.rs': 'Rust',
    '.cpp': 'C++', '.cc': 'C++', '.cxx': 'C++', '.c': 'C', '.h': 'C/C++ Header', '.hpp': 'C++ Header',
    '.cs': 'C#', '.php': 'PHP',
    '.dart': 'Dart', '.lua': 'Lua', '.r': 'R', '.jl': 'Julia',
    '.hs': 'Haskell', '.elm': 'Elm',
    '.ex': 'Elixir', '.exs': 'Elixir', '.erl': 'Erlang', '.hrl': 'Erlang',
    '.fs': 'F#', '.fsx': 'F#',
    '.f': 'Fortran', '.f90': 'Fortran', '.f95': 'Fortran',
    '.adb': 'Ada', '.ads': 'Ada',
    '.pas': 'Pascal',
    '.vb': 'Visual Basic', '.groovy': 'Groovy', '.coffee': 'CoffeeScript',
    '.sol': 'Solidity',
    '.vhd': 'VHDL', '.vhdl': 'VHDL', '.v': 'Verilog', '.sv': 'SystemVerilog',
    '.s': 'Assembly', '.asm': 'Assembly',
    '.lisp': 'Lisp', '.cl': 'Common Lisp', '.scm': 'Scheme', '.ss': 'Scheme',
    '.ml': 'OCaml', '.mli': 'OCaml',
    '.pl': 'Perl',
    '.pro': 'Prolog',
    '.sql': 'SQL',
    '.sh': 'Shell', '.bash': 'Shell', '.zsh': 'Shell',
    '.ps1': 'PowerShell', '.psm1': 'PowerShell',
    '.html': 'HTML', '.htm': 'HTML', '.css': 'CSS',
    '.md': 'Markdown', '.markdown': 'Markdown',
    '.xml': 'XML', '.json': 'JSON', '.yml': 'YAML', '.yaml': 'YAML',
    '.ini': 'INI', '.cfg': 'Config', '.toml': 'TOML',
    '.txt': 'Text', '.svg': 'SVG',
    '.tex': 'LaTeX', '.sty': 'LaTeX', '.cls': 'LaTeX', '.bib': 'BibTeX',
}

SKIP_DIRS = {'.git', 'node_modules', '__pycache__', '.venv', 'venv', '.github'}


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
            lang = EXT_LANG.get(ext)
            if lang is None and size > 0 and ext == '':
                try:
                    with open(full, 'rb') as f:
                        start = f.read(128)
                    if b'python' in start:
                        lang = 'Python'
                    elif b'node' in start or b'js' in start:
                        lang = 'JavaScript'
                except Exception:
                    pass
            counts[lang or 'Other'] += size
    return dict(counts)


# ---------------------------------------------------------------------------
# SVG pie chart (donut)
# ---------------------------------------------------------------------------

def _top_items(counter: dict, n: int = 8):
    items = sorted(counter.items(), key=lambda x: x[1], reverse=True)
    top, others = [], 0
    for i, (lang, size) in enumerate(items):
        if i < n and lang != 'Other':
            top.append((lang, size))
        else:
            others += size
    if others:
        top.append(('Other', others))
    return top


def make_donut_svg(counter: dict, title: str, outpath: str) -> None:
    """Write an accessible donut-chart SVG to *outpath*.

    The generated SVG embeds CSS variables and a `prefers-color-scheme` media
    query so it automatically adapts to light/dark mode in a single file.
    """
    total = sum(counter.values())
    svg_id = os.path.splitext(os.path.basename(outpath))[0]
    title_id = f'{svg_id}-title'
    desc_id = f'{svg_id}-desc'

    if total == 0:
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="500" height="60" '
            f'role="img" aria-labelledby="{title_id} {desc_id}">\n'
            f'<title id="{title_id}">{html.escape(title)}</title>\n'
            f'<desc id="{desc_id}">No data found</desc>\n'
            f'<text x="10" y="30" font-family="sans-serif" font-size="14">No data found</text>\n'
            f'</svg>\n'
        )
        with open(outpath, 'w') as f:
            f.write(svg)
        return

    top = _top_items(counter, n=10)
    n = len(top)

    # Layout
    width = 560
    cx, cy, r_outer, r_inner = 175, 185, 155, 75
    legend_x = 355
    legend_y_start = 30
    legend_item_h = 28
    height = max(380, legend_y_start + n * legend_item_h + 50)

    desc_text = f'{title}. ' + ', '.join(
        f'{lang}: {size / total * 100:.1f}%' for lang, size in top
    )

    style = (
        '<style>'
        ':root{'
        '--bg-fill:#f0f0f0;'
        '--title-fill:#000000;'
        '--subtitle-fill:#333333;'
        '--center-fill:white;'
        '--center-text-main:#444444;'
        '--center-text-sub:#777777;'
        '--legend-text-fill:#000000;'
        '--slice-focus-stroke:#000000;'
        '--pct-label-inside-fill:#ffffff;'
        '--slice-edge:white;'
        '--overlay-color:rgba(0,0,0,0.22);'
        '}'
        '@media (prefers-color-scheme: dark){:root{'
        '--bg-fill:#0b0b0b;'
        '--title-fill:#ffffff;'
        '--subtitle-fill:#dddddd;'
        '--center-fill:#0b0b0b;'
        '--center-text-main:#ffffff;'
        '--center-text-sub:#cccccc;'
        '--legend-text-fill:#ffffff;'
        '--slice-focus-stroke:#ffffff;'
        '--pct-label-inside-fill:#ffffff;'
        '--slice-edge:#0b0b0b;'
        '--overlay-color:rgba(255,255,255,0.18);'
        '}}'
        'text{font-family:sans-serif;} '
        '.slice:focus{stroke:var(--slice-focus-stroke);stroke-width:3;outline:none} '
        '.slice{cursor:pointer} '
        '</style>'
    )

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width}" height="{height}" '
        f'role="img" aria-labelledby="{title_id} {desc_id}">',
        f'<title id="{title_id}">{html.escape(title)}</title>',
        f'<desc id="{desc_id}">{html.escape(desc_text)}</desc>',
        style,
        _make_defs(top),
        # Background circle
        f'<circle cx="{cx}" cy="{cy}" r="{r_outer}" fill="var(--bg-fill)"/>',
        # Chart title
        f'<text x="{cx}" y="{cy - r_outer - 14}" font-size="15" font-weight="bold" '
        f'text-anchor="middle" fill="var(--title-fill)">{html.escape(title)}</text>',
    ]

    # Donut slices
    angle = -math.pi / 2
    for i, (lang, size) in enumerate(top):
        frac = size / total
        sweep = frac * 2 * math.pi
        end_angle = angle + sweep
        large = 1 if sweep > math.pi else 0

        ox1 = cx + r_outer * math.cos(angle)
        oy1 = cy + r_outer * math.sin(angle)
        ox2 = cx + r_outer * math.cos(end_angle)
        oy2 = cy + r_outer * math.sin(end_angle)
        ix1 = cx + r_inner * math.cos(end_angle)
        iy1 = cy + r_inner * math.sin(end_angle)
        ix2 = cx + r_inner * math.cos(angle)
        iy2 = cy + r_inner * math.sin(angle)

        d = (
            f'M {ox1:.3f} {oy1:.3f} '
            f'A {r_outer} {r_outer} 0 {large} 1 {ox2:.3f} {oy2:.3f} '
            f'L {ix1:.3f} {iy1:.3f} '
            f'A {r_inner} {r_inner} 0 {large} 0 {ix2:.3f} {iy2:.3f} '
            f'Z'
        )
        pct_label = f'{frac * 100:.1f}%'
        aria = html.escape(f'{lang}: {pct_label}')

        parts.append(
            f'<path class="slice" d="{d}" fill="url(#p{i})" stroke="var(--slice-edge)" stroke-width="1.5" '
            f'role="img" aria-label="{aria}" tabindex="0">'
            f'<title>{aria}</title>'
            f'</path>'
        )

        # Percentage label inside slice
        if frac > 0.07:
            mid = angle + sweep / 2
            lr = (r_outer + r_inner) / 2
            lx = cx + lr * math.cos(mid)
            ly = cy + lr * math.sin(mid)
            parts.append(
                f'<text x="{lx:.1f}" y="{ly:.1f}" font-size="11" fill="var(--pct-label-inside-fill)" '
                f'text-anchor="middle" dominant-baseline="middle" '
                f'aria-hidden="true">{html.escape(pct_label)}</text>'
            )

        angle = end_angle

    # Center label
    parts.append(
        f'<circle cx="{cx}" cy="{cy}" r="{r_inner}" fill="var(--center-fill)"/>'
        f'<text x="{cx}" y="{cy - 8}" font-size="13" font-weight="bold" '
        f'text-anchor="middle" fill="var(--center-text-main)">Languages</text>'
        f'<text x="{cx}" y="{cy + 12}" font-size="11" '
        f'text-anchor="middle" fill="var(--center-text-sub)">{len(top)} shown</text>'
    )

    # Legend
    for i, (lang, size) in enumerate(top):
        frac = size / total
        ly = legend_y_start + i * legend_item_h
        pct_label = f'{frac * 100:.1f}%'
        parts.append(
            f'<rect x="{legend_x}" y="{ly}" width="14" height="14" '
            f'fill="url(#p{i})" rx="2" stroke="{_color(lang, i)}" stroke-width="1" '
            f'aria-hidden="true"/>'
        )
        parts.append(
            f'<text x="{legend_x + 22}" y="{ly + 11}" font-size="13" aria-hidden="true" fill="var(--legend-text-fill)">'
            f'{html.escape(lang)}\u2009{html.escape(pct_label)}</text>'
        )

    parts.append('</svg>')
    with open(outpath, 'w') as f:
        f.write('\n'.join(parts))


# ---------------------------------------------------------------------------
# SVG horizontal bar chart (top 5 languages)
# ---------------------------------------------------------------------------

def make_bar_chart_svg(counter: dict, outpath: str) -> None:
    """Write an accessible horizontal bar chart SVG of top 5 languages to *outpath*."""
    total = sum(counter.values())
    
    if total == 0:
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="350" height="60" '
            'role="img" aria-label="No data found">\n'
            '<text x="10" y="30" font-family="sans-serif" font-size="14">No data found</text>\n'
            '</svg>\n'
        )
        with open(outpath, 'w') as f:
            f.write(svg)
        return

    # Get top 5 languages
    top = _top_items(counter, n=5)
    
    # Layout parameters
    width = 380
    height = 280
    margin_left = 110
    margin_right = 30
    margin_top = 30
    margin_bottom = 30
    bar_height = 35
    chart_height = len(top) * bar_height
    
    # Build SVG
    svg_id = os.path.splitext(os.path.basename(outpath))[0]
    title_id = f'{svg_id}-title'
    desc_id = f'{svg_id}-desc'
    
    desc_text = 'Top 5 languages by bytes: ' + ', '.join(
        f'{lang}: {size / total * 100:.1f}%' for lang, size in top
    )
    
    style = (
        '<style>'
        ':root{'
        '--bg-fill:#f0f0f0;'
        '--title-fill:#000000;'
        '--text-fill:#333333;'
        '--grid-line:#e0e0e0;'
        '--bar-bg:#d0d0d0;'
        '}'
        '@media (prefers-color-scheme: dark){:root{'
        '--bg-fill:#0b0b0b;'
        '--title-fill:#ffffff;'
        '--text-fill:#dddddd;'
        '--grid-line:#333333;'
        '--bar-bg:#444444;'
        '}}'
        'text{font-family:sans-serif;} '
        '.bar-label{font-size:12;} '
        '.bar-value{font-size:11;} '
        '</style>'
    )
    
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width}" height="{height}" '
        f'role="img" aria-labelledby="{title_id} {desc_id}">',
        f'<title id="{title_id}">Top 5 Languages</title>',
        f'<desc id="{desc_id}">{html.escape(desc_text)}</desc>',
        style,
        f'<rect width="{width}" height="{height}" fill="var(--bg-fill)"/>',
        f'<text x="{width // 2}" y="20" font-size="14" font-weight="bold" '
        f'text-anchor="middle" fill="var(--title-fill)">Top 5 Languages</text>',
    ]
    
    # Chart area background
    chart_x = margin_left
    chart_y = margin_top + 10
    chart_width = width - margin_left - margin_right
    
    parts.append(
        f'<rect x="{chart_x}" y="{chart_y}" width="{chart_width}" height="{chart_height}" '
        f'fill="none" stroke="var(--grid-line)" stroke-width="1"/>'
    )
    
    # Bars
    max_width = chart_width * 0.9
    for i, (lang, size) in enumerate(top):
        frac = size / total
        bar_y = chart_y + i * bar_height + 5
        bar_width = frac * max_width
        color = _color(lang, i)
        pct_label = f'{frac * 100:.1f}%'
        
        # Background bar
        parts.append(
            f'<rect x="{chart_x + 5}" y="{bar_y}" width="{max_width}" height="{bar_height - 10}" '
            f'fill="var(--bar-bg)" rx="2"/>'
        )
        
        # Colored bar
        parts.append(
            f'<rect x="{chart_x + 5}" y="{bar_y}" width="{bar_width}" height="{bar_height - 10}" '
            f'fill="{color}" rx="2"/>'
        )
        
        # Language label (left)
        parts.append(
            f'<text x="{chart_x - 8}" y="{bar_y + (bar_height - 10) // 2 + 4}" '
            f'text-anchor="end" class="bar-label" fill="var(--text-fill)">'
            f'{html.escape(lang)}</text>'
        )
        
        # Percentage label (right)
        parts.append(
            f'<text x="{chart_x + 5 + bar_width + 8}" y="{bar_y + (bar_height - 10) // 2 + 4}" '
            f'class="bar-value" fill="var(--text-fill)">'
            f'{html.escape(pct_label)}</text>'
        )
    
    parts.append('</svg>')
    with open(outpath, 'w') as f:
        f.write('\n'.join(parts))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    if GH_TOKEN and _requests is not None:
        print('Fetching language stats from GitHub API …')
        # All repositories for donut chart
        print('  - Fetching all repositories …')
        counts_all = fetch_all_repo_languages()
        print(f'  - Aggregated {len(counts_all)} language(s) across all repositories')
        
        # Recent repositories for bar chart
        print('  - Fetching repositories from last 90 days …')
        counts_recent = fetch_recent_repo_languages(days_back=90)
        print(f'  - Aggregated {len(counts_recent)} language(s) across recent repositories')
    else:
        print('GH_TOKEN not set or `requests` unavailable — scanning local repo …')
        counts_all = scan_bytes(REPO_ROOT)
        counts_recent = counts_all  # Use same data for both if no API access

    make_donut_svg(counts_all, 'Language distribution', OUTPUT_DONUT)
    print('Wrote', OUTPUT_DONUT)
    
    make_bar_chart_svg(counts_recent, OUTPUT_BAR)
    print('Wrote', OUTPUT_BAR)