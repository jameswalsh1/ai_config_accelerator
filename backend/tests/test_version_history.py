"""Tests for the version_history service."""

import json
import shutil
from pathlib import Path

import pytest

import app.services.version_history as vh_module
from app.services.version_history import (
    save_version,
    list_versions,
    get_version,
    get_version_data,
    get_latest_version_number,
    _next_version,
)


SCOPE = "language"
TARGET = "test_lang"


@pytest.fixture(autouse=True)
def _cleanup():
    """Remove test history directory before and after each test."""
    d = vh_module.HISTORY_DIR / SCOPE / TARGET
    if d.exists():
        shutil.rmtree(d)
    yield
    if d.exists():
        shutil.rmtree(d)


# ---------------------------------------------------------------------------
# _next_version
# ---------------------------------------------------------------------------

class TestNextVersion:
    def test_returns_1_when_no_history(self):
        assert _next_version(SCOPE, TARGET) == 1

    def test_returns_2_after_one_version(self):
        save_version(SCOPE, TARGET, {"id": "x"})
        assert _next_version(SCOPE, TARGET) == 2

    def test_returns_sequential(self):
        save_version(SCOPE, TARGET, {"id": "x"})
        save_version(SCOPE, TARGET, {"id": "y"})
        save_version(SCOPE, TARGET, {"id": "z"})
        assert _next_version(SCOPE, TARGET) == 4


# ---------------------------------------------------------------------------
# save_version
# ---------------------------------------------------------------------------

class TestSaveVersion:
    def test_returns_metadata(self):
        meta = save_version(SCOPE, TARGET, {"id": "x"}, actor="alice", summary="init")
        assert meta["version"] == 1
        assert meta["actor"] == "alice"
        assert meta["summary"] == "init"
        assert meta["scope"] == SCOPE
        assert meta["target"] == TARGET
        assert "timestamp" in meta
        # metadata should NOT include data payload
        assert "data" not in meta

    def test_writes_file_to_disk(self):
        save_version(SCOPE, TARGET, {"id": "x"})
        path = vh_module.HISTORY_DIR / SCOPE / TARGET / "v001.json"
        assert path.exists()
        with path.open() as f:
            envelope = json.load(f)
        assert envelope["version"] == 1
        assert envelope["data"] == {"id": "x"}

    def test_increments_version(self):
        m1 = save_version(SCOPE, TARGET, {"v": 1})
        m2 = save_version(SCOPE, TARGET, {"v": 2})
        assert m1["version"] == 1
        assert m2["version"] == 2

    def test_preserves_full_data(self):
        data = {
            "id": "test",
            "steps": [{"id": "s1", "fields": [{"id": "f1", "value": "hello"}]}],
        }
        save_version(SCOPE, TARGET, data)
        stored = get_version_data(SCOPE, TARGET, 1)
        assert stored == data


# ---------------------------------------------------------------------------
# list_versions
# ---------------------------------------------------------------------------

class TestListVersions:
    def test_empty_when_no_history(self):
        assert list_versions(SCOPE, TARGET) == []

    def test_returns_newest_first(self):
        save_version(SCOPE, TARGET, {"v": 1}, summary="first")
        save_version(SCOPE, TARGET, {"v": 2}, summary="second")
        save_version(SCOPE, TARGET, {"v": 3}, summary="third")
        versions = list_versions(SCOPE, TARGET)
        assert len(versions) == 3
        assert versions[0]["version"] == 3
        assert versions[1]["version"] == 2
        assert versions[2]["version"] == 1

    def test_metadata_shape(self):
        save_version(SCOPE, TARGET, {"v": 1}, actor="bob", summary="init")
        versions = list_versions(SCOPE, TARGET)
        v = versions[0]
        assert set(v.keys()) == {"version", "timestamp", "actor", "summary", "scope", "target"}
        assert v["actor"] == "bob"
        assert v["summary"] == "init"


# ---------------------------------------------------------------------------
# get_version / get_version_data
# ---------------------------------------------------------------------------

class TestGetVersion:
    def test_returns_full_envelope(self):
        save_version(SCOPE, TARGET, {"id": "x"}, actor="alice")
        envelope = get_version(SCOPE, TARGET, 1)
        assert envelope["version"] == 1
        assert envelope["actor"] == "alice"
        assert envelope["data"] == {"id": "x"}

    def test_raises_for_missing_version(self):
        with pytest.raises(FileNotFoundError):
            get_version(SCOPE, TARGET, 99)

    def test_get_version_data_returns_only_data(self):
        save_version(SCOPE, TARGET, {"id": "x"})
        data = get_version_data(SCOPE, TARGET, 1)
        assert data == {"id": "x"}
        assert "version" not in data

    def test_get_version_data_raises_for_missing(self):
        with pytest.raises(FileNotFoundError):
            get_version_data(SCOPE, TARGET, 1)


# ---------------------------------------------------------------------------
# get_latest_version_number
# ---------------------------------------------------------------------------

class TestGetLatestVersionNumber:
    def test_none_when_no_history(self):
        assert get_latest_version_number(SCOPE, TARGET) is None

    def test_returns_latest(self):
        save_version(SCOPE, TARGET, {"v": 1})
        save_version(SCOPE, TARGET, {"v": 2})
        assert get_latest_version_number(SCOPE, TARGET) == 2


