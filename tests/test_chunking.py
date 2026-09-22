from ingestion.chunking import chunk_markdown, chunk_section, split_into_sections


def test_split_into_sections_folds_preamble_into_first_section():
    text = "# Title\n\nLast updated: Jan 2026\n\n## First\n\nbody one\n\n## Second\n\nbody two\n"
    sections = split_into_sections(text)

    assert len(sections) == 2
    header, body = sections[0]
    assert header == "## First"
    assert "# Title" in body
    assert "Last updated: Jan 2026" in body
    assert "body one" in body

    header2, body2 = sections[1]
    assert header2 == "## Second"
    assert "body two" in body2


def test_split_into_sections_no_headers_returns_single_section():
    text = "Just a paragraph.\n\nAnother paragraph."
    sections = split_into_sections(text)

    assert len(sections) == 1
    header, body = sections[0]
    assert header is None
    assert "Just a paragraph." in body


def test_split_into_sections_multiple_sections():
    text = "## A\ntext a\n## B\ntext b\n## C\ntext c\n"
    sections = split_into_sections(text)

    assert [h for h, _ in sections] == ["## A", "## B", "## C"]


def test_chunk_section_under_cap_returns_single_chunk():
    header = "## Remote work"
    body_lines = ["Solstice operates as remote first."]

    chunks = chunk_section(header, body_lines, cap=1500)

    assert len(chunks) == 1
    assert chunks[0].startswith("## Remote work")
    assert "remote first" in chunks[0]


def test_chunk_section_empty_body_and_header_skipped():
    assert chunk_section(None, [], cap=1500) == []
    assert chunk_section(None, ["   ", ""], cap=1500) == []


def test_chunk_section_over_cap_splits_on_paragraphs_and_keeps_header():
    header = "## Long section"
    paragraphs = [f"Paragraph {i} with some filler words to add length." for i in range(10)]
    body_lines = "\n\n".join(paragraphs).splitlines()

    chunks = chunk_section(header, body_lines, cap=120)

    assert len(chunks) > 1
    for c in chunks:
        assert c.startswith("## Long section")
    # every paragraph's content must survive somewhere in the chunks
    joined = " ".join(chunks)
    for p in paragraphs:
        assert p in joined


def test_chunk_section_single_oversized_paragraph_falls_back_to_sentences():
    header = "## Dense"
    sentence = "This is one sentence that repeats. "
    huge_paragraph = sentence * 20  # single paragraph, no blank lines, way over cap
    body_lines = [huge_paragraph]

    chunks = chunk_section(header, body_lines, cap=100)

    assert len(chunks) > 1
    for c in chunks:
        assert c.startswith("## Dense")


def test_chunk_section_oversized_header_does_not_multiply_via_duplicated_prefix():
    # header alone is already longer than the cap -- before the fix, this
    # collapsed the body-packing budget to ~1, causing the oversized header
    # to be re-prepended onto many tiny pieces (far worse than one big chunk)
    header = "## " + ("Very long header title " * 20)  # ~500+ chars, well over cap
    body_lines = ["Paragraph one.", "", "Paragraph two.", "", "Paragraph three."]

    chunks = chunk_section(header, body_lines, cap=100)

    assert len(header) > 100  # confirm the header itself already exceeds cap
    # must degrade to exactly one chunk (header + full body), not many
    # chunks each re-paying the oversized header cost
    assert len(chunks) == 1
    assert chunks[0].startswith(header)
    assert "Paragraph one." in chunks[0]
    assert "Paragraph three." in chunks[0]


def test_chunk_section_normal_header_still_splits_body_correctly():
    # sanity check the fix didn't break the ordinary (short header) path
    header = "## Short"
    paragraphs = [f"Paragraph {i} with some filler words to add length." for i in range(10)]
    body_lines = "\n\n".join(paragraphs).splitlines()

    chunks = chunk_section(header, body_lines, cap=120)

    assert len(chunks) > 1
    for c in chunks:
        assert c.startswith(header)
        assert len(c) <= 200  # each piece stays reasonably close to cap, no multiplication


def test_chunk_markdown_respects_section_boundaries_end_to_end():
    text = (
        "# Employee Handbook\n\n"
        "Last updated: Jan 2026\n\n"
        "## Welcome\n\nWelcome text here.\n\n"
        "## PTO\n\nPTO details here.\n\n"
        "## Remote work\n\nRemote work details here.\n"
    )

    chunks = chunk_markdown(text, cap=1500)

    assert len(chunks) == 3
    assert chunks[0].startswith("## Welcome")
    assert "# Employee Handbook" in chunks[0]
    assert chunks[1].startswith("## PTO")
    assert chunks[2].startswith("## Remote work")


def test_chunk_markdown_real_sample_file_one_chunk_per_section():
    import os

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(root, "hr", "employee_handbook.md")

    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    chunks = chunk_markdown(text, cap=1500)

    # employee_handbook.md has 6 "## " sections and is short enough that
    # none should need splitting under the default cap.
    assert len(chunks) == 6
    for c in chunks:
        assert c.startswith("## ")
