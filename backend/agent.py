import asyncio
import uuid
import nest_asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional, TypedDict
from langgraph.graph import StateGraph, END
from playwright_navigator import run_navigation
from visual_qa import analyze_all_screenshots
from figma_compare import compare_with_figma
from design_intelligence import aggregate_tokens, find_inconsistencies, compute_consistency_score
from memory import save_scan, get_previous_scan, init_db

# Allow nested asyncio loops for synchronous LangGraph wrapping
nest_asyncio.apply()

# Initialize DB to prevent missing table errors
init_db()


class AgentState(TypedDict):
    scan_id: str
    user_id: str
    url: str
    figma_b64: Optional[str]
    screenshots: List[Dict]
    network_issues: List[Dict]
    console_errors: List[Dict]
    pages_visited: List[str]
    performance_metrics: Dict
    visual_results: List[Dict]
    all_bugs: List[Dict]
    functional_bugs: List[Dict]
    dom_a11y_bugs: List[Dict]
    security_bugs: List[Dict]
    figma_deviations: List[Dict]
    fixes: List[Dict]
    new_bugs: List[Dict]
    quality_score: int
    figma_match_score: int
    healing_events: List[Dict]
    page_tokens: List[Dict]
    design_tokens: Dict
    design_inconsistencies: List[Dict]
    design_consistency_score: int
    status: str
    error: Optional[str]


def observe_node(state: AgentState) -> AgentState:
    state["scan_id"] = str(uuid.uuid4())
    state["screenshots"] = []
    state["network_issues"] = []
    state["console_errors"] = []
    state["pages_visited"] = []
    state["performance_metrics"] = {}
    state["visual_results"] = []
    state["all_bugs"] = []
    state["functional_bugs"] = []
    state["dom_a11y_bugs"] = []
    state["security_bugs"] = []
    state["figma_deviations"] = []
    state["fixes"] = []
    state["new_bugs"] = []
    state["quality_score"] = 0
    state["figma_match_score"] = 100
    state["healing_events"] = []
    state["page_tokens"] = []
    state["design_tokens"] = {}
    state["design_inconsistencies"] = []
    state["design_consistency_score"] = 100
    state["error"] = None
    state["status"] = "observe"
    return state


def navigate_node(state: AgentState) -> AgentState:
    state["status"] = "navigate"
    try:
        result = run_navigation(state["url"])
        state["screenshots"]         = result["screenshots"]
        state["network_issues"]      = result["network_issues"]
        state["console_errors"]      = result.get("console_errors", [])
        state["pages_visited"]       = result["pages_visited"]
        state["performance_metrics"] = result["performance_metrics"]
        # Axe-core a11y + security findings are now returned by the navigator
        state["dom_a11y_bugs"]       = result.get("dom_a11y_bugs", [])
        state["security_bugs"]       = result.get("security_bugs", [])
        state["page_tokens"]         = result.get("page_tokens", [])
    except Exception as e:
        state["error"] = f"Navigation error: {str(e)}"
        state["screenshots"] = []
    return state


def detect_node(state: AgentState) -> AgentState:
    state["status"] = "detect"
    if not state["screenshots"]:
        state["all_bugs"] = []
        return state

    visual_results = analyze_all_screenshots(
        state["screenshots"],
        console_errors=state.get("console_errors", []),
        network_issues=state.get("network_issues", []),
    )
    state["visual_results"] = visual_results

    all_bugs = []
    for result in visual_results:
        for bug in result.get("bugs", []):
            bug["url"] = result.get("url", "")
            bug["label"] = result.get("label", "")
            bug["viewport"] = result.get("viewport", "desktop")
            all_bugs.append(bug)

    severity_order = {"critical": 0, "serious": 1, "moderate": 2, "minor": 3}
    all_bugs.sort(key=lambda b: severity_order.get(b.get("severity", "minor"), 3))
    state["all_bugs"] = all_bugs

    if state.get("figma_b64") and state["screenshots"]:
        first_desktop = next(
            (s for s in state["screenshots"] if s.get("viewport") == "desktop"),
            state["screenshots"][0],
        )
        figma_result = compare_with_figma(first_desktop["screenshot"], state["figma_b64"])
        state["figma_deviations"] = figma_result.get("deviations", [])
        state["figma_match_score"] = figma_result.get("design_match_score", 100)

    # dom_a11y_bugs and security_bugs are now set by navigate_node directly from
    # the single Playwright session — no separate browser launches needed here.

    # Design Intelligence: cross-page design-token consistency, grounded in real
    # computed styles (not vision guesswork) — complements the Figma diff above.
    if state.get("page_tokens"):
        aggregated = aggregate_tokens(state["page_tokens"])
        state["design_tokens"] = aggregated
        state["design_inconsistencies"] = find_inconsistencies(aggregated)
        state["design_consistency_score"] = compute_consistency_score(state["design_inconsistencies"])

    # Functional QA — self-healing Playwright interactions (Playwright + Agent)
    from functional_qa import run_functional_test
    try:
        functional_res = run_functional_test(state["url"])
        if functional_res.get("success"):
            state["functional_bugs"] = functional_res.get("bugs", [])
            state["healing_events"] = functional_res.get("healing_events", [])
    except Exception as e:
        print(f"Functional QA error: {e}")

    prev = get_previous_scan(state["user_id"], state["url"])
    if prev:
        prev_descriptions = {b.get("description", "") for b in prev.get("all_bugs", [])}
        state["new_bugs"] = [b for b in all_bugs if b.get("description", "") not in prev_descriptions]
    else:
        state["new_bugs"] = list(all_bugs)

    return state


def fix_node(state: AgentState) -> AgentState:
    state["status"] = "fix"
    fixes = []
    for bug in state["all_bugs"]:
        if bug.get("devtools_command"):
            fixes.append({
                "bug_id": bug.get("bug_id", ""),
                "category": bug.get("category", ""),
                "severity": bug.get("severity", ""),
                "devtools_command": bug.get("devtools_command", ""),
                "css_fix": bug.get("css_fix", ""),
                "html_fix": bug.get("html_fix", ""),
                "description": bug.get("description", ""),
                "element": bug.get("element_description", bug.get("element", "")),
                "label": bug.get("label", ""),
                "url": bug.get("url", ""),
            })
    state["fixes"] = fixes
    return state


def verify_node(state: AgentState) -> AgentState:
    state["status"] = "verify"
    bugs = state["all_bugs"]
    if not bugs:
        state["quality_score"] = 95
        return state

    scores = [r.get("page_quality_score", 0) for r in state.get("visual_results", []) if r.get("page_quality_score")]
    if scores:
        base_score = int(sum(scores) / len(scores))
    else:
        penalty = sum(
            {"critical": 15, "serious": 8, "moderate": 4, "minor": 1}.get(b.get("severity", "minor"), 1)
            for b in bugs
        )
        base_score = max(0, 100 - penalty)

    net_penalty = min(30, len(state.get("network_issues", [])) * 5)
    state["quality_score"] = max(0, min(100, base_score - net_penalty))
    return state


def report_node(state: AgentState) -> AgentState:
    state["status"] = "report"
    try:
        save_scan({
            "scan_id": state["scan_id"],
            "user_id": state["user_id"],
            "url": state["url"],
            "quality_score": state.get("quality_score", 0),
            "figma_match_score": state.get("figma_match_score", 100),
            "all_bugs": state.get("all_bugs", []),
            "functional_bugs": state.get("functional_bugs", []),
            "dom_a11y_bugs": state.get("dom_a11y_bugs", []),
            "security_bugs": state.get("security_bugs", []),
            "network_issues": state.get("network_issues", []),
            "figma_deviations": state.get("figma_deviations", []),
            "fixes": state.get("fixes", []),
            "new_bugs": state.get("new_bugs", []),
            "pages_visited": state.get("pages_visited", []),
            "performance_metrics": state.get("performance_metrics", {}),
            "screenshots_meta": [
                {k: v for k, v in s.items() if k != "screenshot"} for s in state.get("screenshots", [])
            ],
            "healing_events": state.get("healing_events", []),
            "design_tokens": state.get("design_tokens", {}),
            "design_inconsistencies": state.get("design_inconsistencies", []),
            "design_consistency_score": state.get("design_consistency_score", 100),
            "created_at": datetime.now().isoformat(),
        })
    except Exception as e:
        print(f"Save scan error: {e}")
    return state


def build_graph():
    g = StateGraph(AgentState)
    g.add_node("observe", observe_node)
    g.add_node("navigate", navigate_node)
    g.add_node("detect", detect_node)
    g.add_node("fix", fix_node)
    g.add_node("verify", verify_node)
    g.add_node("report", report_node)
    g.set_entry_point("observe")
    g.add_edge("observe", "navigate")
    g.add_edge("navigate", "detect")
    g.add_edge("detect", "fix")
    g.add_edge("fix", "verify")
    g.add_edge("verify", "report")
    g.add_edge("report", END)
    return g.compile()


_graph = build_graph()


def run_scan(user_id: str, url: str, figma_b64: Optional[str] = None) -> Dict[str, Any]:
    init: AgentState = {
        "scan_id": "",
        "user_id": user_id,
        "url": url,
        "figma_b64": figma_b64,
        "screenshots": [],
        "network_issues": [],
        "console_errors": [],
        "pages_visited": [],
        "performance_metrics": {},
        "visual_results": [],
        "all_bugs": [],
        "figma_deviations": [],
        "fixes": [],
        "new_bugs": [],
        "quality_score": 0,
        "figma_match_score": 100,
        "healing_events": [],
        "page_tokens": [],
        "design_tokens": {},
        "design_inconsistencies": [],
        "design_consistency_score": 100,
        "status": "idle",
        "error": None,
    }
    return dict(_graph.invoke(init))
