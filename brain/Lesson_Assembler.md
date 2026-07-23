# Lesson Assembler

## Purpose

The Lesson Assembler converts the completed slide specification and supporting lesson artifacts into one coherent, renderer-ready Lesson Package. It is the renderer handoff boundary between TeacherOS Brain design modules and downstream presentation systems.

The module preserves approved content and decisions while verifying that all required parts are present, consistent, correctly related, and exportable. It does not redesign the lesson, make instructional decisions, or generate slides.

## Responsibilities

The Lesson Assembler is responsible for:

- receiving all approved lesson artifacts from upstream modules;
- confirming artifact identity, status, authority, and compatibility;
- validating package completeness;
- checking consistency across slide specifications, notes, interactions, visuals, timing, metadata, and traceability;
- assembling lesson-level metadata;
- preserving slide order and stable identifiers;
- associating speaker notes, interactions, image directions, timing, and references with the correct slides;
- reconciling repeated metadata without changing authoritative values;
- detecting missing, duplicate, conflicting, or orphaned records;
- preserving adaptation labels and unresolved issues;
- creating a single authoritative Lesson Package;
- declaring export readiness for an identified renderer and presentation format;
- reporting blocking conditions instead of silently repairing instructional content.

The module may normalize packaging structure, naming, and references when meaning is unchanged. Any inconsistency that would require instructional or visual judgment must be returned to the owning module or teacher.

## Non-Responsibilities

The Lesson Assembler must not:

- change the central learning goal, objectives, or success criteria;
- redesign the instructional sequence;
- add, remove, combine, reorder, or rewrite lesson activities;
- create or revise student-facing content;
- create teacher guidance or speaker notes;
- add checks for understanding, assessments, or learner supports;
- design interactions, images, layouts, animations, or transitions;
- make pacing decisions;
- resolve source conflicts through unsupported assumptions;
- hide missing information or unresolved issues;
- create renderer instructions that introduce new design decisions;
- generate Google Slides or another presentation file;
- render or generate final images.

When an input is incomplete or contradictory, the Lesson Assembler identifies the owning artifact and blocks export rather than inventing a correction.

## Inputs

The Lesson Assembler requires:

- the approved Structured Lesson Model version for the lesson;
- complete lesson metadata and identity;
- the ordered slide specifications from the Slide Designer;
- student-facing content for every slide;
- teacher-facing notes and speaker-note guidance;
- image and visual directions;
- interaction descriptions;
- animation and reveal specifications;
- slide-level, phase-level, and lesson-level timing;
- transition guidance;
- required asset and materials inventories;
- curriculum source references;
- curriculum adaptation and fidelity records;
- accessibility and ELD presentation requirements;
- unresolved-issues list;
- upstream validation results and approval statuses;
- target renderer and intended presentation format.

All inputs must retain stable identifiers and origin information. The Assembler must not depend on file order or unstructured proximity to infer relationships that should be explicit.

## Input Validation

Before assembly begins, the module verifies that:

- all artifacts belong to the same curriculum, unit, lesson, and model version;
- the lesson identity is complete enough for export;
- the slide sequence is complete, unique, and ordered;
- every slide has a defined instructional purpose;
- student-facing content and teacher-facing guidance are distinguishable;
- notes, interactions, image directions, timing, transitions, and references point to valid slide identifiers;
- required curriculum components are represented or visibly blocked;
- adaptation labels and fidelity records remain attached;
- unresolved issues are classified by export impact;
- upstream validations have completed successfully or their exceptions are authorized;
- the target renderer and presentation format are supported by the selected package profile.

Validation must distinguish a missing optional element from a missing required element. If an absent or conflicting input requires interpretation, the module must not proceed as though the package were complete.

## Lesson Package Structure

The Lesson Package is a single logical export containing coordinated subpackages. Its structure must include:

- package identity and version;
- lesson metadata;
- ordered slide package;
- speaker notes package;
- image direction package;
- interaction package;
- animation and reveal information;
- timing package;
- transition information;
- curriculum traceability package;
- accessibility requirements;
- asset and material references;
- unresolved issues and validation results;
- renderer profile and export-readiness status.

Subpackages may be stored separately in a future serialization format, but together they form one authoritative lesson export. Relationships among them must use stable identifiers rather than ambiguous titles or positions alone.

## Slide Package

The Slide Package contains the complete ordered presentation specification. Every slide record includes:

- stable slide identifier and slide number;
- slide title and slide type;
- linked lesson phase and instructional objective;
- exact student-facing content;
- required visible labels, directions, references, and attribution;
- rendering and visual-structure guidance already approved by the Slide Designer;
- animation or reveal sequence when applicable;
- linked note, interaction, image, timing, transition, and traceability identifiers;
- adaptation and approval status;
- any unresolved rendering dependency.

The Assembler preserves the Slide Designer’s sequence and content exactly. It may verify numbering and identifier uniqueness, but it may not decide to merge, split, add, delete, or reorder slides.

## Speaker Notes Package

The Speaker Notes Package contains teacher-only guidance aligned to the slide sequence. Each note record identifies:

- the associated slide;
- the slide’s instructional purpose;
- teacher actions;
- concise teacher language;
- expected student evidence or anticipated responses;
- follow-up guidance;
- misconceptions and response guidance;
- ELD, accessibility, and differentiation support;
- materials and preparation reminders;
- pacing and transition cues;
- source or adaptation status where relevant.

Notes must remain separate from student-facing content. The package must preserve their intended order and ensure a renderer does not display them on slides unless an approved specification explicitly requires visible teacher content.

## Image Direction Package

The Image Direction Package contains all approved visual requirements and asset references. Each record includes:

- a stable visual identifier;
- the associated slide or slides;
- instructional purpose;
- image subject;
- composition and focal point;
- style and consistency guidance;
- placement and relative prominence;
- age-appropriateness requirements;
- cultural, historical, and representational considerations;
- text restrictions;
- accessibility description;
- source connection;
- asset status and unresolved dependencies.

The Assembler must distinguish an existing approved asset from a direction for a future asset. It may not select, generate, or reinterpret an image to fill an unresolved requirement.

## Interaction Package

The Interaction Package describes approved student and teacher behavior associated with each slide. Each interaction record includes:

- stable interaction identifier;
- associated slide and lesson phase;
- instructional purpose;
- teacher and student actions;
- grouping structure;
- preparation or think time;
- response method;
- evidence expectations;
- participation and accountability routine;
- teacher monitoring guidance;
- completion condition;
- linked supports and transition.

Interactions must remain distinct from presentation animations. The Assembler confirms that interaction references are complete but does not revise the participation design.

## Timing Package

The Timing Package reconciles approved timing at the lesson, phase, activity, interaction, and slide levels. It contains:

- total estimated lesson duration;
- instructional-day structure when applicable;
- phase durations;
- slide-level estimates;
- interaction and student-work time;
- transition allowances;
- timing ranges or flexibility notes;
- source-provided timing;
- approved adaptations to timing;
- identified pacing conflicts or unresolved constraints.

Timing records must not double-count continuous activities distributed across multiple slides. The Assembler validates arithmetic and relationships but returns instructional timing conflicts to the Instruction Designer rather than deciding how to shorten the lesson.

## Curriculum Traceability Package

The Curriculum Traceability Package preserves the evidence and decision history for major lesson and slide elements. Each record includes:

- associated lesson, phase, activity, assessment, or slide identifier;
- original curriculum requirement;
- source file;
- page number when available;
- section heading or exact source label;
- TeacherOS decision;
- adaptation type;
- rationale;
- effect on pacing and rigor where applicable;
- fidelity status;
- confidence level;
- approval status;
- relationship to unresolved issues.

Traceability must remain intact through export. A downstream renderer may consume only the fields needed for building the presentation, but the complete Lesson Package must remain human-auditable.

## Metadata Package

The Metadata Package identifies, governs, and describes the assembled lesson. It includes:

- package identifier;
- package version and Structured Lesson Model version;
- lesson title and number;
- curriculum, publisher, grade, subject, unit, and lesson identifiers;
- estimated duration and instructional days;
- lesson type;
- source inventory summary;
- creation, validation, approval, and export statuses;
- artifact versions and owning modules;
- intended audience and classroom context;
- target renderer and presentation format;
- required assets and external dependencies;
- accessibility profile;
- unresolved-issue summary;
- revision and approval history.

Metadata values must be derived from authoritative upstream records. When duplicate values conflict, the Assembler must report the conflict instead of choosing one silently.

## Validation

Package validation includes the following dimensions:

### Completeness

Confirm that all required subpackages, lesson elements, slide fields, references, and statuses are present or explicitly marked not applicable.

### Referential Integrity

Confirm that every slide, note, visual, interaction, timing record, transition, asset, and traceability record points to a valid identifier and that no required record is orphaned.

### Sequence Integrity

Confirm that slide numbering is unique and continuous, phase and slide order are consistent, transitions point to the correct destination, and reveal order is valid.

### Content Separation

Confirm that student-facing content, teacher-only guidance, rendering directions, metadata, and traceability are kept in their intended channels.

### Timing Consistency

Confirm that slide and phase timing reconciles with the lesson total and that continuous activities are not counted repeatedly.

### Fidelity Preservation

Confirm that required curriculum elements, source references, adaptation statuses, rationales, and approval states remain attached and unchanged.

### Renderer Compatibility

Confirm that the selected renderer profile can represent every required field or that a documented, approved fallback exists.

### Issue Visibility

Confirm that unresolved items, missing assets, unsupported features, and authorized exceptions remain visible in both the package and readiness report.

Validation produces explicit pass, warning, or blocking results. Warnings may proceed only when the export policy permits them and their impact remains visible.

## Packaging Rules

The Lesson Assembler follows these rules:

1. One package represents one lesson unless an approved multi-day package profile states otherwise.
2. Every package and component uses stable, unique identifiers.
3. Slide numbers represent display order; identifiers represent durable identity.
4. Curriculum-original content and TeacherOS adaptations remain distinguishable.
5. Required fields may not be omitted silently; nonapplicable fields must be marked deliberately.
6. Student-facing content and teacher-facing notes remain separate.
7. References use identifiers rather than duplicated content whenever practical.
8. Source provenance and confidence survive every packaging transformation.
9. Optional components remain labeled optional and may not be promoted to required status by packaging.
10. Missing assets and unsupported renderer features remain explicit dependencies.
11. Packaging normalization may change structure or naming only when meaning is preserved.
12. An assembled package is immutable as an approved export; revisions produce a new package version.
13. A new lesson package must not overwrite an earlier lesson or approved version.
14. Renderer-specific data must not replace the renderer-independent instructional record.

## Export Readiness

Export readiness indicates whether a Lesson Package can be handed to the selected renderer without additional instructional or visual decisions. The package must declare one status:

- **Ready:** All blocking validations pass, required assets and fields are available, and renderer compatibility is confirmed.
- **Ready with warnings:** No blocking issue remains, but documented noncritical limitations or approved fallbacks require attention.
- **Blocked:** One or more missing, conflicting, unsupported, or unapproved conditions prevent responsible rendering.

The readiness record identifies the target renderer, presentation format, package version, validation result, required dependencies, warnings, and blocking issues. Renderer readiness does not imply teacher approval for classroom use unless that approval is separately recorded.

## Internal Workflow

The Lesson Assembler follows this observable workflow:

1. Receive all lesson artifacts.
2. Validate completeness and upstream approval status.
3. Check identities, references, sequence, timing, and content consistency.
4. Assemble lesson metadata.
5. Assemble the ordered slide specifications.
6. Assemble and link teacher-facing notes.
7. Assemble and link interactions.
8. Assemble and link image directions and asset dependencies.
9. Assemble timing, transitions, traceability, and validation records.
10. Create one complete Lesson Package and determine export readiness.

Each stage produces observable package records or validation results. This workflow does not expose or depend upon private reasoning.

## Output Contract

The Lesson Assembler outputs one versioned Lesson Package containing:

- package and lesson metadata;
- the complete ordered Slide Package;
- the Speaker Notes Package;
- the Image Direction Package;
- the Interaction Package;
- animation and reveal specifications;
- the Timing Package;
- transition records;
- the Curriculum Traceability Package;
- accessibility and ELD presentation requirements;
- asset and materials inventories;
- validation results;
- unresolved issues and approved exceptions;
- renderer profile;
- export-readiness status.

The package must be structured, consistent, machine-readable, human-auditable, versioned, and optimized for the declared renderer. Another rendering engine must be able to build the complete presentation without selecting objectives, changing sequence, writing lesson content, inventing supports, or making any other instructional decision.

The output is a specification package, not a presentation file. Rendering remains the responsibility of an authorized downstream presentation renderer.

## Failure Conditions

Assembly or export is blocked when:

- required lesson artifacts are missing;
- artifacts identify different lessons or incompatible model versions;
- slide order is incomplete, duplicated, or contradictory;
- required notes, interactions, visuals, timing, transitions, or references cannot be associated with valid slides;
- student-facing and teacher-facing content cannot be distinguished;
- critical timing values conflict;
- required curriculum components are absent or unapproved;
- adaptation or approval status is missing for a substantive change;
- a critical source conflict remains unresolved;
- the target renderer cannot represent a required element and no approved fallback exists;
- packaging would require an instructional or visual-design decision;
- the package would conceal an unresolved issue or missing dependency.

Failure must produce a blocked-assembly report that identifies the affected components, owning modules, validation evidence, safe partial package state, downstream impact, and action required. The Assembler must not fabricate missing records or silently discard incompatible content.

## Success Criteria

The Lesson Assembler succeeds when:

- every approved lesson artifact is included or correctly referenced;
- all package components identify the same lesson and compatible versions;
- slide sequence and identifiers are complete and stable;
- notes, interactions, visuals, timing, transitions, and traceability link to the correct slides;
- student-facing, teacher-facing, and renderer-facing information remain separate;
- curriculum fidelity and adaptation history are preserved;
- validation results and unresolved issues are visible;
- the target renderer’s requirements are satisfied;
- no instructional, visual-design, or rendering decisions were introduced during assembly;
- the complete lesson can be rendered entirely from the assembled package.

## Version 1 Scope

Version 1 outputs one Lesson Package per lesson, optimized for presentation rendering and Google Slides delivery. It prioritizes stable slide ordering, complete teacher notes, explicit image and interaction directions, reconciled timing, curriculum traceability, human auditability, and clear export readiness.

Version 1 may use renderer-specific packaging conventions where necessary, but the authoritative lesson content must remain separable from those conventions so future renderers can consume the same instructional design.

## Future Enhancements

### Multiple Renderers

_[Placeholder for renderer-neutral package profiles, capability negotiation, fallbacks, validation, and equivalent output review.]_

### PowerPoint

_[Placeholder for editable presentation packaging, notes, assets, animations, compatibility, and export validation.]_

### Canva

_[Placeholder for design mapping, editable elements, templates, notes handling, assets, and fidelity checks.]_

### HTML

_[Placeholder for responsive lesson presentation, interaction, accessibility, offline behavior, and browser compatibility.]_

### PDF

_[Placeholder for fixed-layout presentation or teacher-copy export, pagination, notes, accessibility, and print validation.]_

### LMS Export

_[Placeholder for course packaging, activities, assessments, metadata, standards, grades, and interoperability.]_

### Printable Packets

_[Placeholder for student and teacher packets, page order, handouts, assessments, answer guidance, and print accessibility.]_

### AI Video Generation

_[Placeholder for narration, scenes, timing, visuals, captions, provenance, accessibility, review, and instructional fidelity.]_
