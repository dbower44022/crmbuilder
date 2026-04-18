"""Automated CRM platform research via web fetching and Claude API.

Fetches a CRM platform's website, discovers documentation and pricing
pages, and uses the Claude API to generate a structured YAML profile
conforming to the platform comparison schema.
"""

import datetime
import logging
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Callable
from urllib.parse import urljoin, urlparse

import requests
import yaml

logger = logging.getLogger(__name__)

_FETCH_TIMEOUT = 15
_MAX_TEXT_LENGTH = 15_000
_MAX_DISCOVERED_LINKS = 3
_LINK_KEYWORDS = ("api", "developer", "pricing", "docs", "documentation", "rest", "integration")
_USER_AGENT = "CRMBuilder/1.0 (platform-research)"
_CLAUDE_MODEL = "claude-sonnet-4-20250514"
_CLAUDE_MAX_TOKENS = 8192


@dataclass
class PlatformResearchResult:
    """Result of a platform research operation."""

    success: bool
    yaml_content: str = ""
    yaml_data: dict | None = None
    slug: str = ""
    name: str = ""
    is_update: bool = False
    validation_warnings: list[str] = field(default_factory=list)
    error: str = ""
    pages_fetched: int = 0


class _TextExtractor(HTMLParser):
    """Extract visible text from HTML, stripping tags and scripts."""

    def __init__(self) -> None:
        super().__init__()
        self._text: list[str] = []
        self._skip = False

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in ("script", "style", "noscript"):
            self._skip = True

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style", "noscript"):
            self._skip = False

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self._text.append(data)

    def get_text(self) -> str:
        raw = " ".join(self._text)
        return re.sub(r"\s+", " ", raw).strip()


class _LinkExtractor(HTMLParser):
    """Extract href values from anchor tags."""

    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag == "a":
            for name, value in attrs:
                if name == "href" and value:
                    self.links.append(value)


class PlatformResearcher:
    """Research a CRM platform and generate a YAML profile.

    :param api_key: Anthropic API key.
    :param schema_path: Path to schema.yaml.
    :param example_path: Path to an example platform YAML (e.g., espocrm.yaml).
    :param platforms_dir: Path to the platforms directory.
    :param callback: Optional ``(message, level)`` callback for progress logs.
    """

    def __init__(
        self,
        api_key: str,
        schema_path: Path,
        example_path: Path,
        platforms_dir: Path,
        callback: Callable[[str, str], None] | None = None,
    ) -> None:
        self._api_key = api_key
        self._schema_path = schema_path
        self._example_path = example_path
        self._platforms_dir = platforms_dir
        self._log = callback or (lambda msg, level: None)

    def research(
        self,
        url: str,
        existing_yaml: str | None = None,
        api_docs_url: str | None = None,
    ) -> PlatformResearchResult:
        """Run the full research pipeline.

        :param url: CRM platform URL to research.
        :param existing_yaml: Existing YAML content if updating.
        :param api_docs_url: Optional API documentation URL.
        :returns: Research result with generated YAML.
        """
        # 1. Fetch main page
        self._log(f"Fetching {url}...", "info")
        main_html = self._fetch_page(url)
        if main_html is None:
            return PlatformResearchResult(
                success=False, error=f"Could not fetch {url}"
            )

        web_content: dict[str, str] = {url: self._extract_text(main_html)}
        pages_fetched = 1

        # 1b. Fetch API docs page if provided
        if api_docs_url:
            self._log(f"Fetching API docs: {api_docs_url}...", "info")
            docs_html = self._fetch_page(api_docs_url)
            if docs_html:
                web_content[api_docs_url] = self._extract_text(docs_html)
                pages_fetched += 1
            else:
                self._log(f"Could not fetch API docs URL, continuing.", "warn")

        # 2. Discover related pages
        self._log("Discovering documentation and pricing links...", "info")
        discovered = self._discover_links(main_html, url)
        # Exclude the API docs URL if already fetched
        if api_docs_url:
            discovered = [
                d for d in discovered
                if d.rstrip("/") != api_docs_url.rstrip("/")
            ]
        if discovered:
            self._log(
                f"Found {len(discovered)} related link(s): "
                + ", ".join(discovered),
                "info",
            )
        else:
            self._log("No additional links discovered.", "info")

        for link in discovered:
            self._log(f"Fetching {link}...", "info")
            html = self._fetch_page(link)
            if html:
                web_content[link] = self._extract_text(html)
                pages_fetched += 1
            else:
                self._log(f"Could not fetch {link}, skipping.", "warn")

        # 3. Build prompt and call Claude
        self._log("Sending to Claude API for analysis...", "info")
        messages = self._build_prompt(web_content, existing_yaml)
        raw_yaml = self._call_claude(messages)
        if raw_yaml is None:
            return PlatformResearchResult(
                success=False,
                error="Claude API call failed",
                pages_fetched=pages_fetched,
            )

        # 4. Parse and validate
        self._log("Parsing generated YAML...", "info")
        parsed, warnings = self._parse_and_validate(raw_yaml)
        if parsed is None:
            return PlatformResearchResult(
                success=False,
                error="Could not parse Claude's response as valid YAML",
                yaml_content=raw_yaml,
                pages_fetched=pages_fetched,
            )

        slug = parsed.get("slug", "")
        name = parsed.get("name", "")
        is_update = (self._platforms_dir / f"{slug}.yaml").exists()

        if warnings:
            for w in warnings:
                self._log(f"Warning: {w}", "warn")

        self._log(
            f"Research complete: {name} ({slug}), "
            f"{'update' if is_update else 'new platform'}",
            "info",
        )

        return PlatformResearchResult(
            success=True,
            yaml_content=raw_yaml,
            yaml_data=parsed,
            slug=slug,
            name=name,
            is_update=is_update,
            validation_warnings=warnings,
            pages_fetched=pages_fetched,
        )

    def _fetch_page(self, url: str) -> str | None:
        """Fetch a URL and return the HTML content.

        :param url: URL to fetch.
        :returns: HTML string or None on failure.
        """
        try:
            resp = requests.get(
                url,
                timeout=_FETCH_TIMEOUT,
                headers={"User-Agent": _USER_AGENT},
                allow_redirects=True,
            )
            resp.raise_for_status()
            return resp.text
        except requests.RequestException as exc:
            logger.warning("Failed to fetch %s: %s", url, exc)
            self._log(f"Fetch error for {url}: {exc}", "error")
            return None

    def _discover_links(self, html: str, base_url: str) -> list[str]:
        """Find relevant documentation/pricing links in the HTML.

        :param html: HTML content to scan.
        :param base_url: Base URL for resolving relative links.
        :returns: List of discovered URLs (max 3, same domain).
        """
        parser = _LinkExtractor()
        try:
            parser.feed(html)
        except Exception:
            return []

        base_domain = urlparse(base_url).netloc.lower()
        seen: set[str] = set()
        results: list[str] = []

        for href in parser.links:
            absolute = urljoin(base_url, href)
            parsed = urlparse(absolute)

            # Same domain only
            if parsed.netloc.lower() != base_domain:
                continue

            # Strip fragments and query for dedup
            clean = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            if clean in seen or clean.rstrip("/") == base_url.rstrip("/"):
                continue

            # Check for keyword match
            href_lower = href.lower()
            if any(kw in href_lower for kw in _LINK_KEYWORDS):
                seen.add(clean)
                results.append(clean)
                if len(results) >= _MAX_DISCOVERED_LINKS:
                    break

        return results

    def _extract_text(self, html: str) -> str:
        """Extract visible text from HTML, truncated.

        :param html: HTML content.
        :returns: Plain text, max ``_MAX_TEXT_LENGTH`` characters.
        """
        parser = _TextExtractor()
        try:
            parser.feed(html)
        except Exception:
            return ""
        text = parser.get_text()
        if len(text) > _MAX_TEXT_LENGTH:
            text = text[:_MAX_TEXT_LENGTH] + "\n[truncated]"
        return text

    def _build_prompt(
        self,
        web_content: dict[str, str],
        existing_yaml: str | None,
    ) -> list[dict]:
        """Build the Claude API messages.

        :param web_content: Mapping of URL → extracted text.
        :param existing_yaml: Existing YAML if updating.
        :returns: Messages list for the Claude API.
        """
        schema_text = self._schema_path.read_text(encoding="utf-8")
        example_text = self._example_path.read_text(encoding="utf-8")
        today = datetime.date.today().isoformat()

        system = (
            "You are a CRM platform analyst. Your job is to research CRM "
            "platforms and produce structured YAML profiles describing their "
            "API capabilities.\n\n"
            "You will be given:\n"
            "1. A YAML schema defining all fields and capability dimensions\n"
            "2. An example platform YAML file showing the expected structure\n"
            "3. Web content from the platform's website and documentation\n\n"
            "Produce a complete YAML file conforming to the schema. Use "
            '"unknown" for any capability you cannot determine from the '
            "provided content.\n"
            f"Set last_reviewed to today's date: {today}\n"
            "Output ONLY the YAML content, wrapped in ```yaml code fences.\n"
            "Do NOT include any commentary outside the code fence."
        )

        user_parts = [
            "## Schema\n```yaml\n" + schema_text + "\n```\n",
            "## Example Platform File\n```yaml\n" + example_text + "\n```\n",
            "## Web Content\n",
        ]

        for page_url, text in web_content.items():
            user_parts.append(f"### Page: {page_url}\n{text}\n\n")

        if existing_yaml:
            user_parts.append(
                "## Existing Profile\n```yaml\n" + existing_yaml + "\n```\n"
                "Update this profile with any new information found in the "
                "web content above. Preserve existing ratings that are still "
                "accurate.\n\n"
            )

        user_parts.append(
            "## Task\n"
            "Research the CRM platform described in the web content above "
            "and generate a complete platform YAML profile. Include all "
            "capability dimensions from the schema. For each capability, "
            "assess the rating based on what the documentation reveals "
            "about API access."
        )

        return [
            {"role": "system", "content": system},
            {"role": "user", "content": "".join(user_parts)},
        ]

    def _call_claude(self, messages: list[dict]) -> str | None:
        """Send the prompt to the Claude API and return the YAML response.

        :param messages: Messages list (system + user).
        :returns: Extracted YAML string or None on failure.
        """
        try:
            import anthropic
        except ImportError:
            self._log(
                "anthropic package not installed. Run: uv add anthropic",
                "error",
            )
            return None

        system_msg = ""
        user_msgs = []
        for m in messages:
            if m["role"] == "system":
                system_msg = m["content"]
            else:
                user_msgs.append(m)

        try:
            client = anthropic.Anthropic(api_key=self._api_key)
            response = client.messages.create(
                model=_CLAUDE_MODEL,
                max_tokens=_CLAUDE_MAX_TOKENS,
                system=system_msg,
                messages=user_msgs,
            )
        except Exception as exc:
            exc_str = str(exc)
            if "401" in exc_str or "authentication" in exc_str.lower():
                self._log("Invalid Anthropic API key.", "error")
            elif "429" in exc_str or "rate" in exc_str.lower():
                self._log(
                    "API rate limited. Please try again in a moment.", "error"
                )
            else:
                self._log(f"Claude API error: {exc}", "error")
            logger.exception("Claude API call failed")
            return None

        # Extract text from response
        raw = ""
        for block in response.content:
            if block.type == "text":
                raw += block.text

        # Extract YAML from code fence if present
        match = re.search(r"```ya?ml\s*\n(.*?)```", raw, re.DOTALL)
        if match:
            return match.group(1).strip()

        # Fall back to the full response if it looks like YAML
        if raw.strip().startswith("name:") or raw.strip().startswith("#"):
            return raw.strip()

        self._log("Claude response did not contain a YAML code block.", "error")
        return None

    def _parse_and_validate(
        self, raw_yaml: str
    ) -> tuple[dict | None, list[str]]:
        """Parse YAML and validate required fields.

        :param raw_yaml: Raw YAML string.
        :returns: Tuple of (parsed dict or None, list of warnings).
        """
        warnings: list[str] = []

        try:
            data = yaml.safe_load(raw_yaml)
        except yaml.YAMLError as exc:
            logger.warning("YAML parse error: %s", exc)
            return None, [f"YAML parse error: {exc}"]

        if not isinstance(data, dict):
            return None, ["Response is not a YAML mapping"]

        # Check required fields
        required = [
            "name", "slug", "type", "last_reviewed",
            "pricing", "api", "open_source", "license",
        ]
        for field_name in required:
            if field_name not in data:
                warnings.append(f"Missing required field: {field_name}")

        # Validate date format
        lr = data.get("last_reviewed")
        if lr is not None and not isinstance(lr, datetime.date):
            try:
                datetime.date.fromisoformat(str(lr))
            except ValueError:
                warnings.append(
                    f"last_reviewed is not a valid date: {lr}"
                )

        # Validate slug format
        slug = data.get("slug", "")
        if slug and not re.match(r"^[a-z0-9][a-z0-9_-]*$", str(slug)):
            warnings.append(f"slug contains invalid characters: {slug}")

        return data, warnings
