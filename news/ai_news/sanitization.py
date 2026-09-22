from __future__ import annotations

import re
from html import escape, unescape
from html.parser import HTMLParser
from urllib.parse import urlparse


WHITESPACE_RE = re.compile(r'\s+')
ALLOWED_TAGS = {
    'p',
    'br',
    'h2',
    'h3',
    'ul',
    'ol',
    'li',
    'strong',
    'em',
    'blockquote',
    'a',
}
VOID_TAGS = {'br'}
DROP_CONTENT_TAGS = {'script', 'style', 'template', 'noscript', 'svg', 'iframe', 'object'}


class _PlainTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.drop_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag.lower() in DROP_CONTENT_TAGS:
            self.drop_depth += 1
        elif not self.drop_depth and tag.lower() in {'p', 'br', 'li', 'h1', 'h2', 'h3', 'div'}:
            self.parts.append('\n')

    def handle_endtag(self, tag):
        if tag.lower() in DROP_CONTENT_TAGS and self.drop_depth:
            self.drop_depth -= 1
        elif not self.drop_depth and tag.lower() in {'p', 'li', 'h1', 'h2', 'h3', 'div'}:
            self.parts.append('\n')

    def handle_data(self, data):
        if not self.drop_depth:
            self.parts.append(data)


def normalize_external_text(value: str, *, max_chars: int) -> str:
    parser = _PlainTextExtractor()
    parser.feed(str(value or ''))
    parser.close()
    text = unescape(' '.join(parser.parts))
    return WHITESPACE_RE.sub(' ', text).strip()[:max_chars]


class _SafeHTMLSanitizer(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.stack: list[str] = []
        self.drop_depth = 0

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in DROP_CONTENT_TAGS:
            self.drop_depth += 1
            return
        if self.drop_depth or tag not in ALLOWED_TAGS:
            return
        if tag == 'a':
            href = next((value for name, value in attrs if name.lower() == 'href'), '')
            parsed = urlparse(href or '')
            if parsed.scheme in {'http', 'https'} and parsed.netloc:
                self.parts.append(
                    f'<a href="{escape(href, quote=True)}" rel="noopener noreferrer">'
                )
                self.stack.append(tag)
            return
        self.parts.append(f'<{tag}>')
        if tag not in VOID_TAGS:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in DROP_CONTENT_TAGS and self.drop_depth:
            self.drop_depth -= 1
            return
        if self.drop_depth or tag not in self.stack:
            return
        while self.stack:
            opened = self.stack.pop()
            self.parts.append(f'</{opened}>')
            if opened == tag:
                break

    def handle_data(self, data):
        if not self.drop_depth:
            self.parts.append(escape(data))

    def finish(self):
        while self.stack:
            self.parts.append(f'</{self.stack.pop()}>')
        return ''.join(self.parts).strip()


def sanitize_generated_html(value: str) -> str:
    parser = _SafeHTMLSanitizer()
    parser.feed(str(value or ''))
    parser.close()
    cleaned = parser.finish()
    if '<' not in cleaned and cleaned:
        paragraphs = [part.strip() for part in cleaned.splitlines() if part.strip()]
        return ''.join(f'<p>{part}</p>' for part in paragraphs)
    return cleaned
