"""
Design token extraction.

Unlike the Gemini-vision Figma diff (which looks at one screenshot and guesses
at design intent from pixels), this reads real `getComputedStyle` values
straight out of the DOM for every page the navigator visits. It's the raw
material design_intelligence.py uses to detect design-system drift across a
whole site — the same logical component (e.g. "primary button") rendered
with different colors or font sizes on different pages.
"""
from typing import Any, Dict
from playwright.async_api import Page

TOKEN_EXTRACTION_JS = """
() => {
  function pick(el) {
    const cs = window.getComputedStyle(el);
    return {
      tag: el.tagName.toLowerCase(),
      color: cs.color,
      backgroundColor: cs.backgroundColor,
      fontFamily: cs.fontFamily,
      fontSize: cs.fontSize,
      fontWeight: cs.fontWeight,
      borderRadius: cs.borderRadius,
    };
  }
  function sample(selector, limit) {
    return Array.from(document.querySelectorAll(selector))
      .filter(el => el.offsetParent !== null)
      .slice(0, limit)
      .map(pick);
  }
  return {
    buttons: sample("button, a.btn, [role='button'], input[type='submit'], input[type='button']", 15),
    headings: sample("h1, h2, h3, h4, h5, h6", 15),
    body_text: sample("p, li", 15),
  };
}
"""


async def extract_page_tokens(page: Page, url: str, label: str = "") -> Dict[str, Any]:
    """Pull computed-style samples for buttons/headings/body text from the current page."""
    try:
        raw = await page.evaluate(TOKEN_EXTRACTION_JS)
    except Exception as e:
        print(f"Design token extraction error: {e}")
        raw = {"buttons": [], "headings": [], "body_text": []}
    return {"url": url, "label": label, **raw}
