"""Tests for the FastAPI HTTP routes."""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class TestHealthEndpoint:
    def test_returns_200(self):
        response = client.get("/health")
        assert response.status_code == 200

    def test_returns_ok_status(self):
        response = client.get("/health")
        assert response.json() == {"status": "ok"}


class TestListConfigs:
    def test_returns_200(self):
        response = client.get("/api/wizard/configs")
        assert response.status_code == 200

    def test_returns_list(self):
        data = client.get("/api/wizard/configs").json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_each_entry_has_required_fields(self):
        for cfg in client.get("/api/wizard/configs").json():
            assert "id" in cfg
            assert "title" in cfg
            assert "description" in cfg
            assert "target" in cfg

    def test_known_configs_present(self):
        ids = {cfg["id"] for cfg in client.get("/api/wizard/configs").json()}
        assert "claude" in ids
        assert "copilot" in ids
        assert "cursor" in ids


class TestGetConfig:
    @pytest.mark.parametrize("config_id", ["claude", "copilot", "cursor"])
    def test_returns_200_for_known_ids(self, config_id):
        response = client.get(f"/api/wizard/config/{config_id}")
        assert response.status_code == 200

    @pytest.mark.parametrize("config_id", ["claude", "copilot", "cursor"])
    def test_response_includes_steps(self, config_id):
        data = client.get(f"/api/wizard/config/{config_id}").json()
        assert "steps" in data
        assert len(data["steps"]) > 0

    def test_returns_404_for_unknown_id(self):
        response = client.get("/api/wizard/config/does_not_exist")
        assert response.status_code == 404

    def test_404_response_has_detail(self):
        response = client.get("/api/wizard/config/does_not_exist")
        assert "detail" in response.json()

    def test_id_matches_requested(self):
        data = client.get("/api/wizard/config/claude").json()
        assert data["id"] == "claude"


class TestGenerateEndpoint:
    def test_returns_200_for_valid_config(self):
        response = client.post("/api/generate", json={"config_id": "claude", "answers": {}})
        assert response.status_code == 200

    def test_response_is_zip(self):
        response = client.post("/api/generate", json={"config_id": "claude", "answers": {}})
        assert response.headers["content-type"] == "application/zip"

    def test_content_disposition_includes_filename(self):
        response = client.post("/api/generate", json={"config_id": "claude", "answers": {}})
        assert "claude_config.zip" in response.headers["content-disposition"]

    def test_response_body_is_non_empty_bytes(self):
        response = client.post("/api/generate", json={"config_id": "claude", "answers": {}})
        assert len(response.content) > 0

    def test_returns_404_for_unknown_config(self):
        response = client.post("/api/generate", json={"config_id": "ghost", "answers": {}})
        assert response.status_code == 404

    def test_returns_422_for_missing_config_id(self):
        response = client.post("/api/generate", json={"answers": {}})
        assert response.status_code == 422

    @pytest.mark.parametrize("config_id", ["claude", "copilot", "cursor"])
    def test_all_configs_generate_successfully(self, config_id):
        response = client.post("/api/generate", json={"config_id": config_id, "answers": {}})
        assert response.status_code == 200

    def test_answers_are_reflected_in_zip(self):
        import io
        import zipfile

        answers = {
            "claude_md": {"project_overview": "This is a unique test project overview string."}
        }
        response = client.post("/api/generate", json={"config_id": "claude", "answers": answers})
        assert response.status_code == 200

        zf = zipfile.ZipFile(io.BytesIO(response.content))
        names = zf.namelist()
        assert "CLAUDE.md" in names
        content = zf.read("CLAUDE.md").decode()
        assert "unique test project overview string" in content
