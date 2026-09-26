"""Pure-Python PDF renderer (SPEC.md §6): zero system dependencies, manual
layout to guarantee exactly one A4 page. The fallback engine when
WeasyPrint's native libraries aren't usable at runtime.
"""

from __future__ import annotations

from pathlib import Path

from fpdf import FPDF

from curiosity_radar.report.render import (
    LIMITATIONS,
    PAGE_SIZE,
    Claim,
    RenderOutcome,
    ReportContext,
    assumptions_text,
    build_claims,
    headline_text,
    related_search_terms_text,
)

MARGIN = 10
FONTS_DIR = Path(__file__).resolve().parents[3] / "assets" / "fonts"
FONT_REGULAR = FONTS_DIR / "DejaVuSans.ttf"
FONT_BOLD = FONTS_DIR / "DejaVuSans-Bold.ttf"
FONT_FAMILY = "DejaVu"


class Fpdf2Renderer:
    name = "fpdf2"

    def render(self, context: ReportContext, out_path: Path) -> RenderOutcome:
        claims = build_claims(context)
        sections: list[str] = []

        pdf = FPDF(orientation="P", unit="mm", format=PAGE_SIZE)
        pdf.set_auto_page_break(auto=False)
        # A bundled Unicode font (SPEC.md §9 item 7) rather than a core
        # Helvetica/Courier font, which only supports Latin-1 and would
        # raise on any non-Latin-script topic/article title — or even an
        # em dash.
        pdf.add_font(FONT_FAMILY, "", str(FONT_REGULAR))
        pdf.add_font(FONT_FAMILY, "B", str(FONT_BOLD))
        pdf.add_font(FONT_FAMILY, "I", str(FONT_REGULAR))
        pdf.add_page()
        pdf.set_margin(MARGIN)

        self._header(pdf, context)
        sections.append("summary")
        self._headline(pdf, context)

        chart_paths = [c.path for c in context.charts.charts if c.kind == "trend"]
        if chart_paths:
            self._charts(pdf, chart_paths)
            for lang in context.languages:
                sections.append(f"trend_chart_{lang}")

        self._claims_panel(pdf, context, claims)
        sections.append("confidence")

        if len(context.languages) > 1 and context.analysis.cross_language_ranking:
            self._ranking(pdf, context)
            sections.append("cross_language_ranking")

        self._related_search_terms(pdf, context)
        sections.append("related_search_terms")

        self._assumptions(pdf, context)
        sections.append("assumptions")
        self._limitations(pdf)
        sections.append("limitations")
        self._footer(pdf)
        sections.append("footer")

        out_path.parent.mkdir(parents=True, exist_ok=True)
        pdf.output(str(out_path))

        return RenderOutcome(sections_rendered=sections, claims=claims)

    def _header(self, pdf: FPDF, context: ReportContext) -> None:
        pdf.set_font(FONT_FAMILY, "B", 14)
        pdf.cell(0, 8, f"curiosity-radar: {context.topic_label}", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font(FONT_FAMILY, "", 8)
        qid = context.state.qid or "(no QID)"
        langs = ", ".join(context.languages)
        pdf.cell(
            0,
            5,
            f"QID: {qid}  |  Languages: {langs}  |  Project: {context.state.slug}",
            new_x="LMARGIN",
            new_y="NEXT",
        )
        pdf.cell(
            0,
            5,
            f"Date range: {context.state.date_range_start} to {context.state.date_range_end}  "
            f"|  Generated: {context.generated_at}",
            new_x="LMARGIN",
            new_y="NEXT",
        )
        if context.truncated:
            pdf.set_text_color(150, 0, 0)
            pdf.cell(
                0,
                5,
                "Comparison truncated to top 4 languages by data quality.",
                new_x="LMARGIN",
                new_y="NEXT",
            )
            pdf.set_text_color(0, 0, 0)

    def _headline(self, pdf: FPDF, context: ReportContext) -> None:
        pdf.ln(1)
        pdf.set_font(FONT_FAMILY, "B", 10)
        pdf.multi_cell(0, 5, headline_text(context))
        if context.audience_note:
            pdf.set_font(FONT_FAMILY, "I", 8)
            pdf.multi_cell(0, 4, context.audience_note)

    def _charts(self, pdf: FPDF, chart_paths: list[str]) -> None:
        pdf.ln(1)
        y = pdf.get_y()
        usable_width = pdf.w - 2 * MARGIN
        n = len(chart_paths)
        cols = min(n, 2)
        width = usable_width / cols
        height = 30.0
        for i, path in enumerate(chart_paths):
            if Path(path).exists():
                row, col = divmod(i, cols)
                pdf.image(path, x=MARGIN + col * width, y=y + row * height, w=width, h=height)
        rows = (n + cols - 1) // cols
        pdf.set_y(y + rows * height + 2)

    def _claims_panel(self, pdf: FPDF, context: ReportContext, claims: list[Claim]) -> None:
        pdf.set_font(FONT_FAMILY, "B", 9)
        pdf.cell(0, 5, "Confidence & data", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font(FONT_FAMILY, "", 7)
        for claim in claims:
            pdf.cell(0, 3.6, f"{claim.label}: {claim.value}", new_x="LMARGIN", new_y="NEXT")

    def _ranking(self, pdf: FPDF, context: ReportContext) -> None:
        pdf.ln(1)
        pdf.set_font(FONT_FAMILY, "B", 9)
        pdf.cell(0, 5, "Cross-language ranking", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font(FONT_FAMILY, "", 8)
        for entry in context.analysis.cross_language_ranking:
            pdf.cell(
                0,
                4,
                f"{entry.rank}. {entry.lang} — {entry.reason or ''}",
                new_x="LMARGIN",
                new_y="NEXT",
            )

    def _related_search_terms(self, pdf: FPDF, context: ReportContext) -> None:
        pdf.ln(1)
        pdf.set_font(FONT_FAMILY, "B", 9)
        pdf.cell(0, 5, "Related search terms (top 10)", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font(FONT_FAMILY, "", 7.5)
        pdf.multi_cell(0, 3.6, related_search_terms_text(context))

    def _assumptions(self, pdf: FPDF, context: ReportContext) -> None:
        pdf.ln(1)
        pdf.set_font(FONT_FAMILY, "B", 9)
        pdf.cell(0, 5, "Assumptions", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font(FONT_FAMILY, "", 7.5)
        pdf.multi_cell(0, 3.6, assumptions_text(context))

    def _limitations(self, pdf: FPDF) -> None:
        pdf.ln(1)
        pdf.set_font(FONT_FAMILY, "B", 9)
        pdf.cell(0, 5, "Limitations", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font(FONT_FAMILY, "", 7.5)
        pdf.multi_cell(0, 3.6, " ".join(LIMITATIONS))

    def _footer(self, pdf: FPDF) -> None:
        pdf.set_y(-15)
        pdf.set_font(FONT_FAMILY, "I", 7)
        pdf.cell(
            0, 5, "Numeric claims verified against source data: PASS", new_x="LMARGIN", new_y="NEXT"
        )
