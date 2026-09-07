from __future__ import annotations

import hashlib
import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urldefrag, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from .settings import Settings


@dataclass
class PageData:
    url: str
    status_code: int
    title: str
    meta_description: str
    canonical: str
    h1_count: int
    structured_data_count: int
    noindex: bool
    content: str
    content_hash: str
    links: list[str]


def _is_private_host(hostname: str) -> bool:
    if hostname.lower() in {"localhost", "localhost.localdomain"}:
        return True
    try:
        addresses = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        return False
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
            return True
    return False


def validate_public_url(url: str, allow_private_urls: bool = False) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Only http and https URLs with a hostname are allowed")
    if not allow_private_urls and _is_private_host(parsed.hostname):
        raise ValueError("Private, loopback, link-local, or reserved hosts are not allowed")
    return url.rstrip("/")


def _same_site(url: str, root_host: str) -> bool:
    hostname = (urlparse(url).hostname or "").lower()
    root_host = root_host.lower()
    return hostname == root_host or hostname.endswith(f".{root_host}")


def parse_page(url: str, status_code: int, html: str, root_host: str) -> PageData:
    soup = BeautifulSoup(html, "html.parser")
    structured_data_count = len(soup.find_all("script", type="application/ld+json"))
    for element in soup(["script", "style", "noscript", "template"]):
        element.decompose()

    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    description_tag = soup.find("meta", attrs={"name": lambda value: value and value.lower() == "description"})
    canonical_tag = soup.find("link", rel=lambda value: value and "canonical" in value)
    robots_tag = soup.find("meta", attrs={"name": lambda value: value and value.lower() == "robots"})
    content = " ".join(soup.get_text(" ", strip=True).split())
    links: list[str] = []
    for anchor in soup.find_all("a", href=True):
        candidate, _ = urldefrag(urljoin(url, anchor["href"]))
        parsed = urlparse(candidate)
        if parsed.scheme in {"http", "https"} and _same_site(candidate, root_host):
            links.append(candidate.rstrip("/"))

    return PageData(
        url=url,
        status_code=status_code,
        title=title,
        meta_description=description_tag.get("content", "").strip() if description_tag else "",
        canonical=canonical_tag.get("href", "").strip() if canonical_tag else "",
        h1_count=len(soup.find_all("h1")),
        structured_data_count=structured_data_count,
        noindex="noindex" in (robots_tag.get("content", "").lower() if robots_tag else ""),
        content=content,
        content_hash=hashlib.sha256(html.encode("utf-8", errors="ignore")).hexdigest(),
        links=list(dict.fromkeys(links)),
    )


async def crawl_site(start_url: str, settings: Settings) -> list[PageData]:
    start_url = validate_public_url(start_url, settings.allow_private_urls)
    root_host = urlparse(start_url).hostname or ""
    queue = [start_url]
    visited: set[str] = set()
    pages: list[PageData] = []
    total_bytes = 0

    timeout = httpx.Timeout(settings.crawl_timeout_seconds)
    headers = {"User-Agent": "AIWebsiteGrowthAgent/0.1 (+https://example.invalid/bot)"}
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, headers=headers) as client:
        while queue and len(pages) < settings.max_pages_per_audit:
            url = queue.pop(0)
            if url in visited:
                continue
            visited.add(url)
            try:
                validate_public_url(url, settings.allow_private_urls)
                response = await client.get(url)
                content_type = response.headers.get("content-type", "").lower()
                if "text/html" not in content_type:
                    continue
                body = response.content
                total_bytes += len(body)
                if total_bytes > settings.max_crawl_bytes:
                    break
                page = parse_page(str(response.url), response.status_code, body.decode("utf-8", errors="replace"), root_host)
                pages.append(page)
                for link in page.links:
                    if link not in visited and len(queue) + len(pages) < settings.max_pages_per_audit:
                        queue.append(link)
            except (httpx.HTTPError, ValueError):
                continue
    return pages
