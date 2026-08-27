import asyncio
from typing import Dict, Any, List, Optional
from playwright.async_api import Page, async_playwright

from self_healing import LocatorDescriptor, build_descriptor, locate_with_fallback
from memory import get_fingerprints, save_fingerprints

INPUT_SELECTOR = (
    "input[type='text'], input[type='email'], input[type='search'], "
    "input[type='tel'], input[type='number'], input:not([type]), textarea"
)
SUBMIT_SELECTOR = (
    "button[type='submit'], input[type='submit'], "
    "button:has-text('Submit'), button:has-text('Sign up'), "
    "button:has-text('Send'), button:has-text('Continue')"
)
SAMPLE_VALUES = {
    "email": "qa-agent-test@example.com",
    "tel": "555-0100",
    "number": "1",
    "default": "QA Agent Test",
}


def _css_for_element(el_id: Optional[str], name_attr: Optional[str], fallback_selector: str, index: int) -> str:
    if el_id:
        return f"#{el_id}"
    if name_attr:
        return f"[name='{name_attr}']"
    return f"{fallback_selector} >> nth={index}"


class FunctionalQAAgent:
    def __init__(self, url: str):
        self.url = url
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.logs = []

    async def start(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"]
        )
        self.context = await self.browser.new_context(
            viewport={"width": 1280, "height": 800}
        )
        self.page = await self.context.new_page()

        # Capture console logs, preserving their real severity (log/warning/error)
        self.page.on("console", lambda msg: self.logs.append({"type": msg.type, "text": msg.text}))

        await self.page.goto(self.url, wait_until="networkidle")

    async def stop(self):
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    async def get_page_text(self) -> str:
        """Helper to get text content for the LLM to read."""
        if not self.page:
            return ""
        try:
            return await self.page.evaluate("document.body.innerText")
        except Exception:
            return ""

    async def run_auto_discovery(self, fingerprints: Dict[str, LocatorDescriptor]):
        """
        Fill visible form fields and click the page's primary submit/CTA button,
        self-healing through remembered locators when the DOM has drifted since
        the last scan of this URL.

        Returns (steps, updated_fingerprints, healing_events).
        """
        steps: List[Dict[str, Any]] = []
        healing_events: List[Dict[str, Any]] = []
        updated_fingerprints: Dict[str, LocatorDescriptor] = dict(fingerprints)

        raw_inputs = await self.page.locator(INPUT_SELECTOR).all()
        visible_inputs = []
        for el in raw_inputs[:8]:
            try:
                if await el.is_visible():
                    visible_inputs.append(el)
            except Exception:
                continue
            if len(visible_inputs) >= 5:
                break

        for index, el in enumerate(visible_inputs):
            field_key = f"field_{index}"
            try:
                input_type = (await el.get_attribute("type") or "text").lower()
                name_attr = await el.get_attribute("name")
                placeholder = await el.get_attribute("placeholder")
                el_id = await el.get_attribute("id")
            except Exception:
                input_type, name_attr, placeholder, el_id = "text", None, None, None

            label_text = placeholder or name_attr or f"field {index}"
            descriptor = fingerprints.get(field_key)
            if not descriptor:
                css = _css_for_element(el_id, name_attr, INPUT_SELECTOR, index)
                descriptor = build_descriptor(css, role="textbox", label=label_text, input_type=input_type, index=index)

            heal = await locate_with_fallback(self.page, descriptor)
            if heal["locator"] is None:
                steps.append({
                    "success": False,
                    "action_attempted": f"Fill field '{label_text}'",
                    "element_selector": descriptor.get("value") or label_text,
                    "description": "Could not locate this field via CSS, role, placeholder, label, or positional match.",
                    "healed": False,
                })
                continue

            value = SAMPLE_VALUES.get(input_type, SAMPLE_VALUES["default"])
            try:
                await heal["locator"].fill(value, timeout=3000)
                steps.append({
                    "success": True,
                    "action_attempted": f"Filled '{label_text}'",
                    "element_selector": descriptor.get("value") or label_text,
                    "description": f"Filled via {heal['strategy_used']} strategy.",
                    "healed": heal["healed"],
                    "heal_strategy": heal["strategy_used"] if heal["healed"] else None,
                })
                if heal["healed"]:
                    healing_events.append({
                        "field_key": field_key,
                        "label": label_text,
                        "original_strategy": descriptor.get("strategy"),
                        "healed_strategy": heal["strategy_used"],
                        "description": f"'{label_text}' could not be found the usual way — recovered via {heal['strategy_used']} match.",
                    })
                updated_fingerprints[field_key] = heal["descriptor"]
            except Exception as e:
                steps.append({
                    "success": False,
                    "action_attempted": f"Fill field '{label_text}'",
                    "element_selector": descriptor.get("value") or label_text,
                    "description": str(e),
                    "healed": heal["healed"],
                })

        # Primary submit / CTA button
        field_key = "submit_button"
        descriptor = fingerprints.get(field_key) or build_descriptor(SUBMIT_SELECTOR, role="button", index=0)
        heal = await locate_with_fallback(self.page, descriptor)
        if heal["locator"] is not None:
            try:
                # Capture a durable accessible name so future runs can heal via role+text
                # even if this element's id/class attributes change.
                btn_text = (await heal["locator"].first.text_content() or "").strip()
                btn_id = await heal["locator"].first.get_attribute("id")
                final_descriptor = {
                    **heal["descriptor"],
                    "label": btn_text or heal["descriptor"].get("label"),
                    # Pin down a specific selector for next time instead of persisting the
                    # generic multi-clause SUBMIT_SELECTOR, so a real id/class change on the
                    # next scan actually exercises the fallback chain rather than trivially
                    # matching one of SUBMIT_SELECTOR's own OR clauses again.
                    **({"strategy": "css", "value": f"#{btn_id}"} if btn_id else {}),
                }

                await heal["locator"].click(timeout=3000)
                await self.page.wait_for_load_state("networkidle", timeout=5000)
                steps.append({
                    "success": True,
                    "action_attempted": "Clicked primary submit/CTA button",
                    "element_selector": descriptor.get("value") or "submit",
                    "description": f"Clicked via {heal['strategy_used']} strategy.",
                    "healed": heal["healed"],
                    "heal_strategy": heal["strategy_used"] if heal["healed"] else None,
                })
                if heal["healed"]:
                    healing_events.append({
                        "field_key": field_key,
                        "label": btn_text or "submit button",
                        "original_strategy": descriptor.get("strategy"),
                        "healed_strategy": heal["strategy_used"],
                        "description": f"Submit button could not be found the usual way — recovered via {heal['strategy_used']} match.",
                    })
                updated_fingerprints[field_key] = final_descriptor
            except Exception as e:
                steps.append({
                    "success": False,
                    "action_attempted": "Click primary submit/CTA button",
                    "element_selector": descriptor.get("value") or "submit",
                    "description": str(e),
                    "healed": heal["healed"],
                })

        return steps, updated_fingerprints, healing_events


def _steps_to_bugs(steps: List[Dict[str, Any]], url: str) -> List[Dict[str, Any]]:
    bugs = []
    for i, step in enumerate(steps):
        if not step.get("success"):
            bugs.append({
                "bug_id": f"FUNC_{i + 1}",
                "category": "Functional",
                "severity": "serious",
                "description": step.get("description", "Action failed"),
                "action_attempted": step.get("action_attempted", ""),
                "element_selector": step.get("element_selector", ""),
                "healed": step.get("healed", False),
                "url": url,
            })
    return bugs


def _console_errors_to_bugs(logs: List[Dict[str, Any]], url: str) -> List[Dict[str, Any]]:
    bugs = []
    for i, log in enumerate(logs):
        if log.get("type") == "error":
            bugs.append({
                "bug_id": f"FUNC_CONSOLE_{i + 1}",
                "category": "Functional",
                "severity": "moderate",
                "description": f"Console error during interaction: {log.get('text', '')}",
                "action_attempted": "Console monitoring",
                "element_selector": "",
                "healed": False,
                "url": url,
            })
    return bugs


def run_functional_test(url: str, instruction: Optional[str] = None) -> Dict[str, Any]:
    """
    Fills visible form fields with sample data, tries the page's primary
    submit/CTA button — self-healing through remembered element locators when
    the DOM has drifted since the last scan — and reports failed interactions
    plus any console errors as functional bugs.
    """
    async def _run():
        agent = FunctionalQAAgent(url)
        try:
            await agent.start()
            fingerprints = get_fingerprints(url)
            steps, updated_fingerprints, healing_events = await agent.run_auto_discovery(fingerprints)
            save_fingerprints(url, updated_fingerprints)
            bugs = _steps_to_bugs(steps, url) + _console_errors_to_bugs(agent.logs, url)
            return {
                "success": True,
                "steps": steps,
                "logs": agent.logs,
                "bugs": bugs,
                "healing_events": healing_events,
            }
        finally:
            await agent.stop()

    try:
        return asyncio.run(_run())
    except Exception as e:
        return {"success": False, "error": str(e), "steps": [], "logs": [], "bugs": [], "healing_events": []}
