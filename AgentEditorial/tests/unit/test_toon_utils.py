"""Unit tests for TOON utilities."""

import pytest
from unittest.mock import patch

from python_scripts.utils.toon_utils import (
    is_toon_available,
    json_to_toon,
    toon_to_json,
    safe_json_to_toon,
    estimate_token_savings,
)


class TestToonAvailability:
    """Test TOON library availability detection."""

    def test_is_toon_available(self):
        """Test that we can check if TOON is available."""
        # This should return True or False depending on whether toons is installed
        result = is_toon_available()
        assert isinstance(result, bool)


class TestJsonToToon:
    """Test JSON to TOON conversion."""

    @pytest.mark.unit
    def test_json_to_toon_with_list_of_dicts(self):
        """Test converting a list of dictionaries to TOON format."""
        # Skip if toons library is not available
        if not is_toon_available():
            pytest.skip("toons library not installed")

        data = [
            {"id": 1, "title": "Article 1", "effort": "medium"},
            {"id": 2, "title": "Article 2", "effort": "high"},
            {"id": 3, "title": "Article 3", "effort": "low"},
        ]

        result = json_to_toon(data)

        # TOON should be a string
        assert isinstance(result, str)
        # TOON should be shorter than JSON
        import json
        json_str = json.dumps(data, ensure_ascii=False)
        assert len(result) < len(json_str)

    @pytest.mark.unit
    def test_json_to_toon_with_dict(self):
        """Test converting a dictionary to TOON format."""
        if not is_toon_available():
            pytest.skip("toons library not installed")

        data = {
            "name": "Test",
            "value": 42,
            "active": True,
        }

        result = json_to_toon(data)
        assert isinstance(result, str)

    @pytest.mark.unit
    def test_json_to_toon_raises_import_error_when_not_installed(self):
        """Test that ImportError is raised when toons is not installed."""
        with patch("python_scripts.utils.toon_utils.TOONS_AVAILABLE", False):
            with pytest.raises(ImportError, match="toons library is required"):
                json_to_toon({"test": "data"})


class TestToonToJson:
    """Test TOON to JSON conversion."""

    @pytest.mark.unit
    def test_toon_to_json_roundtrip(self):
        """Test that data can be converted to TOON and back to JSON."""
        if not is_toon_available():
            pytest.skip("toons library not installed")

        original_data = [
            {"id": 1, "title": "Article 1"},
            {"id": 2, "title": "Article 2"},
        ]

        # Convert to TOON and back
        toon_str = json_to_toon(original_data)
        result = toon_to_json(toon_str)

        # Should get back the same structure
        assert result == original_data

    @pytest.mark.unit
    def test_toon_to_json_raises_import_error_when_not_installed(self):
        """Test that ImportError is raised when toons is not installed."""
        with patch("python_scripts.utils.toon_utils.TOONS_AVAILABLE", False):
            with pytest.raises(ImportError, match="toons library is required"):
                toon_to_json("id title\n1 Test")


class TestSafeJsonToToon:
    """Test safe JSON to TOON conversion with fallback."""

    @pytest.mark.unit
    def test_safe_json_to_toon_with_toons_available(self):
        """Test safe conversion when TOON is available."""
        if not is_toon_available():
            pytest.skip("toons library not installed")

        data = [{"id": 1, "name": "Test"}]
        result = safe_json_to_toon(data, fallback_to_json=True)

        # Should return a string
        assert isinstance(result, str)
        # Should not be empty
        assert len(result) > 0

    @pytest.mark.unit
    def test_safe_json_to_toon_fallback_to_json(self):
        """Test that it falls back to JSON when TOON is not available."""
        import json

        data = [{"id": 1, "name": "Test"}]

        with patch("python_scripts.utils.toon_utils.TOONS_AVAILABLE", False):
            result = safe_json_to_toon(data, fallback_to_json=True)

            # Should return JSON string
            assert isinstance(result, str)
            # Should be valid JSON
            parsed = json.loads(result)
            assert parsed == data

    @pytest.mark.unit
    def test_safe_json_to_toon_no_fallback(self):
        """Test that it returns empty string when fallback is disabled."""
        with patch("python_scripts.utils.toon_utils.TOONS_AVAILABLE", False):
            result = safe_json_to_toon({"test": "data"}, fallback_to_json=False)
            assert result == ""


class TestEstimateTokenSavings:
    """Test token savings estimation."""

    @pytest.mark.unit
    def test_estimate_token_savings_with_toons_available(self):
        """Test token savings estimation when TOON is available."""
        if not is_toon_available():
            pytest.skip("toons library not installed")

        data = [
            {"id": 1, "title": "Article 1", "effort": "medium"},
            {"id": 2, "title": "Article 2", "effort": "high"},
            {"id": 3, "title": "Article 3", "effort": "low"},
        ]

        stats = estimate_token_savings(data)

        # Should return statistics
        assert "json_length" in stats
        assert "toon_length" in stats
        assert "savings_chars" in stats
        assert "savings_percent" in stats
        assert "toon_available" in stats

        # TOON should be shorter
        assert stats["toon_length"] < stats["json_length"]
        assert stats["savings_chars"] > 0
        assert stats["savings_percent"] > 0

    @pytest.mark.unit
    def test_estimate_token_savings_without_toons(self):
        """Test token savings estimation when TOON is not available."""
        with patch("python_scripts.utils.toon_utils.TOONS_AVAILABLE", False):
            data = [{"id": 1, "name": "Test"}]
            stats = estimate_token_savings(data)

            # Should still return stats but with zeros
            assert stats["toon_available"] is False
            assert stats["toon_length"] == 0
            assert stats["savings_chars"] == 0
            assert stats["savings_percent"] == 0.0


class TestToonFormatterIntegration:
    """Integration tests for TOON formatter."""

    @pytest.mark.unit
    def test_toon_formatter_creation(self):
        """Test that ToonFormatter can be created."""
        from python_scripts.agents.utils.toon_formatter import create_toon_formatter

        formatter = create_toon_formatter(enable_toon=True, log_savings=False)
        assert formatter is not None

    @pytest.mark.unit
    def test_format_for_prompt(self):
        """Test formatting data for LLM prompts."""
        from python_scripts.agents.utils.toon_formatter import create_toon_formatter

        if not is_toon_available():
            pytest.skip("toons library not installed")

        formatter = create_toon_formatter(enable_toon=True, log_savings=False)

        data = [
            {"id": 1, "title": "Article 1"},
            {"id": 2, "title": "Article 2"},
        ]

        result = formatter.format_for_prompt(data, label="Articles")

        # Should return a string
        assert isinstance(result, str)
        # Should contain the label
        assert "Articles" in result

    @pytest.mark.unit
    def test_format_article_list(self):
        """Test formatting article list."""
        from python_scripts.agents.utils.toon_formatter import create_toon_formatter

        if not is_toon_available():
            pytest.skip("toons library not installed")

        formatter = create_toon_formatter(enable_toon=True, log_savings=False)

        articles = [
            {"id": 1, "title": "Article 1", "hook": "Hook 1", "effort": "medium"},
            {"id": 2, "title": "Article 2", "hook": "Hook 2", "effort": "high"},
        ]

        result = formatter.format_article_list(articles, include_fields=["id", "title", "effort"])

        # Should return a string
        assert isinstance(result, str)
        # Should contain Articles label
        assert "Articles" in result
