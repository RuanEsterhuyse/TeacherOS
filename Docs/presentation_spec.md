# Presentation Specification Foundation

Phase 3D adds a renderer-neutral planning boundary between an approved enriched
Teacher Playbook and future presentation renderers. It does not render slides,
generate images, alter production lesson generation, or connect to Gamma,
Google Slides, PowerPoint, Canva, or HTML.

## Data flow

```text
ApprovedPlaybookEnrichment
        |
        v
PresentationBuildOptions
        |
        v
Deterministic PresentationSpec builder
        |
        v
PresentationSpec validator
        |
        v
Teacher review preview
        |
        v
Explicit approval and atomic JSON persistence
```

The builder accepts exactly one approved enrichment identity. A baseline
playbook ID is not used to guess among multiple enrichment variants.

## Contract

`PresentationSpec` records lesson identity, exact approved enrichment identity,
theme, ordered slides, required sections, source references, deterministic
generation metadata, validation status, and approval status.

`SlideSpec` separates:

- controlled slide and layout types;
- structured student-facing content;
- structured speaker notes;
- teacher and student actions;
- timing;
- visual direction;
- source references;
- grounding labels;
- ELD supports;
- activity and instructional-day association.

Student content is composed from typed `ContentElement` records rather than a
single text blob. Supported records include headings, paragraphs, lists,
questions, quotations, vocabulary terms, sentence frames, callouts, comparison
cards, timeline items, tables, captions, and exit-ticket prompts.

Speaker notes preserve purpose, scripts, teacher actions, anticipated responses,
misconception support, checks for understanding, transitions, pacing, sources,
and source-backed versus generated-guidance labels.

## Visual and theme models

`VisualSpec` describes a visual without creating or downloading one. It supports
illustrations, photos, maps, diagrams, icons, charts, text-only designs,
book-cover references, and activity-page references. Required non-text visuals
must have alt text. Source-document visuals instruct future renderers to use an
approved asset or a neutral replacement placeholder rather than fabricate one.

The built-in `teacheros_classroom` theme is a new schema value and does not
modify production theme files. It uses warm cream, turquoise and deep teal,
coral, charcoal, light gray, rounded cards, soft shadows, and generous spacing.

## Deterministic generation rules

- Preserve instructional-day and activity order.
- Add one visible day opener for every instructional day.
- Represent every approved activity at least once.
- Include the essential question, objectives, vocabulary, assessment or exit
  ticket, and homework when present and enabled.
- Preserve exact prompts, timing, Activity Book references, page mappings,
  source references, ELD supports, transitions, and grounding labels.
- Infer slide type only from an explicit controlled vocabulary and deterministic
  title/content rules.
- Never invent story details, quotations, page numbers, answer keys, or
  activities.
- Treat target and maximum slide counts as planning preferences. Required
  instructional content is never silently dropped to meet a count.

## Validation

Validation checks:

- exact approved-playbook association;
- sequential slide numbers and unique IDs;
- instructional-day and activity order;
- a visible start for every day;
- activity and required-section coverage;
- exact source-reference membership and page mappings;
- nonempty student content;
- required structured speaker notes;
- orphan slides;
- duplicated singleton sections;
- activity timing aggregation;
- windows-and-mirrors coverage when that activity is present;
- exit-ticket and homework coverage when required.

Validation returns structured issues, section coverage, activity coverage,
source coverage, timing totals, and a pass/fail status. A failing preview cannot
be approved or persisted.

## Repository and approval flow

Presentation previews remain server-side and are not saved automatically.
Approval reloads the exact approved enrichment, reruns validation, stamps the
approval status and time, and writes validated JSON atomically under the ignored
pasted-lesson runtime directory. Unsafe IDs, malformed JSON, unapproved inputs,
and association mismatches are rejected.

The local API exposes isolated build, list, load, validate, reorder, and approve
operations. Reordering submits only a complete ordered list of existing slide
IDs. The server reconstructs slide numbers and reruns the full validator; moves
that break day starts, activity order, coverage, timing, or references are
rejected and the previous preview remains unchanged.

## Known limitations

- Phase 3D creates plans, not rendered or downloadable presentations.
- The deterministic builder does not use AI to optimize slide density.
- Long-activity splitting is reserved by the options contract but the first
  builder keeps one authoritative activity slide to preserve timing exactly.
- Visual prompts are directions only and require a future renderer and teacher
  asset review.
- Reordering is protected by instructional sequence; arbitrary client-mutated
  plans are never trusted.

Future renderer adapters should accept only a validated, approved
`PresentationSpec`. They must map the structured objects to their platform
without inventing or removing instructional content.
