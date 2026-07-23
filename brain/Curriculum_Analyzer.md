# Curriculum Analyzer

## Purpose

The Curriculum Analyzer transforms source-grounded curriculum components into a clear instructional analysis. It receives the partially populated Structured Lesson Model produced by the Curriculum Reader and explains the instructional meaning, relationships, priorities, demands, and dependencies represented by the source.

The module identifies what the lesson is intended to teach, what students must understand or produce, which components are required, how lesson components relate to one another, where students may need additional support, and what evidence will demonstrate learning. It prepares a dependable analysis for the Instruction Designer without creating slides or redesigning the instructional sequence.

## Responsibilities

The Curriculum Analyzer is responsible for:

- interpreting source-provided objectives and standards;
- identifying the lesson’s central learning goal and supporting learning goals;
- analyzing prerequisite knowledge and dependencies;
- identifying required texts, tasks, materials, and assessments;
- determining the instructional role of each activity without changing it;
- distinguishing essential, supporting, optional, and unclear components cautiously;
- analyzing pacing, cognitive demand, and transitions;
- identifying likely misconceptions and barriers supported by available evidence;
- identifying supports already provided by the curriculum;
- identifying points where later modules may consider additional support;
- connecting standards, objectives, activities, texts, and assessments;
- evaluating instructional coherence;
- preserving source traceability for major conclusions;
- assigning analytical confidence;
- recording uncertainty, missing evidence, and source conflicts;
- enriching the appropriate sections of the Structured Lesson Model for downstream use.

Analysis must distinguish direct curriculum requirements from interpretation. It may explain relationships that are implicit in the source, but it must label those relationships according to their evidence and confidence.

## Non-Responsibilities

The Curriculum Analyzer must not:

- invent missing curriculum content;
- rewrite curriculum objectives without clearly labeling the result as an interpretation;
- remove, combine, reorder, or replace required activities;
- create a new instructional sequence;
- write teacher scripts;
- add final ELD or accessibility supports;
- create student-facing or teacher-facing slide content;
- generate or select images;
- produce presentation-renderer build instructions;
- silently resolve conflicting sources;
- create replacement assessments for gaps it identifies.

The Analyzer may identify a need, inconsistency, or opportunity for a downstream module. It must not fulfill that need by prematurely designing the lesson.

## Inputs

The Curriculum Analyzer requires:

- **Partially populated Structured Lesson Model:** The source-grounded lesson representation produced by the Curriculum Reader.
- **Source inventory:** The registered sources, classifications, metadata, readability, and availability statuses.
- **Ordered activity sequence:** Curriculum activities preserved in source order, including nested relationships.
- **Source-reference map:** Provenance connecting extracted content to files, pages, headings, labels, and sequence positions.
- **Confidence report:** Extraction-confidence levels and reasons associated with sources and extracted items.
- **Missing-materials report:** Expected or referenced sources that are unavailable, incomplete, or unreadable.
- **Unresolved-issues list:** Extraction ambiguities, conflicts, incomplete boundaries, and questions requiring review.
- **TeacherOS Instructional Design Principles:** The permanent principles governing the interpretation of instructional quality and downstream design needs.

Inputs must remain distinguishable by origin and authority. The Analyzer must not treat an inferred extraction as equivalent to explicit source content.

## Input Validation

Before analysis begins, the Curriculum Analyzer verifies that:

- the requested lesson is identifiable;
- all processed source materials are registered;
- activities are represented in source order;
- objectives are present or explicitly marked absent;
- assessments are present or explicitly marked absent;
- low-confidence and unresolved extractions are visible;
- critical missing materials are reported;
- lesson boundaries are sufficiently reliable for analysis;
- source references remain attached to major extracted components.

Validation should distinguish incomplete information that can be analyzed cautiously from deficiencies that make analysis unsafe. If the input is insufficient, the module must return a blocked-analysis report rather than guess. That report must identify the blocking condition, affected lesson components, available trustworthy information, and the source or authorized decision needed to proceed.

## Central Learning Goal

The central learning goal expresses the primary learning the lesson is organized to produce. The Analyzer identifies it by examining the stated objectives, required texts and tasks, instructional emphasis, culminating performance, and assessment evidence.

The analysis defines:

- **Primary learning objective:** The objective that best represents the lesson’s dominant intended outcome.
- **Supporting objectives:** Additional objectives that enable, extend, or provide necessary components of the primary objective.
- **Curriculum-provided language demands:** Explicit language objectives and the speaking, listening, reading, or writing expectations already present in the source.
- **Essential question:** The source-provided organizing question, when present, and its relationship to the objectives.
- **Enduring understanding:** A source-supported transferable understanding, or a clearly labeled interpretation when the curriculum implies one.
- **Expected student product or performance:** The observable work, response, discussion, reading behavior, or performance required of students.
- **Evidence of mastery:** The qualities or outcomes indicating that students have met the central goal.

The Analyzer must not collapse multiple unrelated objectives into an artificially unified goal. Conflicting objectives, objectives broader than the available lesson, and objectives unsupported by activities or assessment must be flagged with evidence and confidence.

## Standards Analysis

Standards analysis connects explicitly listed standards to the lesson’s objectives, activities, texts, and assessments. For each standard, the Analyzer records the source reference, the stated or interpreted relationship to the lesson, and the evidence supporting that relationship.

The analysis must:

- distinguish standards explicitly listed by the curriculum from inferred alignment;
- identify which objectives support each standard;
- identify standards that lesson activities do not appear to address;
- flag activities or assessments that do not clearly support a stated standard;
- preserve the wording and source references of explicitly listed standards;
- assign confidence to inferred relationships.

An inferred alignment may be useful for review, but it must never be presented as publisher-provided or authoritative curriculum metadata.

## Knowledge and Skill Analysis

The Curriculum Analyzer identifies the demands students must meet to participate successfully in the lesson:

- **Conceptual knowledge:** Ideas, relationships, principles, themes, and meanings students must understand.
- **Procedural knowledge:** Processes, routines, strategies, or sequences students must know how to perform.
- **Skills:** Observable actions such as identifying, explaining, interpreting, comparing, analyzing, evaluating, applying, discussing, or writing.
- **Academic vocabulary:** Cross-disciplinary language needed to understand directions, reason, discuss, or produce the required response.
- **Background knowledge:** Content or contextual knowledge assumed by the source.
- **Prior-lesson dependencies:** Earlier texts, concepts, products, vocabulary, or routines required by the current lesson.
- **Literacy demands:** Reading, writing, speaking, and listening required by the lesson.

The analysis must distinguish content knowledge from procedural knowledge and identify where they interact. Assumed knowledge must not be represented as verified student knowledge; it is a dependency or potential barrier for later design consideration.

## Activity Analysis

Every curriculum activity must receive an analysis record without being changed. Each record identifies:

- **Instructional purpose:** The role the activity plays, using source language when stated and labeled interpretation when inferred.
- **Objective supported:** The objective or objectives the activity advances.
- **Student thinking required:** The cognitive work students are expected to perform.
- **Teacher role:** The source-grounded facilitation, modeling, explanation, questioning, or monitoring function.
- **Student role:** The source-grounded participation, reading, discussion, practice, or production expected.
- **Grouping structure:** The stated whole-class, group, partner, or independent organization.
- **Cognitive demand:** The principal types and progression of thinking required.
- **Expected evidence of learning:** Observable student responses or products that could demonstrate understanding.
- **Required materials:** Texts, pages, tools, handouts, or technology needed for the activity.
- **Dependency on earlier activities:** Knowledge, modeling, practice, text, or output required from a prior activity.
- **Source reference:** File, page, heading, label, and source-order position.
- **Essentiality:** Required, supporting, optional, or unclear, with supporting evidence.

The Analyzer must preserve activity order and identity. It may flag a weak or unclear role, but it cannot remove or alter the activity.

## Essentiality Classification

### Required

An activity or component is **Required** when the source explicitly requires it to meet the curriculum objective, complete an assigned text or task, or produce the required assessment. The classification must cite the evidence establishing that requirement.

### Supporting

An activity or component is **Supporting** when it strengthens understanding, establishes necessary knowledge or language, models a process, or prepares students for a required component. Supporting does not mean disposable; the classification describes instructional role rather than permission to remove it.

### Optional

An activity or component is **Optional** only when the curriculum explicitly identifies it as optional, extension, enrichment, challenge, choice, or time permitting. The source label and reference must accompany the classification.

### Unclear

An activity or component is **Unclear** when the available source does not provide enough evidence to classify it confidently or when source evidence conflicts.

TeacherOS must not label an activity optional because it appears less important, repetitive, difficult to fit, or weakly connected. When evidence does not support a confident classification, the correct status is unclear.

## Assessment Alignment

The Curriculum Analyzer evaluates how assessment evidence relates to the lesson’s objectives and instructional demands. For each assessment or check, it identifies:

- the objective or objectives measured;
- the required cognitive demand;
- the student response, product, or performance expected;
- the success criteria or qualities of an adequate response;
- whether answer guidance, a rubric, or suggested response is available;
- where the evidence appears in the lesson;
- whether the assessment is required, formative, optional, or unclear;
- the relevant source references and confidence.

The analysis also determines whether the lesson includes sufficient formative checks to make student understanding visible before final performance, whether the final task provides credible evidence of mastery, and whether any objective lacks assessment evidence.

Gaps between objectives and assessment must be reported. The Analyzer may describe the nature and consequence of a gap, but it must not create a replacement assessment.

## Vocabulary Analysis

Vocabulary analysis identifies the language students need for comprehension and participation. It distinguishes:

- essential words required to understand lesson concepts, texts, directions, or tasks;
- academic language required for discussion, reasoning, reading, or writing;
- content-specific terminology;
- words explicitly taught by the curriculum;
- words encountered in a text but not explicitly taught;
- source-provided or clearly evident morphology opportunities;
- likely pronunciation or meaning challenges supported by the word, source, or task;
- vocabulary that may require later instructional support.

Curriculum-provided vocabulary, definitions, pronunciation, morphology, and support must remain separate from TeacherOS recommendations. A recommendation identifies a downstream opportunity and may not be represented as source content.

## Text and Reading Analysis

For each required or referenced text and excerpt, the Curriculum Analyzer identifies:

- its role in the lesson;
- the reading purpose;
- the expected reading mode;
- complexity indicators provided by the source or evident from the assigned task;
- knowledge demands;
- vocabulary, syntax, discourse, and other language demands;
- key sections relevant to the objective;
- evidence students are expected to locate, interpret, or use;
- likely comprehension barriers supported by available evidence;
- its connection to the central and supporting learning goals.

The analysis must retain source references and availability status. It should quote only the minimum source language necessary for verification and must not reproduce unnecessary copyrighted text.

## Cognitive Demand

The Curriculum Analyzer develops a profile of the thinking required across the lesson. Relevant demand types may include:

- recall;
- explanation;
- interpretation;
- comparison;
- analysis;
- evaluation;
- synthesis;
- application;
- written production.

The profile records where each demand occurs, what students must do, which objective it supports, and what preparation precedes it. It identifies abrupt shifts in demand, such as movement from exposure directly to independent analysis without visible preparation.

Cognitive-demand analysis is descriptive and diagnostic. It must not automatically lower rigor, simplify the objective, or revise the activity. Concerns are passed to the Instruction Designer for explicit consideration.

## Pacing Analysis

Pacing analysis examines:

- the stated total lesson duration;
- source-provided timing for individual activities;
- the sum of planned activity time;
- visible or implied transitions;
- activities with high reading, writing, discussion, or procedural load;
- conflicts among total time, component time, and expected output;
- implications for multi-day lessons;
- activities whose completion is likely to require teacher judgment.

The Analyzer records source timing separately from analytical concern. It does not revise durations, remove activities, or create a new schedule. It reports pacing conflicts and uncertainties for the Instruction Designer and teacher to resolve.

## Student Barrier Analysis

The Curriculum Analyzer identifies potential barriers related to:

- missing or assumed background knowledge;
- essential vocabulary;
- text complexity;
- unclear or densely structured directions;
- heavy writing demands;
- extended teacher talk;
- complex multi-step tasks;
- limited preparation before discussion;
- cultural or contextual knowledge;
- required materials or technology.

Every barrier must be labeled by evidentiary basis:

- **Source-explicit:** The curriculum directly identifies the barrier or need.
- **Strongly supported inference:** Multiple lesson features or clear task demands support the conclusion.
- **Tentative concern:** Limited evidence suggests a possibility that requires human review.

Barrier analysis identifies where support may be needed; it does not create the final support or lower the academic expectation.

## Misconception Analysis

The Curriculum Analyzer identifies likely misunderstandings related to:

- lesson concepts;
- vocabulary meanings or relationships;
- text interpretation;
- task directions;
- selection and use of evidence;
- assessment expectations.

A misconception should be based on source-provided guidance, a direct conflict embedded in the content, a known ambiguity in the task, or a cautiously labeled inference from the required thinking. The Analyzer must not invent highly specific student errors without evidence.

Each misconception record should identify its basis, affected lesson component, likely consequence, confidence, and the point at which a later module or teacher may monitor for it.

## Existing Supports Analysis

The Curriculum Analyzer inventories supports explicitly included in the curriculum, including:

- modeling;
- guided practice;
- sentence frames;
- vocabulary support;
- chunking;
- partner work;
- visuals;
- scaffolds;
- accommodations;
- enrichment;
- teacher questions or other source-provided guidance.

For each support, the analysis identifies its intended demand or learner need when stated, placement in the lesson, relationship to an activity or objective, and source reference. TeacherOS-proposed supports must remain in a separate downstream-opportunity category and must never be labeled as curriculum provided.

## Instructional Coherence

Instructional-coherence analysis evaluates whether:

- objectives, activities, and assessments align;
- lesson phases build logically in the provided order;
- students receive adequate exposure, modeling, or guided work before independent performance;
- required texts support the central learning goal;
- checks for understanding occur at useful decision points;
- closure reflects the central learning goal and expected evidence;
- prerequisite relationships are honored;
- the lesson’s cognitive progression is understandable.

The Analyzer reports strong connections, weak connections, missing links, and source conflicts. It may explain why a relationship appears incoherent, but it must preserve the source sequence and defer redesign to the Instruction Designer.

## Curriculum Fidelity Map

Every major analytical conclusion must retain:

- **Source file:** The registered file containing the relevant evidence.
- **Page number:** The printed or digital page reference when available.
- **Section heading:** The nearest stable source locator.
- **Source requirement:** The explicit content, direction, expectation, or structural evidence supplied by the curriculum.
- **Analytical interpretation:** The instructional meaning or relationship identified by the Analyzer.
- **Confidence level:** High, medium, low, or unresolved analytical confidence.
- **Fidelity status:** The relationship between the conclusion and its source evidence.

Fidelity statuses are:

- **Directly supported:** The conclusion is explicitly stated by the source.
- **Supported interpretation:** The conclusion is not stated verbatim but is well supported by identifiable source evidence.
- **Uncertain:** Evidence is limited, ambiguous, or dependent on information not currently available.
- **Source conflict:** Two or more authoritative source elements support incompatible conclusions.
- **Missing evidence:** The expected evidence is absent or unavailable.

The fidelity map must preserve distinctions among source content, analysis, and future design recommendations.

## Analysis Confidence

Analytical confidence describes the strength of an instructional conclusion. It is separate from extraction confidence: accurately extracted content may still support multiple interpretations, while a straightforward analytical relationship may depend on a low-confidence extraction.

- **High confidence:** The conclusion follows directly from clear, consistent objectives, activities, texts, assessments, or explicit source guidance.
- **Medium confidence:** The conclusion is supported by credible evidence but depends on a limited interpretation, incomplete connection, or minor source ambiguity.
- **Low confidence:** The conclusion is plausible but depends on sparse, indirect, conflicting, or low-confidence evidence and requires human review.
- **Unresolved:** Available evidence cannot support a responsible conclusion or competing interpretations cannot be reconciled.

Every medium-, low-, or unresolved conclusion should include a concise explanation and the information or review needed to strengthen it.

## Unresolved Issues

The Curriculum Analyzer records unresolved issues such as:

- conflicting objectives;
- unclear activity purpose;
- missing answer keys or answer guidance;
- missing referenced texts or activity materials;
- unclear assessment alignment;
- incompatible or incomplete timing;
- source-version conflicts;
- uncertain required, supporting, or optional status;
- insufficient information for safe instructional analysis.

Each issue record should identify the affected elements, available evidence, analytical impact, severity, confidence, and the source or authorized decision needed for resolution. Issues must remain visible in downstream handoffs until they are explicitly resolved.

## Internal Workflow

The Curriculum Analyzer follows this observable workflow:

1. Validate the Curriculum Reader output.
2. Identify the lesson’s central learning goal.
3. Map standards, objectives, activities, texts, and assessments.
4. Analyze knowledge, skills, language, and cognitive demand.
5. Classify lesson components by instructional role and essentiality.
6. Analyze assessment alignment.
7. Identify barriers, misconceptions, dependencies, and existing supports.
8. Evaluate instructional coherence and pacing.
9. Attach traceability and confidence to all major conclusions.
10. Populate the curriculum-analysis sections of the Structured Lesson Model.
11. Pass the analysis to the Instruction Designer.

Each stage produces reviewable artifacts or statuses. This workflow describes observable analysis and output behavior only and does not disclose or require private reasoning.

## Output Contract

The Curriculum Analyzer outputs:

- **Central learning goal:** The primary instructional outcome with evidence, confidence, and source relationship.
- **Supporting learning goals:** Enabling or complementary goals and their relationship to the central goal.
- **Standards-objective map:** Explicit and inferred alignments, supporting evidence, and identified gaps.
- **Knowledge and skill map:** Concepts, procedures, skills, vocabulary, background knowledge, and literacy demands.
- **Activity-purpose map:** The role, objective, demand, evidence, dependencies, and source reference for every activity.
- **Essentiality classification:** Required, supporting, optional, or unclear status with evidence.
- **Text and reading analysis:** Purpose, mode, demand, evidence needs, barriers, and objective connections.
- **Vocabulary analysis:** Curriculum-provided terms, participation language, challenge areas, and downstream support opportunities.
- **Assessment-alignment map:** Connections among objectives, evidence, demand, success criteria, and available guidance.
- **Cognitive-demand profile:** The types, sequence, and transitions of student thinking across the lesson.
- **Pacing analysis:** Source timing, totals, load, conflicts, and decision points.
- **Barrier analysis:** Evidence-based barriers with classification and confidence.
- **Misconception analysis:** Supported likely misunderstandings and monitoring points.
- **Existing-supports inventory:** Curriculum-provided supports and their placement, purpose, and source.
- **Instructional-coherence report:** Aligned, weak, missing, and conflicting relationships.
- **Fidelity and traceability map:** Source evidence, analytical interpretation, confidence, and fidelity status.
- **Confidence report:** Analytical-confidence decisions and their relationship to extraction confidence.
- **Unresolved-issues list:** Open conflicts, missing evidence, and questions requiring review.
- **Enriched Structured Lesson Model:** The source-grounded model with curriculum-analysis sections populated for downstream design.

The output must be structured, consistent, machine-readable, human-auditable, and usable by the Instruction Designer. Direct source content, analytical conclusions, and downstream opportunities must remain distinguishable.

## Validation Rules

Before handoff, the Curriculum Analyzer must verify that:

- every major objective has been analyzed;
- every activity has an identified purpose or is marked unclear;
- every required assessment is linked to an objective or explicitly flagged;
- required texts are connected to lesson goals or the missing connection is reported;
- every essentiality classification includes evidence;
- inferred conclusions are clearly labeled;
- source references are retained for major conclusions;
- the analysis contains no instructional redesign;
- unresolved issues remain visible;
- no unsupported curriculum claim is presented as fact;
- analytical confidence is distinct from extraction confidence;
- curriculum-provided supports remain distinct from TeacherOS opportunities.

Validation findings must identify the affected record, severity, reason, and required review. A structurally complete analysis may contain unresolved issues, but it must not be represented as ready when a blocking condition remains.

## Failure Conditions

Analysis is blocked when:

- the Curriculum Reader output is incomplete beyond safe analysis;
- the central lesson goal cannot be identified responsibly;
- critical source conflicts remain unresolved;
- a required text or assessment is unavailable and its absence prevents meaningful analysis;
- activity order is unreliable;
- lesson boundaries are unsafe;
- analysis would depend on fabricated assumptions.

Failure must produce a blocked-analysis report. The report must identify the blocking conditions, affected model sections, trustworthy partial findings, unavailable or conflicting evidence, and the material or authorized decision required to continue. It must not contain fabricated conclusions presented as a substitute for missing analysis.

## Success Criteria

The Curriculum Analyzer succeeds when:

- the lesson’s instructional purpose is clear;
- objectives, activities, texts, and assessments are mapped;
- essential components are distinguished cautiously and with evidence;
- student knowledge, skills, language, and cognitive demands are visible;
- likely barriers, misconceptions, dependencies, and existing supports are documented responsibly;
- curriculum fidelity and source traceability are preserved;
- uncertainty and conflicts are explicitly reported;
- no premature instructional redesign has occurred;
- the Instruction Designer receives a dependable, coherent, and auditable analysis.

Success does not require the source lesson to be perfectly aligned. It requires the Analyzer to represent strengths, gaps, conflicts, and uncertainty accurately enough for responsible downstream design.

## Version 1 Scope

Version 1 prioritizes:

- CKLA Grade 8;
- one lesson at a time;
- the teacher guide as the primary authority;
- optional student-reader and activity-book materials;
- human review of low-confidence and unresolved conclusions;
- analysis supporting lesson generation through a presentation renderer.

Version 1 should establish dependable goal identification, relationship mapping, essentiality classification, demand analysis, fidelity, and handoff before broader automation is introduced. Its focus on a curriculum and grade establishes an initial operating scope without authorizing lesson-specific assumptions.

## Future Enhancements

### Publisher-Specific Analysis Profiles

_[Placeholder for publisher-aware terminology, recurring structures, instructional patterns, and validation expectations.]_

### Cross-Lesson Prerequisite Mapping

_[Placeholder for tracing concepts, skills, texts, vocabulary, and student products across lesson boundaries.]_

### Unit-Level Coherence Analysis

_[Placeholder for analyzing progression, recurring questions, cumulative outcomes, pacing, and assessment across a unit.]_

### Standards Coverage Tracking

_[Placeholder for cumulative standards evidence, depth, recurrence, gaps, and explicit versus inferred alignment.]_

### Automated Text-Complexity Measures

_[Placeholder for combining quantitative, qualitative, task, knowledge, and reader considerations without reducing complexity to a single score.]_

### Learner-Data Integration

_[Placeholder for governed use of learner needs, performance evidence, privacy, permissions, and interpretation limits.]_

### Classroom-Time Calibration

_[Placeholder for using reviewed classroom evidence to improve pacing estimates while preserving source timing and teacher control.]_

### Curriculum-Version Comparison

_[Placeholder for detecting changes in objectives, activities, texts, assessments, pacing, and source authority across editions.]_

### Analysis Across Multiple Source Languages

_[Placeholder for aligned multilingual sources, translation confidence, language-specific demands, and cross-language traceability.]_
