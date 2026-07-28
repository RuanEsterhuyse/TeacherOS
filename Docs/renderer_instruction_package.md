# Renderer Instruction Package

## Purpose

Phase 3E compiles an approved, validated `PresentationSpec` into a
provider-neutral `RendererInstructionPackage`. The package is an instruction
contract only. It does not create slides, presentations, PDFs, images, or
provider-specific API requests.

The adapter preserves every source slide exactly once and does not invent,
rewrite, omit, split, or merge instructional content.

## Data flow

```text
Approved PresentationSpec
        |
        v
Deterministic renderer instruction adapter
        |
        +-- compile theme tokens
        +-- map slide intent to named layout
        +-- place structured text blocks
        +-- place unresolved visual blocks
        +-- preserve speaker-note payload
        +-- create one asset disposition per slide
        +-- report overflow risk
        |
        v
Validated RendererInstructionPackage preview
        |
        v
Teacher review and explicit approval
        |
        v
Atomic JSON persistence under ignored runtime storage
```

No existing production renderer imports or consumes this package.

## Coordinate system

The contract uses a 13.333 × 7.5 inch canvas with a 16:9 aspect ratio.
Coordinates begin at the top-left corner:

- `x` increases from left to right.
- `y` increases from top to bottom.
- Width and height use inches.
- Every block must fit inside the canvas.

Inches were chosen because they translate directly to common presentation
page sizes while remaining independent of pixels, points, EMUs, or a provider
API. A future renderer is responsible for converting these coordinates into
its native units without changing block relationships.

## Layout contract

The package carries the complete versioned layout contract. Supported layouts
are:

- `title`
- `title_with_visual`
- `essential_question`
- `objectives_cards`
- `agenda`
- `vocabulary_cards`
- `two_column`
- `three_card`
- `four_card`
- `map_focus`
- `concept_web`
- `reading_chunk`
- `reading_checkpoint`
- `discussion_prompt`
- `comparison`
- `evidence_analysis`
- `reflection`
- `exit_ticket`
- `homework`
- `teacher_only`

Each contract records required and optional blocks, default coordinates,
spacing rules, conservative text capacity, visual-placement rules, and
accessibility expectations. Phase 3E defines composition intent rather than
pixel-perfect rendering.

## Text blocks

Student-visible content remains structured. Each `TextBlockInstruction`
contains:

- its semantic role;
- exact source text;
- position and size;
- typography and alignment;
- list and emphasis behavior;
- overflow policy;
- source-element identity;
- source reference and grounding label.

The adapter never flattens the whole slide into one string. Titles receive
their own blocks, and every `ContentElement` receives exactly one source-linked
block.

## Visual blocks

`VisualBlockInstruction` records composition requirements only. It may carry
an approved source URI from the PresentationSpec, but the adapter never
downloads or generates an image.

Meaningful visuals require alt text. Visual directions retain descriptions,
prompts, cropping intent, aspect ratio, licensing notes, source references,
and grounding labels.

## Speaker notes

Teacher guidance is compiled into a structured `NotesPayload`:

- purpose;
- teacher script;
- teacher actions;
- anticipated responses;
- misconception support;
- checks for understanding;
- transition language;
- pacing notes;
- source references;
- grounding labels.

A deterministic plain-text fallback is included for renderers with limited
notes support. Teacher guidance is never promoted into student-visible text
blocks.

## Theme compilation

The initial supported source theme is `teacheros_classroom`. Compilation
preserves its source palette, typography, spacing, card treatment, footer
style, image treatment, and accessibility preferences. It adds stable
renderer-ready font sizes and fallback font metadata.

Compilation does not edit existing theme configuration or existing renderer
themes.

## Asset manifest

Every slide receives exactly one asset disposition:

- generated illustration needed;
- map needed;
- icon needed;
- book-cover reference;
- activity-page reference;
- external image reference;
- no visual required.

Each record identifies its slide, description, unresolved prompt, required
region, aspect ratio, licensing requirement, source reference, and status.
Statuses make clear whether an approved source is required, a neutral
placeholder is allowed, or no visual is needed.

No asset is resolved in Phase 3E.

## Overflow handling

The adapter performs conservative checks for:

- long titles;
- dense body text;
- too many list items;
- long notes fallback text.

Risks are structured warnings tied to a slide and, where applicable, a block.
The adapter does not truncate, clip, automatically shrink below accessible
minimums, or split slides. A future renderer must block unsafe overflow or
return it for review.

## Validation and approval

Validation requires:

- an approved and valid source PresentationSpec;
- exact identity and digest association;
- exact slide count and order;
- every slide represented once;
- a valid layout for each slide type;
- exact timing and source-content coverage;
- preserved speaker notes;
- supported source references;
- unique and non-orphan blocks;
- meaningful visual alt text;
- one asset disposition per slide;
- valid canvas bounds and theme tokens;
- the complete named layout contract.

The web API builds server-held previews. Approval reloads the exact persisted
PresentationSpec, rebuilds the package with the recorded options, validates
again, and atomically saves strict JSON under:

```text
output/pasted_lesson_intake/renderer_instruction_packages/
```

This directory is runtime output and remains ignored by Git.

## Renderer integration expectations

A future renderer may consume an approved package only if it:

1. creates one output slide per `RendererSlideInstruction`;
2. preserves slide order and count;
3. keeps text and notes in their designated surfaces;
4. converts coordinates without changing layout intent;
5. refuses to truncate required content;
6. resolves assets according to manifest status and licensing requirements;
7. preserves source references, grounding labels, alt text, and reading order;
8. reports unsupported features instead of silently dropping them.

## Known limitations

- No PowerPoint, Google Slides, Gamma, PDF, or image output is created.
- Layouts are deterministic composition contracts, not pixel-perfect designs.
- Automatic slide splitting and animation are not supported.
- Asset discovery, licensing verification, download, and generation are
  deferred.
- The review interface is read-only; content editing remains outside scope.
- Only the existing `teacheros_classroom` theme is compiled.
