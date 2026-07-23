"""Regression tests for deterministic fidelity-containment normalization."""

from brain.lesson_validator import LessonValidator, normalize_containment_text
from schemas.lesson_package_schema import PackageHomework
from Tests.test_generation_pipeline import design, package, reader


LESSON_1_HOMEWORK = (
    "Assign the story 'Güera' (pages 51–57) as reading homework. "
    "Ask students to fill out Activity Page 1.3 after they read the story."
)


def validate_homework(expected: str, assembled: str):
    source = reader()
    source.homework = [expected]
    lesson_package = package()
    lesson_package.homework = [
        PackageHomework(title="Homework", instructions=assembled)
    ]
    return LessonValidator().validate(lesson_package, source, design())


def missing_homework_findings(report):
    return [
        finding
        for finding in report.findings
        if finding.code == "missing_homework"
    ]


def test_lesson_1_ascii_single_quotes_match_typographic_double_quotes() -> None:
    assembled = (
        "Assign the story “Güera” (pages 51–57) as reading homework. "
        "Ask students to fill out Activity Page 1.3 after they read the story."
    )

    report = validate_homework(LESSON_1_HOMEWORK, assembled)

    assert missing_homework_findings(report) == []
    assert report.status == "pass"


def test_curly_and_straight_apostrophes_match() -> None:
    report = validate_homework(
        "Review the student's notes.",
        "Review the student’s notes.",
    )

    assert missing_homework_findings(report) == []


def test_nonbreaking_spaces_match_normal_spaces() -> None:
    report = validate_homework(
        "Read pages 51–57.",
        "Read\u00a0pages\u00a051–57.",
    )

    assert missing_homework_findings(report) == []


def test_repeated_whitespace_matches_single_spaces() -> None:
    report = validate_homework(
        "Read pages 51–57 and complete Activity Page 1.3.",
        "Read   pages 51–57\n\tand complete  Activity Page 1.3.",
    )

    assert missing_homework_findings(report) == []


def test_genuinely_missing_homework_still_fails() -> None:
    report = validate_homework(
        LESSON_1_HOMEWORK,
        "Read a different story.",
    )

    findings = missing_homework_findings(report)
    assert report.status == "fail"
    assert len(findings) == 1
    assert findings[0].severity == "error"
    assert LESSON_1_HOMEWORK in findings[0].message


def test_exact_match_behavior_is_unchanged() -> None:
    report = validate_homework("Read pages 2–3.", "Read pages 2–3.")

    assert missing_homework_findings(report) == []
    assert report.status == "pass"


def test_normalization_preserves_case_and_word_order() -> None:
    assert normalize_containment_text("Read First") != (
        normalize_containment_text("read First")
    )
    assert normalize_containment_text("Read then write") != (
        normalize_containment_text("write then Read")
    )
