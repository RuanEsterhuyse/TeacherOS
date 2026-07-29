"""Phase 3F editable PowerPoint renderer tests."""

from __future__ import annotations

import base64
import json
import zipfile
from pathlib import Path

import pytest

from curriculum.intelligence.renderer_instruction_adapter import (
    build_renderer_instruction_package,
)
from renderer.powerpoint_instruction_renderer import (
    PowerPointRenderOptions,
    PowerPointRenderRepository,
    _runtime_paths,
    render_powerpoint,
)
from schemas.renderer_instruction_schema import RendererPackageApprovalStatus
from Tests.test_renderer_instruction_package import _approved_spec


def _package():
    pending = build_renderer_instruction_package(
        _approved_spec()
    ).instruction_package
    return pending.model_copy(update={
        "approval_status": RendererPackageApprovalStatus.approved,
        "approved_at": _approved_spec().approved_at,
    })


@pytest.fixture
def bundled_powerpoint_runtime():
    """Require the optional Codex-bundled PowerPoint integration runtime."""
    node, setup, _ = _runtime_paths()
    if not node.is_file() or not setup.is_file():
        pytest.skip(
            "Bundled PowerPoint rendering runtime is unavailable in this "
            "environment."
        )


def test_approved_package_and_safe_filename_are_required(tmp_path):
    package = _package()
    pending = package.model_copy(update={
        "approval_status": RendererPackageApprovalStatus.pending,
        "approved_at": None,
    })
    with pytest.raises(ValueError, match="approved"):
        render_powerpoint(pending, output_root=tmp_path)
    with pytest.raises(ValueError, match="unsafe"):
        render_powerpoint(
            package,
            PowerPointRenderOptions(filename="../unsafe.pptx"),
            output_root=tmp_path,
        )


def test_rendered_powerpoint_is_editable_structurally_valid_and_deterministic(
    tmp_path,
    bundled_powerpoint_runtime,
):
    package = _package()
    first = render_powerpoint(package, output_root=tmp_path)
    second = render_powerpoint(package, output_root=tmp_path)

    assert first.render_id == second.render_id
    assert len(first.file_digest) == len(second.file_digest) == 64
    assert first.slide_count == len(package.slides) == 21
    assert first.rendered_slide_ids == [slide.slide_id for slide in package.slides]
    assert first.validation_report.valid
    assert first.validation_report.office_package_valid
    assert first.validation_report.actual_slide_count == 21
    assert first.validation_report.external_relationships == []
    assert Path(first.output_path).is_file()
    with zipfile.ZipFile(first.output_path) as archive:
        assert "ppt/presentation.xml" in archive.namelist()
        assert sum(
            name.startswith("ppt/slides/slide") and name.endswith(".xml")
            for name in archive.namelist()
        ) == 21
        slide = archive.read("ppt/slides/slide1.xml").decode("utf-8")
        assert "Identity, Place, and Perspective" in slide
        assert "#F7F4EE" not in slide  # Office XML stores colors without '#'.
        assert "F7F4EE" in slide


def test_notes_fallback_assets_fonts_and_repository_are_reported(
    tmp_path,
    bundled_powerpoint_runtime,
):
    result = render_powerpoint(_package(), output_root=tmp_path)
    assert Path(result.notes_fallback_path).read_text(encoding="utf-8")
    assert {value.rendered for value in result.font_substitutions} == {
        "Georgia", "Arial"
    }
    assert len(result.asset_report) == 21
    repository = PowerPointRenderRepository(tmp_path)
    assert repository.load(result.render_id) == result
    assert repository.list() == [result]
    assert repository.download_path(result.render_id) == Path(
        result.output_path
    )
    metadata = json.loads(
        (repository.metadata / f"{result.render_id}.json").read_text()
    )
    assert metadata["package_id"] == _package().package_id


def test_invalid_assets_and_download_ids_are_rejected(tmp_path):
    package = _package()
    with pytest.raises(ValueError, match="manifest"):
        render_powerpoint(
            package,
            PowerPointRenderOptions(local_assets={"unknown": __file__}),
            output_root=tmp_path,
        )
    repository = PowerPointRenderRepository(tmp_path)
    with pytest.raises(ValueError, match="identifier"):
        repository.download_path("../unsafe")


def test_explicit_local_asset_is_embedded_and_reported(
    tmp_path,
    bundled_powerpoint_runtime,
):
    package = _package()
    asset_id = package.asset_manifest[0].asset_id
    local_asset = tmp_path / "approved-visual.png"
    local_asset.write_bytes(base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ"
        "AAAADUlEQVR42mP8z8BQDwAFgwJ/l5Z3WQAAAABJRU5ErkJggg=="
    ))

    result = render_powerpoint(
        package,
        PowerPointRenderOptions(local_assets={
            asset_id: str(local_asset),
        }),
        output_root=tmp_path / "renders",
    )

    assert result.validation_report.valid
    report = next(
        item for item in result.asset_report
        if item.asset_id == asset_id
    )
    assert report.disposition == "embedded_local_asset"
    assert report.file_digest
