#!/usr/bin/env python3
"""Converts Markdown files to styled PDF using reportlab + markdown."""

import re
import sys
from pathlib import Path
from html.parser import HTMLParser

import markdown
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable,
    ListFlowable,
    ListItem,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# ── Fonts (Windows TTF — full Unicode/Polish support) ────────────────────────
FONTS_DIR = Path("C:/Windows/Fonts")

def _reg(name, filename):
    pdfmetrics.registerFont(TTFont(name, str(FONTS_DIR / filename)))

_reg("Arial",            "arial.ttf")
_reg("Arial-Bold",       "arialbd.ttf")
_reg("Arial-Italic",     "ariali.ttf")
_reg("Arial-BoldItalic", "arialbi.ttf")
_reg("CourierNew",       "cour.ttf")
_reg("CourierNew-Bold",  "courbd.ttf")

from reportlab.pdfbase.pdfmetrics import registerFontFamily
registerFontFamily("Arial",
    normal="Arial", bold="Arial-Bold",
    italic="Arial-Italic", boldItalic="Arial-BoldItalic")

PAGE_W, PAGE_H = A4
MARGIN = 2.2 * cm
CONTENT_W = PAGE_W - 2 * MARGIN

# ── Palette ──────────────────────────────────────────────────────────────────
DARK     = colors.HexColor("#1a1a2e")
ACCENT   = colors.HexColor("#0f3460")
ACCENT2  = colors.HexColor("#16213e")
CODE_BG  = colors.HexColor("#f4f4f4")
RULE_CLR = colors.HexColor("#cccccc")
TBL_HEAD = colors.HexColor("#0f3460")
TBL_ALT  = colors.HexColor("#eef2f7")


def build_styles():
    base = getSampleStyleSheet()
    def S(name, parent="Normal", **kw):
        return ParagraphStyle(name, parent=base[parent], **kw)

    return {
        "h1": S("h1", fontSize=22, leading=28, textColor=DARK,
                 spaceBefore=18, spaceAfter=6, fontName="Arial-Bold"),
        "h2": S("h2", fontSize=16, leading=22, textColor=ACCENT,
                 spaceBefore=16, spaceAfter=4, fontName="Arial-Bold"),
        "h3": S("h3", fontSize=13, leading=18, textColor=ACCENT2,
                 spaceBefore=12, spaceAfter=3, fontName="Arial-Bold"),
        "h4": S("h4", fontSize=11, leading=16, textColor=ACCENT2,
                 spaceBefore=8,  spaceAfter=2, fontName="Arial-BoldItalic"),
        "body": S("body", fontSize=10, leading=15, textColor=colors.black,
                  spaceBefore=4, spaceAfter=4, alignment=TA_LEFT, fontName="Arial"),
        "code_inline": S("code_inline", fontSize=9, fontName="CourierNew",
                          backColor=CODE_BG, textColor=colors.HexColor("#c7254e")),
        "meta": S("meta", fontSize=8, leading=12, textColor=colors.grey,
                  spaceBefore=0, spaceAfter=10, fontName="Arial-Italic"),
        "li": S("li", fontSize=10, leading=14, spaceBefore=1, spaceAfter=1,
                fontName="Arial"),
    }


def inline_markup(text: str) -> str:
    """Convert markdown inline syntax to reportlab XML tags."""
    # Escape < > that are NOT reportlab tags
    text = text.replace("&", "&amp;")
    # Bold+italic ***text***
    text = re.sub(r"\*\*\*(.+?)\*\*\*", r"<b><i>\1</i></b>", text)
    # Bold **text**
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    # Italic *text*
    text = re.sub(r"\*(.+?)\*", r"<i>\1</i>", text)
    # Inline code `text`
    text = re.sub(r"`([^`]+)`",
                  r'<font name="CourierNew" color="#c7254e" backColor="#f4f4f4"> \1 </font>',
                  text)
    return text


class MDFlowableBuilder:
    """Walks markdown-generated HTML and produces reportlab Flowables."""

    def __init__(self, styles: dict):
        self.S = styles
        self.flowables = []

    def _p(self, text, style="body"):
        text = text.strip()
        if not text:
            return
        self.flowables.append(Paragraph(inline_markup(text), self.S[style]))

    def _spacer(self, h_mm=2):
        self.flowables.append(Spacer(1, h_mm * mm))

    def _hr(self):
        self.flowables.append(
            HRFlowable(width="100%", thickness=0.5, color=RULE_CLR,
                       spaceAfter=6, spaceBefore=6)
        )

    def build(self, md_text: str):
        """Main entry: parse markdown and populate self.flowables."""
        lines = md_text.splitlines()
        i = 0
        while i < len(lines):
            line = lines[i]

            # --- Fenced code block ---
            if line.strip().startswith("```"):
                block_lines = []
                i += 1
                while i < len(lines) and not lines[i].strip().startswith("```"):
                    block_lines.append(lines[i])
                    i += 1
                code_text = "\n".join(block_lines)
                self.flowables.append(
                    Preformatted(
                        code_text,
                        ParagraphStyle(
                            "code_block",
                            fontName="CourierNew",
                            fontSize=8,
                            leading=12,
                            backColor=CODE_BG,
                            textColor=colors.HexColor("#2d2d2d"),
                            leftIndent=8,
                            spaceBefore=6,
                            spaceAfter=6,
                            borderPad=6,
                        ),
                    )
                )
                i += 1
                continue

            # --- Headings ---
            m = re.match(r"^(#{1,4})\s+(.*)", line)
            if m:
                level = len(m.group(1))
                text  = m.group(2).strip()
                style = {1: "h1", 2: "h2", 3: "h3", 4: "h4"}[level]
                if level == 1:
                    self._hr()
                self._p(text, style)
                if level == 1:
                    self._hr()
                i += 1
                continue

            # --- Horizontal rule ---
            if re.match(r"^-{3,}\s*$", line) or re.match(r"^\*{3,}\s*$", line):
                self._hr()
                i += 1
                continue

            # --- Table ---
            if "|" in line and i + 1 < len(lines) and re.match(r"^\|?[\s\-|:]+\|?$", lines[i+1]):
                table_lines = []
                while i < len(lines) and "|" in lines[i]:
                    table_lines.append(lines[i])
                    i += 1
                self._build_table(table_lines)
                continue

            # --- Bullet list ---
            if re.match(r"^[\-\*\+]\s+", line) or re.match(r"^\d+\.\s+", line):
                items = []
                while i < len(lines) and (
                    re.match(r"^[\-\*\+]\s+", lines[i]) or re.match(r"^\d+\.\s+", lines[i])
                ):
                    item_text = re.sub(r"^[\-\*\+]\s+|\d+\.\s+", "", lines[i])
                    items.append(
                        ListItem(
                            Paragraph(inline_markup(item_text), self.S["li"]),
                            leftIndent=16,
                            bulletColor=ACCENT,
                        )
                    )
                    i += 1
                self.flowables.append(
                    ListFlowable(items, bulletType="bullet",
                                 leftIndent=16, spaceBefore=4, spaceAfter=4)
                )
                continue

            # --- Italic/meta line (starts with *Author* or *Data*) ---
            if line.startswith("*") and line.endswith("*") and len(line) > 2:
                self._p(line[1:-1], "meta")
                i += 1
                continue

            # --- Empty line ---
            if not line.strip():
                self._spacer(1)
                i += 1
                continue

            # --- Regular paragraph ---
            # Accumulate continuation lines
            para_lines = [line]
            i += 1
            while i < len(lines) and lines[i].strip() and not lines[i].startswith("#") \
                    and not lines[i].startswith("```") and "|" not in lines[i] \
                    and not re.match(r"^[\-\*\+]\s+", lines[i]) \
                    and not re.match(r"^\d+\.\s+", lines[i]) \
                    and not re.match(r"^-{3,}\s*$", lines[i]):
                para_lines.append(lines[i])
                i += 1
            self._p(" ".join(para_lines), "body")

        return self.flowables

    def _build_table(self, raw_lines: list[str]):
        rows = []
        for line in raw_lines:
            if re.match(r"^\|?[\s\-|:]+\|?$", line):
                continue  # separator row
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            rows.append(cells)

        if not rows:
            return

        n_cols = max(len(r) for r in rows)
        for r in rows:
            while len(r) < n_cols:
                r.append("")

        col_w = CONTENT_W / n_cols
        table_data = []
        for ri, row in enumerate(rows):
            table_data.append(
                [Paragraph(inline_markup(c),
                           ParagraphStyle("tc", fontSize=9, leading=12,
                                          fontName="Arial-Bold" if ri == 0 else "Arial",
                                          textColor=colors.white if ri == 0 else colors.black))
                 for c in row]
            )

        ts = TableStyle([
            ("BACKGROUND",  (0, 0), (-1, 0),  TBL_HEAD),
            ("TEXTCOLOR",   (0, 0), (-1, 0),  colors.white),
            ("FONTNAME",    (0, 0), (-1, 0),  "Arial-Bold"),
            ("FONTSIZE",    (0, 0), (-1, -1), 9),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, TBL_ALT]),
            ("GRID",        (0, 0), (-1, -1), 0.4, RULE_CLR),
            ("VALIGN",      (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING",  (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ])

        tbl = Table(table_data, colWidths=[col_w] * n_cols, hAlign="LEFT")
        tbl.setStyle(ts)
        self.flowables.append(Spacer(1, 4 * mm))
        self.flowables.append(tbl)
        self.flowables.append(Spacer(1, 4 * mm))


def convert(md_path: str, pdf_path: str, title: str = ""):
    md_text = Path(md_path).read_text(encoding="utf-8")
    styles  = build_styles()
    builder = MDFlowableBuilder(styles)
    flowables = builder.build(md_text)

    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN,  bottomMargin=MARGIN,
        title=title or Path(md_path).stem,
    )
    doc.build(flowables)
    print(f"  OK  {pdf_path}")


if __name__ == "__main__":
    docs_dir = Path(__file__).parent

    targets = [
        (docs_dir / "architecture_notes.md",  docs_dir / "architecture_notes.pdf",  "Notatki architektoniczne — Eden Stack"),
        (docs_dir / "llm_rag_proposals.md",   docs_dir / "llm_rag_proposals.pdf",   "Propozycje LLM i RAG — Eden Stack"),
    ]

    for md, pdf, title in targets:
        if not md.exists():
            print(f"  POMINIĘTO (brak pliku): {md}")
            continue
        print(f"Konwertuję: {md.name}")
        convert(str(md), str(pdf), title)
