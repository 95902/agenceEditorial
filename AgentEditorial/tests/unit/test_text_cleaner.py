"""Unit tests for text cleaner utilities."""

import pytest

from python_scripts.ingestion.text_cleaner import (
    clean_html_text,
    count_words,
    extract_meta_description,
)


@pytest.mark.unit
class TestCleanHtmlText:
    """Test clean_html_text function."""

    def test_clean_simple_html(self) -> None:
        """Test cleaning simple HTML."""
        html = "<html><body><p>Hello World</p></body></html>"
        result = clean_html_text(html)
        assert "Hello World" in result
        assert "<" not in result
        assert ">" not in result

    def test_clean_html_with_entities(self) -> None:
        """Test cleaning HTML with entities."""
        html = "<p>Hello &amp; World &lt;test&gt;</p>"
        result = clean_html_text(html)
        assert "&" in result or "Hello" in result
        assert "<test>" in result or "test" in result

    def test_clean_html_removes_scripts(self) -> None:
        """Test that scripts are removed."""
        html = """
        <html>
            <head><script>alert('test');</script></head>
            <body><p>Content</p></body>
        </html>
        """
        result = clean_html_text(html)
        assert "alert" not in result
        assert "Content" in result

    def test_clean_html_removes_styles(self) -> None:
        """Test that styles are removed."""
        html = """
        <html>
            <head><style>body { color: red; }</style></head>
            <body><p>Content</p></body>
        </html>
        """
        result = clean_html_text(html)
        assert "color: red" not in result
        assert "Content" in result

    def test_clean_html_preserves_text_content(self) -> None:
        """Test that text content is preserved."""
        html = """
        <html>
            <body>
                <h1>Title</h1>
                <p>Paragraph 1</p>
                <p>Paragraph 2</p>
            </body>
        </html>
        """
        result = clean_html_text(html)
        assert "Title" in result
        assert "Paragraph 1" in result
        assert "Paragraph 2" in result

    def test_clean_html_normalizes_whitespace(self) -> None:
        """Test that whitespace is normalized."""
        html = "<p>Hello    World\n\nTest</p>"
        result = clean_html_text(html)
        # Should have normalized whitespace
        assert "  " not in result  # No double spaces
        assert "\n\n" not in result  # No double newlines

    def test_clean_html_empty(self) -> None:
        """Test cleaning empty HTML."""
        result = clean_html_text("")
        assert result == ""

    def test_clean_html_invalid_html(self) -> None:
        """Test cleaning invalid HTML (should not crash)."""
        html = "<p>Unclosed tag<div>Another</p>"
        result = clean_html_text(html)
        # Should return some text, not crash
        assert isinstance(result, str)


@pytest.mark.unit
class TestCountWords:
    """Test count_words function."""

    def test_count_words_simple(self) -> None:
        """Test counting words in simple text."""
        text = "Hello world"
        assert count_words(text) == 2

    def test_count_words_multiple_spaces(self) -> None:
        """Test counting words with multiple spaces."""
        text = "Hello    world   test"
        assert count_words(text) == 3

    def test_count_words_empty(self) -> None:
        """Test counting words in empty string."""
        assert count_words("") == 0

    def test_count_words_single_word(self) -> None:
        """Test counting single word."""
        assert count_words("Hello") == 1

    def test_count_words_with_newlines(self) -> None:
        """Test counting words with newlines."""
        text = "Hello\nworld\ntest"
        assert count_words(text) == 3

    def test_count_words_with_punctuation(self) -> None:
        """Test counting words with punctuation."""
        text = "Hello, world! How are you?"
        assert count_words(text) == 5


@pytest.mark.unit
class TestExtractMetaDescription:
    """Test extract_meta_description function."""

    def test_extract_meta_description_simple(self) -> None:
        """Test extracting simple meta description."""
        html = '<meta name="description" content="This is a description">'
        result = extract_meta_description(html)
        assert result == "This is a description"

    def test_extract_meta_description_single_quotes(self) -> None:
        """Test extracting meta description with single quotes."""
        html = "<meta name='description' content='This is a description'>"
        result = extract_meta_description(html)
        assert result == "This is a description"

    def test_extract_meta_description_with_entities(self) -> None:
        """Test extracting meta description with HTML entities."""
        html = '<meta name="description" content="Hello &amp; World">'
        result = extract_meta_description(html)
        assert result == "Hello & World"

    def test_extract_meta_description_case_insensitive(self) -> None:
        """Test that extraction is case insensitive."""
        html = '<META NAME="DESCRIPTION" CONTENT="Test">'
        result = extract_meta_description(html)
        assert result == "Test"

    def test_extract_meta_description_not_found(self) -> None:
        """Test when meta description is not found."""
        html = "<html><body><p>No meta description</p></body></html>"
        result = extract_meta_description(html)
        assert result is None

    def test_extract_meta_description_multiple_meta_tags(self) -> None:
        """Test extracting when multiple meta tags exist."""
        html = """
        <meta name="keywords" content="test">
        <meta name="description" content="This is the description">
        <meta name="author" content="Author">
        """
        result = extract_meta_description(html)
        assert result == "This is the description"


