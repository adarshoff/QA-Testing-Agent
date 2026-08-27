"""
Cross-page design-system consistency analysis.

Takes the raw per-page token samples from design_tokens.py, aggregates them
across every page the navigator visited, and flags drift: the same logical
component rendered with subtly different values on different pages (e.g. a
primary button that's #1a73e8 on the homepage and #1976d2 on the pricing
page — visually almost the same blue, but not the same token, which is
exactly the kind of thing a human reviewer skims past and a design system
audit is supposed to catch).
"""
import re
from typing import Any, Dict, List, Optional, Tuple

# Two distinct colors closer than this (Euclidean distance in 0-255 RGB space,
# max possible ~441) read as "the same intended color rendered inconsistently"
# rather than a deliberate second variant (e.g. primary vs. danger button).
DRIFT_THRESHOLD = 40.0

SEVERITY_PENALTY = {"serious": 15, "moderate": 8, "minor": 3}

TRANSPARENT_VALUES = {"rgba(0, 0, 0, 0)", "transparent", "rgb(0, 0, 0)"}


def _parse_rgb(color: Optional[str]) -> Optional[Tuple[int, int, int]]:
    if not color:
        return None
    m = re.match(r"rgba?\((\d+),\s*(\d+),\s*(\d+)", color)
    if not m:
        return None
    return tuple(int(x) for x in m.groups())


def _color_distance(a: Tuple[int, int, int], b: Tuple[int, int, int]) -> float:
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5


def aggregate_tokens(all_page_tokens: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Flatten per-page token samples into category buckets, tagging each sample with its source page."""
    aggregated: Dict[str, List[Dict[str, Any]]] = {"buttons": [], "headings": [], "body_text": []}
    for page_tok in all_page_tokens:
        url = page_tok.get("url", "")
        label = page_tok.get("label", "") or url
        for category in aggregated:
            for sample in page_tok.get(category, []):
                aggregated[category].append({**sample, "url": url, "label": label})
    return aggregated


def _check_color_drift(samples: List[Dict[str, Any]], component: str, prop: str = "backgroundColor") -> List[Dict[str, Any]]:
    buckets: Dict[str, Dict[str, Any]] = {}
    for s in samples:
        color = s.get(prop)
        if not color or color in TRANSPARENT_VALUES:
            continue
        rgb = _parse_rgb(color)
        if not rgb:
            continue
        bucket = buckets.setdefault(color, {"color": color, "rgb": rgb, "sources": set()})
        bucket["sources"].add(s.get("label", ""))

    items = list(buckets.values())
    findings = []
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            a, b = items[i], items[j]
            dist = _color_distance(a["rgb"], b["rgb"])
            if 0 < dist < DRIFT_THRESHOLD:
                findings.append({
                    "token_type": "color",
                    "component": component,
                    "values_found": [
                        {"value": a["color"], "sources": sorted(a["sources"])},
                        {"value": b["color"], "sources": sorted(b["sources"])},
                    ],
                    "severity": "moderate",
                    "description": (
                        f"{component.replace('_', ' ').title()} color drifts between {a['color']} and "
                        f"{b['color']} across pages — visually near-identical, so this reads as unintentional "
                        f"drift rather than a deliberate second variant."
                    ),
                    "recommendation": f"Consolidate to a single {component.replace('_', ' ')} color token.",
                })
    return findings


def _check_heading_drift(headings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_tag: Dict[str, List[Dict[str, Any]]] = {}
    for s in headings:
        by_tag.setdefault(s.get("tag", "h?"), []).append(s)

    findings = []
    for tag, group in by_tag.items():
        families: Dict[str, set] = {}
        sizes: Dict[str, set] = {}
        for s in group:
            fam = s.get("fontFamily")
            if fam:
                families.setdefault(fam, set()).add(s.get("label", ""))
            size = s.get("fontSize")
            if size:
                sizes.setdefault(size, set()).add(s.get("label", ""))

        if len(families) > 1:
            findings.append({
                "token_type": "font-family",
                "component": tag,
                "values_found": [{"value": f, "sources": sorted(srcs)} for f, srcs in families.items()],
                "severity": "moderate",
                "description": f"<{tag}> uses {len(families)} different font families across pages.",
                "recommendation": f"Standardize <{tag}> to a single font-family token.",
            })
        if len(sizes) > 1:
            findings.append({
                "token_type": "font-size",
                "component": tag,
                "values_found": [{"value": sz, "sources": sorted(srcs)} for sz, srcs in sizes.items()],
                "severity": "minor",
                "description": f"<{tag}> font-size varies ({', '.join(sorted(sizes.keys()))}) across pages.",
                "recommendation": f"Standardize <{tag}> to a single font-size token.",
            })
    return findings


def find_inconsistencies(aggregated: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    findings.extend(_check_color_drift(aggregated.get("buttons", []), component="button"))
    findings.extend(_check_heading_drift(aggregated.get("headings", [])))
    return findings


def compute_consistency_score(inconsistencies: List[Dict[str, Any]]) -> int:
    if not inconsistencies:
        return 100
    penalty = sum(SEVERITY_PENALTY.get(f.get("severity", "minor"), 3) for f in inconsistencies)
    return max(0, min(100, 100 - penalty))
