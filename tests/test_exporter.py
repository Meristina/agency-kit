"""Offline tests for the PDF exporter's asset localization (Wave 3).

``_localize_assets`` is the pure core of the PDF fix: it resolves the ``/media``
server-route references that ``assets.rewrite_delivered`` leaves in a deliverable
back to on-disk files so a PDF render can embed images (and caption audio). These
tests need neither WeasyPrint nor Markdown — they exercise the rewriting directly.
"""

from pathlib import Path

from agency_cli.exporter import _localize_assets


def _seed_image(root: Path, rel: str) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"\x89PNG\r\n")  # not a real image — existence is all that matters here
    return p


def test_image_ref_becomes_an_absolute_file_uri(tmp_path):
    root = tmp_path / "studio_assets"
    img = _seed_image(root, "missions/m1/images/a.png")
    md = "Intro\n\n![a bold banner](/media/missions/m1/images/a.png)\n\nOutro"

    out = _localize_assets(md, root)

    assert img.as_uri() in out
    assert "/media/" not in out  # the server route is gone, replaced by the file URI
    assert "![a bold banner](" in out  # still an embed, caption preserved


def test_missing_image_degrades_to_its_caption_not_a_broken_embed(tmp_path):
    root = tmp_path / "studio_assets"
    root.mkdir()
    md = "![a vanished image](/media/missions/m1/images/gone.png)"

    out = _localize_assets(md, root)

    assert out == "a vanished image"  # caption text, no dangling embed


def test_audio_link_becomes_a_caption_with_the_filename(tmp_path):
    root = tmp_path / "studio_assets"
    _seed_image(root, "missions/m1/audio/v.wav")
    md = "[Generated audio narration](/media/missions/m1/audio/v.wav) (4s)"

    out = _localize_assets(md, root)

    assert "Generated audio narration — v.wav" in out
    assert "/media/" not in out  # a PDF can't play sound: it's a caption, not a link
    assert "(4s)" in out  # the duration suffix outside the link survives


def test_traversal_outside_the_assets_root_is_refused(tmp_path):
    root = tmp_path / "studio_assets"
    root.mkdir()
    # A secret outside the root that a crafted ref must never embed into the PDF.
    (tmp_path / "secret.png").write_bytes(b"x")
    md = "![x](/media/../secret.png)"

    out = _localize_assets(md, root)

    assert out == "x"  # escaped the root → dropped to caption, no file:// leak
    assert "secret" not in out.replace("![x]", "")  # the escaped path is not embedded


def test_non_media_and_external_refs_are_left_untouched(tmp_path):
    root = tmp_path / "studio_assets"
    root.mkdir()
    md = "![remote](https://example.com/a.png)\n[docs](https://example.com)"

    out = _localize_assets(md, root)

    assert out == md  # only /media references are rewritten


def test_no_assets_root_is_a_noop_via_export_path():
    # _localize_assets is only invoked when assets_root is given; with plain text and
    # no /media refs it is the identity, mirroring the byte-identical standalone path.
    md = "# Title\n\nplain body, no assets"
    assert _localize_assets(md, Path("/nonexistent/root")) == md
