"""Typed building blocks of a parsed filing. Text is always verbatim."""

from __future__ import annotations

from dataclasses import dataclass, field

KINDS = ("heading", "paragraph", "speaker_turn", "table_row")


@dataclass
class Element:
    kind: str
    text: str
    order: int
    page: int = 1
    section: str | None = None
    speaker: str | None = None
    table_id: int | None = None
    table_title: str | None = None
    table_group: str | None = None  # sub-heading row inside a table ("Number of Clients")
    table_header: list[str] = field(default_factory=list)

    @property
    def context_line(self) -> str | None:
        """Structural context an index should see in front of the text (never shown as the source)."""
        if self.kind == "table_row":
            parts = [p for p in (self.table_title, self.table_group) if p]
            header = " | ".join(h for h in self.table_header if h)
            line = " — ".join(parts)
            if header:
                line = f"{line}\n{header}" if line else header
            return line or None
        if self.kind == "speaker_turn" and self.speaker:
            return f"{self.speaker}:"
        return None


@dataclass
class ParsedDocument:
    elements: list[Element]
    total_pages: int
    source: str = ""

    def text(self) -> str:
        return "\n\n".join(e.text for e in self.elements)
