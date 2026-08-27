"""
Offline, reproducible proof that Functional QA actually self-heals.

No network access and no GEMINI_API_KEY needed — everything runs against local
file:// HTML fixtures via a real headless Chromium (Playwright is already a
hard dependency of this project).

Run with:
  cd backend && pytest test_self_healing.py -v
"""
from functional_qa import run_functional_test
from memory import get_fingerprints

FIXTURE_V1 = """<!DOCTYPE html>
<html><body>
<form>
  <input id="email-v1" type="email" placeholder="Email address">
  <button id="submit-v1" type="submit">Submit</button>
</form>
</body></html>"""

# Same visible labels/text, but every id and class regenerated -- the exact
# shape of a real frontend redeploy that breaks CSS-selector-based tests.
FIXTURE_V2 = """<!DOCTYPE html>
<html><body>
<form>
  <input id="email-9f3a" class="Input_root__k2j1" type="email" placeholder="Email address">
  <button id="submit-9f3a" class="Button_primary__q8z2" type="submit">Submit</button>
</form>
</body></html>"""


def _write_fixture(tmp_path, content):
    path = tmp_path / "fixture.html"
    path.write_text(content, encoding="utf-8")
    return path.as_uri()


class TestSelfHealing:
    def test_first_run_discovers_and_persists_fingerprints(self, tmp_path):
        url = _write_fixture(tmp_path, FIXTURE_V1)

        result = run_functional_test(url)

        assert result["success"] is True
        assert all(s["success"] for s in result["steps"]), result["steps"]
        # Nothing to heal on a URL's very first-ever scan.
        assert result["healing_events"] == []

        fingerprints = get_fingerprints(url)
        assert "field_0" in fingerprints
        assert "submit_button" in fingerprints
        assert fingerprints["field_0"]["strategy"] == "css"
        assert fingerprints["field_0"]["value"] == "#email-v1"
        assert fingerprints["submit_button"]["value"] == "#submit-v1"

    def test_second_run_heals_when_ids_and_classes_regenerate(self, tmp_path):
        url = _write_fixture(tmp_path, FIXTURE_V1)
        first = run_functional_test(url)
        assert first["success"] is True
        assert all(s["success"] for s in first["steps"])

        # Simulate a redeploy: same file:// URL (same fingerprint key), but the
        # markup underneath it has drifted -- ids/classes regenerated, labels kept.
        (tmp_path / "fixture.html").write_text(FIXTURE_V2, encoding="utf-8")

        second = run_functional_test(url)

        assert second["success"] is True
        assert all(s["success"] for s in second["steps"]), second["steps"]

        healed_fields = {e["field_key"] for e in second["healing_events"]}
        assert "field_0" in healed_fields, second["healing_events"]
        assert "submit_button" in healed_fields, second["healing_events"]

        for event in second["healing_events"]:
            assert event["healed_strategy"] in ("role", "placeholder", "label", "type_index")

        # The persisted descriptors should now reflect the strategy that actually
        # worked, not the stale CSS selector that broke.
        healed_fingerprints = get_fingerprints(url)
        assert healed_fingerprints["field_0"]["strategy"] != "css" or \
            healed_fingerprints["field_0"]["value"] != "#email-v1"

    def test_no_bugs_reported_when_healing_recovers_the_interaction(self, tmp_path):
        """Healing should mean the scan reports zero functional bugs -- the whole
        point is that a DOM change that would otherwise break the interaction
        doesn't turn into a false-positive bug report."""
        url = _write_fixture(tmp_path, FIXTURE_V1)
        run_functional_test(url)

        (tmp_path / "fixture.html").write_text(FIXTURE_V2, encoding="utf-8")
        result = run_functional_test(url)

        assert result["bugs"] == []
