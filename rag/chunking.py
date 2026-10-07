"""Splits a corpus markdown file (YAML frontmatter + `## ` sections) into
retrievable chunks, one per section -- SPEC 3's rag store: "Policy and
coverage chunks with document, section and version date"."""

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)


@dataclass(frozen=True)
class Chunk:
    document: str
    section: str
    language: str
    version_date: str
    content: str
    source_path: str


def parse_file(path: Path) -> list[Chunk]:
    text = path.read_text(encoding="utf-8")
    match = _FRONTMATTER_RE.match(text)
    if not match:
        raise ValueError(f"{path} is missing YAML frontmatter")

    meta = yaml.safe_load(match.group(1))
    body = match.group(2).strip()

    chunks: list[Chunk] = []
    # Split on "## " section headers; the doc title ("# ...") is dropped,
    # each "## Section" becomes its own chunk.
    parts = re.split(r"\n(?=## )", body)
    for part in parts:
        part = part.strip()
        if not part or part.startswith("# "):
            continue
        lines = part.splitlines()
        section_title = lines[0].lstrip("# ").strip()
        content = "\n".join(lines[1:]).strip() or part
        chunks.append(
            Chunk(
                document=meta["document"],
                section=section_title,
                language=meta["language"],
                version_date=str(meta["version_date"]),
                content=content,
                source_path=str(path),
            )
        )
    return chunks


def load_corpus(corpus_dir: Path) -> list[Chunk]:
    chunks: list[Chunk] = []
    for path in sorted(corpus_dir.glob("**/*.md")):
        chunks.extend(parse_file(path))
    return chunks
