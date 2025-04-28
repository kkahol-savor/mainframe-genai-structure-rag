#!/usr/bin/env python3
"""
Repo‑wide COBOL structure & call‑graph extractor (function‑style)
================================================================
* Recurses through **all** `.cbl` files in a folder tree.
* Writes one JSON file per source and a repo‑level `filecall_graph.json`.
* Designed to be invoked **programmatically** via `main()` instead of a CLI.

Example
-------
```python
import repo_cobol_parser  # this file
repo_cobol_parser.main(
    repo_root="/path/to/repo",           # defaults to current dir
    out_dir="cobol_structures",          # per‑file structures
    callgraph="filecall_graph.json"      # aggregated edges
)
```

Dependencies: only the standard library.
"""

from __future__ import annotations

import json, pathlib, re, sys
from collections import defaultdict
from typing import Dict, List, Optional

# ---------------------------------------------------------------------------
# Quick PROGRAM‑ID sniff (for call resolution)
# ---------------------------------------------------------------------------
_PROGID_RE = re.compile(r"^\s*PROGRAM-ID\.\s+([\w-]+)\.", re.I | re.M)


def sniff_program_id(path: pathlib.Path) -> Optional[str]:
    """Return PROGRAM‑ID for a file or None if not found/accessible"""
    try:
        text = path.read_text(errors="ignore")
    except Exception:
        return None
    m = _PROGID_RE.search(text)
    return m[1] if m else None

# ---------------------------------------------------------------------------
# COBOL file parser (regex heuristics)
# ---------------------------------------------------------------------------
_DIV_RE   = re.compile(r"^\s*(\w[\w-]*)\s+DIVISION\b", re.I)
_SEC_RE   = re.compile(r"^\s*(\w[\w-]*)\s+SECTION\.",  re.I)
_VAR_RE   = re.compile(r"^\s*(\d{2})\s+([\w-]+).*?\bPIC\b\s+([A-Za-z0-9()V-]+)", re.I)
_PAR_RE   = re.compile(r"^\s*([\w-]+)\.\s*$", re.I)
_CALL_RE  = re.compile(r"\bCALL\s+\"?([\w-]+)\"?", re.I)
_PERF_RE  = re.compile(r"\bPERFORM\s+([\w-]+)", re.I)
_COMMENT  = ("*", "*>")  # traditional + free‑format comments


class CobolParser:
    """Parse a single COBOL source and capture structure + call sites"""

    def __init__(self, path: pathlib.Path):
        self.path = path
        self.program_id: str = path.stem
        self.divisions: list[str] = []
        self.data_sections: dict[str, list[dict]] = defaultdict(list)
        self.paragraphs: dict[str, dict] = {}
        self.calls: list[dict] = []  # populated during parse()

    # ---------------------------------------------------------
    def parse(self):
        div = sec = para = None
        for lineno, raw in enumerate(self.path.read_text(errors="ignore").splitlines(), 1):
            if raw.lstrip().startswith(_COMMENT):
                continue
            strip = raw.rstrip().strip()
            if not strip:
                continue

            # DIVISION, SECTION, PROGRAM‑ID
            if m := _DIV_RE.match(strip):
                div, sec, para = m[1].upper(), None, None
                if div not in self.divisions:
                    self.divisions.append(div)
                continue
            if m := _SEC_RE.match(strip):
                sec = m[1].upper()
                continue
            if m := _PROGID_RE.match(strip):
                self.program_id = m[1]
                continue

            # DATA items
            if div == "DATA" and sec and (m := _VAR_RE.match(strip)):
                self.data_sections[sec].append(
                    dict(level=int(m[1]), name=m[2], pic=m[3])
                )
                continue

            # PROCEDURE division
            if div == "PROCEDURE":
                if m := _PAR_RE.match(strip):
                    para = m[1]
                    self.paragraphs[para] = dict(statements=[])
                    continue
                if para is None:
                    continue

                # CALL / PERFORM detection
                if m := _CALL_RE.search(strip):
                    tgt = m[1]
                    self.paragraphs[para]["statements"].append(
                        dict(type="CALL", target=tgt, line=lineno)
                    )
                    self.calls.append(
                        dict(from_file=str(self.path), from_paragraph=para, line=lineno, to_program=tgt)
                    )
                if m := _PERF_RE.search(strip):
                    tgt = m[1]
                    self.paragraphs[para]["statements"].append(
                        dict(type="PERFORM", target=tgt, line=lineno)
                    )

    # ---------------------------------------------------------
    def to_dict(self):
        return dict(
            file=str(self.path),
            program_id=self.program_id,
            divisions=self.divisions,
            data_sections=self.data_sections,
            paragraphs=self.paragraphs,
        )

# ---------------------------------------------------------------------------
# Index builder – map PROGRAM‑ID → source path for the whole repo
# ---------------------------------------------------------------------------

def build_index(root: pathlib.Path) -> Dict[str, pathlib.Path]:
    idx: Dict[str, pathlib.Path] = {}
    for f in root.rglob("*.cbl"):
        if pid := sniff_program_id(f):
            idx[pid.lower()] = f
    return idx

# ---------------------------------------------------------------------------
# Repo‑level processor
# ---------------------------------------------------------------------------

def parse_repo(repo_root: pathlib.Path, out_dir: pathlib.Path, callgraph_file: pathlib.Path):
    """Parse every COBOL file once, emit per‑file JSON + global call graph."""

    out_dir.mkdir(parents=True, exist_ok=True)
    program_index = build_index(repo_root)

    # Pass 1 – parse every COBOL file
    structures: Dict[pathlib.Path, CobolParser] = {}
    for file in repo_root.rglob("*.cbl"):
        parser = CobolParser(file)
        parser.parse()
        structures[file] = parser

    # Pass 2 – resolve CALL edges to files (if known)
    all_edges: List[dict] = []
    for parser in structures.values():
        for edge in parser.calls:
            tgt_prog = edge["to_program"].lower()
            edge["to_file"] = str(program_index.get(tgt_prog)) if tgt_prog in program_index else None
            all_edges.append(edge)

    # Emit one JSON per COBOL file – directory layout mirrored
    for file, parser in structures.items():
        dst = (out_dir / file.relative_to(repo_root)).with_suffix(".structure.json")
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(json.dumps(parser.to_dict(), indent=2))

    # Emit aggregated call‑graph
    callgraph_file.write_text(json.dumps(all_edges, indent=2))
    print(f"✔ Parsed {len(structures)} COBOL program(s).")
    print(f"  • Structures  → {out_dir}/<file>.structure.json (mirrors repo layout)")
    print(f"  • Call‑graph  → {callgraph_file}")

# ---------------------------------------------------------------------------
# Public entry – call directly from Python
# ---------------------------------------------------------------------------

def main(*, repo_root: str | pathlib.Path = ".", out_dir: str | pathlib.Path = "cobol_structures", callgraph: str | pathlib.Path = "filecall_graph.json"):
    """Run the parser programmatically.

    Args
    ----
    repo_root : str or Path, optional
        Folder to scan; default is current working directory.
    out_dir   : str or Path, optional
        Destination folder for per‑file JSON. Created if missing.
    callgraph : str or Path, optional
        Path to write the aggregated call‑graph JSON.
    """
    root = pathlib.Path(repo_root).resolve()
    if not root.exists():
        raise FileNotFoundError(f"Repo root '{root}' does not exist.")

    parse_repo(root, pathlib.Path(out_dir), pathlib.Path(callgraph))


# Script execution – default to CWD with standard output locations
if __name__ == "__main__":
    main(
        repo_root="cobol_examples",
        out_dir="cobol_structures",
        callgraph="filecall_graph.json"
    )
