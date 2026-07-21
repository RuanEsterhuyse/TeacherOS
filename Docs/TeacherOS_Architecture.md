# TeacherOS Architecture

## Vision

TeacherOS is a durable instructional-design platform that converts authoritative curriculum materials into coherent, classroom-ready lesson packages. It provides a repeatable system for curriculum analysis, lesson planning, presentation design, teacher guidance, learner support, quality assurance, and permanent lesson storage.

The platform is designed to begin with CKLA Grade 8 while remaining adaptable to additional grades, units, subjects, and curriculum providers. Its architecture separates instructional decisions from presentation rendering so that lesson quality and curriculum fidelity remain consistent as tools and delivery formats evolve.

## Mission

TeacherOS exists to help teachers produce rigorous, accessible, and teachable lessons without losing the intent or required content of the source curriculum. It organizes the work of teachers and AI systems into an accountable workflow in which source evidence, instructional decisions, generated artifacts, and final outputs can be reviewed and improved over time.

## The Problem We Solve

High-quality curriculum materials often span teacher guides, student texts, activity books, assessments, and supplemental resources. Turning those materials into a usable daily lesson requires substantial interpretation and production work. Teachers must locate required elements, establish pacing, prepare student-facing materials, anticipate misconceptions, add language supports, and verify that the final lesson remains faithful to the curriculum.

General-purpose AI and presentation tools can accelerate this work, but they may omit required components, invent unsupported details, overfill slides, or alter instructional sequence. Files can also become fragmented across tools and difficult to reuse.

TeacherOS addresses these problems through a structured lesson pipeline, defined roles, standardized artifacts, explicit fidelity checks, and permanent storage. It preserves a traceable connection between curriculum sources and the finished lesson while allowing thoughtful improvements to clarity, engagement, accessibility, and delivery.

## Guiding Principles

1. **Curriculum fidelity:** Required objectives, texts, activities, sequence, assessments, materials, and homework remain authoritative.
2. **Traceability:** Important instructional decisions can be traced to a source, a documented rationale, or an explicit teacher decision.
3. **Clear responsibility:** Analysis, file management, slide rendering, and final approval have distinct owners.
4. **Instruction before presentation:** Lesson purpose and learning design determine the slide deck, not the reverse.
5. **Teacher authority:** The teacher remains the final decision-maker for every classroom-ready lesson.
6. **Accessible rigor:** Supports improve access to grade-level thinking without reducing intellectual demand.
7. **Purposeful visuals:** Visuals clarify, contextualize, organize, or support analysis; they are not decoration.
8. **Explicit uncertainty:** Missing or ambiguous information is identified for review rather than guessed.
9. **Reusable structure:** Standardized artifacts enable consistent production across lessons and units.
10. **Permanent learning:** Completed lessons and classroom feedback become durable inputs for future improvement.

## Primary Users

### Classroom Teachers

Teachers use TeacherOS to develop, review, teach, and revise lessons. They provide curriculum sources and classroom context, approve instructional decisions, and determine whether a package is ready for students.

### Instructional Designers

Instructional designers use the system to create repeatable lesson structures, strengthen learning sequences, define quality standards, and develop shared patterns that can be reused across a curriculum.

### Curriculum Leads and Reviewers

Curriculum leaders use fidelity checklists, lesson artifacts, and quality-assurance records to verify alignment and identify patterns across lessons, units, or grade levels.

### Content and Production Teams

Production users manage visual assets, presentation builds, templates, file organization, and delivery formats without independently changing the curriculum or approved instructional design.

## User Journey

1. **Initiate a lesson:** The teacher selects a grade, unit, and lesson and provides the available source materials.
2. **Confirm sources:** Teacher guides, student readers, activity books, assessments, and supporting resources are identified and cataloged.
3. **Analyze requirements:** TeacherOS extracts the objectives, texts, activities, questions, materials, timing, assessment expectations, and homework required by the curriculum.
4. **Review fidelity:** Required components and unresolved questions are recorded in a curriculum-fidelity checklist.
5. **Design instruction:** The lesson is organized into a coherent sequence with explicit teacher actions, student actions, checks for understanding, and transitions.
6. **Plan presentation:** The approved lesson sequence becomes a slide-by-slide storyboard with visible content, notes, supports, visuals, and timing.
7. **Prepare supporting artifacts:** TeacherOS develops speaker notes, ELD supports, image directions, and assessment guidance.
8. **Build the deck:** Chalkie renders the approved storyboard as an editable presentation without changing the lesson design.
9. **Assure quality:** The finished deck is checked against the source requirements, blueprint, storyboard, and accessibility expectations.
10. **Approve and teach:** The teacher reviews the complete package, makes classroom-specific adjustments, and uses it for instruction.
11. **Capture feedback:** Classroom evidence and revisions are stored with the lesson and may inform shared templates or design standards.

## Core Modules

### Curriculum Analyzer

The Curriculum Analyzer examines the authoritative lesson sources and produces a structured inventory of instructional requirements. It identifies objectives, lesson components, source texts, activity pages, vocabulary, questions, materials, timing, assessments, and homework. It also records source references and flags missing, contradictory, or uncertain information for teacher review.

Its output establishes the evidence base for all downstream modules. It does not redesign the lesson or fill gaps with invented curriculum content.

### Lesson Blueprint Generator

The Lesson Blueprint Generator converts the verified curriculum inventory into an instructional plan. It defines the lesson purpose, learning sequence, pacing, teacher and student actions, interaction patterns, materials, transitions, and checks for understanding.

The blueprint distinguishes curriculum requirements from optional enhancements and documents any approved adjustment to sequence or delivery. It serves as the instructional contract for the rest of the lesson package.

### Storyboard Generator

The Storyboard Generator translates the blueprint into a slide-by-slide plan. Every slide records its number, title, instructional purpose, student-visible content, teacher actions, student actions, speaker notes, ELD supports, check for understanding, visual direction, estimated timing, and transition.

The storyboard controls slide scope and sequence before rendering begins. It keeps student-facing content concise and places teacher guidance in the appropriate supporting field.

### Speaker Notes Generator

The Speaker Notes Generator creates practical teacher-facing guidance aligned to each stage of the lesson. Notes may include questions, concise explanations, anticipated responses, misconceptions, follow-up prompts, pacing guidance, transitions, pronunciation support, differentiation, sensitive-content guidance, and material reminders.

Notes are designed to support responsive teaching rather than prescribe a continuous script. Exact wording is included only when it serves a clear instructional purpose.

### ELD Engine

The ELD Engine identifies the language demands of the lesson and recommends targeted supports for multilingual learners. Supports may include student-friendly definitions, visuals, gestures, sentence frames, word banks, structured partner talk, rehearsal, chunked directions, modeled responses, cognates, and pronunciation guidance.

The engine separates universal supports, supports for developing multilingual learners, and extensions for advanced learners. Recommendations preserve the lesson’s intellectual rigor and connect directly to required student thinking, speaking, reading, and writing.

### Image Direction Engine

The Image Direction Engine converts instructional needs into precise visual specifications. Each direction identifies the visual’s purpose, subject, composition, context, age appropriateness, cultural considerations, accessibility needs, and intended slide placement.

The module prioritizes accurate, respectful, uncluttered visuals suitable for a 16:9 classroom presentation. It does not request generic imagery when a more specific instructional visual is needed.

### Chalkie Build Engine

The Chalkie Build Engine packages the approved storyboard and supporting directions into a precise presentation-build request. It defines the exact slide sequence, visible text, speaker notes, design requirements, visual directions, timing expectations, editability requirements, and final validation criteria.

This module constrains Chalkie to the role of presentation renderer. Required activities may not be combined, deleted, reordered, or rewritten without explicit approval, and unsupported curriculum content may not be introduced.

### Quality Assurance Engine

The Quality Assurance Engine validates both the lesson artifacts and the rendered presentation. It checks source coverage, objective alignment, required components, sequence, speaker-note usefulness, ELD relevance, visual appropriateness, checks for understanding, assessment alignment, homework accuracy, readability, timing, and classroom readiness.

Quality assurance produces clear pass, revision, or unresolved-review outcomes. It compares the finished deck with the fidelity checklist and storyboard so omissions and unapproved changes are visible before teacher approval.

### Lesson Library

The Lesson Library is the permanent system of record for lesson packages. It organizes lessons by curriculum, grade, unit, and lesson; retains editable and final artifacts; and prevents a new lesson from overwriting prior work.

The library supports discovery, reuse, revision history, and the promotion of successful patterns into shared templates or design-system guidance. Each lesson remains independently understandable through its README, source record, planning artifacts, final output, and revision notes.

## Data Flow

Information moves through TeacherOS as a controlled sequence of transformations:

1. **Teacher Guide and companion sources:** The Teacher Guide is the primary instructional source, supplemented by the Student Reader, Activity Book, assessment materials, and approved supporting resources.
2. **Source inventory:** The Curriculum Analyzer records each required component and its source reference. Missing materials and ambiguities enter an unresolved-items list.
3. **Fidelity model:** Verified requirements become the curriculum-fidelity checklist. This checklist acts as a constraint for every later artifact.
4. **Lesson blueprint:** Curriculum requirements are organized into a teachable sequence. Required content, optional enhancements, timing, interactions, and checks for understanding are made explicit.
5. **Slide storyboard:** The blueprint is decomposed into presentation-sized instructional moments, with separate fields for student-visible content and teacher guidance.
6. **Supporting artifacts:** Speaker notes, ELD supports, image directions, and assessment details are derived from the same approved blueprint and attached to the relevant lesson moments.
7. **Chalkie build prompt:** The complete storyboard and presentation constraints are assembled into a rendering specification.
8. **Editable slide deck:** Chalkie produces the presentation while preserving the approved content and sequence.
9. **Quality review:** The deck is compared with the storyboard, blueprint, and fidelity checklist. Findings lead to revision or teacher review.
10. **Approved lesson package:** The teacher approves the classroom-ready package, which is stored permanently in the Lesson Library.
11. **Feedback loop:** Post-lesson observations and revisions are associated with the lesson. Reusable findings may update shared templates and design standards through a separate review process.

At each stage, downstream artifacts inherit the constraints of upstream approved artifacts. When a source or instructional decision changes, affected downstream artifacts must be reviewed again rather than silently remaining out of sync.

## Project Structure

TeacherOS uses a predictable repository structure that separates shared system resources from curriculum-specific work:

- `Design_System/` contains the master specification, instructional standards, visual standards, reusable patterns, and governance guidance.
- `Templates/` contains reusable artifact structures for blueprints, fidelity checklists, storyboards, build prompts, notes, supports, assessments, and reviews.
- `Assets/` contains shared visual, media, and reference assets with sufficient provenance and usage information.
- `Curriculum/` contains all curriculum-specific lesson packages, organized hierarchically by curriculum, grade, unit, and lesson.
- `Docs/` contains architecture, operating procedures, roadmaps, decisions, and other repository-level documentation.

The curriculum hierarchy follows this conceptual pattern:

`Curriculum/<Curriculum_Name>/<Grade>/<Unit>/<Lesson>/`

Each lesson folder is self-contained. Shared materials belong at the narrowest common level that avoids unnecessary duplication: lesson-specific resources remain in the lesson folder, unit-wide resources may live at the unit level, and broadly reusable patterns belong in `Templates/`, `Assets/`, or `Design_System/`.

Folder and file names should remain stable, descriptive, and sortable. New lessons receive new folders; they never replace existing lesson directories. Revisions should preserve the history and status of prior classroom-ready outputs.

## Lesson Package

Every lesson folder represents one complete instructional-design unit and should contain the following artifacts:

### `README.md`

Provides a concise guide to the lesson package, including lesson identity, source status, artifact status, unresolved items, approval state, and navigation guidance.

### `01_Lesson_Blueprint.md`

Defines the lesson purpose, objectives, required materials, instructional sequence, timing, teacher actions, student actions, interactions, checks for understanding, and transitions. It distinguishes curriculum requirements from approved enhancements.

### `02_Curriculum_Fidelity_Checklist.md`

Lists every required objective, text, activity, question, material, assessment, and homework item, with its source reference and verification status. It records omissions, uncertainty, and any explicitly approved adjustment.

### `03_Slide_Storyboard.md`

Specifies the presentation slide by slide. Each entry includes the required storyboard fields and serves as the authoritative plan for presentation rendering.

### `04_Chalkie_Build_Prompt.md`

Contains the complete, approved instructions used to build the slide deck in Chalkie. It separates visible content from speaker notes and defines sequence, layout, visuals, formatting, editability, and validation requirements.

### `05_Speaker_Notes.md`

Provides teacher-facing guidance synchronized with the lesson sequence and storyboard. It includes only information that helps the teacher explain, question, respond, pace, differentiate, or transition effectively.

### `06_Image_Directions.md`

Documents every required visual, its instructional purpose, exact content direction, style and composition expectations, cultural and historical accuracy requirements, accessibility considerations, and intended use.

### `07_ELD_Supports.md`

Records lesson-specific language demands and aligned supports. It differentiates universal access strategies, supports for developing multilingual learners, and appropriate extensions.

### `08_Assessment.md`

Defines formative and summative evidence of learning, success criteria, response expectations, alignment to lesson objectives, feedback guidance, and any required curriculum assessment or homework.

### Final Slide Deck

Stores the editable, classroom-ready presentation produced from the approved storyboard and build prompt. The file format and naming convention should identify the lesson and distinguish working, reviewed, and approved versions.

### Revision Notes

Record quality-assurance findings, teacher decisions, classroom feedback, changes made after instruction, and reusable insights. Revision notes preserve the rationale for changes and provide evidence for future system improvement.

Additional source files or generated artifacts may be included when needed, but their authority, purpose, and relationship to the standard package should be documented in the lesson README.

## AI Responsibilities

### ChatGPT

ChatGPT is the instructional designer. It interprets provided curriculum materials, identifies instructional requirements, designs the lesson flow, drafts student-facing content, writes speaker notes, proposes ELD supports, creates checks for understanding, defines visual directions, prepares Chalkie build instructions, and reviews outputs for fidelity and instructional quality.

ChatGPT must distinguish source-grounded content from recommendations, identify uncertainty, and avoid inventing quotations, references, standards, or curriculum directions. It may improve clarity, pacing, engagement, accessibility, and differentiation without silently rewriting required curriculum.

### Codex

Codex is the project engineer and repository steward. It creates and organizes files, applies approved updates, preserves existing work, maintains naming and folder conventions, verifies package completeness, manages version-control operations when requested, and supports future automation.

Codex does not independently author curriculum content unless explicitly instructed. It must scope changes to the requested files, protect prior lesson packages, and keep repository artifacts internally consistent.

### Chalkie

Chalkie is the presentation renderer. It converts the approved storyboard and build prompt into an editable, visually coherent slide deck, follows image and design directions, and places speaker notes where supported.

Chalkie does not act as the primary instructional designer. It may not independently change objectives, sequence, required activities, texts, assessments, or homework, and it must not invent missing curriculum content.

### Teacher

The teacher is the final instructional authority. The teacher provides or confirms source materials, resolves ambiguity, approves instructional choices, reviews the lesson package, tests the deck, makes classroom-specific adjustments, and determines when the lesson is ready to use.

After instruction, the teacher supplies evidence about pacing, student understanding, successful supports, weak points, and needed revisions. Teacher approval is required before a generated lesson is treated as classroom-ready.

## Future Modules

Future modules are architectural extension points. Their detailed requirements, dependencies, privacy constraints, and delivery milestones will be defined through separate design decisions before implementation.

### Google Slides Integration

_[Placeholder for direct presentation creation, synchronization, editing, export, and review workflows.]_

### Browser Extension

_[Placeholder for in-context curriculum capture, lesson access, workflow actions, and classroom-tool integration.]_

### Image Generation

_[Placeholder for governed visual generation, provenance, rights management, accessibility, consistency, and approval.]_

### Curriculum Search

_[Placeholder for indexed source discovery, metadata, permissions, retrieval, citation, and cross-lesson search.]_

### TeacherOS Web App

_[Placeholder for the product interface, workspace model, lesson dashboard, review experience, collaboration, and administration.]_

### AI Agents

_[Placeholder for specialized agents, orchestration, handoffs, shared context, human approval boundaries, monitoring, and auditability.]_

## Version Roadmap

### Version 1 — Structured Repository Workflow

Version 1 establishes TeacherOS as a reliable, file-based instructional-design system for CKLA Grade 8. It standardizes the repository structure, lesson package, role boundaries, fidelity workflow, storyboard requirements, Chalkie handoff, quality checks, and permanent storage model. Human review remains explicit at critical decisions and final approval.

### Version 2 — Assisted Production and Integrations

Version 2 introduces governed automation around repeated production tasks. Priorities include stronger source intake, curriculum search, validation assistance, visual-asset workflows, presentation integration, structured revision tracking, and easier movement between lesson artifacts. Automation must preserve the approval gates and traceability established in Version 1.

### Version 3 — TeacherOS Product Platform

Version 3 evolves the repository workflow into a multi-user TeacherOS application. The target architecture includes managed curriculum libraries, role-aware workspaces, orchestrated AI agents, collaborative review, reusable design-system components, analytics from classroom feedback, and integrations with presentation and instructional tools. The platform should support additional curricula and organizations without weakening fidelity, privacy, auditability, or teacher control.
# Presentation-design stage

After instructional design, `PresentationDesigner` produces `04_presentation_design.json` as a Pydantic structured output through the shared Responses API client. Its schema deliberately separates student projection, speaker notes, semantic layout, visual asset planning, interaction, sources, and fidelity. Exact typography and color decisions live in the deterministic `config/presentation_theme.json` rather than model output.

`LessonAssembler` remains a compatibility boundary: it converts presentation slides to the existing renderer-ready slide records for older consumers. Day-divider slides contribute zero instructional minutes, preventing overview timing from being counted twice. Presentation-quality issues are warnings unless core package fidelity or structure is invalid.

The Google Slides renderer now also accepts `PresentationDesignOutput` directly. New CLI rendering prefers the rich stage file, while the legacy `Lesson` renderer remains available. A fixed dispatcher maps every semantic layout to theme-driven geometry; student content is sanitized and bounded before visible requests are built, and rich teacher fields plus sources are inserted into editable speaker notes. Missing visuals become native placeholders with structured warnings. Local files are detected but are never uploaded, extracted, or downloaded automatically; a future asset-publication service can supply approved Google-accessible URLs.
