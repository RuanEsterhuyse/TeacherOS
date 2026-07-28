"""Source-grounded, optional enrichment of deterministic teacher playbooks."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from curriculum.intelligence.ids import content_digest, stable_id
from curriculum.intelligence.playbook_enrichment_provider import (
    OpenAIPlaybookEnrichmentProvider,
    PlaybookEnrichmentProvider,
)
from schemas.pasted_lesson_schema import (
    AnalysisWarning,
    PlaybookAnalysisResult,
    PastedLessonSource,
    TeacherPlaybook,
)
from schemas.playbook_enrichment_schema import (
    ActivitySourceCoverage,
    EnrichmentStatus,
    GENERATED_GUIDANCE_LABEL,
    GeneratedPlaybookEnrichment,
    GroundingReport,
    PLAYBOOK_ENRICHMENT_VERSION,
    PlaybookEnrichmentContext,
    PlaybookEnrichmentOptions,
    PlaybookEnrichmentResult,
    ProviderMetadata,
    UnsupportedClaim,
)


PROMPT_PATH = (
    Path(__file__).parents[2]
    / "brain"
    / "prompts"
    / "teacher_playbook_enrichment_v1.md"
)
PAGE_PATTERN = re.compile(
    r"\b(?:pages?|pp\.|activity\s+page)\s*([0-9]+(?:\s*[–—-]\s*[0-9]+)?)",
    re.IGNORECASE,
)
QUOTE_PATTERN = re.compile(r"[“\"]([^”\"]{4,})[”\"]")


def _warning(code: str, message: str, field: str | None = None) -> AnalysisWarning:
    return AnalysisWarning(code=code, message=message, field=field)


def _reference_key(reference: Any) -> str:
    return content_digest(reference.model_dump(mode="json"))


def _coverage(
    baseline: TeacherPlaybook,
    enriched: TeacherPlaybook,
) -> list[ActivitySourceCoverage]:
    enriched_by_id = {
        activity.activity_id: activity for activity in enriched.activities
    }
    output: list[ActivitySourceCoverage] = []
    for activity in baseline.activities:
        candidate = enriched_by_id.get(activity.activity_id)
        retained = candidate.source_references if candidate else []
        expected_keys = {_reference_key(value) for value in activity.source_references}
        retained_keys = {_reference_key(value) for value in retained}
        output.append(ActivitySourceCoverage(
            activity_id=activity.activity_id,
            retained_source_references=retained,
            baseline_reference_count=len(activity.source_references),
            retained_reference_count=len(retained_keys & expected_keys),
            fully_retained=expected_keys == retained_keys,
        ))
    return output


def _protected_claims(
    baseline: TeacherPlaybook,
    enriched: TeacherPlaybook,
) -> list[UnsupportedClaim]:
    claims: list[UnsupportedClaim] = []
    protected = (
        "playbook_id",
        "source_id",
        "lesson_metadata",
        "instructional_days",
        "objectives",
        "essential_question",
        "success_criteria",
        "materials",
        "vocabulary",
        "homework",
        "assessment",
        "source_references",
        "generation_metadata",
        "schema_version",
    )
    for name in protected:
        if getattr(baseline, name) != getattr(enriched, name):
            claims.append(UnsupportedClaim(
                field_path=name,
                claim=f"Provider attempted to alter protected field {name}.",
                reason="Curriculum facts must match the deterministic baseline.",
            ))
    if len(baseline.activities) != len(enriched.activities):
        claims.append(UnsupportedClaim(
            field_path="activities",
            claim="Provider changed the activity count.",
            reason="Baseline lesson sequence is immutable.",
        ))
        return claims
    for index, (before, after) in enumerate(
        zip(baseline.activities, enriched.activities)
    ):
        for name in (
            "activity_id",
            "title",
            "instructional_day",
            "duration_minutes",
            "purpose",
            "questions",
            "source_references",
        ):
            if getattr(before, name) != getattr(after, name):
                claims.append(UnsupportedClaim(
                    field_path=f"activities.{index}.{name}",
                    claim=f"Provider attempted to alter {name}.",
                    reason="Activity facts, questions, and references are immutable.",
                ))
    return claims


def _all_added_strings(before: Any, after: Any, path: str = "") -> list[tuple[str, str]]:
    additions: list[tuple[str, str]] = []
    if isinstance(after, dict):
        prior = before if isinstance(before, dict) else {}
        for key, value in after.items():
            additions.extend(_all_added_strings(
                prior.get(key), value, f"{path}.{key}".strip(".")
            ))
    elif isinstance(after, list):
        prior = before if isinstance(before, list) else []
        for index, value in enumerate(after):
            old = prior[index] if index < len(prior) else None
            additions.extend(_all_added_strings(
                old, value, f"{path}.{index}".strip(".")
            ))
    elif isinstance(after, str) and after and after != before:
        additions.append((path, after))
    return additions


def _source_claims(
    source: PastedLessonSource,
    baseline: TeacherPlaybook,
    enriched: TeacherPlaybook,
) -> list[UnsupportedClaim]:
    source_text = "\n".join(filter(None, (
        source.teacher_guide_text,
        source.student_reader_text,
        source.activity_book_text,
    )))
    before = baseline.model_dump(mode="json")
    after = enriched.model_dump(mode="json")
    claims: list[UnsupportedClaim] = []
    for path, value in _all_added_strings(before, after):
        for page in PAGE_PATTERN.findall(value):
            token = re.sub(r"\s+", "", page).replace("—", "-").replace("–", "-")
            normalized_source = source_text.replace("—", "-").replace("–", "-")
            if token not in re.sub(r"\s+", "", normalized_source):
                claims.append(UnsupportedClaim(
                    field_path=path,
                    claim=value,
                    reason=f"Page reference {page!r} is not present in supplied source.",
                ))
        for quote in QUOTE_PATTERN.findall(value):
            if quote not in source_text:
                claims.append(UnsupportedClaim(
                    field_path=path,
                    claim=quote,
                    reason="Generated quotation is not present in supplied source.",
                ))
    return claims


def _option_claims(
    baseline: TeacherPlaybook,
    enriched: TeacherPlaybook,
    options: PlaybookEnrichmentOptions,
) -> list[UnsupportedClaim]:
    claims: list[UnsupportedClaim] = []
    controlled = {
        "include_teacher_scripts": "teacher_script",
        "include_possible_student_responses": "possible_student_responses",
        "include_misconceptions": "misconceptions",
        "include_eld_supports": "eld_supports",
        "include_checks_for_understanding": "checks_for_understanding",
        "include_transition_language": "transition",
    }
    for index, (before, after) in enumerate(
        zip(baseline.activities, enriched.activities)
    ):
        for option_name, field_name in controlled.items():
            if (
                not getattr(options, option_name)
                and getattr(before, field_name) != getattr(after, field_name)
            ):
                claims.append(UnsupportedClaim(
                    field_path=f"activities.{index}.{field_name}",
                    claim=f"Provider added disabled support: {field_name}.",
                    reason=f"{option_name} is disabled.",
                ))
        if options.preserve_original_wording:
            for field_name in (
                "teacher_script",
                "possible_student_responses",
                "teacher_responses",
                "misconceptions",
                "examples",
                "eld_supports",
                "checks_for_understanding",
                "look_fors",
                "ready_to_move_on_criteria",
            ):
                old_values = getattr(before, field_name)
                new_values = getattr(after, field_name)
                if new_values[:len(old_values)] != old_values:
                    claims.append(UnsupportedClaim(
                        field_path=f"activities.{index}.{field_name}",
                        claim="Provider changed or removed baseline wording.",
                        reason="preserve_original_wording is enabled.",
                    ))
    if (
        not options.include_teacher_reflection
        and baseline.end_of_day_reflection != enriched.end_of_day_reflection
    ):
        claims.append(UnsupportedClaim(
            field_path="end_of_day_reflection",
            claim="Provider added disabled teacher reflection.",
            reason="include_teacher_reflection is disabled.",
        ))
    for field_name in ("teacher_survival_guide", "end_of_day_reflection"):
        old_values = getattr(baseline, field_name)
        new_values = getattr(enriched, field_name)
        if (
            options.preserve_original_wording
            and new_values[:len(old_values)] != old_values
        ):
            claims.append(UnsupportedClaim(
                field_path=field_name,
                claim="Provider changed or removed baseline wording.",
                reason="preserve_original_wording is enabled.",
            ))
    return claims


def _label_added_guidance(
    baseline: TeacherPlaybook,
    enriched: TeacherPlaybook,
) -> tuple[TeacherPlaybook, list[str]]:
    before = baseline.model_dump(mode="json")
    after = enriched.model_dump(mode="json")
    protected_prefixes = {
        "source_id", "lesson_metadata", "instructional_days", "objectives",
        "essential_question", "success_criteria", "materials", "vocabulary",
        "homework", "assessment", "source_references", "generation_metadata",
    }
    added_paths: list[str] = []

    def visit(old: Any, new: Any, path: str = "") -> Any:
        root = path.split(".", 1)[0]
        if root in protected_prefixes:
            return new
        if isinstance(new, dict):
            prior = old if isinstance(old, dict) else {}
            return {
                key: visit(prior.get(key), value, f"{path}.{key}".strip("."))
                for key, value in new.items()
            }
        if isinstance(new, list):
            prior = old if isinstance(old, list) else []
            return [
                visit(prior[index] if index < len(prior) else None, value,
                      f"{path}.{index}".strip("."))
                for index, value in enumerate(new)
            ]
        if isinstance(new, str) and new and new != old:
            if any(part in path.split(".") for part in (
                "activity_id", "title", "questions", "source_references",
                "duration_minutes", "instructional_day",
            )):
                return new
            added_paths.append(path)
            if not new.startswith(GENERATED_GUIDANCE_LABEL):
                return f"{GENERATED_GUIDANCE_LABEL} {new}"
        return new

    return TeacherPlaybook.model_validate(visit(before, after)), added_paths


def _failure_result(
    *,
    source: PastedLessonSource,
    baseline: PlaybookAnalysisResult,
    options: PlaybookEnrichmentOptions,
    provider: PlaybookEnrichmentProvider | None,
    code: str,
    reason: str,
    unsupported: list[UnsupportedClaim] | None = None,
) -> PlaybookEnrichmentResult:
    unsupported = unsupported or []
    coverage = _coverage(baseline.playbook, baseline.playbook)
    warning = _warning(code, reason)
    identity = stable_id(
        "playbook-enrichment",
        source.source_id,
        baseline.playbook.playbook_id,
        content_digest(options.model_dump(mode="json")),
        PLAYBOOK_ENRICHMENT_VERSION,
    )
    metadata = None
    if provider is not None:
        metadata = ProviderMetadata(
            provider_name=provider.provider_name,
            model_name=provider.model_name,
        )
    report = GroundingReport(
        warnings=[warning],
        unsupported_claims_rejected=unsupported,
        source_coverage_by_activity=coverage,
        retained_source_references=baseline.playbook.source_references,
    )
    return PlaybookEnrichmentResult(
        enrichment_id=identity,
        status=EnrichmentStatus.failed,
        enriched_playbook=baseline.playbook,
        grounding_report=report,
        warnings=[warning],
        unsupported_claims=unsupported,
        source_coverage=coverage,
        provider_metadata=metadata,
        baseline_preserved=True,
        failure_reason=reason,
    )


def enrich_teacher_playbook(
    source: PastedLessonSource,
    baseline: PlaybookAnalysisResult,
    options: PlaybookEnrichmentOptions | None = None,
    *,
    provider: PlaybookEnrichmentProvider | None = None,
) -> PlaybookEnrichmentResult:
    """Enrich a baseline without ever making it unavailable on failure."""
    options = options or PlaybookEnrichmentOptions()
    if source.source_id != baseline.playbook.source_id:
        return _failure_result(
            source=source, baseline=baseline, options=options, provider=provider,
            code="source_mismatch",
            reason="Baseline playbook does not belong to the supplied source.",
        )
    try:
        provider = provider or OpenAIPlaybookEnrichmentProvider()
        context = PlaybookEnrichmentContext(
            source=source, baseline=baseline, options=options
        )
        response = provider.enrich(
            context, PROMPT_PATH.read_text(encoding="utf-8")
        )
        if response.raw_payload in (None, "", {}):
            raise ValueError("Provider returned an empty enrichment response.")
        generated = GeneratedPlaybookEnrichment.model_validate(
            response.raw_payload
        )
    except TimeoutError as error:
        return _failure_result(
            source=source, baseline=baseline, options=options, provider=provider,
            code="provider_timeout", reason=str(error) or "Provider timed out.",
        )
    except (ValidationError, ValueError, TypeError, OSError) as error:
        return _failure_result(
            source=source, baseline=baseline, options=options, provider=provider,
            code="enrichment_failed", reason=str(error),
        )
    except Exception as error:
        return _failure_result(
            source=source, baseline=baseline, options=options, provider=provider,
            code="provider_error", reason=str(error),
        )

    claims = _protected_claims(
        baseline.playbook, generated.enriched_playbook
    )
    claims.extend(_source_claims(
        source, baseline.playbook, generated.enriched_playbook
    ))
    claims.extend(_option_claims(
        baseline.playbook, generated.enriched_playbook, options
    ))
    coverage = _coverage(
        baseline.playbook, generated.enriched_playbook
    )
    if any(not value.fully_retained for value in coverage):
        claims.append(UnsupportedClaim(
            field_path="activities.source_references",
            claim="One or more activities did not retain exact references.",
            reason="Every enriched activity must retain baseline references.",
        ))
    if claims:
        return _failure_result(
            source=source, baseline=baseline, options=options, provider=provider,
            code="unsupported_claims",
            reason="Enrichment was rejected because unsupported claims were found.",
            unsupported=claims,
        )

    labeled, added_paths = _label_added_guidance(
        baseline.playbook, generated.enriched_playbook
    )
    warning_values = [
        _warning("unsupported_claim", item.reason, item.field_path)
        for item in claims
    ]
    metadata = ProviderMetadata(
        provider_name=provider.provider_name,
        model_name=provider.model_name,
        usage=response.usage,
        retry_count=response.retry_count,
    )
    identity = stable_id(
        "playbook-enrichment",
        source.source_id,
        baseline.playbook.playbook_id,
        content_digest(options.model_dump(mode="json")),
        provider.provider_name,
        provider.model_name,
        PLAYBOOK_ENRICHMENT_VERSION,
    )
    report = GroundingReport(
        source_backed_fields=generated.source_backed_fields,
        inferred_fields=sorted(set(generated.inferred_fields + added_paths)),
        omitted_unsupported_fields=generated.omitted_unsupported_fields,
        retained_source_references=labeled.source_references,
        added_teacher_guidance=sorted(set(added_paths)),
        warnings=warning_values,
        unsupported_claims_rejected=claims,
        source_coverage_by_activity=coverage,
    )
    return PlaybookEnrichmentResult(
        enrichment_id=identity,
        status=(
            EnrichmentStatus.partial
            if generated.omitted_unsupported_fields
            else EnrichmentStatus.success
        ),
        enriched_playbook=labeled,
        grounding_report=report,
        warnings=warning_values,
        unsupported_claims=claims,
        source_coverage=coverage,
        provider_metadata=metadata,
        baseline_preserved=False,
    )


__all__ = ["enrich_teacher_playbook"]
