import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from amazon_job_detector.state import SeenStore


def test_is_new_then_marked(tmp_path):
    store = SeenStore(tmp_path / "seen.json")
    assert store.is_new("job-1")
    store.mark("job-1")
    assert not store.is_new("job-1")


def test_persists_across_instances(tmp_path):
    path = tmp_path / "seen.json"
    s1 = SeenStore(path)
    s1.mark("job-1")
    s1.save()
    s2 = SeenStore(path)
    assert not s2.is_new("job-1")


def test_ttl_expiry(tmp_path):
    path = tmp_path / "seen.json"
    store = SeenStore(path, ttl_seconds=1)
    store.mark("job-1")
    store.save()
    time.sleep(1.1)
    reloaded = SeenStore(path, ttl_seconds=1)
    assert reloaded.is_new("job-1")


def test_corrupt_file_is_tolerated(tmp_path):
    path = tmp_path / "seen.json"
    path.write_text("{not valid json")
    store = SeenStore(path)
    assert store.is_new("anything")
