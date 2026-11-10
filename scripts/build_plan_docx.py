"""Build docs/icd_mapping_3month_plan.docx from the markdown plan.

The markdown is the source of truth; this script regenerates the Word copy.
It runs pandoc with the existing .docx as the style reference, then fits every
table to the page width (pandoc's fixed column widths can overflow the page)
and shrinks code blocks so the layout listing does not wrap.

Requires pandoc on PATH. Run from the repo root:
    uv run --with python-docx python scripts/build_plan_docx.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import docx
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "docs" / "icd_mapping_3month_plan.md"
OUT = REPO / "docs" / "icd_mapping_3month_plan.docx"
CODE_PT = 7.5


def fit_tables(d: docx.document.Document) -> None:
    sec = d.sections[0]
    text_twips = int((sec.page_width - sec.left_margin - sec.right_margin) / 635)
    for t in d.tables:
        tbl_pr = t._tbl.tblPr
        for tag in ("w:tblW", "w:tblLayout"):
            el = tbl_pr.find(qn(tag))
            if el is not None:
                tbl_pr.remove(el)
        width = OxmlElement("w:tblW")
        width.set(qn("w:w"), "5000")
        width.set(qn("w:type"), "pct")
        tbl_pr.append(width)
        layout = OxmlElement("w:tblLayout")
        layout.set(qn("w:type"), "autofit")
        tbl_pr.append(layout)

        cols = t._tbl.tblGrid.findall(qn("w:gridCol"))
        n = len(cols)
        # Column weight: longest cell text plus extra for long unbreakable words (code names).
        weights = [0] * n
        for row in t.rows:
            for i, cell in enumerate(row.cells[:n]):
                longest_word = max((len(w) for w in cell.text.split()), default=0)
                weights[i] = max(weights[i], len(cell.text) + 2 * longest_word)
        weights = [max(w, 10) for w in weights]
        total = sum(weights)
        widths = [int(text_twips * w / total) for w in weights]
        for gc, w in zip(cols, widths, strict=True):
            gc.set(qn("w:w"), str(w))
        for row in t.rows:
            for cell, w in zip(row.cells[:n], widths, strict=False):
                tc_pr = cell._tc.get_or_add_tcPr()
                tc_w = tc_pr.find(qn("w:tcW"))
                if tc_w is None:
                    tc_w = OxmlElement("w:tcW")
                    tc_pr.append(tc_w)
                tc_w.set(qn("w:w"), str(w))
                tc_w.set(qn("w:type"), "dxa")


def shrink_code(d: docx.document.Document) -> None:
    for p in d.paragraphs:
        if p.style is not None and p.style.name == "Source Code":
            for r in p.runs:
                r.font.size = Pt(CODE_PT)


def main() -> int:
    if shutil.which("pandoc") is None:
        print("pandoc not found on PATH", file=sys.stderr)
        return 1
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        ref = tmp_dir / "reference.docx"
        raw = tmp_dir / "raw.docx"
        ref_args: list[str] = []
        if OUT.exists():
            shutil.copy(OUT, ref)
            ref_args = [f"--reference-doc={ref}"]
        subprocess.run(
            ["pandoc", str(SRC), "-f", "gfm", "-t", "docx", *ref_args, "-o", str(raw)],
            check=True,
        )
        d = docx.Document(str(raw))
        fit_tables(d)
        shrink_code(d)
        d.save(str(OUT))
    print(f"Wrote {OUT.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
