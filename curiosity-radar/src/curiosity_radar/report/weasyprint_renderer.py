"""HTML/CSS PDF renderer via WeasyPrint (SPEC.md §6): the best one-page
layout control, but depends on system Cairo/Pango/GDK-Pixbuf libraries not
installable via `uv` alone — `report/render.py`'s engine selection falls
back to `fpdf2_renderer.py` when this isn't usable at runtime.
"""

from __future__ import annotations

from html import escape
from pathlib import Path
from string import Template

from curiosity_radar.report.render import (
    LIMITATIONS,
    Claim,
    RenderOutcome,
    ReportContext,
    assumptions_text,
    build_claims,
    headline_text,
)

TEMPLATE_PATH = Path(__file__).parent / "template.html"
FONTS_DIR = Path(__file__).resolve().parents[3] / "assets" / "fonts"
FONT_REGULAR = FONTS_DIR / "DejaVuSans.ttf"
FONT_BOLD = FONTS_DIR / "DejaVuSans-Bold.ttf"


class WeasyPrintRenderer:
    name = "weasyprint"

    def render(self, context: ReportContext, out_path: Path) -> RenderOutcome:
        # Imported lazily so a missing/broken native install only breaks
        # this renderer, never module import for callers that never use it.
        from weasyprint import HTML

        claims = build_claims(context)
        body, sections = _build_body(context, claims)
        # A bundled Unicode font (SPEC.md §9 item 7), referenced by an
        # absolute file:// URL, rather than trusting the runtime to have a
        # Unicode-capable font installed under a matching family name.
        html = Template(TEMPLATE_PATH.read_text()).substitute(
            body=body,
            font_regular=FONT_REGULAR.as_uri(),
            font_bold=FONT_BOLD.as_uri(),
        )

        out_path.parent.mkdir(parents=True, exist_ok=True)
        HTML(string=html, base_url=str(TEMPLATE_PATH.parent)).write_pdf(str(out_path))

        return RenderOutcome(sections_rendered=sections, claims=claims)


def _build_body(context: ReportContext, claims: list[Claim]) -> tuple[str, list[str]]:
    sections = ["summary"]
    parts = [_header_html(context)]
    parts.append(f'<div class="headline">{escape(headline_text(context))}</div>')
    if context.audience_note:
        parts.append(f'<div class="audience-note">{escape(context.audience_note)}</div>')

    chart_paths = [c.path for c in context.charts.charts if c.kind == "trend"]
    if chart_paths:
        imgs = "".join(f'<img src="file://{escape(p)}">' for p in chart_paths)
        parts.append(f'<div class="charts">{imgs}</div>')
        sections.extend(f"trend_chart_{lang}" for lang in context.languages)

    claims_text = "\n".join(f"{c.label}: {c.value}" for c in claims)
    parts.append(f'<h2>Confidence &amp; data</h2><div class="claims">{escape(claims_text)}</div>')
    sections.append("confidence")

    if len(context.languages) > 1 and context.analysis.cross_language_ranking:
        rows = "".join(
            f"<div>{entry.rank}. {escape(entry.lang)} — {escape(entry.reason or '')}</div>"
            for entry in context.analysis.cross_language_ranking
        )
        parts.append(f'<h2>Cross-language ranking</h2><div class="ranking">{rows}</div>')
        sections.append("cross_language_ranking")

    parts.append(
        f'<h2>Assumptions</h2><div class="assumptions">{escape(assumptions_text(context))}</div>'
    )
    sections.append("assumptions")
    parts.append(
        f'<h2>Limitations</h2><div class="limitations">{escape(" ".join(LIMITATIONS))}</div>'
    )
    sections.append("limitations")
    sections.append("footer")

    return "\n".join(parts), sections


def _header_html(context: ReportContext) -> str:
    qid = context.state.qid or "(no QID)"
    langs = ", ".join(context.languages)
    lines = [
        f"<h1>curiosity-radar: {escape(context.topic_label)}</h1>",
        f'<div class="meta">QID: {escape(qid)} | Languages: {escape(langs)} | '
        f"Project: {escape(context.state.slug)}</div>",
        f'<div class="meta">Date range: {context.state.date_range_start} to '
        f"{context.state.date_range_end} | Generated: {context.generated_at}</div>",
    ]
    if context.truncated:
        lines.append(
            '<div class="truncation">Comparison truncated to top 4 languages by data quality.</div>'
        )
    return "\n".join(lines)
