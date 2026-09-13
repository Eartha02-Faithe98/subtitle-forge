"""Deterministic language-labeled Markdown summary artifacts."""

from dataclasses import dataclass

from subtitle_forge_api.domain import Summary


@dataclass(frozen=True)
class RenderedSummaryArtifact:
    filename: str
    media_type: str
    content: bytes


def render_summary_artifact(summary: Summary) -> RenderedSummaryArtifact:
    if summary.language == "en":
        filename = "summary-en.md"
        heading = "English Summary"
    else:
        filename = "summary-zh-TW.md"
        heading = "繁體中文摘要"
    markdown = f"# {heading}\n\n{summary.text}\n"
    return RenderedSummaryArtifact(
        filename=filename,
        media_type="text/markdown; charset=utf-8",
        content=markdown.encode("utf-8"),
    )
