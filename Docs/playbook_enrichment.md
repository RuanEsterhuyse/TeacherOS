# Source-Grounded Playbook Enrichment

Phase 3C is an optional companion to the deterministic pasted-lesson analyzer.
It does not participate in production lesson generation, canonical preparation,
bridging, caching, Gamma, or presentation rendering.

## Data flow

1. The repository loads an exact `PastedLessonSource`.
2. `analyze_pasted_lesson()` recreates the deterministic
   `PlaybookAnalysisResult`.
3. `PlaybookEnrichmentContext` sends the exact source, baseline warnings,
   unclassified text, optional Reader and Activity Book text, and teacher
   options through the provider-neutral `PlaybookEnrichmentProvider`.
4. The response is parsed as `GeneratedPlaybookEnrichment` and its
   `TeacherPlaybook` is validated with the existing strict schema.
5. The grounding service compares protected facts, activity identities,
   sequence, questions, source references, page claims, and quotations against
   the baseline and supplied source.
6. The UI displays a nonpersistent preview beside the baseline. Only an explicit
   teacher approval writes an `ApprovedPlaybookEnrichment`.

## Grounding guarantees

Lesson identity, duration, objectives, vocabulary, homework, assessment,
activity sequence, questions, and source references are immutable. New page
claims and quotations must occur in supplied source text. Every activity must
retain its exact baseline references. Added guidance is labeled
`[Generated guidance — review]`. Unsupported claims reject the preview under
the default strict policy; omitted support is reported as a partial enrichment.

These checks reduce unsupported output but do not establish that generated
pedagogy is correct. A teacher must review every enrichment.

## Provider abstraction and failures

The service accepts any provider implementing `PlaybookEnrichmentProvider`.
The optional OpenAI implementation uses the existing environment-backed
configuration and structured-output client. Tests use deterministic fake
providers and make no network calls.

Missing configuration, timeouts, empty output, provider errors, malformed JSON,
schema failures, and grounding failures return a failed result containing the
unchanged baseline. Raw provider responses and secrets are never persisted.

## Persistence

Approved files use the repository's atomic JSON convention under the isolated,
ignored pasted-lesson runtime directory. They include source and analyzer
identity, enrichment and schema versions, provider/model metadata, timestamp,
grounding summary, and approval status. Provider usage metadata is retained;
raw responses and credentials are not.

## Known limitations and future consumption

Grounding is constrained to exact structured comparisons and conservative
page/quotation checks. It cannot prove every general pedagogical statement or
story inference. Complete trade-book answer generation is out of scope.

A future slide-plan generator may consume only a validated, teacher-approved
enriched playbook. That future step must remain separate and must not infer
slide content from an unapproved preview. Phase 3C creates no slide plan and
performs no rendering.
