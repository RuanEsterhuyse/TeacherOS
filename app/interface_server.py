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
from curriculum.intelligence.publishing import write_publishing_metadata
from renderer.google_docs_publisher import GoogleDocsPublisher
from renderer.teaching_package_slides import (
    TeachingPackageGoogleSlidesPublisher,
)
from schemas.teaching_package_schema import StructuredTeachingPackage


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

    def __init__(self, teacheros: TeacherOS | None = None) -> None:
        self.teacheros = teacheros or TeacherOS(project_root=PROJECT_ROOT)
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
