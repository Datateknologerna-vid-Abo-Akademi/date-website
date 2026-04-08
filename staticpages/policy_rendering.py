import re
from types import SimpleNamespace

from django.shortcuts import render
from django.utils.html import escape
from django.utils.safestring import mark_safe

MARKDOWN_HEADING_RE = re.compile(r'^(#{1,6})\s+(.*)$')


def _render_inline_markdown(text):
    return escape(text)


def render_markdown_to_html(markdown_text):
    blocks = []
    paragraph_lines = []
    list_items = []

    def flush_paragraph():
        if paragraph_lines:
            paragraph = " ".join(paragraph_lines)
            blocks.append(f"<p>{_render_inline_markdown(paragraph)}</p>")
            paragraph_lines.clear()

    def flush_list():
        if list_items:
            rendered_items = "".join(f"<li>{_render_inline_markdown(item)}</li>" for item in list_items)
            blocks.append(f"<ul>{rendered_items}</ul>")
            list_items.clear()

    for raw_line in markdown_text.splitlines():
        line = raw_line.strip()
        if not line:
            flush_paragraph()
            flush_list()
            continue

        heading_match = MARKDOWN_HEADING_RE.match(line)
        if heading_match:
            flush_paragraph()
            flush_list()
            level = len(heading_match.group(1))
            content = _render_inline_markdown(heading_match.group(2))
            blocks.append(f"<h{level}>{content}</h{level}>")
            continue

        if line.startswith("- "):
            flush_paragraph()
            list_items.append(line[2:].strip())
            continue

        paragraph_lines.append(line)

    flush_paragraph()
    flush_list()
    return mark_safe("\n".join(blocks))


def render_policy_document(request, title, markdown_text, fetch_error=None, show_page_title=False):
    lines = markdown_text.splitlines()
    document_starts_with_title = bool(lines and lines[0].strip() == f"# {title}")
    if document_starts_with_title:
        markdown_text = "\n".join(lines[1:]).lstrip()
    page = SimpleNamespace(title=title, content="")
    return render(
        request,
        'staticpages/staticpage.html',
        {
            'page': page,
            'show_content': True,
            'show_document_title': show_page_title,
            'document_html': render_markdown_to_html(markdown_text),
            'fetch_error': fetch_error,
        },
    )
