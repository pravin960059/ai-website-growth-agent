from dataclasses import dataclass

from .crawler import PageData


@dataclass
class FindingCandidate:
    category: str
    severity: str
    confidence: float
    title: str
    description: str
    recommendation: str
    quote: str
    action_type: str
    payload: dict


def analyze_page(page: PageData) -> list[FindingCandidate]:
    findings: list[FindingCandidate] = []
    if not page.title:
        findings.append(
            FindingCandidate(
                category="seo",
                severity="medium",
                confidence=0.99,
                title="Missing page title",
                description="The page does not expose a document title for search engines or browser tabs.",
                recommendation="Create a concise title aligned to the page's primary search intent.",
                quote=f"URL: {page.url}",
                action_type="update_metadata",
                payload={"url": page.url, "field": "title", "suggested_value": ""},
            )
        )
    elif len(page.title) > 60:
        findings.append(
            FindingCandidate(
                category="seo",
                severity="low",
                confidence=0.96,
                title="Title may be too long",
                description="The title is longer than the common display budget used as a practical review heuristic.",
                recommendation="Review the title for unnecessary words while preserving the primary intent.",
                quote=f"Title: {page.title}",
                action_type="draft_only",
                payload={"url": page.url, "field": "title", "current_value": page.title},
            )
        )
    if not page.meta_description:
        findings.append(
            FindingCandidate(
                category="seo",
                severity="low",
                confidence=0.98,
                title="Missing meta description",
                description="The page has no meta description that can help describe the result in search previews.",
                recommendation="Draft a direct description that states the page value and matches its intent.",
                quote=f"URL: {page.url}",
                action_type="update_metadata",
                payload={"url": page.url, "field": "description", "suggested_value": ""},
            )
        )
    if page.h1_count == 0:
        findings.append(
            FindingCandidate(
                category="seo",
                severity="medium",
                confidence=0.99,
                title="Missing H1 heading",
                description="The page has no H1 heading that clearly identifies its primary topic.",
                recommendation="Add one descriptive H1 that matches the page purpose and user intent.",
                quote=f"H1 count: {page.h1_count}",
                action_type="draft_only",
                payload={"url": page.url, "field": "h1", "suggested_value": ""},
            )
        )
    elif page.h1_count > 1:
        findings.append(
            FindingCandidate(
                category="seo",
                severity="low",
                confidence=0.94,
                title="Multiple H1 headings",
                description="The page contains multiple H1 headings and should be reviewed for a clear primary topic.",
                recommendation="Keep one primary H1 and demote unrelated headings where appropriate.",
                quote=f"H1 count: {page.h1_count}",
                action_type="draft_only",
                payload={"url": page.url, "field": "h1_count", "current_value": page.h1_count},
            )
        )
    if page.noindex:
        findings.append(
            FindingCandidate(
                category="seo",
                severity="high",
                confidence=0.99,
                title="Page is marked noindex",
                description="A robots directive asks crawlers not to index this page.",
                recommendation="Confirm that the noindex directive is intentional before changing it.",
                quote="robots meta contains noindex",
                action_type="draft_only",
                payload={"url": page.url, "field": "robots", "current_value": "noindex"},
            )
        )
    if not page.canonical:
        findings.append(
            FindingCandidate(
                category="seo",
                severity="low",
                confidence=0.97,
                title="Missing canonical URL",
                description="The page does not declare a canonical URL.",
                recommendation="Review whether this page needs a self-referencing or intentional canonical URL.",
                quote=f"URL: {page.url}",
                action_type="draft_only",
                payload={"url": page.url, "field": "canonical", "suggested_value": page.url},
            )
        )
    if not page.structured_data_count:
        findings.append(
            FindingCandidate(
                category="geo",
                severity="low",
                confidence=0.88,
                title="No JSON-LD structured data detected",
                description="No JSON-LD block was detected in the fetched page.",
                recommendation="Assess whether a relevant schema type would clarify the page entity or answer intent.",
                quote="JSON-LD script count: 0",
                action_type="draft_only",
                payload={"url": page.url, "field": "structured_data", "suggested_value": ""},
            )
        )
    return findings
