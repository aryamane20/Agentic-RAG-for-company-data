"""Markdown chunking that respects ## section boundaries, with a size cap
for sections too long to keep as a single chunk."""

import re

DEFAULT_CHUNK_CAP = 1500

_HEADER_PREFIX = "## "


def split_into_sections(text):
    """Split markdown text into (header, body_lines) pairs on '## ' lines.

    Any text before the first '## ' header (title, metadata lines, etc.) is
    folded into the first section's body rather than becoming its own chunk.
    If the document has no '## ' headers at all, the whole text becomes a
    single section with header=None.
    """
    lines = text.splitlines()

    i = 0
    n = len(lines)
    preamble = []
    while i < n and not lines[i].startswith(_HEADER_PREFIX):
        preamble.append(lines[i])
        i += 1

    sections = []
    current_header = None
    current_body = []
    while i < n:
        line = lines[i]
        if line.startswith(_HEADER_PREFIX):
            if current_header is not None:
                sections.append((current_header, current_body))
            current_header = line.strip()
            current_body = []
        else:
            current_body.append(line)
        i += 1
    if current_header is not None:
        sections.append((current_header, current_body))

    if not sections:
        return [(None, preamble)]

    first_header, first_body = sections[0]
    if preamble:
        combined = preamble + ([""] if first_body else []) + first_body
    else:
        combined = first_body
    sections[0] = (first_header, combined)

    return sections


def _split_into_paragraphs(text):
    paragraphs = re.split(r"\n\s*\n", text)
    return [p.strip() for p in paragraphs if p.strip()]


def _split_into_sentences(text):
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return [s.strip() for s in sentences if s.strip()]


def _pack(units, prefix, cap, join_sep):
    """Greedily pack `units` (paragraphs or sentences) into chunks no
    longer than `cap`, each prefixed with `prefix`. A single unit that
    alone exceeds the cap (after the prefix) is kept as its own
    over-cap chunk rather than being silently truncated.
    """
    chunks = []
    current = []

    def build(parts):
        body = join_sep.join(parts)
        return f"{prefix}{body}" if prefix else body

    for unit in units:
        candidate = current + [unit]
        if len(build(candidate)) <= cap or not current:
            current = candidate
        else:
            chunks.append(build(current))
            current = [unit]

    if current:
        chunks.append(build(current))

    return chunks


def _chunk_section_text(full_text, cap):
    paragraphs = _split_into_paragraphs(full_text)
    if not paragraphs:
        return []

    chunks = _pack(paragraphs, prefix="", cap=cap, join_sep="\n\n")

    final = []
    for chunk in chunks:
        if len(chunk) <= cap:
            final.append(chunk)
            continue
        sentences = _split_into_sentences(chunk)
        final.extend(_pack(sentences, prefix="", cap=cap, join_sep=" "))

    return final


def chunk_section(header, body_lines, cap=DEFAULT_CHUNK_CAP):
    """Turn one (header, body_lines) section into a list of chunk strings,
    each carrying the section header, splitting the body if it exceeds cap.
    """
    body_text = "\n".join(body_lines).strip()

    if header:
        full_chunk = f"{header}\n\n{body_text}" if body_text else header
    else:
        full_chunk = body_text

    if not full_chunk.strip():
        return []

    if len(full_chunk) <= cap:
        return [full_chunk]

    prefix = f"{header}\n\n" if header else ""

    if len(prefix) >= cap:
        # The header alone already meets or exceeds the cap. Splitting the
        # body into the tiny (or negative) budget left over would just
        # re-prepend this oversized prefix onto every resulting piece,
        # multiplying the overage instead of bounding it. Give up on
        # sub-splitting and emit the section as one chunk -- worse than
        # the cap, but far better than N copies of an oversized header.
        return [full_chunk]

    budget = cap - len(prefix)
    body_pieces = _chunk_section_text(body_text, budget)
    return [f"{prefix}{piece}" for piece in body_pieces]


def chunk_markdown(text, cap=DEFAULT_CHUNK_CAP):
    """Split a full markdown document into a list of chunk strings that
    respect ## section boundaries, capping any section that runs too long.
    """
    sections = split_into_sections(text)
    chunks = []
    for header, body_lines in sections:
        chunks.extend(chunk_section(header, body_lines, cap=cap))
    return chunks
