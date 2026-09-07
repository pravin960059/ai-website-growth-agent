import pytest

from app.crawler import parse_page, validate_public_url


def test_parser_extracts_structured_page_signals():
    html = """
    <html><head>
      <title>Pricing</title>
      <meta name="description" content="Plans for teams">
      <link rel="canonical" href="https://example.com/pricing">
      <script type="application/ld+json">{"@type":"Product"}</script>
    </head><body><h1>Plans</h1><a href="/about">About</a></body></html>
    """

    page = parse_page("https://example.com/pricing", 200, html, "example.com")

    assert page.title == "Pricing"
    assert page.h1_count == 1
    assert page.structured_data_count == 1
    assert page.links == ["https://example.com/about"]


def test_private_hosts_are_rejected_by_default():
    with pytest.raises(ValueError):
        validate_public_url("http://localhost:8000")


def test_public_url_is_normalized():
    assert validate_public_url("https://example.com/") == "https://example.com"
