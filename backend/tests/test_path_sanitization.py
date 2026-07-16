"""Tests for Ticket 14: Output path sanitisation in file_generator."""
import pytest
from app.services.file_generator import _sanitize_output_filename


class TestSanitizeOutputFilename:
    def test_valid_filename_passes(self):
        assert _sanitize_output_filename("my-file.md") == "my-file.md"

    def test_strips_whitespace(self):
        assert _sanitize_output_filename("  file.txt  ") == "file.txt"

    def test_empty_raises(self):
        with pytest.raises(ValueError, match="empty"):
            _sanitize_output_filename("")

    def test_whitespace_only_raises(self):
        with pytest.raises(ValueError, match="empty"):
            _sanitize_output_filename("   ")

    def test_absolute_path_raises(self):
        with pytest.raises(ValueError, match="absolute"):
            _sanitize_output_filename("/etc/passwd")

    def test_dotdot_raises(self):
        with pytest.raises(ValueError, match=r"\.\."): 
            _sanitize_output_filename("../secrets.txt")

    def test_dotdot_in_middle_raises(self):
        with pytest.raises(ValueError, match=r"\.\."):
            _sanitize_output_filename("foo/../bar.txt")

    def test_null_byte_raises(self):
        with pytest.raises(ValueError, match="null"):
            _sanitize_output_filename("file\x00name.txt")

    def test_windows_drive_prefix_raises(self):
        with pytest.raises(ValueError, match="drive"):
            _sanitize_output_filename("C:\\path\\file.txt")

    def test_forward_slash_raises(self):
        with pytest.raises(ValueError, match="separator"):
            _sanitize_output_filename("subdir/file.txt")

    def test_backslash_raises(self):
        with pytest.raises(ValueError, match="separator"):
            _sanitize_output_filename("subdir\\file.txt")

    def test_simple_dotdot_raises(self):
        with pytest.raises(ValueError):
            _sanitize_output_filename("..")

    def test_dot_filename_passes(self):
        # A single dot is unusual but not a path traversal
        result = _sanitize_output_filename(".")
        assert result == "."

    def test_filename_with_extension_passes(self):
        assert _sanitize_output_filename("copilot-instructions.md") == "copilot-instructions.md"
