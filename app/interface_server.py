"""Local HTTP bridge between the TeacherOS web interface and generation engine."""

from __future__ import annotations

import json
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from app.teacheros import TeacherOS
from schemas.reader_output_schema import CurriculumReaderOutput
from curriculum.intelligence.generate_teaching_package import (
    generate_teaching_package,
)
from curriculum.intelligence.pasted_lesson_analyzer import (
    analyze_pasted_lesson,
)
from curriculum.intelligence.daily_lesson_generator import (
    generate_daily_lesson_package,
)
from curriculum.intelligence.daily_lesson_provider import (
    DailyLessonProvider,
)
from curriculum.intelligence.daily_lesson_repository import (
    DailyLessonRepository,
)
from curriculum.intelligence.pasted_lesson_repository import (
    PastedLessonRepository,
    create_pasted_lesson_source,
)
from curriculum.intelligence.playbook_enrichment import (
    enrich_teacher_playbook,
)
from curriculum.intelligence.playbook_enrichment_provider import (
    PlaybookEnrichmentProvider,
)
from curriculum.intelligence.presentation_spec import (
    build_presentation_spec,
)
from curriculum.intelligence.presentation_spec_validator import (
    validate_presentation_spec,
)
from curriculum.intelligence.renderer_instruction_adapter import (
    build_renderer_instruction_package,
)
from curriculum.intelligence.renderer_instruction_validator import (
    validate_renderer_instruction_package,
)
from curriculum.intelligence.publishing import write_publishing_metadata
from renderer.google_docs_publisher import GoogleDocsPublisher
from renderer.teaching_package_slides import (
    TeachingPackageGoogleSlidesPublisher,
)
from renderer.powerpoint_instruction_renderer import (
    PowerPointRenderRepository,
    render_powerpoint,
)
from schemas.teaching_package_schema import StructuredTeachingPackage
from schemas.playbook_enrichment_schema import (
    ApprovedPlaybookEnrichment,
    EnrichmentStatus,
    PlaybookEnrichmentOptions,
    PlaybookEnrichmentResult,
    TeacherApprovalStatus,
)
from schemas.pasted_lesson_schema import utc_now
from schemas.presentation_spec_schema import (
    ApprovalStatus,
    PresentationBuildOptions,
    PresentationBuildResult,
)
from schemas.renderer_instruction_schema import (
    RendererInstructionOptions,
    RendererInstructionResult,
    RendererPackageApprovalStatus,
)
from schemas.powerpoint_render_schema import PowerPointRenderOptions
from schemas.daily_lesson_schema import DailyLessonGenerationOptions


PROJECT_ROOT = Path(__file__).parents[1].resolve()
GENERATION_STAGES = [
    ("prepare_lesson", None, "Preparing lesson"),
    ("curriculum_reader", "01_reader_output.json", "Reading curriculum"),
    ("curriculum_analyzer", "02_analyzer_output.json", "Analyzing curriculum"),
    ("instruction_designer", "03_instruction_design.json", "Designing instruction"),
    ("presentation_designer", "04_presentation_design.json", "Designing presentation"),
    ("lesson_assembler", "05_lesson_package.json", "Assembling lesson"),
    ("lesson_validator", "06_validation_report.json", "Validating lesson"),
    (
        "presentation_renderer_prompt_generator",
        "RendererPromptBundle.md",
        "Preparing renderer prompt",
    ),
    (
        "gamma_handoff_prompt_generator",
        "GammaDeckPrompt.md",
        "Preparing Gamma handoff",
    ),
    ("lesson_package_parser", "07_validated_lesson.json", "Finalizing package"),
]


@dataclass
class GenerationJob:
    job_id: str
    request_id: str
    curriculum_name: str
    grade: str
    unit: str
    lesson_number: int
    started_at_ns: int = field(default_factory=time.time_ns)
    state: str = "running"
    result: dict[str, Any] | None = None
    errors: list[str] = field(default_factory=list)
    job_kind: str = "lesson"


class TeacherOSInterface:
    """Read-only catalog plus asynchronous access to the existing pipeline."""

    def __init__(
        self,
        teacheros: TeacherOS | None = None,
        pasted_repository: PastedLessonRepository | None = None,
        playbook_enrichment_provider: PlaybookEnrichmentProvider | None = None,
        daily_lesson_repository: DailyLessonRepository | None = None,
        daily_lesson_provider: DailyLessonProvider | None = None,
    ) -> None:
        self.teacheros = teacheros or TeacherOS(project_root=PROJECT_ROOT)
        self.pasted_repository = (
            pasted_repository
            or PastedLessonRepository(
                PROJECT_ROOT / "output" / "pasted_lesson_intake"
            )
        )
        self.playbook_enrichment_provider = playbook_enrichment_provider
        self.daily_lesson_repository = (
            daily_lesson_repository
            or DailyLessonRepository(
                PROJECT_ROOT / "output" / "daily_lesson_generator"
            )
        )
        self.daily_lesson_provider = daily_lesson_provider
        self.powerpoint_repository = PowerPointRenderRepository(
            PROJECT_ROOT / "output" / "powerpoint_renderer"
        )
        self.enrichment_previews: dict[str, PlaybookEnrichmentResult] = {}
        self.presentation_previews: dict[str, PresentationBuildResult] = {}
        self.renderer_package_previews: dict[
            str, RendererInstructionResult
        ] = {}
        self.renderer_package_options: dict[
            str, RendererInstructionOptions
        ] = {}
        self.jobs: dict[str, GenerationJob] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _read_generated_vocabulary(request_id: str) -> list[str]:
        path = PROJECT_ROOT / "output" / "generation_runs" / request_id / "01_reader_output.json"
        if not path.is_file():
            return []
        try:
            return CurriculumReaderOutput.model_validate_json(
                path.read_text(encoding="utf-8")
            ).vocabulary
        except (OSError, ValueError):
            return []

    def catalog(self) -> dict[str, Any]:
        curricula: dict[str, dict[str, Any]] = {}
        for unit in self.teacheros.library.list_units():
            adapter = self.teacheros.curriculum_adapter(
                unit.curriculum_name
            )
            index_path = adapter.default_index_path(unit)
            index = adapter.load_index(index_path)
            file_status = self.teacheros.library.verify_files_exist(unit)
            curriculum = curricula.setdefault(
                unit.curriculum_name,
                {
                    "id": unit.curriculum_name.lower().replace(" ", "-"),
                    "name": unit.curriculum_name,
                    "units": [],
                },
            )
            lessons = []
            for entry in index.lessons:
                request = self.teacheros.create_lesson_request(
                    curriculum_name=unit.curriculum_name,
                    grade=unit.grade,
                    unit=unit.unit,
                    lesson_number=entry.lesson_number,
                )
                lessons.append(
                    {
                        "number": entry.lesson_number,
                        "title": entry.lesson_title or f"Lesson {entry.lesson_number}",
                        "duration": entry.lesson_duration,
                        "objectives": entry.lesson_objective,
                        "vocabulary": self._read_generated_vocabulary(request.request_id),
                        "resources": {
                            "materials": entry.materials,
                            "reader_pages": entry.reader_pages,
                            "activity_pages": entry.activity_book_pages,
                            "teacher_guide_pages": (
                                f"{entry.start_printed_page}–{entry.end_printed_page}"
                                if entry.start_printed_page and entry.end_printed_page
                                else None
                            ),
                        },
                        "generated": (
                            PROJECT_ROOT
                            / "output"
                            / "generation_runs"
                            / request.request_id
                            / "RendererPromptBundle.md"
                        ).is_file(),
                    }
                )
            curriculum["units"].append(
                {
                    "grade": unit.grade,
                    "number": unit.unit,
                    "title": unit.unit_title or f"Unit {unit.unit}",
                    "lesson_count": len(lessons),
                    "source_ready": all(file_status.values()),
                    "lessons": lessons,
                }
            )
        ordered = sorted(curricula.values(), key=lambda item: item["name"])
        for curriculum in ordered:
            curriculum["units"].sort(key=lambda item: (item["grade"], item["number"]))
        return {"curricula": ordered}

    def start_generation(
        self, curriculum_name: str, grade: str, unit: str, lesson_number: int
    ) -> GenerationJob:
        request = self.teacheros.create_lesson_request(
            curriculum_name=curriculum_name,
            grade=grade,
            unit=unit,
            lesson_number=lesson_number,
        )
        job = GenerationJob(
            job_id=uuid.uuid4().hex,
            request_id=request.request_id,
            curriculum_name=curriculum_name,
            grade=grade,
            unit=unit,
            lesson_number=lesson_number,
        )
        with self._lock:
            self.jobs[job.job_id] = job
        threading.Thread(target=self._run_generation, args=(job,), daemon=True).start()
        return job

    def start_teaching_package(
        self, curriculum_name: str, grade: str, unit: str, lesson_number: int
    ) -> GenerationJob:
        if (
            curriculum_name.casefold() != "ckla"
            or str(grade) != "8"
            or str(unit) != "1"
        ):
            raise ValueError(
                "Teaching packages currently support indexed CKLA Grade 8 "
                "Unit 1 lessons."
            )
        request = self.teacheros.create_lesson_request(
            curriculum_name=curriculum_name,
            grade=grade,
            unit=unit,
            lesson_number=lesson_number,
        )
        job = GenerationJob(
            job_id=uuid.uuid4().hex,
            request_id=request.request_id,
            curriculum_name=curriculum_name,
            grade=grade,
            unit=unit,
            lesson_number=lesson_number,
            job_kind="teaching_package",
        )
        with self._lock:
            self.jobs[job.job_id] = job
        threading.Thread(
            target=self._run_teaching_package,
            args=(job,),
            daemon=True,
        ).start()
        return job

    def _run_teaching_package(self, job: GenerationJob) -> None:
        output = PROJECT_ROOT / "output" / f"lesson_{job.lesson_number:03d}"
        try:
            package, paths, resumed = generate_teaching_package(
                lesson=job.lesson_number,
                output_directory=output,
            )
            job.result = {
                "validation_result": package.validation.status,
                "output_directory": str(output),
                "resumed": resumed,
                "artifacts": {
                    key: str(value) for key, value in paths.items()
                },
                "agenda": [
                    {
                        "order": value.official_order,
                        "official": value.official_title.text,
                        "student_friendly":
                            value.student_friendly_title.text,
                        "duration": value.duration_minutes,
                    }
                    for value in package.agenda
                ],
                "objectives": [
                    {
                        "official": value.official.text,
                        "student_friendly": value.student_friendly.text,
                        "meaning_preserved": value.meaning_preserved,
                    }
                    for value in package.objectives
                ],
                "teaching_steps": len(package.teaching_steps),
                "questions": len(package.questions),
                "student_slides": len(package.student_slides),
                "warnings": package.warnings + [
                    finding.message
                    for finding in package.validation.findings
                    if finding.severity.value == "warning"
                ],
            }
            job.state = "complete"
        except Exception as error:
            job.errors = [str(error)]
            job.state = "failed"

    def _run_generation(self, job: GenerationJob) -> None:
        try:
            result = self.teacheros.generate_lesson(
                curriculum_name=job.curriculum_name,
                grade=job.grade,
                unit=job.unit,
                lesson_number=job.lesson_number,
            )
            job.result = result.model_dump(mode="json")
            job.errors = result.errors
            job.state = "complete" if result.status in {
                "completed",
                "completed_with_warnings",
            } else "failed"
        except Exception as error:  # keep the UI responsive on unexpected failures
            job.errors = [str(error)]
            job.state = "failed"

    def job_status(self, job_id: str) -> dict[str, Any]:
        with self._lock:
            job = self.jobs.get(job_id)
        if job is None:
            raise KeyError(job_id)
        if job.job_kind == "teaching_package":
            return {
                "job_id": job.job_id,
                "request_id": job.request_id,
                "kind": job.job_kind,
                "state": job.state,
                "progress": 100 if job.state in {"complete", "failed"} else 50,
                "current_stage": (
                    "Teaching package ready"
                    if job.state == "complete"
                    else (
                        "Teaching package failed"
                        if job.state == "failed"
                        else "Building synchronized teaching package"
                    )
                ),
                "errors": job.errors,
                **(job.result or {}),
            }
        run_dir = PROJECT_ROOT / "output" / "generation_runs" / job.request_id
        completed_stages = (
            job.result.get("completed_stages", []) if job.result else []
        )
        current_indices = [0]
        for index, (stage_id, filename, _) in enumerate(GENERATION_STAGES):
            path = run_dir / filename if filename else None
            artifact_is_current = (
                path is not None
                and path.is_file()
                and path.stat().st_mtime_ns >= job.started_at_ns
            )
            if artifact_is_current or stage_id in completed_stages:
                current_indices.append(index)
        furthest_completed = max(current_indices)
        completed_count = furthest_completed + 1
        current_index = min(
            furthest_completed + 1,
            len(GENERATION_STAGES) - 1,
        )
        if job.state == "complete":
            current_index = len(GENERATION_STAGES) - 1
        failed_stage = job.result.get("failed_stage") if job.result else None
        if job.state == "failed" and failed_stage:
            failed_index = next(
                (
                    index
                    for index, (stage_id, _, _) in enumerate(GENERATION_STAGES)
                    if stage_id == failed_stage
                ),
                current_index,
            )
            current_index = failed_index
        progress = round((completed_count / len(GENERATION_STAGES)) * 100)
        if job.state == "complete":
            progress = 100
        blocking_findings: list[dict[str, Any]] = []
        report_path = run_dir / "06_validation_report.json"
        if (
            job.state == "failed"
            and failed_stage == "lesson_validator"
            and report_path.is_file()
            and report_path.stat().st_mtime_ns >= job.started_at_ns
        ):
            report = json.loads(report_path.read_text(encoding="utf-8"))
            blocking_findings = [
                finding
                for finding in report.get("findings", [])
                if finding.get("severity") == "error"
            ]
        return {
            "job_id": job.job_id,
            "request_id": job.request_id,
            "state": job.state,
            "progress": progress,
            "current_stage": GENERATION_STAGES[current_index][2],
            "failed_stage": failed_stage,
            "stages": [
                {
                    "id": stage_id,
                    "label": label,
                    "complete": (
                        index <= furthest_completed
                        or stage_id in completed_stages
                    ),
                }
                for index, (stage_id, filename, label) in enumerate(
                    GENERATION_STAGES
                )
            ],
            "validation_result": (
                job.result.get("validation_result") if job.result else None
            ),
            "slide_count": job.result.get("slide_count", 0) if job.result else 0,
            "warnings": job.result.get("warnings", []) if job.result else [],
            "errors": job.errors,
            "blocking_findings": blocking_findings,
        }

    def open_output(self, request_id: str, target: str) -> None:
        run_dir = self.artifact_path(request_id)
        selected = (
            run_dir / "RendererPromptBundle.md" if target == "bundle" else run_dir
        )
        if not selected.exists():
            raise FileNotFoundError(selected)
        subprocess.Popen(["open", str(selected)])

    @staticmethod
    def artifact_path(request_id: str, filename: str | None = None) -> Path:
        run_dir = (PROJECT_ROOT / "output" / "generation_runs" / request_id).resolve()
        output_root = (PROJECT_ROOT / "output" / "generation_runs").resolve()
        if run_dir.parent != output_root:
            raise ValueError("invalid output path")
        return run_dir / filename if filename else run_dir

    def read_gamma_prompt(self, request_id: str) -> str:
        path = self.artifact_path(request_id, "GammaDeckPrompt.md")
        if not path.is_file():
            raise FileNotFoundError(path)
        return path.read_text(encoding="utf-8")

    def copy_gamma_prompt(self, request_id: str) -> None:
        prompt = self.read_gamma_prompt(request_id)
        subprocess.run(
            ["pbcopy"],
            input=prompt,
            text=True,
            check=True,
        )

    @staticmethod
    def teaching_package_path(
        lesson_number: int, filename: str | None = None
    ) -> Path:
        root = (PROJECT_ROOT / "output" / f"lesson_{lesson_number:03d}").resolve()
        output_root = (PROJECT_ROOT / "output").resolve()
        if root.parent != output_root:
            raise ValueError("invalid teaching-package path")
        return root / filename if filename else root

    def read_teaching_artifact(
        self, lesson_number: int, artifact: str
    ) -> str:
        allowed = {
            "teacher_companion.md",
            "student_slides.md",
            "teaching_package_validation.md",
            "teaching_package.json",
            "teacher_companion.json",
            "student_slides.json",
        }
        if artifact not in allowed:
            raise ValueError("unsupported teaching-package artifact")
        path = self.teaching_package_path(lesson_number, artifact)
        if not path.is_file():
            raise FileNotFoundError(path)
        return path.read_text(encoding="utf-8")

    def publish_teaching_package(
        self, lesson_number: int, target: str
    ) -> dict[str, Any]:
        path = self.teaching_package_path(
            lesson_number, "teaching_package.json"
        )
        package = StructuredTeachingPackage.model_validate_json(
            path.read_text(encoding="utf-8")
        )
        if target == "google-doc":
            result = GoogleDocsPublisher().publish(package)
            write_publishing_metadata(path.parent, google_doc=result)
        elif target == "google-slides":
            result = TeachingPackageGoogleSlidesPublisher().publish(package)
            write_publishing_metadata(path.parent, google_slides=result)
        else:
            raise ValueError("unsupported publishing target")
        return result

    def save_pasted_lesson_source(
        self, payload: dict[str, Any]
    ) -> dict[str, Any]:
        source = create_pasted_lesson_source(
            grade=str(payload["grade"]),
            unit=str(payload["unit"]),
            lesson_number=int(payload["lesson_number"]),
            lesson_title=str(payload["lesson_title"]),
            teacher_guide_page_start=(
                int(payload["teacher_guide_page_start"])
                if payload.get("teacher_guide_page_start") not in {
                    None, ""
                } else None
            ),
            teacher_guide_page_end=(
                int(payload["teacher_guide_page_end"])
                if payload.get("teacher_guide_page_end") not in {
                    None, ""
                } else None
            ),
            teacher_guide_text=str(payload["teacher_guide_text"]),
            student_reader_text=(
                str(payload["student_reader_text"])
                if payload.get("student_reader_text") not in {None, ""}
                else None
            ),
            activity_book_text=(
                str(payload["activity_book_text"])
                if payload.get("activity_book_text") not in {None, ""}
                else None
            ),
            source_notes=(
                str(payload["source_notes"])
                if payload.get("source_notes") not in {None, ""}
                else None
            ),
        )
        return self.pasted_repository.save_source(source).model_dump(
            mode="json"
        )

    def generate_daily_lesson(
        self, payload: dict[str, Any]
    ) -> dict[str, Any]:
        source = create_pasted_lesson_source(
            grade=str(payload["grade"]),
            unit=str(payload["unit"]),
            lesson_number=int(payload["lesson_number"]),
            lesson_title=str(payload["lesson_title"]),
            teacher_guide_page_start=(
                int(payload["teacher_guide_page_start"])
                if payload.get("teacher_guide_page_start") not in {None, ""}
                else None
            ),
            teacher_guide_page_end=(
                int(payload["teacher_guide_page_end"])
                if payload.get("teacher_guide_page_end") not in {None, ""}
                else None
            ),
            teacher_guide_text=str(payload["teacher_guide_text"]),
            student_reader_text=(
                str(payload["student_reader_text"])
                if payload.get("student_reader_text") not in {None, ""}
                else None
            ),
            activity_book_text=(
                str(payload["activity_book_text"])
                if payload.get("activity_book_text") not in {None, ""}
                else None
            ),
        )
        self.pasted_repository.save_source(source)
        options = DailyLessonGenerationOptions.model_validate(
            payload.get("options") or {}
        )
        result = generate_daily_lesson_package(
            source,
            options,
            provider=self.daily_lesson_provider,
            repository=self.daily_lesson_repository,
        )
        return result.model_dump(mode="json")

    def list_daily_lesson_packages(self) -> list[dict[str, Any]]:
        return [
            value.model_dump(mode="json")
            for value in self.daily_lesson_repository.list_packages()
        ]

    def load_daily_lesson_package(
        self, package_id: str
    ) -> dict[str, Any]:
        return self.daily_lesson_repository.load(package_id).model_dump(
            mode="json"
        )

    def read_daily_lesson_artifact(
        self, package_id: str, artifact: str
    ) -> str:
        return self.daily_lesson_repository.read_markdown(
            package_id, artifact
        )

    def list_pasted_lesson_sources(self) -> list[dict[str, Any]]:
        return [
            value.model_dump(mode="json")
            for value in self.pasted_repository.list_sources()
        ]

    def load_pasted_lesson_source(
        self, source_id: str
    ) -> dict[str, Any]:
        return self.pasted_repository.load_source(source_id).model_dump(
            mode="json"
        )

    def analyze_pasted_lesson_source(
        self, source_id: str
    ) -> dict[str, Any]:
        source = self.pasted_repository.load_source(source_id)
        return analyze_pasted_lesson(source).model_dump(mode="json")

    def save_preliminary_playbook(
        self, source_id: str
    ) -> dict[str, Any]:
        source = self.pasted_repository.load_source(source_id)
        result = analyze_pasted_lesson(source)
        return self.pasted_repository.save_playbook(
            result.playbook
        ).model_dump(mode="json")

    def list_teacher_playbooks(self) -> list[dict[str, Any]]:
        return [
            value.model_dump(mode="json")
            for value in self.pasted_repository.list_playbooks()
        ]

    def load_teacher_playbook(
        self, playbook_id: str
    ) -> dict[str, Any]:
        return self.pasted_repository.load_playbook(
            playbook_id
        ).model_dump(mode="json")

    def enrich_pasted_lesson_source(
        self, source_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        source = self.pasted_repository.load_source(source_id)
        baseline = analyze_pasted_lesson(source)
        options = PlaybookEnrichmentOptions.model_validate(payload or {})
        result = enrich_teacher_playbook(
            source,
            baseline,
            options,
            provider=self.playbook_enrichment_provider,
        )
        if result.status != EnrichmentStatus.failed:
            self.enrichment_previews[result.enrichment_id] = result
        return result.model_dump(mode="json")

    def approve_playbook_enrichment(
        self, enrichment_id: str
    ) -> dict[str, Any]:
        result = self.enrichment_previews.get(enrichment_id)
        if result is None:
            raise KeyError(enrichment_id)
        if (
            result.status == EnrichmentStatus.failed
            or result.provider_metadata is None
        ):
            raise ValueError("A failed enrichment cannot be approved.")
        source = self.pasted_repository.load_source(
            result.enriched_playbook.source_id
        )
        baseline = analyze_pasted_lesson(source)
        approved = ApprovedPlaybookEnrichment(
            enrichment_id=result.enrichment_id,
            source_id=source.source_id,
            baseline_analyzer_version=baseline.analyzer_version,
            enrichment_version=result.enrichment_version,
            enriched_playbook=result.enriched_playbook,
            provider_metadata=result.provider_metadata,
            grounding_summary=result.grounding_report,
            teacher_approval_status=TeacherApprovalStatus.approved,
            approved_at=utc_now(),
        )
        saved = self.pasted_repository.save_approved_enrichment(approved)
        self.enrichment_previews.pop(enrichment_id, None)
        return saved.model_dump(mode="json")

    def list_approved_playbook_enrichments(
        self,
    ) -> list[dict[str, Any]]:
        return [
            value.model_dump(mode="json")
            for value in self.pasted_repository.list_approved_enrichments()
        ]

    def _approved_enrichment(self, identifier: str):
        try:
            return self.pasted_repository.load_approved_enrichment(identifier)
        except FileNotFoundError:
            matches = [
                value
                for value in self.pasted_repository.list_approved_enrichments()
                if value.enriched_playbook.playbook_id == identifier
            ]
            if len(matches) != 1:
                raise ValueError(
                    "Approved playbook identifier is missing or ambiguous."
                )
            return matches[0]

    def build_presentation_spec(
        self, approved_playbook_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        approved = self._approved_enrichment(approved_playbook_id)
        options = PresentationBuildOptions.model_validate(payload or {})
        result = build_presentation_spec(approved, options)
        self.presentation_previews[
            result.presentation_spec.presentation_id
        ] = result
        return result.model_dump(mode="json")

    def list_presentation_specs(self) -> list[dict[str, Any]]:
        return [
            value.model_dump(mode="json")
            for value in self.pasted_repository.list_presentation_specs()
        ]

    def load_presentation_spec(
        self, presentation_id: str
    ) -> dict[str, Any]:
        return self.pasted_repository.load_presentation_spec(
            presentation_id
        ).model_dump(mode="json")

    def validate_presentation_preview(
        self, presentation_id: str
    ) -> dict[str, Any]:
        preview = self.presentation_previews.get(presentation_id)
        if preview is not None:
            spec = preview.presentation_spec
        else:
            spec = self.pasted_repository.load_presentation_spec(
                presentation_id
            )
        approved = self.pasted_repository.load_approved_enrichment(
            spec.approved_enrichment_id
        )
        return validate_presentation_spec(
            spec, approved
        ).model_dump(mode="json")

    def reorder_presentation_preview(
        self, presentation_id: str, ordered_slide_ids: list[str]
    ) -> dict[str, Any]:
        preview = self.presentation_previews.get(presentation_id)
        if preview is None:
            raise KeyError(presentation_id)
        current = preview.presentation_spec
        current_ids = [slide.slide_id for slide in current.slides]
        if (
            len(ordered_slide_ids) != len(set(ordered_slide_ids))
            or set(ordered_slide_ids) != set(current_ids)
        ):
            raise ValueError(
                "Reordering must include every existing slide exactly once."
            )
        by_id = {slide.slide_id: slide for slide in current.slides}
        slides = [
            by_id[slide_id].model_copy(update={"slide_number": index})
            for index, slide_id in enumerate(ordered_slide_ids, 1)
        ]
        candidate = current.model_copy(update={
            "slides": slides,
            "validation_status": current.validation_status,
        })
        approved = self.pasted_repository.load_approved_enrichment(
            current.approved_enrichment_id
        )
        report = validate_presentation_spec(candidate, approved)
        if not report.valid:
            codes = ", ".join(
                sorted({issue.code for issue in report.issues})
            )
            raise ValueError(
                f"Reordering would break instructional requirements: {codes}"
            )
        candidate = candidate.model_copy(update={
            "validation_status": report.status
        })
        updated = preview.model_copy(update={
            "presentation_spec": candidate,
            "source_coverage": report.source_coverage,
            "activity_coverage": report.activity_coverage,
            "validation_report": report,
        })
        self.presentation_previews[presentation_id] = updated
        return updated.model_dump(mode="json")

    def approve_presentation_spec(
        self, presentation_id: str
    ) -> dict[str, Any]:
        preview = self.presentation_previews.get(presentation_id)
        if preview is None:
            raise KeyError(presentation_id)
        spec = preview.presentation_spec
        approved_playbook = (
            self.pasted_repository.load_approved_enrichment(
                spec.approved_enrichment_id
            )
        )
        report = validate_presentation_spec(spec, approved_playbook)
        if not report.valid:
            raise ValueError(
                "Presentation specification failed validation and cannot be approved."
            )
        approved_spec = spec.model_copy(update={
            "validation_status": report.status,
            "approval_status": ApprovalStatus.approved,
            "approved_at": utc_now(),
        })
        saved = self.pasted_repository.save_presentation_spec(approved_spec)
        self.presentation_previews.pop(presentation_id, None)
        return saved.model_dump(mode="json")

    def build_renderer_instruction_package(
        self, presentation_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        presentation = self.pasted_repository.load_presentation_spec(
            presentation_id
        )
        options = RendererInstructionOptions.model_validate(payload or {})
        result = build_renderer_instruction_package(presentation, options)
        package_id = result.instruction_package.package_id
        self.renderer_package_previews[package_id] = result
        self.renderer_package_options[package_id] = options
        return result.model_dump(mode="json")

    def list_renderer_instruction_packages(self) -> list[dict[str, Any]]:
        return [
            value.model_dump(mode="json")
            for value in (
                self.pasted_repository.list_renderer_instruction_packages()
            )
        ]

    def load_renderer_instruction_package(
        self, package_id: str
    ) -> dict[str, Any]:
        return self.pasted_repository.load_renderer_instruction_package(
            package_id
        ).model_dump(mode="json")

    def validate_renderer_instruction_preview(
        self, package_id: str
    ) -> dict[str, Any]:
        preview = self.renderer_package_previews.get(package_id)
        if preview is not None:
            package = preview.instruction_package
        else:
            package = (
                self.pasted_repository.load_renderer_instruction_package(
                    package_id
                )
            )
        presentation = self.pasted_repository.load_presentation_spec(
            package.presentation_id
        )
        return validate_renderer_instruction_package(
            package, presentation
        ).model_dump(mode="json")

    def approve_renderer_instruction_package(
        self, package_id: str
    ) -> dict[str, Any]:
        preview = self.renderer_package_previews.get(package_id)
        options = self.renderer_package_options.get(package_id)
        if preview is None or options is None:
            raise KeyError(package_id)
        package = preview.instruction_package
        presentation = self.pasted_repository.load_presentation_spec(
            package.presentation_id
        )
        rebuilt = build_renderer_instruction_package(
            presentation, options
        )
        if rebuilt.instruction_package.package_id != package_id:
            raise ValueError(
                "Renderer instruction package source association changed."
            )
        report = validate_renderer_instruction_package(
            rebuilt.instruction_package, presentation
        )
        if not report.valid:
            raise ValueError(
                "Renderer instruction package failed validation."
            )
        approved = rebuilt.instruction_package.model_copy(update={
            "validation_report": report,
            "approval_status": RendererPackageApprovalStatus.approved,
            "approved_at": utc_now(),
        })
        saved = (
            self.pasted_repository.save_renderer_instruction_package(
                approved
            )
        )
        self.renderer_package_previews.pop(package_id, None)
        self.renderer_package_options.pop(package_id, None)
        return saved.model_dump(mode="json")

    def render_powerpoint(self, package_id: str, payload: dict[str, Any]):
        package = self.pasted_repository.load_renderer_instruction_package(
            package_id
        )
        options = PowerPointRenderOptions.model_validate(payload or {})
        return render_powerpoint(
            package, options,
            output_root=self.powerpoint_repository.root,
        ).model_dump(mode="json")

    def list_powerpoint_renders(self):
        return [value.model_dump(mode="json")
                for value in self.powerpoint_repository.list()]

    def load_powerpoint_render(self, render_id: str):
        return self.powerpoint_repository.load(render_id).model_dump(mode="json")

    def powerpoint_download_path(self, render_id: str) -> Path:
        return self.powerpoint_repository.download_path(render_id)


INTERFACE = TeacherOSInterface()


class InterfaceRequestHandler(BaseHTTPRequestHandler):
    """Small JSON API for the local TeacherOS interface."""

    server_version = "TeacherOSInterface/0.2"

    def _headers(self, content_type: str, status: int = HTTPStatus.OK) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    def _json(self, payload: dict[str, Any], status: int = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._headers("application/json; charset=utf-8", status)
        self.wfile.write(body)

    def _text(
        self,
        body: str,
        *,
        filename: str | None = None,
        status: int = HTTPStatus.OK,
    ) -> None:
        encoded = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/markdown; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Access-Control-Allow-Origin", "*")
        if filename:
            self.send_header(
                "Content-Disposition",
                f'attachment; filename="{filename}"',
            )
        self.end_headers()
        self.wfile.write(encoded)

    def _powerpoint(self, path: Path) -> None:
        body = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header(
            "Content-Type",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        )
        self.send_header("Content-Length", str(len(body)))
        self.send_header(
            "Content-Disposition", f'attachment; filename="{path.name}"'
        )
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        return json.loads(self.rfile.read(length) or b"{}")

    def do_OPTIONS(self) -> None:
        self._headers("text/plain", HTTPStatus.NO_CONTENT)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        try:
            if path == "/api/health":
                self._json({"status": "ok", "version": "0.2"})
                return
            if path == "/api/catalog":
                self._json(INTERFACE.catalog())
                return
            if path == "/api/pasted-lessons":
                self._json({
                    "sources": INTERFACE.list_pasted_lesson_sources()
                })
                return
            if path == "/api/daily-lessons":
                self._json({
                    "packages": INTERFACE.list_daily_lesson_packages()
                })
                return
            if path.startswith("/api/daily-lessons/"):
                parts = path.strip("/").split("/")
                if len(parts) == 3:
                    self._json(
                        INTERFACE.load_daily_lesson_package(parts[2])
                    )
                    return
                if (
                    len(parts) == 5
                    and parts[3] == "artifacts"
                    and parts[4] in {
                        "teacher_playbook.md",
                        "gemini_slide_prompts.md",
                    }
                ):
                    download = urlparse(self.path).query == "download=1"
                    self._text(
                        INTERFACE.read_daily_lesson_artifact(
                            parts[2], parts[4]
                        ),
                        filename=parts[4] if download else None,
                    )
                    return
                raise KeyError(path)
            if path.startswith("/api/pasted-lessons/"):
                parts = path.strip("/").split("/")
                if len(parts) != 3:
                    raise KeyError(path)
                self._json(
                    INTERFACE.load_pasted_lesson_source(parts[2])
                )
                return
            if path == "/api/teacher-playbooks":
                self._json({
                    "playbooks": INTERFACE.list_teacher_playbooks()
                })
                return
            if path == "/api/playbook-enrichments":
                self._json({
                    "enrichments":
                        INTERFACE.list_approved_playbook_enrichments()
                })
                return
            if path == "/api/presentation-specs":
                self._json({
                    "presentation_specs":
                        INTERFACE.list_presentation_specs()
                })
                return
            if path == "/api/renderer-packages":
                self._json({
                    "renderer_packages":
                        INTERFACE.list_renderer_instruction_packages()
                })
                return
            if path == "/api/powerpoint-renders":
                self._json({"powerpoint_renders":
                            INTERFACE.list_powerpoint_renders()})
                return
            if path.startswith("/api/powerpoint-renders/"):
                parts = path.strip("/").split("/")
                if len(parts) == 4 and parts[3] == "download":
                    self._powerpoint(
                        INTERFACE.powerpoint_download_path(parts[2])
                    )
                    return
                if len(parts) == 3:
                    self._json(INTERFACE.load_powerpoint_render(parts[2]))
                    return
                raise KeyError(path)
            if path.startswith("/api/renderer-packages/"):
                parts = path.strip("/").split("/")
                if len(parts) != 3:
                    raise KeyError(path)
                self._json(
                    INTERFACE.load_renderer_instruction_package(parts[2])
                )
                return
            if path.startswith("/api/presentation-specs/"):
                parts = path.strip("/").split("/")
                if len(parts) != 3:
                    raise KeyError(path)
                self._json(
                    INTERFACE.load_presentation_spec(parts[2])
                )
                return
            if path.startswith("/api/teacher-playbooks/"):
                parts = path.strip("/").split("/")
                if len(parts) != 3:
                    raise KeyError(path)
                self._json(
                    INTERFACE.load_teacher_playbook(parts[2])
                )
                return
            if path.startswith("/api/jobs/"):
                self._json(INTERFACE.job_status(path.rsplit("/", 1)[-1]))
                return
            if path.startswith("/api/teaching-package/artifacts/"):
                parts = path.strip("/").split("/")
                if len(parts) != 5:
                    raise KeyError(path)
                content = INTERFACE.read_teaching_artifact(
                    int(parts[3]), parts[4]
                )
                download = urlparse(self.path).query == "download=1"
                self._text(
                    content,
                    filename=parts[4] if download else None,
                )
                return
            if path.startswith("/api/artifacts/") and path.endswith("/gamma"):
                parts = path.strip("/").split("/")
                if len(parts) != 4:
                    raise KeyError(path)
                prompt = INTERFACE.read_gamma_prompt(parts[2])
                download = urlparse(self.path).query == "download=1"
                self._text(
                    prompt,
                    filename="GammaDeckPrompt.md" if download else None,
                )
                return
            self._json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
        except KeyError:
            self._json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
        except Exception as error:
            self._json({"error": str(error)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        try:
            payload = self._body()
            if path == "/api/daily-lessons/generate":
                self._json(
                    INTERFACE.generate_daily_lesson(payload),
                    HTTPStatus.CREATED,
                )
                return
            if path == "/api/pasted-lessons":
                self._json(
                    INTERFACE.save_pasted_lesson_source(payload),
                    HTTPStatus.CREATED,
                )
                return
            if (
                path.startswith("/api/pasted-lessons/")
                and path.endswith("/analyze")
            ):
                parts = path.strip("/").split("/")
                if len(parts) != 4:
                    raise KeyError(path)
                self._json(
                    INTERFACE.analyze_pasted_lesson_source(parts[2])
                )
                return
            if (
                path.startswith("/api/pasted-lessons/")
                and path.endswith("/playbook")
            ):
                parts = path.strip("/").split("/")
                if len(parts) != 4:
                    raise KeyError(path)
                self._json(
                    INTERFACE.save_preliminary_playbook(parts[2]),
                    HTTPStatus.CREATED,
                )
                return
            if (
                path.startswith("/api/pasted-lessons/")
                and path.endswith("/enrich")
            ):
                parts = path.strip("/").split("/")
                if len(parts) != 4:
                    raise KeyError(path)
                self._json(
                    INTERFACE.enrich_pasted_lesson_source(parts[2], payload)
                )
                return
            if (
                path.startswith("/api/playbook-enrichments/")
                and path.endswith("/approve")
            ):
                parts = path.strip("/").split("/")
                if len(parts) != 4:
                    raise KeyError(path)
                self._json(
                    INTERFACE.approve_playbook_enrichment(parts[2]),
                    HTTPStatus.CREATED,
                )
                return
            if (
                path.startswith("/api/teacher-playbooks/")
                and path.endswith("/presentation-spec")
            ):
                parts = path.strip("/").split("/")
                if len(parts) != 4:
                    raise KeyError(path)
                self._json(
                    INTERFACE.build_presentation_spec(parts[2], payload)
                )
                return
            if (
                path.startswith("/api/presentation-specs/")
                and path.endswith("/renderer-package")
            ):
                parts = path.strip("/").split("/")
                if len(parts) != 4:
                    raise KeyError(path)
                self._json(
                    INTERFACE.build_renderer_instruction_package(
                        parts[2], payload
                    )
                )
                return
            if (
                path.startswith("/api/presentation-specs/")
                and path.endswith("/validate")
            ):
                parts = path.strip("/").split("/")
                if len(parts) != 4:
                    raise KeyError(path)
                self._json(
                    INTERFACE.validate_presentation_preview(parts[2])
                )
                return
            if (
                path.startswith("/api/presentation-specs/")
                and path.endswith("/reorder")
            ):
                parts = path.strip("/").split("/")
                if len(parts) != 4:
                    raise KeyError(path)
                ordered = payload.get("ordered_slide_ids")
                if not isinstance(ordered, list):
                    raise ValueError("ordered_slide_ids must be a list.")
                self._json(
                    INTERFACE.reorder_presentation_preview(
                        parts[2], [str(value) for value in ordered]
                    )
                )
                return
            if (
                path.startswith("/api/presentation-specs/")
                and path.endswith("/approve")
            ):
                parts = path.strip("/").split("/")
                if len(parts) != 4:
                    raise KeyError(path)
                self._json(
                    INTERFACE.approve_presentation_spec(parts[2]),
                    HTTPStatus.CREATED,
                )
                return
            if (
                path.startswith("/api/renderer-packages/")
                and path.endswith("/powerpoint")
            ):
                parts = path.strip("/").split("/")
                if len(parts) != 4:
                    raise KeyError(path)
                self._json(
                    INTERFACE.render_powerpoint(parts[2], payload),
                    HTTPStatus.CREATED,
                )
                return
            if (
                path.startswith("/api/renderer-packages/")
                and path.endswith("/validate")
            ):
                parts = path.strip("/").split("/")
                if len(parts) != 4:
                    raise KeyError(path)
                self._json(
                    INTERFACE.validate_renderer_instruction_preview(parts[2])
                )
                return
            if (
                path.startswith("/api/powerpoint-renders/")
                and path.endswith("/validate")
            ):
                parts = path.strip("/").split("/")
                if len(parts) != 4:
                    raise KeyError(path)
                self._json(
                    INTERFACE.load_powerpoint_render(parts[2])[
                        "validation_report"
                    ]
                )
                return
            if (
                path.startswith("/api/renderer-packages/")
                and path.endswith("/approve")
            ):
                parts = path.strip("/").split("/")
                if len(parts) != 4:
                    raise KeyError(path)
                self._json(
                    INTERFACE.approve_renderer_instruction_package(parts[2]),
                    HTTPStatus.CREATED,
                )
                return
            if path == "/api/generate":
                job = INTERFACE.start_generation(
                    curriculum_name=str(payload["curriculum_name"]),
                    grade=str(payload["grade"]),
                    unit=str(payload["unit"]),
                    lesson_number=int(payload["lesson_number"]),
                )
                self._json(
                    {"job_id": job.job_id, "request_id": job.request_id},
                    HTTPStatus.ACCEPTED,
                )
                return
            if path == "/api/teaching-package/generate":
                job = INTERFACE.start_teaching_package(
                    curriculum_name=str(payload["curriculum_name"]),
                    grade=str(payload["grade"]),
                    unit=str(payload["unit"]),
                    lesson_number=int(payload["lesson_number"]),
                )
                self._json(
                    {"job_id": job.job_id, "request_id": job.request_id},
                    HTTPStatus.ACCEPTED,
                )
                return
            if path == "/api/teaching-package/publish":
                result = INTERFACE.publish_teaching_package(
                    int(payload["lesson_number"]),
                    str(payload["target"]),
                )
                self._json(result)
                return
            if path == "/api/open":
                INTERFACE.open_output(
                    request_id=str(payload["request_id"]),
                    target=str(payload.get("target", "folder")),
                )
                self._json({"status": "opened"})
                return
            if path == "/api/clipboard":
                INTERFACE.copy_gamma_prompt(str(payload["request_id"]))
                self._json({"status": "copied"})
                return
            self._json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
        except (KeyError, TypeError, ValueError) as error:
            self._json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
        except FileNotFoundError as error:
            self._json({"error": str(error)}, HTTPStatus.NOT_FOUND)
        except Exception as error:
            self._json({"error": str(error)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def log_message(self, format: str, *args: Any) -> None:
        return


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 8765), InterfaceRequestHandler)
    print("TeacherOS interface available at http://127.0.0.1:8765")
    server.serve_forever()


if __name__ == "__main__":
    main()


__all__ = ["TeacherOSInterface", "main"]
