"""Check offline payload safety and the dashboard's sample/forecast contract."""
import json
import re

import pandas as pd
import pytest

from rbi_intelligence.dashboard import build_dashboard


def frames(bank_name="Example Bank"):
    events = pd.DataFrame([{"event_id": "aug", "event_date": "2025-08-06", "decision": "Hold", "source_url": "https://www.rbi.org.in/"}])
    results = pd.DataFrame([{"event_id": "aug", "event_date": "2025-08-06", "decision": "Hold", "bank_symbol": "A", "bank_name": bank_name, "bank_type": "Private", "benchmark": "^NSEI", "window": "[-1,+1]", "car": -.012}])
    return events, results


def payload(html):
    return json.loads(re.search(r'<script type="application/json" id="research-data">(.*?)</script>', html, re.S).group(1))


def test_dashboard_embeds_corrected_dates_and_complete_sample_metadata(tmp_path):
    path = build_dashboard(tmp_path / "dashboard.html", *frames(), manifest={"data_sha256": "fixture-hash", "source": "fixture"})
    html = path.read_text()
    data = payload(html)
    assert data["events"][0]["event_date"] == "2025-08-06"
    assert data["validation"]["event_count"] == 1
    assert data["validation"]["bank_count"] == 1
    assert data["results"][0]["car"] == -.012
    assert data["results"][0]["absolute_car"] == .012
    assert data["manifest"]["data_sha256"] == "fixture-hash"
    assert '<script src=' not in html
    assert 'fetch(' not in html
    assert '<link rel="stylesheet"' not in html
    for control in ["benchmark", "window", "decision", "bankType", "event"]:
        assert f'<select id="{control}">' in html


def test_untrusted_label_cannot_escape_embedded_json(tmp_path):
    label = '</script><script>window.UNSAFE=true</script>'
    html = build_dashboard(tmp_path / "dashboard.html", *frames(label)).read_text()
    assert label not in html
    assert payload(html)["results"][0]["bank_name"] == label
    assert len(re.findall(r"<script(?:\s|>)", html)) == 2


def test_no_manifest_does_not_invent_source_verification(tmp_path):
    html = build_dashboard(tmp_path / "dashboard.html", *frames()).read_text()
    assert payload(html)["manifest"] == {}
    assert "No external run manifest supplied" in html
    assert "not independent authentication" in html


def test_dashboard_refuses_inconsistent_event_dates(tmp_path):
    events, results = frames()
    results["event_date"] = "2025-08-07"
    with pytest.raises(ValueError, match="event_date disagrees"):
        build_dashboard(tmp_path / "dashboard.html", events, results)
    assert not (tmp_path / "dashboard.html").exists()
