# Slide Designer

## Purpose

The Slide Designer converts an approved, classroom-ready instructional design into a complete slide-by-slide presentation specification. It determines how the lesson should be visually communicated while preserving the learning goals, required curriculum content, instructional sequence, student tasks, assessment expectations, supports, and teacher guidance established upstream.

The module creates an authoritative plan that a downstream rendering engine can execute without making instructional decisions. It does not create Google Slides or render another presentation format directly.

## Responsibilities

The Slide Designer is responsible for:

- translating each relevant instructional phase into one or more purposeful slides;
- determining the complete slide sequence;
- assigning a functional slide type to every slide;
- defining one primary instructional objective for each slide;
- writing concise student-facing content;
- organizing teacher-facing guidance and speaker notes;
- specifying interactions and participation routines;
- creating precise image and visual directions;
- defining appropriate animation or staged-reveal behavior;
- allocating slide-level instructional time;
- creating conceptual and procedural transitions;
- maintaining consistent terminology, hierarchy, and presentation patterns;
- supporting readability, accessibility, and age appropriateness;
- preserving curriculum references and adaptation status;
- recording unresolved presentation dependencies;
- producing a complete specification for downstream rendering.

The Slide Designer must preserve the distinction between curriculum-original content, TeacherOS clarification, TeacherOS enhancement, teacher-authorized change, and unresolved decisions.

## Non-Responsibilities

The Slide Designer must not:

- change the central learning goal or success criteria;
- redesign the approved instructional sequence;
- remove, combine, replace, or reorder required activities without authorization;
- create new assessments or instructional supports to repair upstream gaps;
- invent curriculum claims, quotations, page references, or directions;
- make unresolved instructional decisions on behalf of the teacher;
- generate final images;
- build or render Google Slides;
- send incomplete instructional content directly to a presentation renderer;
- prioritize visual novelty over learning, clarity, fidelity, or accessibility;
- hide adaptations made by upstream modules.

When the lesson design is incomplete or unsafe to translate, the module reports the problem rather than compensating through presentation choices.

## Inputs

The Slide Designer requires:

- the enriched Structured Lesson Model produced by the Instruction Designer;
- the complete instructional sequence and lesson-phase map;
- the central learning goal, supporting objectives, and success criteria;
- teacher actions and student actions;
- teacher-language guidance;
- student tasks and expected evidence;
- discussion, vocabulary, and reading-instruction plans;
- ELD and accessibility supports;
- checks for understanding and assessment plan;
- misconception-response guidance;
- pacing and transition plans;
- materials and preparation requirements;
- differentiation guidance;
- curriculum adaptation log;
- fidelity and traceability records;
- unresolved-issues list;
- applicable visual-design standards and teacher preferences.

Each input must retain its origin, authority, approval state, and relationship to the lesson sequence.

## Input Validation

Before slide design begins, the module verifies that:

- the central learning goal is stable;
- the instructional sequence is complete and ordered;
- required curriculum components are present or visibly flagged;
- each phase has a clear instructional purpose;
- teacher and student actions are distinguishable;
- required texts, tasks, assessments, and materials are identified;
- pacing is sufficiently defined for slide allocation;
- adaptations are labeled and traceable;
- accessibility and ELD needs are available where required;
- critical unresolved issues are visible;
- the lesson design is approved or otherwise authorized for presentation specification.

If missing information would require the Slide Designer to make an instructional decision, the module must return a blocked-design report. Noncritical gaps may remain explicitly unresolved when they do not prevent a complete and safe specification.

## Slide Design Goals

The Slide Designer aims to:

- preserve the approved instructional intent;
- make the lesson sequence visible and easy to follow;
- focus student attention on the current learning task;
- keep student-facing language concise and usable;
- place detailed teacher guidance outside the student display;
- support meaningful reading, discussion, writing, and practice;
- reduce unnecessary cognitive load;
- provide clear visual and interaction directions;
- maintain accessibility and middle-school age appropriateness;
- make pacing and transitions practical;
- eliminate the need for downstream instructional interpretation;
- produce a complete, auditable rendering specification.

## Slide Architecture

A slide is the smallest presentation unit with one primary instructional purpose. One instructional phase may require multiple slides when students need progressive directions, readable text, staged modeling, separate discussion questions, or distinct checks for understanding. Multiple phases should not be compressed into one slide when doing so obscures purpose or overloads students.

Every slide specification must define its identity, instructional objective, visible content, teacher guidance, interaction, visual requirements, timing, transition, and curriculum references. Slides should also remain linked to the instructional phase and relevant lesson objectives from which they were derived.

The architecture must distinguish:

- **student display:** Information intended to be visible to students at that moment;
- **teacher support:** Notes and decisions intended only for the teacher;
- **rendering direction:** Layout, visual, interaction, and reveal instructions for the downstream engine;
- **traceability:** Source and adaptation records showing why the slide exists and what it represents.

## Slide Types

Slide types describe instructional function rather than fixed visual templates. A slide may have one primary type and, when necessary, a secondary function that does not compete with its main purpose.

- **Title:** Identifies the lesson and establishes an appropriate visual entry point.
- **Hook:** Creates purposeful curiosity, relevance, or a problem connected to the learning goal.
- **Objectives:** Communicates what students will learn and how success will be demonstrated.
- **Vocabulary:** Introduces, clarifies, or revisits essential language in context.
- **Background Knowledge:** Activates or builds knowledge required to access the lesson.
- **Reading:** Presents a reading purpose, selection reference, manageable excerpt when authorized, or evidence-gathering direction.
- **Modeling:** Makes a target process, strategy, or expert decision visible.
- **Guided Practice:** Supports students as they begin applying the target learning.
- **Discussion:** Presents a substantive question, preparation expectations, evidence requirements, and participation structure.
- **Partner Activity:** Defines a purposeful partner task, roles, timing, and accountability.
- **Independent Practice:** Directs students to demonstrate learning with reduced support.
- **Check for Understanding:** Elicits evidence that informs the teacher’s next instructional decision.
- **Assessment:** Presents or directs students to an aligned required or approved assessment task.
- **Reflection:** Prompts students to consolidate learning, examine reasoning, or recognize progress.
- **Exit Ticket:** Collects concise closing evidence aligned to the lesson objective.
- **Homework:** Communicates accurate assignment expectations, materials, and due conditions.

Additional types may be used when they have a distinct instructional function. Type selection must follow the approved lesson design rather than force content into a preferred presentation pattern.

## Visual Design Principles

### Minimal Cognitive Load

Each slide should display only the information students need for the current instructional moment. Unnecessary text, decoration, repeated directions, and competing elements should be removed.

### Visual Hierarchy

The relative importance and reading order of titles, directions, questions, evidence, and supporting details must be immediately clear. Position, scale, spacing, contrast, and grouping should communicate structure consistently.

### Readable Typography

Typography must be legible from a classroom viewing distance. Text size, line length, spacing, emphasis, and contrast must support fluent reading, with denser text reserved for situations in which students must directly read or analyze it.

### Instructional Visuals

Every image, diagram, organizer, or icon must serve a stated learning purpose. Visuals should clarify context, vocabulary, relationships, sequence, evidence, or analysis rather than decorate the slide.

### Consistency

Layouts, terminology, navigation signals, color meanings, activity labels, and interaction cues should follow stable patterns. Consistency should reduce orientation effort without making every slide visually identical.

### Accessibility

Design directions must consider contrast, color dependence, text size, visual complexity, reading order, meaningful descriptions, and alternatives for information communicated visually. Accessibility must be part of the initial specification, not a final cosmetic check.

### Age Appropriateness

Language, imagery, density, visual tone, and interaction patterns must be suitable for the intended students. Middle-school materials should be clear and inviting without appearing childish or sacrificing academic seriousness.

## Student-Facing Content

Student-facing content is the exact information intended to appear on the slide. It may include titles, learning goals, directions, questions, brief definitions, text references, authorized excerpts, task steps, response frames, timing cues, and success criteria.

Student-facing content must:

- use concise, direct, age-appropriate language;
- preserve academic accuracy and required curriculum wording where necessary;
- communicate one primary purpose;
- make actions and expected products explicit;
- distinguish directions from content to be analyzed;
- avoid teacher-only explanation, anticipated responses, and facilitation guidance;
- avoid unnecessary duplication of source texts;
- preserve required attribution and source constraints.

When a slide requires more text for direct reading or analysis, the specification must justify the density and protect readability.

## Teacher-Facing Notes

Teacher-facing notes provide the guidance needed to teach the slide effectively. They may include teacher actions, questions, concise explanations, anticipated responses, misconceptions, follow-up questions, ELD supports, differentiation, pacing, materials, grouping guidance, checks for understanding, and transition cues.

Notes must remain synchronized with the student-facing content and approved instructional design. They should be concise, scannable, natural, and adaptable rather than a continuous mandatory script. Required curriculum language and TeacherOS guidance must remain distinguishable.

## Image Direction

Every requested visual must have a precise direction that defines:

- the visual’s instructional purpose;
- the subject or information to depict;
- composition, focal point, and spatial relationships;
- preferred visual style and consistency requirements;
- age appropriateness and emotional intensity;
- cultural, historical, and representational considerations;
- restrictions on embedded text;
- accessibility description;
- placement and relative prominence;
- connection to the lesson objective, text, task, or source.

The Slide Designer specifies what a visual must communicate but does not generate the final asset. Generic requests for a relevant image are insufficient.

## Interaction Design

Interaction design describes what teachers and students do while a slide is displayed. Each interaction must define:

- the instructional purpose;
- participant actions;
- grouping structure;
- preparation or think time;
- response method;
- evidence expectations;
- accountability or participation routine;
- teacher monitoring guidance;
- completion signal or transition condition.

Interactions must be academically meaningful, accessible, feasible in the allotted time, and aligned with the lesson design. A slide should not imply interaction when students are only expected to watch or listen.

## Animation and Reveal Strategy

Animation and staged reveals should manage attention, sequence information, preserve question integrity, or support modeling. They must not be used solely for novelty.

The specification should define:

- which elements are initially visible;
- which elements appear later and in what order;
- the teacher or student action that triggers each reveal;
- the instructional reason for the sequence;
- the final state that must remain available for reference.

Answers, models, and follow-up guidance should not appear before students have had the intended opportunity to think. Motion should remain simple, consistent, and accessible, with a usable nonanimated state.

## Speaker Notes Strategy

Speaker notes are the primary location for teacher-only guidance that should not compete with student attention. The Slide Designer organizes notes in a predictable order so teachers can quickly locate the purpose, actions, language, expected evidence, supports, pacing, and transition.

Notes should include only guidance relevant to the current slide and should refer clearly to related materials or lesson phases. Repeated notes may reference an established routine when that is easier to use than duplicating extensive text, provided the reference is unambiguous.

The specification must identify any note that contains required curriculum language, teacher-authorized wording, or unresolved guidance. Rendering systems must preserve notes without converting them into visible slide text.

## Time Allocation

Every slide receives an estimated instructional duration derived from its lesson phase and expected interaction. Time allocation must account for reading, think time, student response, discussion, writing, materials, reveals, and transition—not only teacher presentation.

Slide-level estimates must reconcile with phase-level and total lesson pacing. When several slides support one continuous activity, the specification should distinguish display time from the activity’s total time. Pacing conflicts must remain visible and must not be resolved by silently removing required content.

## Transition Strategy

Transitions connect both ideas and classroom procedures. Each slide should state how it leads to the next instructional moment, including the reasoning students carry forward and any change in materials, grouping, location, or response mode.

Transitions should be concise and purposeful. They should minimize confusion, preserve momentum, and help students understand why the next task follows. A transition may appear as teacher-facing guidance, student-facing direction, or both, depending on classroom need.

## Slide Sequencing

The slide sequence must mirror the approved instructional sequence and preserve required curriculum order. The Slide Designer may distribute a phase across several slides, insert transparently labeled support slides, or use a return slide for reference, but it may not reorder lesson logic through presentation design.

Sequence decisions should ensure that:

- objectives and purpose appear before dependent work;
- necessary background and vocabulary precede use;
- directions appear before students begin a task;
- models precede guided or independent application when required;
- questions appear before answers or explanations;
- discussion preparation precedes public response;
- formative evidence appears before decisions that depend on it;
- assessment follows sufficient instruction and practice;
- reflection and closure return to the learning goal.

Every slide must have a stable number and remain linked to its phase. Insertions or deletions require renumbering and revalidation of notes, transitions, timing, and references.

## Curriculum Traceability

Every slide must preserve the evidence and design history that justify its content. The traceability record should include:

- instructional phase and objective;
- original curriculum requirement;
- source file;
- page number when available;
- section heading or source label;
- adaptation status;
- TeacherOS design decision;
- rationale;
- fidelity status;
- confidence level;
- related required text, activity, or assessment identifier.

Student-facing quotations, directions, questions, page references, and assessment content require direct source support. A slide derived from a TeacherOS enhancement must remain labeled as such and linked to the preserved curriculum goal it supports.

## Internal Workflow

The Slide Designer follows this observable workflow:

1. Receive the completed lesson design.
2. Determine the slide sequence from the approved instructional sequence.
3. Assign a functional slide type to every slide.
4. Determine each slide’s primary instructional objective.
5. Write concise student-facing content.
6. Write aligned teacher-facing notes.
7. Create precise image and visual directions.
8. Create interaction descriptions and reveal behavior.
9. Create transition guidance and reconcile timing.
10. Create and validate the complete slide specifications.

Each stage produces inspectable specifications or statuses. This workflow describes observable processing only and does not expose or require private reasoning.

## Output Contract

The Slide Designer outputs one complete specification for every slide. Each specification includes:

- **Slide number:** The stable ordered identifier.
- **Slide title:** The exact title or a deliberate indication that no visible title is required.
- **Slide type:** The primary functional classification.
- **Instructional objective:** The single main purpose and its connection to the lesson objective.
- **Student-facing content:** Exact visible text, directions, references, labels, and authorized excerpts.
- **Teacher-facing notes:** Actions, language, expected evidence, supports, misconceptions, pacing, and facilitation guidance.
- **Interaction:** Participants, grouping, preparation, response method, evidence, accountability, and monitoring.
- **Image direction:** Instructional purpose, subject, composition, style, accessibility, and source connection.
- **Animation or reveal plan:** Initial state, reveal order, trigger, purpose, and accessible final state.
- **Timing:** Estimated slide or activity duration and its relationship to phase pacing.
- **Transition:** Conceptual and procedural movement to the next slide or phase.
- **Curriculum references:** Source file, page, section, requirement, adaptation, fidelity, and confidence.

The complete output must also provide the total slide count, total estimated lesson time, unresolved-issues list, required asset inventory, and slide-to-phase map.

The output must be structured, consistent, machine-readable, human-auditable, and optimized for downstream rendering. A renderer must be able to distinguish exact content from guidance and must not need to infer instructional purpose, sequence, or teacher actions.

## Validation Rules

Before handoff, the Slide Designer verifies that:

- every slide has one primary instructional purpose;
- every slide maps to an approved lesson phase and objective;
- all required curriculum components appear in the specification or remain explicitly blocked;
- slide order preserves the instructional sequence;
- student-facing and teacher-facing content are separated;
- visible text is concise, accurate, and readable;
- directions state clear student actions and expected products;
- interactions match the approved lesson design;
- teacher notes provide usable guidance where needed;
- required ELD and accessibility supports are represented appropriately;
- images have specific instructional directions and accessibility descriptions;
- reveal plans do not expose answers prematurely;
- timing reconciles with phase and lesson pacing;
- transitions are complete and coherent;
- source references and adaptation labels remain intact;
- unresolved issues are visible;
- no final slide rendering or unauthorized instructional redesign has occurred.

Validation findings must identify the affected slide, severity, reason, and required resolution. A slide marked not applicable for a field must include enough context to show that the omission is deliberate.

## Failure Conditions

Slide design is blocked when:

- the instructional sequence is incomplete or unresolved;
- the central learning goal or required assessment is unstable;
- required curriculum components cannot be mapped to the lesson design;
- critical student or teacher content is missing;
- required source text or materials are unavailable;
- pacing cannot be represented without unauthorized omission;
- unresolved adaptations require teacher authorization;
- a complete specification would require the module to make new instructional decisions;
- source conflicts prevent accurate visible content or sequencing.

Failure must produce a blocked-design report identifying the affected phases and slides, trustworthy partial specifications, missing or conflicting information, downstream impact, and recommended human decision. The module must not create plausible-looking slides to conceal incomplete instructional design.

## Success Criteria

The Slide Designer succeeds when:

- the complete lesson is represented in a coherent slide sequence;
- every slide has a clear instructional purpose;
- required content, activities, texts, and assessments are preserved;
- student-facing content is concise and classroom-readable;
- teacher-facing guidance is complete and usable;
- interactions, visuals, timing, reveals, and transitions are explicit;
- accessibility and age appropriateness are built into the specification;
- curriculum traceability and adaptation status are preserved;
- unresolved issues are visible;
- a presentation renderer can build the entire presentation without making instructional decisions.

## Version 1 Scope

Version 1 targets:

- CKLA Grade 8;
- one lesson at a time;
- Google Slides as the intended presentation format;
- an external presentation tool as the downstream rendering system;
- middle-school classroom instruction.

Version 1 prioritizes complete, reliable slide specifications, consistent visual communication, accurate speaker notes, and transparent handoff over automated rendering or broad theme customization.

## Future Enhancements

### Adaptive Slide Layouts

_[Placeholder for content-aware layout selection, density management, responsive composition, and renderer constraints.]_

### Multiple Presentation Themes

_[Placeholder for governed visual themes that preserve hierarchy, readability, consistency, and curriculum identity.]_

### Accessibility Themes

_[Placeholder for configurable contrast, typography, motion, visual complexity, and alternative-display needs.]_

### Interactive Widgets

_[Placeholder for structured interactive elements, participation behavior, fallbacks, accessibility, and evidence capture.]_

### Embedded Assessments

_[Placeholder for assessment presentation, response collection, scoring boundaries, privacy, and alignment metadata.]_

### Live Polling

_[Placeholder for real-time response collection, participation visibility, teacher decisions, privacy, and offline alternatives.]_

### AI-Generated Diagrams

_[Placeholder for instructional purpose, source grounding, visual accuracy, review, accessibility, and revision.]_

### Multilingual Presentations

_[Placeholder for language variants, translation review, layout adaptation, source equivalence, and teacher control.]_
