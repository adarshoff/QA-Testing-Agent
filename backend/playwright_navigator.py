import asyncio
import base64
import time
import concurrent.futures
from typing import List, Dict, Any
from urllib.parse import urlparse
from playwright.async_api import async_playwright, Page, Response

from design_tokens import extract_page_tokens


VIEWPORTS = [
    {"name": "desktop", "width": 1280, "height": 800},
    {"name": "mobile",  "width": 375,  "height": 812},
]

MAX_PAGES = 10000   # Restriction essentially removed per user request


def _same_domain(url: str, base: str) -> bool:
    try:
        base_host = urlparse(base).netloc.lstrip("www.")
        link_host = urlparse(url).netloc.lstrip("www.")
        return link_host == base_host or link_host.endswith("." + base_host)
    except Exception:
        return False


def _page_label(url: str, base: str) -> str:
    try:
        path = urlparse(url).path.strip("/")
        return path if path else "Home"
    except Exception:
        return url


async def _collect_links(page: Page, base_url: str, visited: set) -> List[str]:
    try:
        links = await page.eval_on_selector_all(
            "a[href]",
            "els => els.map(e => e.href)"
        )
    except Exception:
        return []
    result = []
    seen = set()
    for link in links:
        link = link.split("#")[0].split("?")[0].rstrip("/")
        if (
            link
            and link not in seen
            and link not in visited
            and _same_domain(link, base_url)
            and link != base_url.rstrip("/")
            and not link.endswith((".pdf", ".zip", ".png", ".jpg", ".svg", ".css", ".js"))
        ):
            seen.add(link)
            result.append(link)
    return result[:8]


async def _screenshot_b64(page: Page) -> str:
    raw = await page.screenshot(full_page=True, type="png")
    return base64.b64encode(raw).decode()


async def _run_axe_on_page(page: Page) -> List[Dict]:
    """Inject axe-core and collect WCAG violations from an already-open page."""
    try:
        await page.add_script_tag(
            url="https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.9.0/axe.min.js"
        )
        results = await page.evaluate(
            "async () => { const r = await axe.run({ runOnly: ['wcag2a', 'wcag2aa'] }); return r; }",
        )
        violations = []
        for violation in results.get("violations", []):
            for node in violation.get("nodes", []):
                violations.append({
                    "id": violation["id"],
                    "impact": violation["impact"],
                    "description": violation["description"],
                    "help": violation["help"],
                    "helpUrl": violation["helpUrl"],
                    "html": node.get("html", "")[:200],
                })
        return violations
    except Exception as e:
        print(f"axe-core error: {e}")
        return []


async def _run_security_on_page(page: Page, url: str) -> List[Dict]:
    """Discover input fields and run shallow security checks on an already-open page."""
    XSS_PAYLOAD = "<script>alert(1)</script>"
    SQLI_PAYLOAD = "' OR 1=1--"
    issues = []
    try:
        inputs = await page.locator(
            "input[type='text'], input[type='email'], input[type='search'], input[type='password'], textarea"
        ).all()
        for i, el in enumerate(inputs[:3]):
            try:
                is_visible = await el.is_visible(timeout=1000)
                if not is_visible:
                    continue
                name = await el.get_attribute("name") or await el.get_attribute("id") or f"input_{i}"
                input_type = await el.get_attribute("type") or "text"
                # Fill with a test payload to simply confirm the field is reachable
                await el.fill(SQLI_PAYLOAD if input_type == "password" else XSS_PAYLOAD, timeout=2000)
                issues.append({
                    "type": "input_discovered",
                    "severity": "info",
                    "description": f"Input field '{name}' (type='{input_type}') accepts arbitrary text input — candidate for security testing.",
                    "url": url,
                })
                # Clear so we don't break the page
                await el.fill("", timeout=2000)
            except Exception:
                continue
    except Exception as e:
        print(f"Security scan error: {e}")
    return issues


async def navigate_and_capture(url: str) -> Dict[str, Any]:
    screenshots = []
    network_log = []
    pages_visited = []
    performance_metrics = {}
    console_errors = []
    dom_a11y_bugs = []
    security_bugs = []
    page_tokens = []

    async with async_playwright() as p:
        import shutil
        chromium_path = shutil.which("chromium") or shutil.which("chromium-browser")
        launch_opts = {
            "headless": True,
            "args": [
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-setuid-sandbox",
            ],
        }
        if chromium_path:
            launch_opts["executable_path"] = chromium_path

        browser = await p.chromium.launch(**launch_opts)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
        )
        page = await context.new_page()

        # ── Network interception ──────────────────────────────────────────
        async def on_response(response: Response):
            try:
                timing = response.request.timing
                start = timing.get("requestStart", 0) if timing else 0
                end   = timing.get("responseEnd",   0) if timing else 0
                elapsed = max(0.0, end - start)
                network_log.append({
                    "url":              response.url,
                    "method":           response.request.method,
                    "status":           response.status,
                    "response_time_ms": round(elapsed, 2),
                    "resource_type":    response.request.resource_type,
                    "is_error":         response.status >= 400,
                })
            except Exception:
                pass

        page.on("response", on_response)

        # ── Console / JS error capture ────────────────────────────────────
        async def on_console(msg):
            if msg.type in ("error", "warning"):
                text = msg.text
                # Skip noisy browser-internal messages
                if any(skip in text for skip in ("favicon", "fonts.googleapis", "ERR_BLOCKED_BY_CLIENT")):
                    return
                console_errors.append({
                    "type":  msg.type,
                    "text":  text[:300],
                    "source": "console",
                })

        async def on_page_error(error):
            console_errors.append({
                "type":   "page_error",
                "text":   str(error)[:300],
                "source": "uncaught_exception",
            })

        page.on("console",   on_console)
        page.on("pageerror", on_page_error)

        # ── Navigate to starting URL ──────────────────────────────────────
        t0 = time.time()
        try:
            await page.goto(url, wait_until="networkidle", timeout=20000)
        except Exception:
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=12000)
            except Exception as e:
                await browser.close()
                return {
                    "screenshots": [], "network_issues": [], "pages_visited": [],
                    "performance_metrics": {}, "raw_network_log": [],
                    "console_errors": [], "dom_a11y_bugs": [], "security_bugs": [],
                    "page_tokens": [],
                    "error": str(e),
                }
        load_time = round((time.time() - t0) * 1000, 2)
        performance_metrics["initial_load_ms"] = load_time

        await page.wait_for_timeout(800)

        # ── Run a11y + security + design tokens on home page (same session) ──
        dom_a11y_bugs = await _run_axe_on_page(page)
        security_bugs = await _run_security_on_page(page, url)
        page_tokens.append(await extract_page_tokens(page, url, "Home"))

        # ── Home page: desktop + mobile ───────────────────────────────────
        for vp in VIEWPORTS:
            await page.set_viewport_size({"width": vp["width"], "height": vp["height"]})
            if vp["name"] != "desktop":
                await page.wait_for_timeout(200)
            shot = await _screenshot_b64(page)
            screenshots.append({
                "url":       url,
                "viewport":  vp["name"],
                "screenshot": shot,
                "label":     f"Home — {vp['name'].capitalize()}",
            })

        pages_visited.append(url)
        await page.set_viewport_size({"width": 1280, "height": 800})

        # ── BFS crawl sub-pages (desktop only) ───────────────────────────
        visited_set = {url.rstrip("/")}
        queue = await _collect_links(page, url, visited_set)

        while queue and len(pages_visited) < MAX_PAGES:
            link = queue.pop(0)
            normalized = link.rstrip("/")
            if normalized in visited_set:
                continue
            visited_set.add(normalized)
            try:
                await page.goto(link, wait_until="domcontentloaded", timeout=10000)
                await page.wait_for_timeout(400)
                shot = await _screenshot_b64(page)
                label = _page_label(link, url)
                screenshots.append({
                    "url":        link,
                    "viewport":   "desktop",
                    "screenshot":  shot,
                    "label":      label,
                })
                pages_visited.append(link)
                page_tokens.append(await extract_page_tokens(page, link, label))

                if len(pages_visited) < MAX_PAGES:
                    deeper = await _collect_links(page, url, visited_set)
                    queue.extend(deeper[:2])
            except Exception:
                pass

        await browser.close()

    # ── Build network issue list ──────────────────────────────────────────
    api_errors = [
        n for n in network_log
        if n["is_error"] and n["resource_type"] in ("fetch", "xhr", "document")
    ]
    slow_apis = [
        n for n in network_log
        if n["response_time_ms"] > 2000 and n["resource_type"] in ("fetch", "xhr")
    ]
    cors_errors = [
        n for n in network_log
        if n.get("status") == 0 and n.get("resource_type") in ("fetch", "xhr")
    ]

    network_issues = []
    seen_urls: set = set()

    for e in api_errors[:10]:
        if e["url"] not in seen_urls:
            seen_urls.add(e["url"])
            network_issues.append({
                "type":        "api_error",
                "severity":    "critical" if e["status"] >= 500 else "serious",
                "url":         e["url"],
                "method":      e["method"],
                "status_code": e["status"],
                "description": f"{e['method']} {e['url']} returned HTTP {e['status']}",
                "fix": f"Investigate server endpoint returning HTTP {e['status']}. Check server logs and ensure the API contract is correct.",
            })

    for s in slow_apis[:5]:
        network_issues.append({
            "type":              "slow_api",
            "severity":          "moderate",
            "url":               s["url"],
            "method":            s["method"],
            "response_time_ms":  s["response_time_ms"],
            "description":       f"{s['method']} {s['url']} took {s['response_time_ms']}ms (target <500ms)",
            "fix": "Add server-side caching, optimise DB queries, or paginate large responses.",
        })

    for c in cors_errors[:5]:
        if c["url"] not in seen_urls:
            seen_urls.add(c["url"])
            network_issues.append({
                "type":        "cors_error",
                "severity":    "critical",
                "url":         c["url"],
                "method":      c["method"],
                "status_code": 0,
                "description": f"CORS/Network failure on {c['method']} {c['url']} (status 0 — blocked or no response)",
                "fix": "Add the correct Access-Control-Allow-Origin header on the server, or check the endpoint is reachable.",
            })

    # JS console errors → network issues so they surface in the report
    js_err_seen: set = set()
    for err in console_errors[:8]:
        key = err["text"][:80]
        if key not in js_err_seen:
            js_err_seen.add(key)
            is_page_err = err.get("source") == "uncaught_exception"
            network_issues.append({
                "type":        "js_error" if not is_page_err else "uncaught_exception",
                "severity":    "serious" if is_page_err else "moderate",
                "url":         url,
                "description": err["text"],
                "fix": "Open browser DevTools → Console to see the full stack trace and fix the underlying JavaScript error.",
            })

    performance_metrics["pages_scanned"]      = len(pages_visited)
    performance_metrics["total_requests"]     = len(network_log)
    performance_metrics["error_count"]        = len(api_errors)
    performance_metrics["slow_request_count"] = len(slow_apis)
    performance_metrics["js_error_count"]     = len(console_errors)
    performance_metrics["cors_error_count"]   = len(cors_errors)

    return {
        "screenshots":       screenshots,
        "network_issues":    network_issues,
        "pages_visited":     pages_visited,
        "performance_metrics": performance_metrics,
        "raw_network_log":   network_log[:50],
        "console_errors":    console_errors,
        "dom_a11y_bugs":     dom_a11y_bugs,
        "security_bugs":     security_bugs,
        "page_tokens":       page_tokens,
    }


def run_navigation(url: str) -> Dict[str, Any]:
    def _run():
        return asyncio.run(navigate_and_capture(url))
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(_run)
        return future.result(timeout=120)
