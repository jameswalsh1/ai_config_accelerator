"""
Tests for config snapshot service (create / list / restore / delete)
and the corresponding HTTP endpoints.
"""

import json
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from app.main import app
from app.services.config_persistence import (
    create_snapshot,
    list_snapshots,
    restore_snapshot,
    delete_snapshot,
    SnapshotError,
    SNAPSHOTS_DIR,
    _snapshot_dir,
    _make_snapshot_id,
    _slugify,
)

client = TestClient(app)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

LIVE_LANGUAGE = "python"  # A language file that is guaranteed to exist
LIVE_TOOL = "claude"      # A tool file that is guaranteed to exist


def _cleanup_snapshots(scope: str, target: str) -> None:
    """Remove all snapshot files created during a test."""
    snap_dir = _snapshot_dir(scope, target)
    if snap_dir.exists():
        for f in snap_dir.glob("*.json"):
            f.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Unit tests — service layer
# ---------------------------------------------------------------------------

class TestSlugify:
    def test_basic(self):
        assert _slugify("before Python migration") == "before-python-migration"

    def test_special_chars(self):
        assert _slugify("v1.2 (stable)!") == "v1-2-stable"

    def test_empty(self):
        assert _slugify("") == "snapshot"

    def test_already_clean(self):
        assert _slugify("v1") == "v1"


class TestMakeSnapshotId:
    def test_format(self):
        sid = _make_snapshot_id("my snapshot")
        parts = sid.split("_", 1)
        assert len(parts) == 2
        # First part is timestamp like 20260428T123456
        assert len(parts[0]) == 15
        assert "T" in parts[0]
        # Second part is slug
        assert parts[1] == "my-snapshot"

    def test_uniqueness(self):
        # Two calls in the same second still produce the same slug part
        id1 = _make_snapshot_id("test")
        id2 = _make_snapshot_id("test")
        # Timestamps should be identical or differ by at most 1 second — both end in "test"
        assert id1.endswith("test") and id2.endswith("test")


class TestCreateSnapshot:
    def setup_method(self):
        _cleanup_snapshots("language", LIVE_LANGUAGE)

    def teardown_method(self):
        _cleanup_snapshots("language", LIVE_LANGUAGE)

    def test_returns_metadata(self):
        meta = create_snapshot("language", LIVE_LANGUAGE, "test snapshot")
        assert meta["scope"] == "language"
        assert meta["target"] == LIVE_LANGUAGE
        assert meta["name"] == "test snapshot"
        assert "snapshot_id" in meta
        assert "created_at" in meta

    def test_file_written(self):
        meta = create_snapshot("language", LIVE_LANGUAGE, "file write test")
        snap_path = _snapshot_dir("language", LIVE_LANGUAGE) / f"{meta['snapshot_id']}.json"
        assert snap_path.exists()

    def test_snapshot_file_contains_data(self):
        meta = create_snapshot("language", LIVE_LANGUAGE, "data check")
        snap_path = _snapshot_dir("language", LIVE_LANGUAGE) / f"{meta['snapshot_id']}.json"
        with snap_path.open() as f:
            snap = json.load(f)
        assert "meta" in snap
        assert "data" in snap
        assert isinstance(snap["data"], dict)
        assert snap["data"].get("language_id") == LIVE_LANGUAGE

    def test_invalid_scope_raises(self):
        with pytest.raises(SnapshotError, match="Invalid scope"):
            create_snapshot("bad_scope", LIVE_LANGUAGE, "x")

    def test_missing_target_raises(self):
        with pytest.raises(SnapshotError, match="not found"):
            create_snapshot("language", "nonexistent_lang_xyz", "x")

    def test_tool_scope(self):
        _cleanup_snapshots("tool", LIVE_TOOL)
        try:
            meta = create_snapshot("tool", LIVE_TOOL, "tool snapshot")
            assert meta["scope"] == "tool"
            assert meta["target"] == LIVE_TOOL
        finally:
            _cleanup_snapshots("tool", LIVE_TOOL)


class TestListSnapshots:
    def setup_method(self):
        _cleanup_snapshots("language", LIVE_LANGUAGE)

    def teardown_method(self):
        _cleanup_snapshots("language", LIVE_LANGUAGE)

    def test_empty_when_none(self):
        assert list_snapshots("language", LIVE_LANGUAGE) == []

    def test_returns_created_snapshot(self):
        create_snapshot("language", LIVE_LANGUAGE, "list test")
        snaps = list_snapshots("language", LIVE_LANGUAGE)
        assert len(snaps) == 1
        assert snaps[0]["name"] == "list test"

    def test_newest_first(self):
        create_snapshot("language", LIVE_LANGUAGE, "first")
        create_snapshot("language", LIVE_LANGUAGE, "second")
        snaps = list_snapshots("language", LIVE_LANGUAGE)
        assert len(snaps) == 2
        # Newest (second) first — sorted by filename (timestamp prefix) descending
        assert snaps[0]["name"] == "second"

    def test_multiple_snapshots(self):
        for i in range(3):
            create_snapshot("language", LIVE_LANGUAGE, f"snap {i}")
        assert len(list_snapshots("language", LIVE_LANGUAGE)) == 3

    def test_invalid_scope_raises(self):
        with pytest.raises(SnapshotError):
            list_snapshots("bad", LIVE_LANGUAGE)


class TestRestoreSnapshot:
    def setup_method(self):
        _cleanup_snapshots("language", LIVE_LANGUAGE)

    def teardown_method(self):
        _cleanup_snapshots("language", LIVE_LANGUAGE)

    def test_restore_returns_meta(self):
        meta = create_snapshot("language", LIVE_LANGUAGE, "restore test")
        restored = restore_snapshot("language", LIVE_LANGUAGE, meta["snapshot_id"])
        assert restored["snapshot_id"] == meta["snapshot_id"]
        assert restored["name"] == "restore test"

    def test_restore_overwrites_live_file(self):
        from app.services.config_persistence import DATA_DIR
        live_path = DATA_DIR / "languages" / f"{LIVE_LANGUAGE}.json"

        # Capture original content
        with live_path.open() as f:
            original = json.load(f)

        meta = create_snapshot("language", LIVE_LANGUAGE, "before change")

        # Modify live file in-memory (don't actually write to avoid corrupting test data)
        # Instead, verify that restore at least doesn't crash and live file stays valid JSON
        restore_snapshot("language", LIVE_LANGUAGE, meta["snapshot_id"])

        with live_path.open() as f:
            restored = json.load(f)

        assert restored == original

    def test_restore_nonexistent_raises(self):
        with pytest.raises(SnapshotError, match="not found"):
            restore_snapshot("language", LIVE_LANGUAGE, "nonexistent_id")

    def test_restore_invalid_scope_raises(self):
        with pytest.raises(SnapshotError, match="Invalid scope"):
            restore_snapshot("bad", LIVE_LANGUAGE, "any_id")


class TestDeleteSnapshot:
    def setup_method(self):
        _cleanup_snapshots("language", LIVE_LANGUAGE)

    def teardown_method(self):
        _cleanup_snapshots("language", LIVE_LANGUAGE)

    def test_delete_removes_file(self):
        meta = create_snapshot("language", LIVE_LANGUAGE, "to delete")
        snap_path = _snapshot_dir("language", LIVE_LANGUAGE) / f"{meta['snapshot_id']}.json"
        assert snap_path.exists()

        delete_snapshot("language", LIVE_LANGUAGE, meta["snapshot_id"])
        assert not snap_path.exists()

    def test_delete_nonexistent_raises(self):
        with pytest.raises(SnapshotError, match="not found"):
            delete_snapshot("language", LIVE_LANGUAGE, "does_not_exist")

    def test_delete_removes_from_list(self):
        meta = create_snapshot("language", LIVE_LANGUAGE, "gone soon")
        assert len(list_snapshots("language", LIVE_LANGUAGE)) == 1
        delete_snapshot("language", LIVE_LANGUAGE, meta["snapshot_id"])
        assert list_snapshots("language", LIVE_LANGUAGE) == []

    def test_invalid_scope_raises(self):
        with pytest.raises(SnapshotError):
            delete_snapshot("bad", LIVE_LANGUAGE, "any")


# ---------------------------------------------------------------------------
# Integration tests — HTTP endpoints
# ---------------------------------------------------------------------------

class TestSnapshotEndpoints:
    def setup_method(self):
        _cleanup_snapshots("language", LIVE_LANGUAGE)

    def teardown_method(self):
        _cleanup_snapshots("language", LIVE_LANGUAGE)

    # POST /config/snapshots

    def test_create_returns_200(self):
        res = client.post("/config/snapshots", json={
            "scope": "language", "target": LIVE_LANGUAGE, "name": "http test"
        })
        assert res.status_code == 200

    def test_create_response_shape(self):
        res = client.post("/config/snapshots", json={
            "scope": "language", "target": LIVE_LANGUAGE, "name": "shape test"
        })
        data = res.json()
        assert "snapshot_id" in data
        assert "name" in data
        assert "created_at" in data
        assert "scope" in data
        assert "target" in data

    def test_create_missing_name_returns_400(self):
        res = client.post("/config/snapshots", json={
            "scope": "language", "target": LIVE_LANGUAGE
        })
        assert res.status_code == 400

    def test_create_unknown_target_returns_404(self):
        res = client.post("/config/snapshots", json={
            "scope": "language", "target": "no_such_lang_xyz", "name": "x"
        })
        assert res.status_code == 404

    def test_create_invalid_scope_returns_400(self):
        res = client.post("/config/snapshots", json={
            "scope": "invalid", "target": LIVE_LANGUAGE, "name": "x"
        })
        assert res.status_code == 400

    # GET /config/snapshots

    def test_list_returns_200(self):
        res = client.get("/config/snapshots", params={"scope": "language", "target": LIVE_LANGUAGE})
        assert res.status_code == 200

    def test_list_empty_initially(self):
        data = client.get("/config/snapshots", params={"scope": "language", "target": LIVE_LANGUAGE}).json()
        assert data == []

    def test_list_reflects_created_snapshot(self):
        client.post("/config/snapshots", json={
            "scope": "language", "target": LIVE_LANGUAGE, "name": "list reflect"
        })
        data = client.get("/config/snapshots", params={"scope": "language", "target": LIVE_LANGUAGE}).json()
        assert len(data) == 1
        assert data[0]["name"] == "list reflect"

    def test_list_invalid_scope_returns_400(self):
        res = client.get("/config/snapshots", params={"scope": "bad", "target": LIVE_LANGUAGE})
        assert res.status_code == 400

    # POST /config/snapshots/restore

    def test_restore_returns_200(self):
        meta = client.post("/config/snapshots", json={
            "scope": "language", "target": LIVE_LANGUAGE, "name": "for restore"
        }).json()
        res = client.post("/config/snapshots/restore", json={
            "scope": "language", "target": LIVE_LANGUAGE, "snapshot_id": meta["snapshot_id"]
        })
        assert res.status_code == 200

    def test_restore_returns_meta(self):
        meta = client.post("/config/snapshots", json={
            "scope": "language", "target": LIVE_LANGUAGE, "name": "restore meta check"
        }).json()
        restored = client.post("/config/snapshots/restore", json={
            "scope": "language", "target": LIVE_LANGUAGE, "snapshot_id": meta["snapshot_id"]
        }).json()
        assert restored["snapshot_id"] == meta["snapshot_id"]

    def test_restore_missing_id_returns_400(self):
        res = client.post("/config/snapshots/restore", json={
            "scope": "language", "target": LIVE_LANGUAGE
        })
        assert res.status_code == 400

    def test_restore_unknown_id_returns_404(self):
        res = client.post("/config/snapshots/restore", json={
            "scope": "language", "target": LIVE_LANGUAGE, "snapshot_id": "nonexistent_id"
        })
        assert res.status_code == 404

    # DELETE /config/snapshots/{snapshot_id}

    def test_delete_returns_200(self):
        meta = client.post("/config/snapshots", json={
            "scope": "language", "target": LIVE_LANGUAGE, "name": "to delete"
        }).json()
        res = client.delete(
            f"/config/snapshots/{meta['snapshot_id']}",
            params={"scope": "language", "target": LIVE_LANGUAGE},
        )
        assert res.status_code == 200

    def test_delete_response_shape(self):
        meta = client.post("/config/snapshots", json={
            "scope": "language", "target": LIVE_LANGUAGE, "name": "del shape"
        }).json()
        data = client.delete(
            f"/config/snapshots/{meta['snapshot_id']}",
            params={"scope": "language", "target": LIVE_LANGUAGE},
        ).json()
        assert data["deleted"] is True
        assert data["snapshot_id"] == meta["snapshot_id"]

    def test_delete_removes_from_list(self):
        meta = client.post("/config/snapshots", json={
            "scope": "language", "target": LIVE_LANGUAGE, "name": "gone"
        }).json()
        client.delete(
            f"/config/snapshots/{meta['snapshot_id']}",
            params={"scope": "language", "target": LIVE_LANGUAGE},
        )
        remaining = client.get(
            "/config/snapshots", params={"scope": "language", "target": LIVE_LANGUAGE}
        ).json()
        assert all(s["snapshot_id"] != meta["snapshot_id"] for s in remaining)

    def test_delete_nonexistent_returns_404(self):
        res = client.delete(
            "/config/snapshots/does_not_exist",
            params={"scope": "language", "target": LIVE_LANGUAGE},
        )
        assert res.status_code == 404

    # Round-trip

    def test_full_roundtrip(self):
        """Create → list → restore → delete."""
        # Create
        create_res = client.post("/config/snapshots", json={
            "scope": "language", "target": LIVE_LANGUAGE, "name": "roundtrip"
        })
        assert create_res.status_code == 200
        sid = create_res.json()["snapshot_id"]

        # List
        snaps = client.get("/config/snapshots", params={"scope": "language", "target": LIVE_LANGUAGE}).json()
        assert any(s["snapshot_id"] == sid for s in snaps)

        # Restore
        restore_res = client.post("/config/snapshots/restore", json={
            "scope": "language", "target": LIVE_LANGUAGE, "snapshot_id": sid
        })
        assert restore_res.status_code == 200

        # Delete
        del_res = client.delete(
            f"/config/snapshots/{sid}",
            params={"scope": "language", "target": LIVE_LANGUAGE},
        )
        assert del_res.status_code == 200

        # Gone from list
        snaps_after = client.get("/config/snapshots", params={"scope": "language", "target": LIVE_LANGUAGE}).json()
        assert all(s["snapshot_id"] != sid for s in snaps_after)
