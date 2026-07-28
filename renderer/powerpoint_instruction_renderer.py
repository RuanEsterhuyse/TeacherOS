"""Isolated editable PowerPoint renderer for approved instruction packages."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from curriculum.intelligence.ids import content_digest, file_checksum, stable_id
from renderer.powerpoint_validator import validate_powerpoint
from schemas.powerpoint_render_schema import (
    FontSubstitution,
    NotesSupportStatus,
    POWERPOINT_RENDERER_VERSION,
    PowerPointRenderOptions,
    PowerPointRenderResult,
    PowerPointRenderWarning,
    RenderedAsset,
)
from schemas.renderer_instruction_schema import (
    RendererInstructionPackage,
    RendererPackageApprovalStatus,
)


SAFE_ID = re.compile(r"^[A-Za-z0-9_-]+$")
SAFE_FILENAME = re.compile(r"^[A-Za-z0-9_.-]+\.pptx$")
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}


def _runtime_paths() -> tuple[Path, Path, Path]:
    home = Path.home()
    dependency_root = home / (
        ".cache/codex-runtimes/codex-primary-runtime/dependencies"
    )
    node = Path(os.environ.get(
        "TEACHEROS_NODE_BINARY",
        dependency_root / "node/bin/node",
    ))
    skill = Path(os.environ.get(
        "TEACHEROS_PRESENTATION_SKILL",
        home / (
            ".codex/plugins/cache/openai-primary-runtime/presentations/"
            "26.727.11326/skills/presentations"
        ),
    ))
    setup = skill / "container_tools/setup_artifact_tool_workspace.mjs"
    return node, setup, skill


def _atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent,
        prefix=f".{path.stem}-", suffix=".tmp", delete=False,
    ) as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")
        temporary = Path(stream.name)
    temporary.replace(path)


class PowerPointRenderRepository:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.decks = self.root / "decks"
        self.metadata = self.root / "metadata"
        self.notes = self.root / "notes"
        self.previews = self.root / "previews"
        for directory in (self.decks, self.metadata, self.notes, self.previews):
            directory.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _id(value: str) -> str:
        if not SAFE_ID.fullmatch(value):
            raise ValueError("Invalid PowerPoint render identifier.")
        return value

    def save(self, result: PowerPointRenderResult) -> None:
        _atomic_json(
            self.metadata / f"{self._id(result.render_id)}.json",
            result.model_dump(mode="json"),
        )

    def load(self, render_id: str) -> PowerPointRenderResult:
        path = self.metadata / f"{self._id(render_id)}.json"
        if not path.is_file():
            raise FileNotFoundError(path)
        return PowerPointRenderResult.model_validate_json(
            path.read_text(encoding="utf-8")
        )

    def list(self) -> list[PowerPointRenderResult]:
        return [
            PowerPointRenderResult.model_validate_json(
                path.read_text(encoding="utf-8")
            )
            for path in sorted(self.metadata.glob("*.json"))
        ]

    def download_path(self, render_id: str) -> Path:
        result = self.load(render_id)
        path = Path(result.output_path).resolve()
        if self.decks not in path.parents or not path.is_file():
            raise ValueError("PowerPoint output path is invalid.")
        return path


def render_powerpoint(
    instruction_package: RendererInstructionPackage,
    options: PowerPointRenderOptions | None = None,
    *,
    output_root: str | Path,
    source_module: str | Path | None = None,
) -> PowerPointRenderResult:
    options = options or PowerPointRenderOptions()
    if (
        instruction_package.approval_status
        != RendererPackageApprovalStatus.approved
        or not instruction_package.validation_report.valid
    ):
        raise ValueError(
            "PowerPoint rendering requires an approved, valid renderer package."
        )
    if not SAFE_FILENAME.fullmatch(options.filename):
        raise ValueError("PowerPoint filename is unsafe.")
    repository = PowerPointRenderRepository(output_root)
    package_digest = content_digest(
        instruction_package.model_dump(mode="json")
    )
    options_digest = content_digest(options.model_dump(mode="json"))
    render_id = stable_id(
        "powerpoint-render", instruction_package.package_id,
        package_digest, options_digest, POWERPOINT_RENDERER_VERSION,
    )
    output = repository.decks / f"{render_id}-{options.filename}"
    notes_path = repository.notes / f"{render_id}.txt"
    preview = repository.previews / render_id

    assets: list[RenderedAsset] = []
    validated_assets: dict[str, str] = {}
    known_assets = {
        asset.asset_id: asset for asset in instruction_package.asset_manifest
    }
    for asset_id, raw_path in options.local_assets.items():
        if asset_id not in known_assets:
            raise ValueError("Local asset does not match the package manifest.")
        supplied_path = Path(raw_path).expanduser()
        if ".." in supplied_path.parts or supplied_path.is_symlink():
            raise ValueError("Local asset path is unsafe.")
        path = supplied_path.resolve()
        if not path.is_file() or path.suffix.casefold() not in IMAGE_EXTENSIONS:
            raise ValueError("Local assets must be existing PNG or JPEG files.")
        validated_assets[asset_id] = str(path)
    for asset in instruction_package.asset_manifest:
        local = validated_assets.get(asset.asset_id)
        assets.append(RenderedAsset(
            asset_id=asset.asset_id,
            slide_id=asset.slide_id,
            disposition="embedded_local_asset" if local else asset.status.value,
            local_path=local,
            file_digest=file_checksum(local) if local else None,
        ))

    node, setup, _ = _runtime_paths()
    if not node.is_file() or not setup.is_file():
        raise RuntimeError("Bundled PowerPoint rendering runtime is unavailable.")
    module = Path(source_module or Path(__file__).with_name(
        "powerpoint_artifact_renderer.mjs"
    ))
    with tempfile.TemporaryDirectory(
        prefix=f".{render_id}-", dir=repository.root
    ) as temporary_name:
        temporary = Path(temporary_name)
        subprocess.run(
            [str(node), str(setup), "--workspace", str(temporary)],
            check=True, capture_output=True, text=True,
        )
        script = temporary / "powerpoint_renderer.mjs"
        shutil.copy2(module, script)
        input_path = temporary / "input.json"
        manifest_path = temporary / "manifest.json"
        payload = {
            "instruction_package":
                instruction_package.model_dump(mode="json"),
            "options": {
                **options.model_dump(mode="json"),
                "local_assets": validated_assets,
            },
        }
        input_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        subprocess.run(
            [str(node), str(script), str(input_path), str(output),
             str(manifest_path), str(preview)],
            cwd=temporary, check=True, capture_output=True, text=True,
        )
        validation = validate_powerpoint(
            output, instruction_package, manifest_path
        )
    if not validation.valid:
        output.unlink(missing_ok=True)
        raise ValueError(
            "Generated PowerPoint failed structural validation: "
            + ", ".join(issue.code for issue in validation.issues)
        )
    notes_path.write_text(
        "\n\n".join(
            f"SLIDE {slide.slide_number}: {slide.slide_id}\n"
            f"{slide.notes_payload.plain_text_fallback}"
            for slide in instruction_package.slides
        ) + "\n",
        encoding="utf-8",
    )
    font_substitutions = [
        FontSubstitution(
            role="display/title",
            requested=instruction_package.theme.title_font_family,
            rendered="Georgia",
            reason="Cross-platform editorial fallback for Google Slides import.",
        ),
        FontSubstitution(
            role="body/label/footer",
            requested=instruction_package.theme.body_font_family,
            rendered="Arial",
            reason="Cross-platform classroom fallback for Google Slides import.",
        ),
    ]
    result = PowerPointRenderResult(
        render_id=render_id,
        output_path=str(output),
        notes_fallback_path=str(notes_path),
        preview_directory=str(preview) if options.render_previews else None,
        presentation_id=instruction_package.presentation_id,
        package_id=instruction_package.package_id,
        slide_count=len(instruction_package.slides),
        rendered_slide_ids=validation.rendered_slide_ids,
        warnings=[],
        unsupported_features=[],
        font_substitutions=font_substitutions,
        overflow_report=[
            PowerPointRenderWarning(
                code="source_capacity_warning",
                message="Source package flagged conservative text capacity.",
                slide_id=slide.slide_id,
            )
            for slide in instruction_package.slides
            if any(
                len(block.text) > 700 for block in slide.text_blocks
            )
        ],
        asset_report=assets,
        validation_report=validation,
        notes_support_status=(
            NotesSupportStatus.native_verified
            if validation.native_notes_verified
            else NotesSupportStatus.fallback_only
        ),
        file_digest=file_checksum(output),
    )
    repository.save(result)
    return result


__all__ = [
    "PowerPointRenderRepository", "render_powerpoint",
]
