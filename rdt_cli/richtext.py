"""Reddit RTJSON (rich text) document building for self-post bodies.

New Reddit stores post/comment bodies canonically as RTJSON ("Lexical"-style
rich text) and merely *exports* markdown. The fancy-pants editor submits
``content.richText`` (a stringified JSON document) to the shreddit GraphQL
mutations; a markdown-only body renders ``[text](https://i.redd.it/<id>.<ext>)``
as a plain link, while an ``img`` RTJSON node renders as a real inline image
and links the media into the post's ``media_metadata``.

Document model (matches editor output and served ``richtext_json`` blobs):
top-level blocks in ``document`` — paragraphs
(``{"e": "par", "c": [{"e": "text", "t": ...}]}``) and image blocks
(``{"e": "img", "id": "<media_id>", "c": "<caption>"}``, caption optional).
"""

from __future__ import annotations

import json


def _paragraph(line: str) -> dict:
    return {"e": "par", "c": [{"e": "text", "t": line}]}


def build_rtjson(text: str, media: list[tuple[str, str]]) -> str:
    """Build a stringified RTJSON document from a marker-bearing body.

    ``text`` is the markdown body still containing one ``![img]`` marker per
    image; ``media`` holds ``(media_id, caption)`` per marker, in order
    (``len(media)`` must equal the marker count). Text is split at the markers
    and each ``![img]`` becomes a top-level ``img`` block between paragraphs —
    the same shape the fancy-pants editor produces when an image is dropped
    into a body. Non-empty lines within a text segment become separate
    paragraphs; blank lines are dropped (editor documents never contain empty
    ``par`` nodes — paragraphs are visually separated regardless).

    Note: inline markdown formatting (bold, links, …) inside the text is NOT
    translated to RTJSON format ranges — segments are emitted as plain text.
    When a post is submitted as RTJSON, Reddit derives the markdown export
    from it, so formatting written in the body will show literally.
    """
    parts = text.split("![img]")
    document: list[dict] = []

    def add_text(segment: str) -> None:
        for line in segment.split("\n"):
            if line:  # markers at edges / blank lines contribute no paragraph
                document.append(_paragraph(line))

    add_text(parts[0])
    for (media_id, caption), tail in zip(media, parts[1:], strict=True):
        node: dict = {"e": "img", "id": media_id}
        if caption:
            node["c"] = caption
        document.append(node)
        add_text(tail)
    if not document:
        document.append(_paragraph(""))
    return json.dumps({"document": document}, separators=(",", ":"))
