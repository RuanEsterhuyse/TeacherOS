"""Phase 1 curriculum source-manifest orchestration."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from curriculum.adapters.ckla_intelligence import (
    CKLACurriculumIntelligenceAdapter,
)
from curriculum.intelligence.extractor import (
    EXTRACTION_VERSION,
    ResourceExtractor,
)
from curriculum.intelligence.ids import content_digest, stable_id
from curriculum.intelligence.mappings import apply_coordinate_mappings
from curriculum.intelligence.readiness import evaluate_readiness
from curriculum.intelligence.repository import (
    CurriculumIntelligenceRepository,
)
from curriculum.intelligence.snapshot import readiness_markdown, write_json
from curriculum.lesson_locator import CKLALessonLocator
from schemas.curriculum_intelligence_schema import (
    BuildManifest,
    CurriculumLesson,
    ReadinessReport,
    SourceCoordinateMapping,
)
from schemas.curriculum_schema import CurriculumIndex


@dataclass(frozen=True)
class CurriculumIntelligenceBuildResult:
    lesson: CurriculumLesson
    readiness: ReadinessReport
    build_manifest: BuildManifest
    output_directory: Path
    output_files: tuple[Path, ...]


class CurriculumIntelligenceService:
    """Build a parallel source manifest without invoking lesson generation."""

    def __init__(
        self,
        *,
        database_path: str | Path,
        output_directory: str | Path,
        extractor: ResourceExtractor | None = None,
        adapter: CKLACurriculumIntelligenceAdapter | None = None,
    ) -> None:
        self.repository = CurriculumIntelligenceRepository(database_path)
        self.output_directory = Path(output_directory)
        self.extractor = extractor or ResourceExtractor()
        self.adapter = adapter or CKLACurriculumIntelligenceAdapter()

    def build_lesson_one(
        self,
        *,
        index_path: str | Path,
        teacher_guide_path: str | Path,
        instructional_text_path: str | Path,
        activity_resource_path: str | Path,
        online_resources_path: str | Path,
        terms_of_use_path: str | Path,
        coordinate_mappings_path: str | Path | None = None,
    ) -> CurriculumIntelligenceBuildResult:
        index: CurriculumIndex = CKLALessonLocator().load_index(index_path)
        lesson_entry = CKLALessonLocator.get_lesson_entry(index, 1)
        curriculum_id = stable_id(
            "curriculum",
            index.curriculum.curriculum_name,
            index.curriculum.grade,
            "language-arts",
        )
        specs = {
            "teacher_guide": (
                "teacher_guide",
                "Teacher Guide",
                teacher_guide_path,
            ),
            "instructional_text": (
                "instructional_text",
                "Us, in Progress: Short Stories About Young Latinos",
                instructional_text_path,
            ),
            "activity_resource": (
                "activity_resource",
                "Grade 8 Unit 1 Activity Resource",
                activity_resource_path,
            ),
            "online_resources": (
                "online_resource_guide",
                "Grade 8 Unit 1 Online Resources",
                online_resources_path,
            ),
            "terms_of_use": (
                "license_document",
                "Curriculum Terms of Use",
                terms_of_use_path,
            ),
        }
        resources = {}
        pages = {}
        stale_resource_ids = []
        for key, (resource_type, title, source_path) in specs.items():
            resource, resource_pages = self.extractor.extract(
                curriculum_id=curriculum_id,
                resource_type=resource_type,
                title=title,
                source_path=source_path,
            )
            previous = self.repository.resource_checksum(resource.id)
            if previous and previous != resource.checksum:
                stale_resource_ids.append(resource.id)
                resource = resource.model_copy(update={
                    "warnings": list(resource.warnings)
                    + [
                        "Stored resource checksum changed; dependent source intelligence was rebuilt."
                    ]
                })
            resources[key] = resource
            pages[key] = resource_pages

        translation = self.adapter.build_source_lesson(
            curriculum_id=curriculum_id,
            curriculum_title=index.curriculum.curriculum_name,
            unit_title=(
                index.curriculum.unit_title
                or f"Unit {index.curriculum.unit}"
            ),
            lesson_entry=lesson_entry,
            resources=resources,
            pages=pages,
        )
        coordinate_mappings: list[SourceCoordinateMapping] = []
        if coordinate_mappings_path is not None:
            mapping_payload = json.loads(
                Path(coordinate_mappings_path).read_text(encoding="utf-8")
            )
            if not isinstance(mapping_payload, list):
                raise ValueError(
                    "Coordinate mapping file must contain a JSON list."
                )
            coordinate_mappings = [
                SourceCoordinateMapping.model_validate(value)
                for value in mapping_payload
            ]
        assignments, coordinate_mappings = apply_coordinate_mappings(
            translation.assignments,
            coordinate_mappings,
            resources=translation.resources,
            segments=translation.segments,
        )
        readiness = evaluate_readiness(
            translation.lesson.id,
            translation.resources,
            assignments,
        )
        lesson = translation.lesson.model_copy(
            update={"readiness_state": readiness.state}
        )

        snapshot_basis = {
            "curriculum": translation.curriculum.model_dump(mode="json"),
            "unit": translation.unit.model_dump(mode="json"),
            "lesson": lesson.model_dump(mode="json"),
            "resources": [
                value.model_dump(mode="json")
                for value in sorted(
                    translation.resources, key=lambda item: item.id
                )
            ],
            "assignments": [
                value.model_dump(mode="json")
                for value in sorted(
                    assignments, key=lambda item: item.id
                )
            ],
            "coordinate_mappings": [
                value.model_dump(mode="json")
                for value in sorted(
                    coordinate_mappings, key=lambda item: item.id
                )
            ],
            "segments": [
                value.model_dump(mode="json")
                for value in sorted(
                    translation.segments, key=lambda item: item.id
                )
            ],
            "readiness": readiness.model_dump(mode="json"),
        }
        snapshot_digest = content_digest(snapshot_basis)
        build_manifest = BuildManifest(
            build_id=stable_id(
                "build",
                curriculum_id,
                lesson.id,
                snapshot_digest,
                self.adapter.adapter_version,
                EXTRACTION_VERSION,
            ),
            adapter_id=self.adapter.adapter_id,
            adapter_version=self.adapter.adapter_version,
            extraction_version=EXTRACTION_VERSION,
            curriculum_id=curriculum_id,
            lesson_id=lesson.id,
            resource_checksums={
                value.id: value.checksum
                for value in sorted(
                    translation.resources, key=lambda item: item.id
                )
            },
            stale_resource_ids=sorted(stale_resource_ids),
            snapshot_digest=snapshot_digest,
        )

        self.repository.save_curriculum(translation.curriculum)
        self.repository.save_unit(translation.unit)
        for key, resource in resources.items():
            self.repository.save_resource(resource)
            self.repository.replace_pages(
                resource.id, translation.pages[key]
            )
        self.repository.save_lesson(lesson)
        self.repository.replace_assignments(
            lesson.id, assignments
        )
        self.repository.replace_segments(
            [value.id for value in translation.resources],
            translation.segments,
        )
        self.repository.replace_coordinate_mappings(
            lesson.id, coordinate_mappings
        )
        self.repository.save_readiness(readiness)
        self.repository.save_build_manifest(build_manifest)

        page_summary = [
            {
                "resource_id": resource.id,
                "title": resource.title,
                "page_count": resource.page_count,
                "pages": [
                    {
                        "page_id": page.id,
                        "pdf_page_number": page.pdf_page_number,
                        "display_page_number": page.display_page_number,
                        "printed_page_label": page.printed_page_label,
                        "document_page_label": page.document_page_label,
                        "headings": page.headings,
                        "extraction_confidence": page.extraction_confidence,
                        "warnings": page.warnings,
                    }
                    for page in translation.pages[key]
                ],
            }
            for key, resource in resources.items()
        ]
        curriculum_manifest = {
            "curriculum": translation.curriculum,
            "units": [translation.unit],
            "lesson_ids": [lesson.id],
        }
        output_values = {
            "curriculum_manifest.json": curriculum_manifest,
            "resources.json": sorted(
                translation.resources, key=lambda item: item.id
            ),
            "resource_pages_summary.json": page_summary,
            "lesson_1_curriculum_lesson.json": lesson,
            "lesson_1_assignments.json": assignments,
            "lesson_1_coordinate_mappings.json": coordinate_mappings,
            "lesson_1_text_segments.json": translation.segments,
            "lesson_1_readiness.json": readiness,
            "build_manifest.json": build_manifest,
        }
        output_files = [
            write_json(self.output_directory / name, value)
            for name, value in output_values.items()
        ]
        markdown_path = self.output_directory / "lesson_1_readiness.md"
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(
            readiness_markdown(
                lesson,
                translation.resources,
                assignments,
                readiness,
                coordinate_mappings,
            ),
            encoding="utf-8",
        )
        output_files.append(markdown_path)
        return CurriculumIntelligenceBuildResult(
            lesson=lesson,
            readiness=readiness,
            build_manifest=build_manifest,
            output_directory=self.output_directory,
            output_files=tuple(output_files),
        )


__all__ = [
    "CurriculumIntelligenceBuildResult",
    "CurriculumIntelligenceService",
]
