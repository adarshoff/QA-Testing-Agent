"""
Self-healing element location.

Instead of a single brittle CSS selector that either matches or doesn't,
every interactive element is represented as a LocatorDescriptor — a small,
structured hint about *how it was last found*. `locate_with_fallback` tries
that hint first; if the DOM has changed enough that it no longer resolves,
it walks a chain of more resilient strategies (accessible role+name,
placeholder, label, positional match by input type) to find the same
logical element again. Whichever strategy succeeds becomes the new
descriptor, so the next run starts from the strategy that actually worked.
"""
from typing import Optional, TypedDict
from playwright.async_api import Page, Locator


class LocatorDescriptor(TypedDict, total=False):
    strategy: str                # "css" | "role" | "placeholder" | "label" | "type_index"
    value: str                   # CSS selector, only meaningful for strategy == "css"
    label: Optional[str]         # accessible name / placeholder / label text
    role: Optional[str]          # ARIA role, for strategy == "role"
    input_type: Optional[str]    # e.g. "email", "text" — for strategy == "type_index"
    index: Optional[int]         # ordinal among same-type elements, for strategy == "type_index"


class HealResult(TypedDict):
    locator: Optional[Locator]
    healed: bool
    strategy_used: Optional[str]
    descriptor: Optional[LocatorDescriptor]


async def _try_visible(locator: Locator, timeout: int = 1500) -> bool:
    try:
        await locator.first.wait_for(state="visible", timeout=timeout)
        return True
    except Exception:
        return False


async def _by_strategy(page: Page, descriptor: LocatorDescriptor) -> Optional[Locator]:
    strategy = descriptor.get("strategy")
    label = descriptor.get("label") or ""

    if strategy == "css":
        css = descriptor.get("value") or ""
        if not css:
            return None
        loc = page.locator(css)
    elif strategy == "role":
        if not label:
            return None
        loc = page.get_by_role(descriptor.get("role") or "textbox", name=label)
    elif strategy == "placeholder":
        if not label:
            return None
        loc = page.get_by_placeholder(label)
    elif strategy == "label":
        if not label:
            return None
        loc = page.get_by_label(label)
    elif strategy == "type_index":
        input_type = descriptor.get("input_type") or "text"
        index = descriptor.get("index") or 0
        loc = page.locator(f"input[type='{input_type}'], textarea").nth(index)
    else:
        return None

    if await _try_visible(loc):
        return loc
    return None


FALLBACK_CHAIN = ["role", "placeholder", "label", "type_index"]


async def locate_with_fallback(page: Page, descriptor: LocatorDescriptor) -> HealResult:
    """Try the descriptor's own strategy first; on failure, walk the fallback chain."""
    primary = await _by_strategy(page, descriptor)
    if primary is not None:
        return {
            "locator": primary,
            "healed": False,
            "strategy_used": descriptor.get("strategy"),
            "descriptor": descriptor,
        }

    for strategy in FALLBACK_CHAIN:
        if strategy == descriptor.get("strategy"):
            continue
        candidate: LocatorDescriptor = {**descriptor, "strategy": strategy}
        loc = await _by_strategy(page, candidate)
        if loc is not None:
            return {
                "locator": loc,
                "healed": True,
                "strategy_used": strategy,
                "descriptor": candidate,
            }

    return {"locator": None, "healed": False, "strategy_used": None, "descriptor": None}


def build_descriptor(
    css_selector: str,
    role: Optional[str] = None,
    label: Optional[str] = None,
    input_type: Optional[str] = None,
    index: int = 0,
) -> LocatorDescriptor:
    """Build the initial descriptor for a freshly-discovered element (before any healing)."""
    return {
        "strategy": "css",
        "value": css_selector,
        "label": label,
        "role": role,
        "input_type": input_type,
        "index": index,
    }
