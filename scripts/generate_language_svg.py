#!/usr/bin/env python3
"""
Generate language percentage SVGs for this repository by counting bytes per file extension.
Writes: languages_programming.svg and languages_markup.svg at the repo root.

Note / 表記:
This script was created or updated with the assistance of an AI model: GPT-5 mini (model ID: gpt-5-mini).
このスクリプトは AI（GPT-5 mini, model ID: gpt-5-mini）の支援により作成または更新されました。
"""
import os
from collections import defaultdict, Counter

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
OUTPUT_PROG = os.path.join(REPO_ROOT, 'languages_programming.svg')
OUTPUT_MARK = os.path.join(REPO_ROOT, 'languages_markup.svg')

# Simple extension -> language mapping
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
    '.pl': 'Perl',  # note: .pl is used by both Perl and Prolog; defaulting to Perl
    '.pro': 'Prolog',
    '.sql': 'SQL',
    '.sh': 'Shell', '.bash': 'Shell', '.zsh': 'Shell',
    '.ps1': 'PowerShell', '.psm1': 'PowerShell',
    '.html': 'HTML', '.htm': 'HTML', '.css': 'CSS',
    '.md': 'Markdown', '.markdown': 'Markdown',
    '.xml': 'XML', '.json': 'JSON', '.yml': 'YAML', '.yaml': 'YAML',
    '.ini': 'INI', '.cfg': 'Config', '.toml': 'TOML',
    '.txt': 'Text', '.svg': 'SVG',
    # TeX / LaTeX
    '.tex': 'LaTeX', '.sty': 'LaTeX', '.cls': 'LaTeX', '.bib': 'BibTeX'
}

SKIP_DIRS = {'.git', 'node_modules', '__pycache__', '.venv', 'venv', '.github'}

def scan_bytes(root):
    counts = defaultdict(int)
    for dirpath, dirnames, filenames in os.walk(root):
        # prune
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            try:
                full = os.path.join(dirpath, fn)
                size = os.path.getsize(full)
            except OSError:
                continue
            ext = os.path.splitext(fn)[1].lower()
            lang = EXT_LANG.get(ext, None)
            if lang is None:
                # try shebang for scripts
                if size > 0 and ext == '':
                    try:
                        with open(full, 'rb') as f:
                            start = f.read(128)
                            if b'python' in start:
                                lang = 'Python'
                            elif b'node' in start or b'js' in start:
                                lang = 'JavaScript'
                    except Exception:
                        pass
            if lang is None:
                lang = 'Other'
            counts[lang] += size
    return counts

PALETTE = [
    '#4e79a7', '#f28e2b', '#e15759', '#76b7b2', '#59a14f', '#edc949',
    '#af7aa1', '#ff9da7', '#9c755f', '#bab0ab'
]

def color_for(i):
    return PALETTE[i % len(PALETTE)]


def make_bar_svg(counter, title, outpath, width=820, height=140):
    total = sum(counter.values())
    if total == 0:
        svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">\n'
        svg += f'<text x="10" y="20" font-family="sans-serif" font-size="14">{title}: No data found</text>\n</svg>\n'
        with open(outpath, 'w') as f:
            f.write(svg)
        return

    # sort by size
    items = sorted(counter.items(), key=lambda x: x[1], reverse=True)
    # keep top 8, rest -> Other
    top = []
    others = 0
    for i, (lang, size) in enumerate(items):
        if i < 8 and lang != 'Other':
            top.append((lang, size))
        else:
            others += size
    if others > 0:
        top.append(('Other', others))

    bar_x = 20
    bar_y = 30
    bar_w = width - 40
    bar_h = 28

    svg_parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">']
    svg_parts.append(f'<style>text{{font-family:sans-serif}}</style>')
    svg_parts.append(f'<text x="{bar_x}" y="18" font-size="16" font-weight="bold">{title}</text>')

    # draw segments
    cur_x = bar_x
    for i, (lang, size) in enumerate(top):
        frac = size / total
        seg_w = max(int(round(frac * bar_w)), 1)
        color = color_for(i)
        svg_parts.append(f'<rect x="{cur_x}" y="{bar_y}" width="{seg_w}" height="{bar_h}" fill="{color}" rx="4" ry="4"/>')
        # label if segment wide enough
        if seg_w > 60:
            pct = frac * 100
            svg_parts.append(f'<text x="{cur_x+6}" y="{bar_y+19}" font-size="12" fill="#fff">{lang} {pct:.1f}%</text>')
        cur_x += seg_w

    # legend
    legend_x = bar_x
    legend_y = bar_y + bar_h + 30
    lx = legend_x
    for i, (lang, size) in enumerate(top):
        pct = size / total * 100
        color = color_for(i)
        svg_parts.append(f'<rect x="{lx}" y="{legend_y}" width="12" height="12" fill="{color}" rx="2" ry="2"/>')
        svg_parts.append(f'<text x="{lx+18}" y="{legend_y+11}" font-size="12">{lang} {pct:.1f}%</text>')
        lx += 140
        if lx > width - 120:
            lx = legend_x
            legend_y += 20

    svg_parts.append('</svg>')
    with open(outpath, 'w') as f:
        f.write('\n'.join(svg_parts))


if __name__ == '__main__':
    counts = scan_bytes(REPO_ROOT)
    # separate markup vs programming
    markup_keys = {'Markdown', 'HTML', 'CSS', 'SVG', 'XML'}
    markup = {k: v for k, v in counts.items() if k in markup_keys}
    programming = {k: v for k, v in counts.items() if k not in markup_keys}

    make_bar_svg(programming, 'Language distribution (programming & scripts)', OUTPUT_PROG)
    make_bar_svg(markup, 'Markup & docs distribution', OUTPUT_MARK)
    print('Wrote', OUTPUT_PROG, OUTPUT_MARK)
