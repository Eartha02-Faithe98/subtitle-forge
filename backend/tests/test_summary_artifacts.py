import pytest

from subtitle_forge_api.domain import Summary
from subtitle_forge_api.summary_artifacts import render_summary_artifact


@pytest.mark.parametrize(
    ("summary", "filename", "expected"),
    [
        (
            Summary(language="en", text="A concise local summary."),
            "summary-en.md",
            "# English Summary\n\nA concise local summary.\n",
        ),
        (
            Summary(language="zh-TW", text="一段精簡的本機摘要。"),
            "summary-zh-TW.md",
            "# 繁體中文摘要\n\n一段精簡的本機摘要。\n",
        ),
    ],
)
def test_summary_artifact_is_separate_language_labeled_utf8_markdown(
    summary: Summary,
    filename: str,
    expected: str,
) -> None:
    artifact = render_summary_artifact(summary)

    assert artifact.filename == filename
    assert artifact.media_type == "text/markdown; charset=utf-8"
    assert artifact.content == expected.encode("utf-8")
    assert artifact.content.decode("utf-8") == expected


def test_summary_artifact_has_no_phase_two_metadata() -> None:
    artifact = render_summary_artifact(Summary(language="en", text="Plain summary only."))
    rendered = artifact.content.decode("utf-8").lower()

    assert "chapter" not in rendered
    assert "key point" not in rendered
    assert "timestamp" not in rendered
    assert "citation" not in rendered
