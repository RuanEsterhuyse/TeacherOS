# Pasted Lesson Intake and Teacher Playbook Foundation

## Scope

Phase 3B is an isolated, local workflow for one teacher-provided lesson. It
does not replace curriculum extraction, prepared curriculum bundles,
CanonicalLesson, production lesson generation, cached lessons, Gamma, or any
presentation renderer.

The phase supports:

1. pasting one Teacher Guide lesson and optional supporting text;
2. saving the exact source;
3. running a deterministic baseline analysis;
4. reviewing extracted fields, warnings, missing information, and
   unclassified text; and
5. saving a preliminary structured Teacher Playbook.

It does not call an AI provider or generate slides.

## Data flow

```text
Teacher form
    |
    v
PastedLessonSource
    |  exact source JSON
    v
PastedLessonRepository
    |
    v
Deterministic baseline analyzer
    |
    v
PlaybookAnalysisResult
    |-- TeacherPlaybook
    |-- warnings
    |-- unclassified source lines
    `-- extraction confidence summary
    |
    v
Teacher review
    |
    v
Saved preliminary TeacherPlaybook
```

Runtime JSON is stored beneath `output/pasted_lesson_intake/`, which is
excluded from Git with the existing `output/` rule.

## Source model

`PastedLessonSource` records lesson identity, optional Teacher Guide page
coordinates, the complete Teacher Guide text, optional Student Reader and
Activity Book text, notes, timestamps, and a schema version.

The source identifier is a stable digest of lesson identity and the exact
provided content. The repository never normalizes the stored source text.
Changing the source text creates a different source identity.

## Teacher Playbook models

`TeacherPlaybook` is curriculum-agnostic and associates with exactly one
`PastedLessonSource`. It supports optional lesson summary, days, objectives,
essential question, success criteria, materials, vocabulary, survival
guidance, activities, homework, assessment, reflection, source references,
and generation metadata.

`PlaybookActivity` stores timing, purpose, teacher goal/script, discussion
questions, response guidance, misconceptions, examples, ELD supports, checks
for understanding, look-fors, readiness criteria, transitions, and source
references.

Fields remain optional or use empty collections where source lessons may not
contain that information. Strict model validation rejects unknown fields.

## Repository behavior

`PastedLessonRepository` uses strict, human-inspectable JSON:

```text
output/pasted_lesson_intake/
  sources/
    <source_id>.json
  playbooks/
    <playbook_id>.json
```

Writes use a temporary file followed by an atomic replacement. Loads validate
the complete saved payload. Unsafe identifiers, missing artifacts, malformed
JSON, invalid schemas, and playbooks without a saved source fail clearly.
Listing order is stable by artifact identifier.

## Baseline analyzer

The baseline analyzer is pure and deterministic. It recognizes explicit:

- `Day N` headings;
- activity headings with stated minutes;
- labeled objectives, materials, vocabulary, essential questions, success
  criteria, homework, assessment, and reflection;
- labeled activity guidance;
- Teacher Guide, Student Reader, and Activity Page references.

It does not infer absent content. Missing fields produce structured warnings.
Nonblank lines that cannot be classified are returned verbatim in
`unclassified_sections`.

Confidence values describe the reliability of the mechanical extraction, not
instructional quality.

## Web API

The local server exposes an isolated workflow:

- `POST /api/pasted-lessons` — validate and save an exact source;
- `GET /api/pasted-lessons` — list sources;
- `GET /api/pasted-lessons/{source_id}` — load one source;
- `POST /api/pasted-lessons/{source_id}/analyze` — return a review result;
- `POST /api/pasted-lessons/{source_id}/playbook` — rerun the deterministic
  analyzer and save its preliminary playbook;
- `GET /api/teacher-playbooks` — list saved playbooks;
- `GET /api/teacher-playbooks/{playbook_id}` — load one playbook.

Saving reruns the server-side analyzer instead of accepting a client-mutated
playbook.

## Future AI analyzer

A future analyzer can implement the same function boundary:

```python
analyze_pasted_lesson(
    source: PastedLessonSource,
) -> PlaybookAnalysisResult
```

It must preserve the source association, populate the same models, mark
unsupported information unavailable, retain source references, and return
warnings and unclassified content. The repository and review interface do not
need replacement.

## Future slide planning

A future slide-plan generator should accept a validated, reviewed
`TeacherPlaybook`. It must not read raw pasted text independently or invent
sequence, timing, questions, answers, or source facts. Slide generation is
explicitly outside Phase 3B.

## Current limitations

- Heading recognition is intentionally conservative.
- The analyzer does not interpret prose that lacks explicit labels.
- Optional Reader and Activity Book text is stored but not deeply analyzed.
- No AI enrichment or source-dependent answer generation occurs.
- No PDF ingestion, batch processing, slide planning, or rendering occurs.
- The preliminary playbook is not a replacement for teacher review.
