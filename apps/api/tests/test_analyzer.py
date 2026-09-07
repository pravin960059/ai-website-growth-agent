from app.analyzer import analyze_page
from app.crawler import PageData


def page(**overrides) -> PageData:
    values = {
        "url": "https://example.com/pricing",
        "status_code": 200,
        "title": "",
        "meta_description": "",
        "canonical": "",
        "h1_count": 0,
        "structured_data_count": 0,
        "noindex": False,
        "content": "Pricing content",
        "content_hash": "hash",
        "links": [],
    }
    values.update(overrides)
    return PageData(**values)


def test_missing_metadata_creates_evidence_backed_findings():
    findings = analyze_page(page())
    titles = {finding.title for finding in findings}

    assert "Missing page title" in titles
    assert "Missing meta description" in titles
    assert "Missing H1 heading" in titles
    assert all(finding.confidence > 0.8 for finding in findings)


def test_valid_page_has_no_basic_metadata_findings():
    findings = analyze_page(
        page(
            title="Pricing for growth teams",
            meta_description="Plans for growing websites.",
            canonical="https://example.com/pricing",
            h1_count=1,
            structured_data_count=1,
        )
    )

    assert findings == []
