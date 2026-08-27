"""
Offline, reproducible proof that Design Intelligence detects real design-token
drift across pages -- no GEMINI_API_KEY or network access needed, everything
runs against local file:// HTML fixtures via headless Chromium.

Run with:
  cd backend && pytest test_design_intelligence.py -v
"""
import asyncio
import pytest
from playwright.async_api import async_playwright

from design_tokens import extract_page_tokens
from design_intelligence import aggregate_tokens, find_inconsistencies, compute_consistency_score

PAGE_A = """<!DOCTYPE html>
<html><body>
  <h1 style="font-family: Arial; font-size: 32px;">Welcome</h1>
  <button style="background-color: rgb(26, 115, 232); color: white;">Get Started</button>
</body></html>"""

# Near-identical blue (drift, not a deliberate variant) and a different h1 font.
PAGE_B = """<!DOCTYPE html>
<html><body>
  <h1 style="font-family: Georgia; font-size: 32px;">Pricing</h1>
  <button style="background-color: rgb(25, 118, 210); color: white;">Get Started</button>
</body></html>"""

PAGE_C_CONSISTENT = """<!DOCTYPE html>
<html><body>
  <h1 style="font-family: Arial; font-size: 32px;">Contact</h1>
  <button style="background-color: rgb(26, 115, 232); color: white;">Get Started</button>
</body></html>"""


def _write(tmp_path, name, content):
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return path.as_uri()


async def _extract(url, label):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        page = await browser.new_page()
        await page.goto(url)
        tokens = await extract_page_tokens(page, url, label)
        await browser.close()
        return tokens


def _extract_sync(url, label):
    return asyncio.run(_extract(url, label))


class TestDesignIntelligence:
    def test_extract_page_tokens_reads_real_computed_styles(self, tmp_path):
        url = _write(tmp_path, "a.html", PAGE_A)
        tokens = _extract_sync(url, "Page A")

        assert tokens["url"] == url
        assert tokens["label"] == "Page A"
        assert len(tokens["buttons"]) == 1
        assert tokens["buttons"][0]["backgroundColor"] == "rgb(26, 115, 232)"
        assert len(tokens["headings"]) == 1
        assert tokens["headings"][0]["tag"] == "h1"

    def test_detects_near_identical_color_drift_across_pages(self, tmp_path):
        url_a = _write(tmp_path, "a.html", PAGE_A)
        url_b = _write(tmp_path, "b.html", PAGE_B)

        tokens_a = _extract_sync(url_a, "Home")
        tokens_b = _extract_sync(url_b, "Pricing")

        aggregated = aggregate_tokens([tokens_a, tokens_b])
        inconsistencies = find_inconsistencies(aggregated)

        color_findings = [f for f in inconsistencies if f["token_type"] == "color"]
        assert len(color_findings) == 1
        values = {v["value"] for v in color_findings[0]["values_found"]}
        assert values == {"rgb(26, 115, 232)", "rgb(25, 118, 210)"}
        sources = {s for v in color_findings[0]["values_found"] for s in v["sources"]}
        assert sources == {"Home", "Pricing"}

        font_findings = [f for f in inconsistencies if f["token_type"] == "font-family"]
        assert len(font_findings) == 1
        assert font_findings[0]["component"] == "h1"

        score = compute_consistency_score(inconsistencies)
        assert score < 100

    def test_consistent_pages_produce_zero_inconsistencies_and_full_score(self, tmp_path):
        url_a = _write(tmp_path, "a.html", PAGE_A)
        url_c = _write(tmp_path, "c.html", PAGE_C_CONSISTENT)

        tokens_a = _extract_sync(url_a, "Home")
        tokens_c = _extract_sync(url_c, "Contact")

        aggregated = aggregate_tokens([tokens_a, tokens_c])
        inconsistencies = find_inconsistencies(aggregated)

        assert inconsistencies == []
        assert compute_consistency_score(inconsistencies) == 100
