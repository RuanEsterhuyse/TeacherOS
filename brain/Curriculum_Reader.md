# Curriculum Reader

## Purpose

The Curriculum Reader is the ingestion and extraction layer of the TeacherOS Brain. It accepts curriculum and teacher-guide materials, identifies the content belonging to a requested lesson, and converts that content into a reliable, structured source representation for the Structured Lesson Model and Curriculum Analyzer.

The module extracts only source-grounded information. It preserves available page and section references, records the order in which information appears, and flags missing, unreadable, conflicting, or uncertain information for review. It does not redesign the lesson or make independent instructional decisions.

## Responsibilities

The Curriculum Reader is responsible for:

- ingesting supported curriculum source formats;
- registering and classifying every source provided for a lesson;
- identifying the curriculum hierarchy represented by the sources;
- detecting lesson boundaries and sections that continue across pages or files;
- separating teacher directions from student-facing content;
- identifying headings and structural relationships within the curriculum;
- extracting objectives, standards, vocabulary, texts, activities, questions, assessments, materials, preparation, homework, timing, differentiation, and references;
- preserving the original source order of lesson components;
- tracking provenance for every extracted item;
- assigning an extraction-confidence level based on source clarity and extraction quality;
- reporting incomplete, unavailable, ambiguous, conflicting, or unreadable content;
- populating the source-grounded portions of the Structured Lesson Model;
- supplying the Curriculum Analyzer with dependable, auditable input.

The module must preserve distinctions present in the source. It should not collapse teacher guidance, student directions, required content, optional content, answer guidance, and supporting references into an undifferentiated body of text.

## Non-Responsibilities

The Curriculum Reader must not:

- invent missing curriculum content;
- improve or redesign the lesson’s instructional structure;
- rewrite, simplify, strengthen, or replace objectives;
- add ELD or accessibility supports not present in the source;
- design slides or presentation layouts;
- create new assessments, questions, rubrics, or answer guidance;
- decide which activities should be changed, combined, reordered, or removed;
- resolve instructional ambiguity through unsupported assumptions;
- send content directly to a presentation renderer.

Instructional interpretation and design belong to downstream modules. The Reader’s role ends with a faithful, structured, and qualified representation of the available sources.

## Supported Inputs

The Curriculum Reader is designed to accept:

- pasted text;
- PDF teacher guides;
- Word documents;
- Google Docs exports;
- activity books;
- student readers;
- lesson supplements;
- images or scanned pages when reliable text extraction is available.

Inputs may contain a single lesson, multiple lessons, an entire unit, or resources referenced by another source. The module must retain each file’s identity and relationship to the requested lesson.

Version 1 may begin with pasted text and digitally readable PDFs. Other input types remain supported architectural targets and should be treated as unavailable when the active system cannot extract them reliably, rather than being represented as successfully processed.

## Input Classification

Every input must be assigned one source-role classification:

- **Teacher guide:** Authoritative teacher-facing lesson directions, sequence, pacing, questions, supports, and answer guidance.
- **Student reader:** Text intended primarily for student reading, reference, or analysis.
- **Activity book:** Student-facing activity pages, organizers, practice, or written-response materials.
- **Assessment:** Formal or informal assessment materials, rubrics, scoring guidance, or answer keys provided separately from the main guide.
- **Supplemental resource:** An additional source that supports the lesson but is not one of the primary curriculum components.
- **Unknown source:** A source whose role cannot be determined confidently from available evidence.

Each registered input must support the following metadata:

- **Curriculum:** The official curriculum or program title when available.
- **Publisher:** The source organization or publisher when available.
- **Grade:** The grade level or grade band represented by the source.
- **Subject:** The academic subject or discipline.
- **Unit:** The unit identifier and title represented by the source.
- **Lesson:** The lesson identifier and title represented by or associated with the source.
- **File name:** The original source file name or a stable label for pasted content.
- **Page range:** The printed or digital page range contained in the input, when determinable.
- **Source type:** One of the source-role classifications defined above.

Unknown values must be recorded as unknown or unresolved. They must not be inferred solely to complete a metadata field.

## Lesson Boundary Detection

The Curriculum Reader must locate the requested lesson within the available sources before extracting its content. Boundary detection should identify:

- the lesson title;
- the lesson number or identifier;
- the point at which the lesson begins;
- the point at which the lesson ends;
- whether the lesson spans multiple instructional days;
- sections that begin on one page and continue onto another;
- appendices, answer keys, handouts, or other resources referenced outside the main lesson pages.

Evidence for a boundary may include headings, repeated page structures, tables of contents, lesson labels, unit markers, page headers, navigation elements, and explicit continuation references. A detected boundary must remain linked to the evidence that supports it.

The Reader must distinguish a multi-day lesson from neighboring lessons and must not treat a page break as a lesson boundary by itself. When lesson boundaries cannot be determined with adequate confidence, the module must flag the ambiguity and request review rather than silently guessing.

## Extraction Categories

### Lesson Identity

The Curriculum Reader extracts:

- **Title:** The lesson title exactly as identified in the source.
- **Number:** The lesson number or stable identifier.
- **Unit:** The associated unit identifier and title.
- **Grade:** The stated grade level or grade band.
- **Subject:** The stated academic subject or discipline.
- **Duration:** Any explicit total, phase-level, or day-level timing.
- **Lesson type:** Any source-provided classification of the lesson’s instructional function.

Source-provided identity values must be preserved as written. Conflicting identities across files must be reported rather than silently reconciled.

### Standards and Objectives

The Curriculum Reader extracts:

- standards explicitly associated with the lesson;
- content objectives;
- language objectives already present in the curriculum;
- essential questions;
- success criteria or equivalent source-provided expectations.

Each entry must retain its source label and reference. The Reader must not convert an activity description into a formal objective, infer an unstated standard, or create success criteria when none are provided.

### Materials and Preparation

The Curriculum Reader extracts:

- required teacher and student materials;
- advance preparation steps;
- technology requirements;
- handouts and reproducible resources;
- student-reader page references;
- activity-book page references.

Materials must remain connected to the lesson or activity for which they are required. References to unavailable materials must be recorded in the missing-materials report.

### Vocabulary

The Curriculum Reader extracts:

- vocabulary words and phrases;
- curriculum-provided definitions;
- pronunciation guidance;
- morphology or word-part guidance;
- vocabulary categories or instructional labels;
- source references.

The Reader must preserve the distinction between definitions supplied by the curriculum and contextual language that merely suggests meaning. It must not create student-friendly definitions, examples, cognates, or visual supports unless they are explicitly present in the source.

### Texts and Reading Selections

The Curriculum Reader extracts:

- text title;
- author, when stated;
- page range;
- identified excerpt or section;
- stated reading purpose;
- whether the text is designated for teacher read-aloud, student reading, partner reading, independent reading, or another source-defined mode.

The Reader must identify references to texts located in other files and record whether those files are available. It should retain only the amount of source text necessary for accurate extraction and verification.

### Instructional Activities

For each activity, the Curriculum Reader extracts:

- **Title:** The activity heading or a source label that identifies it.
- **Sequence:** Its position within the lesson and within any larger section.
- **Purpose:** The instructional purpose only when explicitly stated.
- **Teacher directions:** Actions, explanations, questions, and guidance directed to the teacher.
- **Student directions:** Directions and task language intended for students.
- **Grouping structure:** Whole-class, partner, small-group, independent, or other stated participation format.
- **Estimated time:** Source-provided duration or pacing guidance.
- **Required materials:** Resources associated with the activity.
- **Source reference:** File, page, section, label, and sequence position.

The Reader must preserve activity order and nesting. It must not infer a missing purpose, alter grouping, merge repeated-looking activities, or remove activities that appear redundant.

### Questions and Discussion

The Curriculum Reader extracts and classifies, when the source supports the distinction:

- literal questions;
- inferential questions;
- analytical questions;
- discussion prompts;
- expected or suggested responses;
- requirements for citing, quoting, or discussing textual evidence.

Questions must remain connected to the relevant text, activity, phase, and answer guidance. Classification uncertainty must be recorded rather than resolved through unsupported interpretation.

### Assessment

The Curriculum Reader extracts:

- checks for understanding;
- formative assessments;
- written responses;
- exit tickets;
- quizzes;
- rubrics or scoring criteria;
- answer guidance.

The Reader must preserve any source distinction among required assessments, optional checks, practice, and answer keys. It must not create missing answer guidance or infer assessment alignment beyond what the source explicitly supports.

### Differentiation and Supports

The Curriculum Reader extracts only supports explicitly present in the source, including:

- scaffolds;
- challenge or extension options;
- accommodations;
- ELD supports;
- special education notes;
- grouping guidance.

Each support must retain its source label, intended learner group when stated, associated activity, and source reference. The Reader must not supplement, modernize, or evaluate the adequacy of source-provided supports.

### Homework and Follow-Up

The Curriculum Reader extracts:

- assigned homework;
- independent reading;
- extension tasks;
- preparation required for the next lesson.

Each item must indicate whether the source presents it as required, optional, or conditional. References to unavailable pages or resources must be reported.

## Source Traceability

Every extracted item must retain sufficient provenance for a human reviewer to locate and verify it. At minimum, each item supports:

- **Source file name:** The exact registered file or stable pasted-text label.
- **Page number:** The printed or digital page number when available, with the numbering system distinguished when necessary.
- **Section heading:** The nearest relevant source heading or structural locator.
- **Sequence position:** The item’s ordered location within the lesson and its containing section or activity.
- **Exact source label:** The curriculum’s own label for the item, when one is present.
- **Confidence level:** High, medium, low, or unresolved extraction confidence.

Traceability records must remain attached when content is passed to downstream modules. Short source quotations may be retained internally when they are necessary to verify a label, requirement, boundary, or interpretation. The Reader should avoid unnecessary duplication of copyrighted materials and should prefer precise references over copying extended passages.

## Confidence Levels

Confidence describes the reliability of extraction and classification, not the instructional quality of the source.

- **High confidence:** The source is readable, the item is explicit, its boundaries and label are clear, and its reference can be verified directly.
- **Medium confidence:** The item is probably identified correctly, but formatting, continuation, classification, or reference evidence contains a limited ambiguity that does not prevent useful extraction.
- **Low confidence:** The item may be incomplete, misordered, poorly scanned, weakly labeled, or dependent on interpretation that requires human verification before downstream reliance.
- **Unresolved:** Available evidence is insufficient or contradictory, and the item cannot be represented reliably without additional source material or an authorized decision.

Confidence may be assigned at the source, section, or item level. A high-confidence file does not automatically make every extraction from that file high confidence. Medium-, low-, and unresolved results must include a concise reason and recommended review need.

## Missing and Ambiguous Information

The Curriculum Reader must explicitly report:

- missing pages;
- unreadable or corrupted text;
- activities that begin or end outside the available source;
- references to unavailable readers, activity pages, handouts, appendices, media, or supplements;
- conflicting timing values;
- duplicated lesson sections whose authority or intended use is unclear;
- unclear or conflicting printed and digital page numbering;
- absent answer keys or answer guidance referenced by the lesson;
- extraction whose source order appears broken.

Each issue record should identify the affected source, lesson component, severity, evidence, potential downstream impact, and what would be needed to resolve it. The Reader must preserve partial reliable extraction when useful, but it must never silently fill a gap or present incomplete content as complete.

## Internal Workflow

The Curriculum Reader follows this observable processing workflow:

1. Register and classify source files.
2. Identify the curriculum hierarchy.
3. Detect the requested lesson boundaries.
4. Extract lesson components in source order.
5. Separate teacher-facing and student-facing content.
6. Attach source references to every extracted item.
7. Identify missing or ambiguous information.
8. Calculate extraction-confidence indicators.
9. Populate the relevant portions of the Structured Lesson Model.
10. Pass the structured source representation to the Curriculum Analyzer.

Each stage produces reviewable outputs or statuses. This workflow describes externally observable processing and artifacts only; it does not expose or depend on private reasoning.

## Output Contract

The Curriculum Reader outputs:

- **Source inventory:** Registered files, classifications, metadata, availability, readability, and processing status.
- **Lesson identity:** Source-grounded curriculum, unit, lesson, grade, subject, duration, and lesson-type information.
- **Extracted curriculum components:** Structured objectives, standards, vocabulary, texts, materials, preparation, questions, assessments, supports, homework, and other identified components.
- **Ordered activity sequence:** Activities and nested elements represented in their original source order.
- **Source-reference map:** Verifiable provenance connecting extracted items to files, pages, headings, labels, and sequence positions.
- **Confidence report:** Confidence levels, reasons, and review needs at the relevant source, section, and item levels.
- **Missing-materials report:** Expected or referenced resources that were not provided or could not be accessed.
- **Unresolved-issues list:** Ambiguities, conflicts, boundary questions, and incomplete extractions requiring review.
- **Partially populated Structured Lesson Model:** The source-grounded model sections owned or supplied by the Reader, ready for authorized downstream enrichment.

The output must be structured, internally consistent, machine-readable, and human-auditable. It must preserve distinctions among direct source content, extraction metadata, confidence judgments, and unresolved issues.

## Validation Rules

Before output is accepted for downstream analysis, the Curriculum Reader must check that:

- a lesson title or identifier is present, or its absence is explicitly unresolved;
- all processed source files are registered;
- objectives are captured or explicitly marked absent from the available sources;
- activity order matches the source order;
- assessments are captured or explicitly marked absent from the available sources;
- page references are attached wherever reliable page information is available;
- referenced external resources are listed and their availability is recorded;
- low-confidence and unresolved extractions are visibly flagged;
- teacher-facing and student-facing content are distinguished;
- no unsupported instructional additions have been introduced.

Validation findings must identify the affected source and item. A structurally valid output may still contain flagged uncertainty, but unresolved issues that compromise lesson identity, boundaries, or critical requirements must prevent the output from being represented as complete.

## Failure Conditions

The Curriculum Reader cannot produce a dependable complete extraction when:

- the requested lesson cannot be located;
- the source is substantially unreadable;
- lesson boundaries cannot be determined;
- critical pages are missing;
- extraction would require inventing content;
- conflicting source versions cannot be reconciled or assigned a clear authority.

A failure must produce a clear, auditable report describing what was attempted, which sources were available, what prevented reliable extraction, any partial information that remains trustworthy, and what additional source or decision is required. Failure must never result in fabricated or silently reconstructed curriculum content.

## Success Criteria

The Curriculum Reader succeeds when:

- the requested lesson is accurately located;
- curriculum content is extracted in source order;
- all major available components are captured or explicitly marked absent;
- provenance is preserved for every major extracted item;
- gaps, conflicts, readability problems, and uncertainty are visible;
- teacher-facing and student-facing content remain distinguishable;
- no instructional redesign or unsupported addition has occurred;
- the Curriculum Analyzer receives dependable, structured, and auditable input.

Success does not require every field to contain data when the source itself omits that information. It requires the representation to be truthful about what is present, absent, uncertain, or unavailable.

## Version 1 Scope

Version 1 prioritizes:

- CKLA Grade 8 source materials;
- one requested lesson at a time;
- pasted text and digitally readable PDFs;
- the teacher guide as the primary instructional source;
- optional student-reader and activity-book files;
- human review of flagged uncertainty.

Version 1 should establish reliable ingestion, boundary detection, ordered extraction, provenance, confidence reporting, and handoff to the Curriculum Analyzer before broader automation or source coverage is introduced. This scope does not authorize references to or assumptions about any specific lesson.

## Future Enhancements

### OCR for Scanned Curriculum

_[Placeholder for reliable text recovery, layout preservation, confidence reporting, and human verification of scanned materials.]_

### Automatic Multi-File Lesson Linking

_[Placeholder for associating teacher-guide sections, reader selections, activity pages, assessments, and supplements with the same lesson.]_

### Table and Diagram Extraction

_[Placeholder for preserving structured tables, diagrams, captions, labels, relationships, and reading order.]_

### Publisher-Specific Parsers

_[Placeholder for source-aware recognition of recurring publisher layouts and labels without changing the common output contract.]_

### Cross-Lesson Dependency Detection

_[Placeholder for identifying prerequisites, recurring texts, prior activities, next-lesson preparation, and unit-level dependencies.]_

### Multilingual Source Materials

_[Placeholder for language identification, aligned editions, translated source relationships, and cross-language provenance.]_

### Curriculum Version Comparison

_[Placeholder for detecting changes in lesson content, source references, sequence, and requirements across curriculum editions.]_

### Batch Unit Ingestion

_[Placeholder for processing multiple lessons while preserving lesson boundaries, independent validation, and per-lesson issue reporting.]_
