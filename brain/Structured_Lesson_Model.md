# Structured Lesson Model

## Purpose

The Structured Lesson Model is the shared data contract used by all TeacherOS Brain modules. It converts curriculum evidence and instructional decisions into a stable, organized representation that can be created, enriched, reviewed, validated, and rendered by different modules without losing meaning.

Passing raw curriculum text between modules would require each module to reinterpret the same source independently. That approach would create inconsistent terminology, duplicate analysis, weak traceability, and a greater risk of omissions or unsupported additions. The shared model preserves authoritative source evidence while giving every module a consistent view of lesson identity, content, sequence, supports, assessment, and presentation requirements.

The model is an architectural specification rather than an implementation schema. It defines the information TeacherOS must represent and the relationships the system must preserve, independent of any future storage technology.

## Design Principles

### Curriculum Fidelity

The model must preserve the curriculum’s stated objectives, texts, activities, sequence, assessments, materials, and instructional intent. Adaptations must remain distinguishable from direct curriculum requirements.

### Consistency

All Brain modules must use the same field meanings, naming conventions, status definitions, and structural relationships. A concept created by one module must retain its meaning when consumed by another.

### Traceability

Major lesson elements and decisions must link to their source evidence or be explicitly labeled as TeacherOS adaptations. The model must make unsupported claims, unresolved uncertainty, and approved deviations visible.

### Modularity

The model must be divided into coherent sections that modules can own or consume without requiring responsibility for the entire lesson. Module boundaries must not fragment information that needs to remain connected.

### Extensibility

The model must support future fields, modules, curricula, delivery formats, and learner needs without requiring older lesson records to be discarded or silently reinterpreted.

### Human Readability

Teachers, curriculum reviewers, and instructional designers must be able to inspect and understand the model’s contents. Labels, relationships, status values, and rationales should communicate meaning without requiring specialized technical knowledge.

### Machine Readability

The model must be structured consistently enough for automated creation, validation, comparison, transformation, and export. Free-form text may be used where professional judgment is necessary, but critical identities, relationships, states, and references must remain explicit.

## Source Metadata

Source Metadata establishes the provenance and completeness of the curriculum evidence used to construct a lesson.

- **Curriculum title:** The official name of the curriculum or program.
- **Publisher:** The organization responsible for publishing or maintaining the curriculum.
- **Grade:** The intended grade level or grade band, using the curriculum’s own designation.
- **Subject:** The primary academic subject or discipline.
- **Unit:** The official unit identifier and title, when available.
- **Lesson:** The source curriculum’s lesson identifier and designation.
- **Source file names:** A complete list of files reviewed or expected for the lesson, preserving their original names.
- **Source page numbers:** The relevant printed and digital page references associated with extracted information.
- **Source type:** The role of each source, such as Teacher Guide, Student Reader, Activity Book, assessment, or supporting resource.
- **Extraction confidence:** A documented confidence level for information derived from each source, with uncertainty noted for review.
- **Missing source materials:** A list of expected but unavailable, inaccessible, incomplete, or unreadable sources and the potential impact of each omission.

Source records should remain independently identifiable so that a page reference cannot be separated from the file and source type to which it belongs.

## Lesson Identity

Lesson Identity provides the stable identifiers and planning attributes required to distinguish and organize a lesson.

- **Lesson title:** The official lesson title when supplied by the curriculum, or a clearly labeled working title when one is not supplied.
- **Lesson number:** The curriculum’s lesson number or other stable lesson identifier.
- **Estimated duration:** The total planned instructional time, including the unit and basis used for the estimate.
- **Instructional days:** The number of class meetings expected to complete the lesson.
- **Lesson type:** A controlled description of the lesson’s primary instructional function or functions.
- **Prerequisites:** Required prior knowledge, skills, completed readings, earlier lessons, materials, or preparation.

Identity fields must distinguish source-provided values from TeacherOS planning values whenever they differ.

## Standards and Objectives

Standards and Objectives define what the lesson is intended to accomplish and how successful learning will be recognized.

- **Standards:** Identifiers, descriptions, source authority, and alignment status for standards explicitly associated with the lesson.
- **Content objectives:** Curriculum-grounded statements describing the knowledge and disciplinary skills students should develop.
- **Language objectives:** Statements describing the language functions and forms students need to participate successfully in the lesson.
- **Essential question:** The central inquiry that organizes student thinking across the lesson or its larger unit.
- **Enduring understanding:** The transferable understanding students should retain beyond the immediate activity.
- **Success criteria:** Observable evidence that demonstrates progress toward or attainment of each objective.

Objectives and criteria must remain linked. TeacherOS must not infer a formal standard or present an adaptation as curriculum-authored unless the source supports that classification.

## Lesson Content

Lesson Content represents the academic substance, resources, and preparation required for instruction.

- **Lesson summary:** A concise overview of the lesson’s purpose, progression, and expected outcome.
- **Key concepts:** The central ideas, relationships, and disciplinary understandings students encounter.
- **Background knowledge:** Knowledge or context required to access the lesson, including whether it is assumed, reviewed, or newly introduced.
- **Required texts:** All texts mandated by the curriculum, with titles, locations, relevant sections, and usage requirements.
- **Reading selections:** Specific excerpts, chapters, passages, or page spans assigned for reading or analysis.
- **Vocabulary:** References to the lesson’s structured Vocabulary Model entries.
- **Materials:** Teacher, student, classroom, and technology resources required for the lesson.
- **Preparation:** Actions that must be completed before instruction, including setup, copying, display, review, or resource access.
- **Homework:** Required or optional work assigned outside the instructional session, with source status and completion expectations.

Required content must be distinguishable from optional enrichment, TeacherOS recommendations, and teacher-added materials.

## Instructional Sequence

The Instructional Sequence organizes the lesson into ordered phases. A phase is a coherent instructional interval with a clear purpose and defined transition; phases may contain one or more activities but must retain their relationship to the curriculum sequence.

Each phase supports the following fields:

- **Phase name:** A stable, descriptive label for the instructional interval.
- **Purpose:** The phase’s contribution to the lesson objectives and overall progression.
- **Duration:** The planned time and any relevant pacing range or source-provided timing.
- **Teacher actions:** Observable actions the teacher performs to facilitate learning.
- **Student actions:** Observable actions students perform individually or collaboratively.
- **Teacher language:** Questions, explanations, directions, prompts, or exact wording when pedagogically necessary.
- **Student task:** The product, response, practice, reading, discussion, or other work students are expected to complete.
- **Discussion structure:** The participation format, grouping, roles, turn-taking, and reporting expectations.
- **Checks for understanding:** Evidence gathered during the phase and the decision it informs.
- **Transitions:** The conceptual and procedural connection into the following phase.
- **Source references:** The curriculum evidence supporting the phase, its sequence, and its required activities.

Phases must be ordered, uniquely identifiable within the lesson, and connected to relevant objectives, assessments, supports, and slides. Changes to curriculum-provided sequence or timing require an explicit adaptation record and rationale.

## Vocabulary Model

The Vocabulary Model represents the academic, domain-specific, and instructional language required by the lesson.

- **Word:** The canonical term or phrase students will encounter.
- **Student-friendly definition:** An accessible explanation appropriate to the lesson context and grade level.
- **Curriculum definition:** The definition supplied by the curriculum, preserved without being silently replaced.
- **Part of speech:** The grammatical role relevant to the term’s lesson usage.
- **Pronunciation:** Teacher- and student-usable pronunciation guidance when needed.
- **Example in context:** A contextually accurate usage that supports understanding without introducing unsupported lesson content.
- **Morphology:** Relevant roots, affixes, word families, or meaningful word parts.
- **Cognates:** Accurate cross-language connections when instructionally useful.
- **Visual support:** A description or reference for a visual that clarifies meaning.
- **Likely misconceptions:** Predictable confusions, overgeneralizations, or incorrect meanings.
- **Instructional priority:** The term’s importance and expected depth of instruction within the lesson.
- **Source reference:** The source location and context in which the term or definition appears.

Vocabulary entries should link to the phases, texts, language objectives, supports, and slides where they are introduced or used.

## Assessment Model

The Assessment Model represents evidence of learning across the lesson and connects that evidence to objectives and success criteria.

- **Diagnostic assessment:** Evidence collected before or at the start of instruction to identify relevant readiness or prior understanding.
- **Formative checks:** Planned observations, responses, tasks, or decisions used to adjust instruction during the lesson.
- **Comprehension questions:** Questions that assess understanding of required texts, concepts, or relationships.
- **Discussion evidence:** Observable indicators of understanding demonstrated through structured student talk.
- **Written response:** Short or extended writing used to demonstrate learning.
- **Exit ticket:** A closing measure of progress toward the lesson objectives.
- **Homework:** Assessed or reviewable work assigned beyond the instructional session.
- **Success criteria:** The observable qualities used to judge each assessment response.
- **Answer guidance:** Expected ideas, acceptable response features, evidence requirements, misconceptions, and review guidance for the teacher.
- **Source references:** The curriculum source supporting required questions, tasks, answer expectations, or assessment placement.

Every assessment entry should identify its purpose, associated objective, instructional phase, required or optional status, and intended use of the resulting evidence.

## ELD and Accessibility Supports

ELD and Accessibility Supports represent targeted ways to improve access and participation while preserving the lesson’s academic goals.

- **Proficiency level:** The learner profile or language-development range for which a support is appropriate.
- **Language function:** The communicative purpose students must perform, such as explaining, comparing, justifying, or sequencing.
- **Language forms:** The vocabulary, grammatical structures, discourse patterns, or text structures needed for the language function.
- **Sentence frames:** Optional language structures that support complete and increasingly independent responses.
- **Vocabulary supports:** Definitions, word banks, morphology, cognates, pronunciation, or contextual reinforcement.
- **Visual supports:** Images, diagrams, gestures, organizers, or displayed language that improve access.
- **Chunking:** Planned segmentation of text, directions, tasks, or processing time.
- **Modeling:** Demonstrations, worked examples, think-alouds, or sample responses that clarify expectations.
- **Partner structures:** Grouping, rehearsal, roles, turn-taking, and participation routines.
- **Accommodations:** Approved changes to access, environment, timing, response mode, or presentation that do not alter the intended construct.
- **Extensions:** Opportunities for deeper, broader, or more independent work beyond the core expectation.

Each support should identify the actual lesson demand it addresses, the learners for whom it is intended, and where it appears in the instructional sequence. The model should distinguish universal supports, targeted multilingual learner supports, formal accommodations, and extensions.

## Slide Specification

The Slide Specification represents each planned presentation screen as an instructional artifact derived from the approved lesson sequence.

- **Slide number:** The unique ordered position of the slide in the presentation.
- **Slide type:** A controlled classification describing the slide’s functional pattern.
- **Instructional purpose:** The single primary contribution the slide makes to learning or lesson management.
- **Title:** The concise student-facing or organizational heading.
- **Student-facing text:** The exact content intended to be visible to students.
- **Teacher-facing notes:** Explanations, questions, anticipated responses, pacing, scaffolds, transitions, and other guidance not intended for display.
- **Visual direction:** The purpose and specification for imagery, diagrams, layout, or other visual elements.
- **Interaction:** The expected teacher-student or student-student action associated with the slide.
- **Estimated time:** The planned duration of the instructional moment supported by the slide.
- **Source reference:** The curriculum evidence supporting visible content, required directions, texts, questions, or sequence.

Each slide must link to an instructional phase. Fields that do not apply should be explicitly marked as not applicable rather than silently omitted.

## Image Direction Model

The Image Direction Model defines the instructional and representational requirements for each proposed visual.

- **Visual purpose:** The comprehension, context, vocabulary, organization, sequence, or analysis need served by the visual.
- **Image subject:** The precise people, objects, setting, event, relationship, or concept to depict.
- **Composition:** Framing, orientation, hierarchy, focal point, spatial relationships, and placement requirements.
- **Style:** The appropriate visual treatment and consistency expectations for the lesson or presentation.
- **Age appropriateness:** Suitability for the intended grade level, including emotional intensity and complexity.
- **Cultural considerations:** Accuracy, respect, representation, historical context, and stereotype avoidance requirements.
- **Text restrictions:** Limits on embedded labels, captions, typography, quotations, or generated text within the image.
- **Accessibility description:** A concise description of the visual’s meaningful content and function for accessible use.
- **Source connection:** The curriculum text, concept, vocabulary item, activity, or instructional phase the visual supports.

Image directions must be specific enough to review for instructional relevance and representational accuracy before a visual is selected or produced.

## Curriculum Fidelity and Traceability

Every major lesson decision must be connected to the original curriculum source or explicitly identified as an adaptation. Traceability applies to objectives, required content, instructional phases, questions, assessments, homework, slide content, quotations, page references, and any change to curriculum-provided sequence or timing.

Each traceability record includes:

- **Source file:** The exact file containing the authoritative evidence.
- **Page number:** The printed or digital page location, including the page-system type when necessary.
- **Section heading:** The nearest relevant source heading or other stable locator.
- **Direct curriculum requirement:** A concise representation of what the source requires, with exact quotations separately governed and clearly identified.
- **TeacherOS adaptation:** The clarification, scaffold, reorganization, presentation choice, or enhancement introduced by TeacherOS.
- **Rationale:** The instructional or operational reason for the adaptation.
- **Fidelity status:** A controlled review state indicating whether the element is verified, adapted with justification, unresolved, missing, unsupported, or approved by the teacher.

Source evidence and TeacherOS interpretation must never be merged in a way that obscures authorship. When a source is unavailable or ambiguous, the affected elements must remain flagged until an authorized reviewer resolves them.

## Validation Rules

Validation evaluates structural completeness, internal consistency, source support, and readiness for downstream use. A validation result should identify the affected field, severity, reason, responsible module, and required resolution.

The model must support checks for:

- **Required fields:** Confirm that all mandatory identity, source, objective, sequence, assessment, and status fields are present and meaningfully populated.
- **Missing objectives:** Identify lessons or phases without verified objectives and objectives that are not represented in instruction.
- **Missing assessments:** Identify objectives without corresponding evidence of learning and required curriculum assessments that are absent.
- **Unsupported additions:** Flag content, claims, standards, activities, quotations, or requirements that lack source support or an explicit adaptation record.
- **Contradictory pacing:** Detect totals, phase durations, slide timing, or instructional-day assumptions that conflict with one another or with stated constraints.
- **Duplicate activities:** Detect repeated activities that appear to be accidental duplication rather than intentional practice or revisiting.
- **Missing source references:** Identify major lesson elements that lack sufficient provenance.
- **Incomplete slide notes:** Identify slides missing required teacher guidance, actions, timing, transitions, or explicitly marked non-applicable fields.
- **Absent ELD supports:** Identify language demands, phases, or learner profiles for which required supports have not been considered or documented.

Validation must distinguish blocking errors, review-required warnings, and advisory improvements. Passing structural validation does not replace professional curriculum review or teacher approval.

## Module Ownership

Ownership identifies which module is authoritative for creating or changing a model section. Enrichment allows a module to add specialized information without replacing authoritative fields. Validation assesses conformance without silently rewriting content. Consumption uses approved information to produce or evaluate downstream artifacts.

### Curriculum Reader

The Curriculum Reader creates Source Metadata and source-linked extracted records from the available curriculum materials. It supplies evidence to downstream modules and flags missing or uncertain sources without making instructional adaptations.

### Curriculum Analyzer

The Curriculum Analyzer creates and enriches Lesson Identity, source-grounded Standards and Objectives, Lesson Content, curriculum-provided sequence requirements, and initial traceability records. It validates coverage of curriculum requirements and consumes Curriculum Reader outputs.

### Instruction Designer

The Instruction Designer creates and enriches the Instructional Sequence, lesson summary, pacing plan, teacher and student actions, transitions, and aligned checks for understanding. It consumes curriculum analysis and must record adaptations to source-provided design.

### Vocabulary Designer

The Vocabulary Designer owns enrichment of the Vocabulary Model, including accessible definitions, pronunciation, morphology, contextual use, cognates, visual support, misconceptions, and priority. It consumes source vocabulary and validates alignment with lesson texts and language demands.

### Discussion Designer

The Discussion Designer enriches instructional phases with discussion structures, questions, participation expectations, teacher language, student evidence, and follow-up pathways. It consumes objectives, texts, sequence, assessment needs, and learner supports.

### Assessment Designer

The Assessment Designer creates and enriches the Assessment Model, links evidence to objectives and success criteria, and validates assessment coverage. It preserves required curriculum assessments and clearly labels supplemental checks or adaptations.

### ELD Specialist

The ELD Specialist creates and enriches Language Objectives and ELD and Accessibility Supports. It validates that supports correspond to actual language demands and consumes lesson content, vocabulary, instructional phases, assessments, and student interaction requirements.

### Slide Designer

The Slide Designer creates the Slide Specification from the approved Instructional Sequence and supporting models. It consumes objectives, content, discussion, assessment, ELD, and timing information while keeping student-facing content separate from teacher-facing notes.

### Image Director

The Image Director creates and enriches the Image Direction Model and visual-direction fields within Slide Specifications. It validates instructional purpose, relevance, age appropriateness, cultural accuracy, accessibility, and source connection.

### Quality Checker

The Quality Checker validates the complete model for fidelity, traceability, completeness, consistency, accessibility, pacing, assessment alignment, and downstream readiness. It reports findings and statuses but does not silently assume ownership of corrections.

### Lesson Assembler

The Lesson Assembler consumes approved sections of the model and organizes them into a coherent lesson package. It verifies that artifact boundaries, identifiers, ordering, and versions remain consistent and that unresolved findings are visible.

### Chalkie Build Engine

The Chalkie Build Engine consumes approved Slide Specifications, Image Directions, teacher-facing notes, timing, and presentation constraints. It produces a controlled build specification for Chalkie without redefining curriculum, instructional sequence, assessment, or learner supports.

When more than one module enriches a section, the authoritative owner remains explicit. Conflicting updates require validation and resolution rather than last-write-wins replacement.

## Serialization

The Structured Lesson Model may eventually be stored as JSON or another structured format that supports validation, interchange, versioning, and automated transformation. The chosen representation must preserve human-readable meaning, stable identifiers, explicit relationships, provenance, review status, and extension points.

This document does not define a final serialization format or JSON schema. Serialization decisions should follow validation of the conceptual model through real lesson workflows and should not prematurely constrain instructional requirements.

## Versioning

Each stored model should declare the version of the Structured Lesson Model it follows. Model versions must use a documented, predictable convention that distinguishes compatible additions from changes requiring migration or reinterpretation.

New optional fields and controlled values should be introduced with clear defaults or absence semantics. Existing fields must not be repurposed with a different meaning. When a breaking change is necessary, TeacherOS should retain the original lesson record, provide an explicit migration path, record the migration outcome, and preserve source and decision history.

Modules must declare which model versions they can create, consume, enrich, and validate. Older lessons should remain readable even when they do not contain fields introduced by later versions, and unsupported fields must not be silently discarded during processing.

## Success Criteria

The Structured Lesson Model is complete and usable when:

- all required curriculum evidence and lesson artifacts can be represented without relying on hidden module context;
- every major lesson decision can be traced to a source or explicit adaptation record;
- modules can exchange information without independently reinterpreting raw curriculum text;
- ownership and permitted enrichment are clear for every major section;
- objectives, instruction, assessment, supports, slides, and visuals remain connected;
- missing, uncertain, unsupported, or conflicting information is visible and reviewable;
- teachers and curriculum reviewers can understand the model without reading implementation documentation;
- automated systems can validate required fields, relationships, statuses, and references consistently;
- the model can support a complete lesson package while remaining independent of a particular presentation or storage tool;
- future model versions can extend the structure without making existing lessons unreadable.

## Future Enhancements

The following areas are reserved for future architectural development. They are not part of the current model contract and require separate requirements and review before adoption.

### Multi-Day Units

_[Placeholder for relationships among lessons, days, unit-level objectives, recurring resources, pacing, and cumulative assessments.]_

### Differentiated Lesson Variants

_[Placeholder for shared lesson cores, learner-specific variants, adaptation provenance, approval, and comparison.]_

### Multilingual Support

_[Placeholder for translated or multilingual content, language metadata, equivalence review, and cross-language traceability.]_

### Teacher Preferences

_[Placeholder for teacher-controlled pacing, routines, formats, accessibility choices, and reusable instructional preferences.]_

### Google Slides Integration

_[Placeholder for presentation synchronization, editable output, identifiers, notes, assets, revision status, and round-trip updates.]_

### Printable Materials

_[Placeholder for handouts, organizers, assessments, accessibility, print layout, and their relationship to lesson phases.]_

### Generated Media

_[Placeholder for generated images, audio, video, provenance, rights, review status, accessibility, and source alignment.]_

### Analytics

_[Placeholder for classroom evidence, usage signals, outcomes, privacy, interpretation limits, and feedback into lesson improvement.]_
