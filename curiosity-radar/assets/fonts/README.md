# Bundled font

`DejaVuSans.ttf` / `DejaVuSans-Bold.ttf`, from the [DejaVu Fonts](https://dejavu-fonts.github.io/)
project (Bitstream Vera License + public-domain additions — free to
redistribute). Bundled here, rather than relying on the runtime having a
Unicode-capable font installed, so `report`'s PDF output doesn't crash or
lose glyphs on non-Latin-script topics (SPEC.md §9 item 7's Ukrainian
example, or any accented/Cyrillic article title) regardless of what fonts
the eventual eval/grading machine has — both `report/fpdf2_renderer.py`
and `report/weasyprint_renderer.py`'s `template.html` reference these files
directly rather than a font family name that may or may not resolve.
