from __future__ import annotations

import hashlib
import ipaddress
import re
import socket
from dataclasses import dataclass
from datetime import datetime, timezone as datetime_timezone
from email.utils import parsedate_to_datetime
from http.client import HTTPConnection, HTTPSConnection
from urllib.parse import urljoin, urlparse
from urllib.request import (
    HTTPHandler,
    HTTPRedirectHandler,
    HTTPSHandler,
    ProxyHandler,
    Request,
    build_opener,
)
from urllib.robotparser import RobotFileParser
from xml.etree import ElementTree

from .sanitization import normalize_external_text


USER_AGENT = 'StavplusAINewsBot/1.0 (+https://stavplus.ru/)'
MAX_FEED_BYTES = 2 * 1024 * 1024
MAX_REDIRECTS = 5
INJECTION_MARKERS = (
    'ignore previous',
    'ignore all previous',
    'system prompt',
    'developer message',
    'выполни инструкц',
    'игнорируй предыдущ',
    'системный промпт',
)
SENTENCE_RE = re.compile(r'(?<=[.!?])\s+')


class SourceFetchError(RuntimeError):
    pass


@dataclass(frozen=True)
class FeedEntry:
    title: str
    url: str
    published_at: datetime | None
    content: str


def validate_source_url(url: str, allowed_domains: list[str]) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {'http', 'https'} or not parsed.hostname:
        raise SourceFetchError('Only absolute HTTP(S) source URLs are allowed.')
    if parsed.username is not None or parsed.password is not None:
        raise SourceFetchError('Source URLs with credentials are not allowed.')
    hostname = parsed.hostname.rstrip('.').lower()
    if hostname == 'localhost' or hostname.endswith('.local'):
        raise SourceFetchError('Local source hosts are not allowed.')
    try:
        port = parsed.port or (443 if parsed.scheme == 'https' else 80)
    except ValueError as error:
        raise SourceFetchError('Source URL contains an invalid port.') from error
    domains = [domain.lstrip('.').rstrip('.').lower() for domain in allowed_domains]
    if not domains or not any(hostname == domain or hostname.endswith(f'.{domain}') for domain in domains):
        raise SourceFetchError('Source URL is outside the approved domain allowlist.')
    _validate_destination_addresses(hostname, port)
    return url


def _validate_destination_addresses(hostname: str, port: int) -> list[tuple]:
    try:
        results = socket.getaddrinfo(
            hostname,
            port,
            family=socket.AF_UNSPEC,
            type=socket.SOCK_STREAM,
        )
    except (OSError, UnicodeError) as error:
        raise SourceFetchError('Source hostname could not be resolved safely.') from error
    if not results:
        raise SourceFetchError('Source hostname did not resolve to an address.')

    for result in results:
        try:
            address = ipaddress.ip_address(result[4][0].split('%', 1)[0])
        except (IndexError, TypeError, ValueError) as error:
            raise SourceFetchError('Source hostname resolved to an invalid address.') from error
        if (
            not address.is_global
            or address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_multicast
            or address.is_unspecified
            or address.is_reserved
        ):
            raise SourceFetchError('Non-public source addresses are not allowed.')
    return results


def _connect_to_validated_address(hostname, port, timeout, source_address=None):
    """Resolve once, validate every address, then connect to an exact validated sockaddr."""
    results = _validate_destination_addresses(hostname, port)
    last_error = None
    for family, socktype, proto, _, sockaddr in results:
        sock = None
        try:
            sock = socket.socket(family, socktype, proto)
            if timeout is not socket._GLOBAL_DEFAULT_TIMEOUT:
                sock.settimeout(timeout)
            if source_address:
                sock.bind(source_address)
            sock.connect(sockaddr)
            return sock
        except OSError as error:
            last_error = error
            if sock is not None:
                sock.close()
    raise SourceFetchError('Could not connect to a validated public source address.') from last_error


class _PinnedHTTPConnection(HTTPConnection):
    def connect(self):
        if self._tunnel_host:
            raise SourceFetchError('Proxy tunnels are not allowed for source fetches.')
        self.sock = _connect_to_validated_address(
            self.host,
            self.port,
            self.timeout,
            self.source_address,
        )


class _PinnedHTTPSConnection(HTTPSConnection):
    def connect(self):
        if self._tunnel_host:
            raise SourceFetchError('Proxy tunnels are not allowed for source fetches.')
        self.sock = _connect_to_validated_address(
            self.host,
            self.port,
            self.timeout,
            self.source_address,
        )
        self.sock = self._context.wrap_socket(self.sock, server_hostname=self.host)


class _PinnedHTTPHandler(HTTPHandler):
    def http_open(self, request):
        return self.do_open(_PinnedHTTPConnection, request)


class _PinnedHTTPSHandler(HTTPSHandler):
    def https_open(self, request):
        return self.do_open(
            _PinnedHTTPSConnection,
            request,
            context=self._context,
        )


class _SourceRedirectHandler(HTTPRedirectHandler):
    def __init__(self, *, allowed_domains: list[str], max_redirects: int = MAX_REDIRECTS):
        super().__init__()
        self.allowed_domains = allowed_domains
        self.max_redirects = max_redirects
        self.redirect_count = 0

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        self.redirect_count += 1
        if self.redirect_count > self.max_redirects:
            raise SourceFetchError('Source response exceeded the redirect limit.')
        target_url = urljoin(req.full_url, newurl)
        validate_source_url(target_url, self.allowed_domains)
        return super().redirect_request(req, fp, code, msg, headers, target_url)


def fetch_bytes(url: str, *, allowed_domains: list[str], timeout: int) -> bytes:
    validate_source_url(url, allowed_domains)
    request = Request(url, headers={'User-Agent': USER_AGENT, 'Accept': 'application/xml,text/xml,*/*'})
    opener = build_opener(
        ProxyHandler({}),
        _SourceRedirectHandler(allowed_domains=allowed_domains),
        _PinnedHTTPHandler(),
        _PinnedHTTPSHandler(),
    )
    with opener.open(request, timeout=timeout) as response:
        validate_source_url(response.geturl(), allowed_domains)
        payload = response.read(MAX_FEED_BYTES + 1)
    if len(payload) > MAX_FEED_BYTES:
        raise SourceFetchError('Source response exceeded the 2 MiB safety limit.')
    return payload


def robots_allows(url: str, *, allowed_domains: list[str], timeout: int) -> bool:
    parsed = urlparse(validate_source_url(url, allowed_domains))
    robots_url = f'{parsed.scheme}://{parsed.netloc}/robots.txt'
    payload = fetch_bytes(robots_url, allowed_domains=allowed_domains, timeout=timeout)
    parser = RobotFileParser()
    parser.set_url(robots_url)
    parser.parse(payload.decode('utf-8', errors='replace').splitlines())
    return parser.can_fetch(USER_AGENT, url)


def parse_feed(payload: bytes) -> list[FeedEntry]:
    lowered_payload = payload.lower()
    if b'<!doctype' in lowered_payload or b'<!entity' in lowered_payload:
        raise SourceFetchError('Source XML declarations with DTD or entities are not allowed.')
    try:
        root = ElementTree.fromstring(payload)
    except ElementTree.ParseError as error:
        raise SourceFetchError('Source returned invalid RSS/Atom XML.') from error

    root_name = _local_name(root.tag)
    if root_name == 'feed':
        nodes = [node for node in root if _local_name(node.tag) == 'entry']
    else:
        nodes = [node for node in root.iter() if _local_name(node.tag) == 'item']
    return [entry for node in nodes if (entry := _parse_entry(node)) is not None]


def _parse_entry(node) -> FeedEntry | None:
    values: dict[str, list] = {}
    for child in node:
        values.setdefault(_local_name(child.tag), []).append(child)
    title = _element_text(_first(values, 'title'))
    link_node = _first(values, 'link')
    url = ''
    if link_node is not None:
        url = (link_node.attrib.get('href') or _element_text(link_node)).strip()
    published_node = _first(values, 'published')
    if published_node is None:
        published_node = _first(values, 'updated')
    if published_node is None:
        published_node = _first(values, 'pubDate')
    published = _element_text(published_node)
    content_node = None
    for field_name in ('encoded', 'content', 'description', 'summary'):
        content_node = _first(values, field_name)
        if content_node is not None:
            break
    content = _element_text(content_node, include_markup=True)
    if not title or not url or not content:
        return None
    return FeedEntry(title=title, url=url, published_at=_parse_date(published), content=content)


def _first(values, name):
    items = values.get(name, [])
    return items[0] if items else None


def _element_text(element, *, include_markup=False):
    if element is None:
        return ''
    if include_markup and list(element):
        return ''.join(ElementTree.tostring(child, encoding='unicode') for child in element)
    return ''.join(element.itertext()).strip()


def _local_name(tag):
    return str(tag).rsplit('}', 1)[-1]


def _parse_date(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        try:
            parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime_timezone.utc)
    return parsed


def normalize_entry(entry: FeedEntry, *, max_chars: int) -> tuple[str, str]:
    title = normalize_external_text(entry.title, max_chars=500)
    content = normalize_external_text(entry.content, max_chars=max_chars)
    return title, content


def content_digest(title: str, content: str) -> str:
    canonical = f'{title.strip()}\n{content.strip()}'.casefold().encode('utf-8')
    return hashlib.sha256(canonical).hexdigest()


def extract_fact_candidates(content: str, source_url: str, *, limit: int = 12) -> list[dict]:
    candidates = []
    for sentence in SENTENCE_RE.split(content):
        text = sentence.strip()
        lowered = text.casefold()
        if len(text) < 20 or any(marker in lowered for marker in INJECTION_MARKERS):
            continue
        candidates.append(
            {
                'id': f'fact-{len(candidates) + 1}',
                'statement': text[:700],
                'source_url': source_url,
            }
        )
        if len(candidates) >= limit:
            break
    return candidates
