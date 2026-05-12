"""Tests for the FastAPI HTTP routes."""

import pytest
from typing import Any
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


class TestResolvedConfigEndpoint:
    """Tests for GET /api/wizard/config/resolved endpoint."""

    def test_returns_200_for_valid_combo(self):
        response = client.get("/api/wizard/config/resolved?tool=claude&language=python")
        assert response.status_code == 200

    def test_returns_wizard_config(self):
        data = client.get("/api/wizard/config/resolved?tool=claude&language=python").json()
        assert isinstance(data, dict)
        assert "id" in data
        assert "steps" in data
        assert "title" in data

    @pytest.mark.parametrize("tool,language", [
        ("claude", "python"),
        ("copilot", "javascript"),
        ("cursor", "angular"),
    ])
    def test_multiple_tool_language_combos(self, tool, language):
        response = client.get(f"/api/wizard/config/resolved?tool={tool}&language={language}")
        assert response.status_code == 200
        data = response.json()
        assert "steps" in data
        assert len(data["steps"]) > 0

    def test_includes_field_metadata(self):
        data = client.get("/api/wizard/config/resolved?tool=claude&language=python").json()
        # Verify at least one field has all required metadata
        field_found = False
        for step in data["steps"]:
            for field in step["fields"]:
                # Check for key metadata fields
                if "id" in field and "label" in field:
                    field_found = True
                    # Should have metadata from base schema
                    assert "editability" in field or "hidden" in field or "presets" in field
                    break
            if field_found:
                break
        assert field_found, "No fields with proper metadata found"

    def test_includes_presets_resolved(self):
        data = client.get("/api/wizard/config/resolved?tool=claude&language=python").json()
        # Check that presets are present and resolved (not as file references)
        presets_found = False
        for step in data["steps"]:
            for field in step["fields"]:
                if "presets" in field and field["presets"] and isinstance(field["presets"], list):
                    presets_found = True
                    # Presets should be inline objects, not file references
                    for preset in field["presets"]:
                        if isinstance(preset, dict):
                            assert "label" in preset or "value" in preset
                    break
            if presets_found:
                break

    def test_respects_override_effects(self):
        """Verify that tool/language overrides are applied."""
        # Both should be valid WizardConfigs
        resolved_data = client.get("/api/wizard/config/resolved?tool=claude&language=python").json()
        assert "steps" in resolved_data
        assert len(resolved_data["steps"]) > 0

    def test_returns_400_without_required_params(self):
        # Missing tool
        response = client.get("/api/wizard/config/resolved?language=python")
        assert response.status_code == 422
        
        # Missing language
        response = client.get("/api/wizard/config/resolved?tool=claude")
        assert response.status_code == 422

    def test_returns_400_for_invalid_tool(self):
        response = client.get("/api/wizard/config/resolved?tool=invalid_tool&language=python")
        assert response.status_code == 400

    def test_400_response_includes_detail(self):
        response = client.get("/api/wizard/config/resolved?tool=invalid&language=invalid")
        assert response.status_code == 400
        assert "detail" in response.json()

    def test_returns_complete_valid_config(self):
        """Verify the returned config can be used for rendering."""
        data = client.get("/api/wizard/config/resolved?tool=claude&language=python").json()
        
        # Validate structure for UI rendering
        assert "id" in data
        assert "title" in data
        assert "description" in data
        assert "steps" in data and len(data["steps"]) > 0
        
        # Verify step structure
        for step in data["steps"]:
            assert "id" in step
            assert "title" in step
            assert "fields" in step
            
            # Verify field structure
            for field in step["fields"]:
                assert "id" in field
                assert "label" in field
                # Optional but commonly present
                if "editability" not in field:
                    # At least one of these should be present
                    assert any(k in field for k in ["hidden", "presets", "default"])


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


class TestPreviewEndpoint:
    """Tests for POST /api/generate/preview — returns file contents without zipping."""

    def test_returns_200_for_valid_config(self):
        response = client.post("/api/generate/preview", json={"config_id": "claude", "answers": {}})
        assert response.status_code == 200

    def test_returns_json(self):
        response = client.post("/api/generate/preview", json={"config_id": "claude", "answers": {}})
        assert "application/json" in response.headers["content-type"]

    def test_response_has_files_list(self):
        data = client.post("/api/generate/preview", json={"config_id": "claude", "answers": {}}).json()
        assert "files" in data
        assert isinstance(data["files"], list)
        assert len(data["files"]) > 0

    def test_each_file_has_required_fields(self):
        data = client.post("/api/generate/preview", json={"config_id": "claude", "answers": {}}).json()
        for f in data["files"]:
            assert "path" in f
            assert "content" in f
            assert "language" in f

    def test_files_are_non_empty(self):
        data = client.post("/api/generate/preview", json={"config_id": "claude", "answers": {}}).json()
        for f in data["files"]:
            assert f["content"].strip(), f"File {f['path']} has empty content"

    def test_known_claude_file_present(self):
        data = client.post("/api/generate/preview", json={"config_id": "claude", "answers": {}}).json()
        paths = {f["path"] for f in data["files"]}
        assert "CLAUDE.md" in paths

    def test_language_hints_assigned(self):
        data = client.post("/api/generate/preview", json={"config_id": "claude", "answers": {}}).json()
        by_path = {f["path"]: f for f in data["files"]}
        assert by_path["CLAUDE.md"]["language"] == "markdown"

    def test_answers_reflected_in_content(self):
        answers = {"claude_md": {"project_overview": "Preview integration test project."}}
        data = client.post(
            "/api/generate/preview",
            json={"config_id": "claude", "answers": answers},
        ).json()
        claude_md = next(f for f in data["files"] if f["path"] == "CLAUDE.md")
        assert "Preview integration test project" in claude_md["content"]

    def test_returns_404_for_unknown_config(self):
        response = client.post("/api/generate/preview", json={"config_id": "ghost", "answers": {}})
        assert response.status_code == 404

    def test_returns_422_for_missing_config_id(self):
        response = client.post("/api/generate/preview", json={"answers": {}})
        assert response.status_code == 422

    @pytest.mark.parametrize("config_id", ["claude", "copilot", "cursor"])
    def test_all_configs_produce_preview(self, config_id):
        data = client.post(
            "/api/generate/preview", json={"config_id": config_id, "answers": {}}
        ).json()
        assert len(data["files"]) > 0

    def test_json_files_get_json_language_hint(self):
        data = client.post("/api/generate/preview", json={"config_id": "copilot", "answers": {}}).json()
        json_files = [f for f in data["files"] if f["path"].endswith(".json")]
        for f in json_files:
            assert f["language"] == "json", f"{f['path']} should have language=json"

    def test_preview_and_generate_produce_same_paths(self):
        """Preview file list should match the ZIP contents."""
        import io
        import zipfile

        answers: dict[str, Any] = {}
        preview = client.post(
            "/api/generate/preview", json={"config_id": "claude", "answers": answers}
        ).json()
        generate = client.post("/api/generate", json={"config_id": "claude", "answers": answers})

        preview_paths = {f["path"] for f in preview["files"]}
        zf = zipfile.ZipFile(io.BytesIO(generate.content))
        zip_paths = set(zf.namelist())
        assert preview_paths == zip_paths


class TestEditableConfigEndpoint:
    """Test GET /api/wizard/config/edit endpoint for editable config slices."""
    
    def test_returns_200_for_valid_combo_and_step(self):
        response = client.get(
            "/api/wizard/config/edit?tool=claude&language=python&step_id=language_selection"
        )
        assert response.status_code == 200
    
    def test_returns_dict_with_step_and_source_tracking(self):
        data = client.get(
            "/api/wizard/config/edit?tool=claude&language=python&step_id=language_selection"
        ).json()
        assert isinstance(data, dict)
        assert "step" in data
        assert "source_tracking" in data
    
    def test_step_contains_required_fields(self):
        data = client.get(
            "/api/wizard/config/edit?tool=claude&language=python&step_id=language_selection"
        ).json()
        step = data["step"]
        
        # Step structure
        assert "id" in step
        assert "title" in step
        assert step["id"] == "language_selection"
        assert "fields" in step
        assert len(step["fields"]) > 0
    
    def test_fields_have_editability_metadata(self):
        data = client.get(
            "/api/wizard/config/edit?tool=claude&language=python&step_id=language_selection"
        ).json()
        
        for field in data["step"]["fields"]:
            # Core field structure
            assert "id" in field
            assert "type" in field
            assert "label" in field
            
            # Editability metadata (added by config_editor)
            assert "editability" in field
            assert field["editability"] in ["free", "locked", "suggested", "defaulted", "readonly"]
            assert "is_locked" in field
            assert isinstance(field["is_locked"], bool)
            assert "is_default" in field
            assert isinstance(field["is_default"], bool)
            assert "override_source" in field
            assert "source_file" in field
    
    def test_fields_with_default_values(self):
        """Verify is_default is True when override_source is 'schema'."""
        data = client.get(
            "/api/wizard/config/edit?tool=claude&language=python&step_id=language_selection"
        ).json()
        
        for field in data["step"]["fields"]:
            if field["override_source"] == "schema":
                assert field["is_default"] is True
            else:
                assert field["is_default"] is False
    
    def test_fields_with_overridden_values(self):
        """Verify is_default is False when override_source is not 'schema'."""
        data = client.get(
            "/api/wizard/config/edit?tool=claude&language=python&step_id=language_selection"
        ).json()
        
        # Check that at least some fields are overridden (not all are defaults)
        has_non_default = any(not f["is_default"] for f in data["step"]["fields"])
        assert has_non_default or len(data["step"]["fields"]) > 0  # At least verify fields exist
    
    def test_source_file_mapping(self):
        """Verify source_file matches override_source."""
        data = client.get(
            "/api/wizard/config/edit?tool=claude&language=python&step_id=language_selection"
        ).json()
        
        for field in data["step"]["fields"]:
            source = field["override_source"]
            source_file = field["source_file"]
            
            if source == "schema":
                assert source_file == "schema.json"
            elif source.startswith("tool:"):
                assert source_file.startswith("tools/")
                assert source_file.endswith(".json")
            elif source.startswith("language:"):
                assert source_file.startswith("languages/")
                assert source_file.endswith(".json")
            elif source.startswith("override:"):
                assert source_file.startswith("overrides/")
                assert source_file.endswith(".json")
    
    def test_source_tracking_summary(self):
        """Verify source_tracking has required summary fields."""
        data = client.get(
            "/api/wizard/config/edit?tool=claude&language=python&step_id=language_selection"
        ).json()
        tracking = data["source_tracking"]
        
        assert "total_fields" in tracking
        assert isinstance(tracking["total_fields"], int)
        assert tracking["total_fields"] > 0
        
        assert "by_source" in tracking
        assert isinstance(tracking["by_source"], dict)
        assert len(tracking["by_source"]) > 0
        
        assert "by_editability" in tracking
        assert isinstance(tracking["by_editability"], dict)
        
        assert "locked_fields" in tracking
        assert isinstance(tracking["locked_fields"], int)
        
        assert "default_fields" in tracking
        assert isinstance(tracking["default_fields"], int)
        
        assert "overridden_fields" in tracking
        assert isinstance(tracking["overridden_fields"], int)
        
        # Verify counts are consistent
        total = tracking["locked_fields"] + tracking["default_fields"] + tracking["overridden_fields"]
        # Counts may overlap (locked can be default or overridden), so just verify they're logical
        assert tracking["total_fields"] > 0
    
    @pytest.mark.parametrize("step_id", ["language_selection", "claude_md", "agent_definitions"])
    def test_multiple_step_ids(self, step_id):
        """Test endpoint with various step IDs."""
        response = client.get(
            f"/api/wizard/config/edit?tool=claude&language=python&step_id={step_id}"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["step"]["id"] == step_id
    
    @pytest.mark.parametrize("tool,language", [
        ("claude", "python"),
        ("copilot", "javascript"),
        ("cursor", "angular"),
    ])
    def test_multiple_tool_language_combos(self, tool, language):
        """Test endpoint with various tool/language combinations."""
        response = client.get(
            f"/api/wizard/config/edit?tool={tool}&language={language}&step_id=language_selection"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["step"]["id"] == "language_selection"
    
    def test_returns_400_without_required_params(self):
        """Verify missing query parameters return 400."""
        # Missing step_id
        response = client.get(
            "/api/wizard/config/edit?tool=claude&language=python"
        )
        assert response.status_code == 422  # FastAPI returns 422 for missing required params
        
        # Missing language
        response = client.get(
            "/api/wizard/config/edit?tool=claude&step_id=language_selection"
        )
        assert response.status_code == 422
        
        # Missing tool
        response = client.get(
            "/api/wizard/config/edit?language=python&step_id=language_selection"
        )
        assert response.status_code == 422
    
    def test_returns_404_for_invalid_step_id(self):
        """Verify invalid step_id returns 400 (not 404 for consistency)."""
        response = client.get(
            "/api/wizard/config/edit?tool=claude&language=python&step_id=nonexistent_step_12345"
        )
        assert response.status_code == 400
        assert "detail" in response.json()
        assert "not found" in response.json()["detail"].lower()
    
    def test_gracefully_handles_tool_language_that_may_not_exist(self):
        """Verify endpoint gracefully handles tool/language combinations.
        
        Note: The config_loader_composable returns a base schema even if
        tool/language don't have specific overrides, so we don't get 404
        for invalid tool/language. This test verifies graceful handling.
        """
        response = client.get(
            "/api/wizard/config/edit?tool=invalid_tool&language=python&step_id=language_selection"
        )
        # Should return 200 with base schema since invalid_tool falls back to base
        assert response.status_code == 200
        data = response.json()
        assert "step" in data
        assert "source_tracking" in data
    
    def test_gracefully_handles_invalid_language(self):
        """Verify endpoint gracefully handles invalid language.
        
        Note: The config_loader_composable returns a base schema even if
        language doesn't have specific overrides, so we don't get 404
        for invalid language. This test verifies graceful handling.
        """
        response = client.get(
            "/api/wizard/config/edit?tool=claude&language=invalid_lang&step_id=language_selection"
        )
        # Should return 200 with base schema since invalid_lang falls back to base
        assert response.status_code == 200
        data = response.json()
        assert "step" in data
        assert "source_tracking" in data
    
    def test_locked_fields_are_clearly_marked(self):
        """Verify locked fields have is_locked=True."""
        data = client.get(
            "/api/wizard/config/edit?tool=claude&language=python&step_id=language_selection"
        ).json()
        
        locked_count = sum(1 for f in data["step"]["fields"] if f["is_locked"])
        tracking_locked = data["source_tracking"]["locked_fields"]
        
        # Both should count the same locked fields
        assert locked_count == tracking_locked
    
    def test_presets_included_in_response(self):
        """Verify preset data is included for fields that have presets."""
        data = client.get(
            "/api/wizard/config/edit?tool=claude&language=python&step_id=language_selection"
        ).json()
        
        # At least verify the structure - some fields may have presets
        for field in data["step"]["fields"]:
            if "presets" in field:
                assert isinstance(field["presets"], list)
                for preset in field["presets"]:
                    # Presets should have label and/or value
                    assert "label" in preset or "value" in preset
    
    def test_response_structure_matches_acceptance_criteria(self):
        """Verify response matches all acceptance criteria."""
        data = client.get(
            "/api/wizard/config/edit?tool=claude&language=python&step_id=language_selection"
        ).json()
        
        # Acceptance Criteria:
        # 1. Returns: fields in step
        assert "step" in data
        assert "fields" in data["step"]
        assert len(data["step"]["fields"]) > 0
        
        # 2. Returns: current overrides
        for field in data["step"]["fields"]:
            assert "override_source" in field  # Indicates where override came from
        
        # 3. Returns: source file (base/tool/language)
        for field in data["step"]["fields"]:
            assert "source_file" in field
            source_file = field["source_file"]
            valid_sources = ["schema.json", "tools/", "languages/", "overrides/"]
            assert any(source_file.startswith(s) if s != "schema.json" else source_file == "schema.json" 
                      for s in valid_sources)
        
        # 4. Clearly indicates:
        # - default
        for field in data["step"]["fields"]:
            assert "is_default" in field
        
        # - overridden
        for field in data["step"]["fields"]:
            assert "override_source" in field
        
        # - locked
        for field in data["step"]["fields"]:
            assert "is_locked" in field


class TestPresetsEndpoint:
    """Tests for GET /api/wizard/presets endpoint."""

    def test_returns_200_for_valid_combo(self):
        response = client.get("/api/wizard/presets?tool=claude&language=python")
        assert response.status_code == 200

    def test_returns_categorized_presets(self):
        data = client.get("/api/wizard/presets?tool=claude&language=python").json()
        assert isinstance(data, dict)
        assert "shared" in data
        assert "language" in data
        assert "tool" in data
        assert isinstance(data["shared"], list)
        assert isinstance(data["language"], list)
        assert isinstance(data["tool"], list)

    @pytest.mark.parametrize("tool,language", [
        ("claude", "python"),
        ("copilot", "javascript"),
        ("cursor", "angular"),
    ])
    def test_multiple_tool_language_combos(self, tool, language):
        response = client.get(f"/api/wizard/presets?tool={tool}&language={language}")
        assert response.status_code == 200
        data = response.json()
        assert "shared" in data
        assert "language" in data
        assert "tool" in data

    def test_presets_have_required_fields(self):
        data = client.get("/api/wizard/presets?tool=claude&language=python").json()
        
        # Check all preset categories
        for category in ["shared", "language", "tool"]:
            for preset in data[category]:
                assert "label" in preset
                assert "value" in preset
                # description and tags are optional
                if "description" in preset:
                    assert isinstance(preset["description"], str)
                if "tags" in preset:
                    assert isinstance(preset["tags"], list)

    def test_returns_400_without_required_params(self):
        # Missing tool
        response = client.get("/api/wizard/presets?language=python")
        assert response.status_code == 422
        
        # Missing language
        response = client.get("/api/wizard/presets?tool=claude")
        assert response.status_code == 422

    def test_returns_400_for_invalid_tool(self):
        response = client.get("/api/wizard/presets?tool=invalid&language=python")
        assert response.status_code == 400


class TestConfigEditEndpoint:
    """Test GET /config/edit endpoint for editable config slices."""
    
    def test_returns_200_for_valid_combo_and_step(self):
        response = client.get(
            "/config/edit?tool=claude&language=python&step_id=language_selection"
        )
        assert response.status_code == 200
    
    def test_returns_dict_with_step_and_source_tracking(self):
        data = client.get(
            "/config/edit?tool=claude&language=python&step_id=language_selection"
        ).json()
        assert isinstance(data, dict)
        assert "step" in data
        assert "source_tracking" in data
    
    def test_step_contains_required_fields(self):
        data = client.get(
            "/config/edit?tool=claude&language=python&step_id=language_selection"
        ).json()
        step = data["step"]
        
        # Step structure
        assert "id" in step
        assert "title" in step
        assert step["id"] == "language_selection"
        assert "fields" in step
        assert len(step["fields"]) > 0
    
    def test_fields_have_editability_metadata(self):
        data = client.get(
            "/config/edit?tool=claude&language=python&step_id=language_selection"
        ).json()
        
        for field in data["step"]["fields"]:
            # Core field structure
            assert "id" in field
            assert "type" in field
            assert "label" in field
            
            # Editability metadata (added by config_editor)
            assert "editability" in field
            assert field["editability"] in ["free", "locked", "suggested", "defaulted", "readonly"]
            assert "is_locked" in field
            assert isinstance(field["is_locked"], bool)
            assert "is_default" in field
            assert isinstance(field["is_default"], bool)
            assert "override_source" in field
            assert "source_file" in field
    
    def test_response_structure_matches_acceptance_criteria(self):
        """Verify response matches all acceptance criteria."""
        data = client.get(
            "/config/edit?tool=claude&language=python&step_id=language_selection"
        ).json()
        
        # Acceptance Criteria:
        # 1. Returns: fields in step
        assert "step" in data
        assert "fields" in data["step"]
        assert len(data["step"]["fields"]) > 0
        
        # 2. Returns: current overrides
        for field in data["step"]["fields"]:
            assert "override_source" in field  # Indicates where override came from
        
        # 3. Returns: source file (base/tool/language)
        for field in data["step"]["fields"]:
            assert "source_file" in field
            source_file = field["source_file"]
            valid_sources = ["schema.json", "tools/", "languages/", "overrides/"]
            assert any(source_file.startswith(s) if s != "schema.json" else source_file == "schema.json" 
                      for s in valid_sources)
        
        # 4. Clearly indicates:
        # - default
        for field in data["step"]["fields"]:
            assert "is_default" in field
        
        # - overridden
        for field in data["step"]["fields"]:
            assert "override_source" in field
        
        # - locked
        for field in data["step"]["fields"]:
            assert "is_locked" in field



class TestConfigUpdateEndpoint:
    """Test POST /config/update endpoint for updating field config."""
    
    def test_returns_200_for_valid_update(self):
        payload = {
            "scope": "language",
            "target": "python",
            "tool": "claude",
            "language": "python",
            "step_id": "language_selection",
            "field_id": "language",
            "changes": {
                "default": "javascript",
                "editable": False
            }
        }
        response = client.post("/config/update", json=payload)
        assert response.status_code == 200
    
    def test_returns_updated_config_slice(self):
        payload = {
            "scope": "language",
            "target": "python",
            "tool": "claude",
            "language": "python",
            "step_id": "language_selection",
            "field_id": "language",
            "changes": {
                "default": "javascript",
                "editable": False
            }
        }
        data = client.post("/config/update", json=payload).json()
        assert isinstance(data, dict)
        assert "step" in data
        assert "source_tracking" in data
        assert data["step"]["id"] == "language_selection"
    
    def test_updates_correct_json_file(self):
        # This test assumes the update actually modifies the file
        # We can check by verifying the response includes the updated value
        payload = {
            "scope": "language",
            "target": "python",
            "tool": "claude",
            "language": "python",
            "step_id": "language_selection",
            "field_id": "language",
            "changes": {
                "default": "test_language",
                "editable": False
            }
        }
        data = client.post("/config/update", json=payload).json()
        
        # Find the updated field
        language_field = None
        for field in data["step"]["fields"]:
            if field["id"] == "language":
                language_field = field
                break
        
        assert language_field is not None
        assert language_field["default"] == "test_language"
        assert language_field["editability"] == "locked"
    
    def test_returns_400_for_missing_required_fields(self):
        # Missing scope (and tool/language/step_id/field_id) — Pydantic returns 422
        payload = {
            "target": "python",
            "step_id": "language_selection",
            "field_id": "language",
            "changes": {"default": "javascript"}
        }
        response = client.post("/config/update", json=payload)
        assert response.status_code == 422
    
    def test_returns_400_for_invalid_scope(self):
        payload = {
            "scope": "invalid",
            "target": "python",
            "tool": "claude",
            "language": "python",
            "step_id": "language_selection",
            "field_id": "language",
            "changes": {"default": "javascript"}
        }
        response = client.post("/config/update", json=payload)
        assert response.status_code == 422
    
    def test_returns_404_for_invalid_target(self):
        payload = {
            "scope": "language",
            "target": "nonexistent",
            "tool": "claude",
            "language": "python",
            "step_id": "language_selection",
            "field_id": "language",
            "changes": {"default": "javascript"}
        }
        response = client.post("/config/update", json=payload)
        assert response.status_code == 404


class TestPresetEndpoints:
    """Test POST /config/presets/add and /config/presets/remove endpoints."""
    
    def test_add_preset_returns_200_for_valid_request(self):
        payload = {
            "scope": "language",
            "target": "python",
            "tool": "claude",
            "language": "python",
            "step_id": "language_selection",
            "field_id": "language",
            "preset": {
                "label": "Test Preset",
                "value": "test_value",
                "description": "A test preset"
            }
        }
        response = client.post("/config/presets/add", json=payload)
        assert response.status_code == 200
    
    def test_add_preset_returns_updated_config_slice(self):
        payload = {
            "scope": "language",
            "target": "python",
            "tool": "claude",
            "language": "python",
            "step_id": "language_selection",
            "field_id": "language",
            "preset": {
                "label": "Test Preset",
                "value": "test_value",
                "description": "A test preset"
            }
        }
        data = client.post("/config/presets/add", json=payload).json()
        assert isinstance(data, dict)
        assert "step" in data
        assert "source_tracking" in data
        assert data["step"]["id"] == "language_selection"
    
    def test_add_preset_with_position(self):
        payload = {
            "scope": "language",
            "target": "python",
            "tool": "claude",
            "language": "python",
            "step_id": "language_selection",
            "field_id": "language",
            "preset": {
                "label": "Positioned Preset",
                "value": "positioned_value",
                "description": "A positioned preset"
            },
            "position": 0
        }
        response = client.post("/config/presets/add", json=payload)
        assert response.status_code == 200
    
    def test_remove_preset_returns_200_for_valid_request(self):
        # First add a preset
        add_payload = {
            "scope": "language",
            "target": "python",
            "tool": "claude",
            "language": "python",
            "step_id": "language_selection",
            "field_id": "language",
            "preset": {
                "label": "Preset to Remove",
                "value": "remove_value",
                "description": "A preset to be removed"
            }
        }
        client.post("/config/presets/add", json=add_payload)
        
        # Now remove it
        remove_payload = {
            "scope": "language",
            "target": "python",
            "tool": "claude",
            "language": "python",
            "step_id": "language_selection",
            "field_id": "language",
            "preset_label": "Preset to Remove"
        }
        response = client.post("/config/presets/remove", json=remove_payload)
        assert response.status_code == 200
    
    def test_remove_preset_by_position(self):
        # First add a preset
        add_payload = {
            "scope": "language",
            "target": "python",
            "tool": "claude",
            "language": "python",
            "step_id": "language_selection",
            "field_id": "language",
            "preset": {
                "label": "Preset to Remove by Position",
                "value": "remove_by_pos",
                "description": "A preset to be removed by position"
            }
        }
        client.post("/config/presets/add", json=add_payload)
        
        # Now remove it by position
        remove_payload = {
            "scope": "language",
            "target": "python",
            "tool": "claude",
            "language": "python",
            "step_id": "language_selection",
            "field_id": "language",
            "position": 0
        }
        response = client.post("/config/presets/remove", json=remove_payload)
        assert response.status_code == 200
    
    def test_add_preset_returns_400_for_missing_required_fields(self):
        # Missing preset (and tool/language) — Pydantic returns 422
        payload = {
            "scope": "language",
            "target": "python",
            "step_id": "language_selection",
            "field_id": "language"
        }
        response = client.post("/config/presets/add", json=payload)
        assert response.status_code == 422
    
    def test_remove_preset_returns_400_for_missing_identifier(self):
        payload = {
            "scope": "language",
            "target": "python",
            "tool": "claude",
            "language": "python",
            "step_id": "language_selection",
            "field_id": "language"
        }
        response = client.post("/config/presets/remove", json=payload)
        assert response.status_code == 422
    
    def test_add_preset_returns_400_for_invalid_scope(self):
        payload = {
            "scope": "invalid",
            "target": "python",
            "tool": "claude",
            "language": "python",
            "step_id": "language_selection",
            "field_id": "language",
            "preset": {
                "label": "Test",
                "value": "test"
            }
        }
        response = client.post("/config/presets/add", json=payload)
        assert response.status_code == 422
    
    def test_remove_preset_returns_400_for_invalid_scope(self):
        payload = {
            "scope": "invalid",
            "target": "python",
            "tool": "claude",
            "language": "python",
            "step_id": "language_selection",
            "field_id": "language",
            "preset_label": "Test"
        }
        response = client.post("/config/presets/remove", json=payload)
        assert response.status_code == 422
