import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from amazon_job_detector.config import MatchConfig
from amazon_job_detector.models import Job


def job(**kw):
    base = dict(job_id="1", title="", location_name="", city="", state="")
    base.update(kw)
    return Job(**base)


def test_site_code_matches_in_location():
    j = job(title="Warehouse Associate", location_name="SMF1 - Sacramento")
    assert matches_(j, site_codes=["SMF1", "SMF6"])


def test_site_code_matches_in_raw_payload():
    j = job(title="Associate", raw={"siteId": "SMF6", "x": 1})
    assert matches_(j, site_codes=["SMF6"])


def test_site_code_no_match():
    j = job(title="Associate", location_name="SMF7 - Reno", city="Reno")
    assert not matches_(j, site_codes=["SMF1", "SMF6"])


def test_title_contains_filter():
    j = job(title="Sortation Center Associate", location_name="SMF1")
    assert matches_(j, site_codes=["SMF1"], title_contains=["sortation"])
    assert not matches_(j, site_codes=["SMF1"], title_contains=["fulfillment"])


def test_min_pay_rate():
    j = job(title="Associate", location_name="SMF1", pay_rate=18.0)
    assert not matches_(j, site_codes=["SMF1"], min_pay_rate=20.0)
    assert matches_(j, site_codes=["SMF1"], min_pay_rate=18.0)


def test_min_pay_rate_unknown_fails():
    j = job(title="Associate", location_name="SMF1", pay_rate=None)
    assert not matches_(j, site_codes=["SMF1"], min_pay_rate=20.0)


def test_no_criteria_matches_everything():
    j = job(title="Anything", location_name="Anywhere")
    assert matches_(j)


def matches_(j, **kw):
    from amazon_job_detector.matcher import matches

    return matches(j, MatchConfig(**kw))
