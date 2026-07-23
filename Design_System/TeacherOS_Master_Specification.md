# TeacherOS Master Specification

## 1. Purpose

TeacherOS is a reusable instructional design system that transforms curriculum source materials into complete, classroom-ready lesson packages.

TeacherOS does not replace the curriculum. It interprets, organizes, and presents the curriculum while preserving its required objectives, texts, activities, sequence, assessments, and instructional intent.

Its first use case is CKLA Grade 8 lesson development, with an external presentation renderer used to build the final deck.

## 2. Core Workflow

TeacherOS follows this workflow:

1. Collect the lesson’s source materials.
2. Analyze the Teacher Guide, Student Reader, Activity Book, and supporting resources.
3. Identify all required objectives, activities, texts, questions, assessments, materials, and homework.
4. Create a curriculum-fidelity checklist.
5. Design the lesson’s instructional sequence.
6. Create a detailed slide storyboard.
7. Write teacher-facing speaker notes.
8. Add ELD supports and differentiation.
9. Define visual and image directions.
10. Produce a precise Presentation Renderer Prompt.
11. Review the presentation renderer’s output against the storyboard and fidelity checklist.
12. Save the final deck and lesson package permanently.

## 3. Division of Responsibilities

### ChatGPT
ChatGPT acts as the instructional designer.

ChatGPT is responsible for:

- interpreting curriculum materials
- designing instruction
- determining lesson flow
- writing slide content
- writing teacher notes
- creating ELD supports
- creating checks for understanding
- preserving curriculum fidelity
- reviewing presentation-renderer output

### Codex
Codex acts as the project engineer.

Codex is responsible for:

- creating and organizing files
- updating lesson files
- preserving existing work
- maintaining consistent folder structures
- committing project changes
- supporting future automation

Codex must not invent curriculum content unless explicitly instructed.

### Presentation Renderer
The external presentation tool acts as the presentation renderer.

The presentation renderer is responsible for:

- turning the storyboard into slides
- applying visual design
- creating editable presentation layouts
- following image and design directions
- placing teacher notes where supported

The presentation renderer must not independently change lesson objectives, sequence, required activities, texts, or assessments.

### Teacher
The teacher acts as the final decision-maker.

The teacher is responsible for:

- reviewing the lesson
- approving instructional choices
- testing the deck
- making classroom-specific adjustments
- providing feedback for future improvement

## 4. Curriculum Fidelity Rules

Every lesson must:

- preserve the curriculum’s stated objectives
- include all required lesson components
- preserve required texts and activity pages
- maintain the intended sequence unless a change is explicitly justified
- distinguish required content from optional enrichment
- preserve assigned homework
- avoid inventing quotations, page references, standards, or curriculum directions
- identify any uncertainty rather than guessing
- include a fidelity checklist before the renderer prompt is finalized

TeacherOS may improve clarity, pacing, engagement, accessibility, and differentiation, but it must not silently rewrite the curriculum.

## 5. Instructional Design Principles

Every lesson should:

- begin with a clear purpose
- activate relevant prior knowledge
- make the learning objective understandable to students
- introduce vocabulary in context
- divide complex reading into manageable sections
- include purposeful student interaction
- require students to think, speak, read, or write regularly
- use checks for understanding throughout the lesson
- include opportunities to cite or discuss evidence
- end with a meaningful assessment or reflection
- use transitions that make the lesson feel coherent

Slides should support instruction, not replace the teacher.

## 6. Slide Design Rules

Each slide should have one primary instructional purpose.

Student-facing slides should:

- use concise language
- avoid dense paragraphs
- use readable font sizes
- include only the information students need at that moment
- use consistent layouts and terminology
- make directions visually clear
- include discussion or writing time when applicable
- avoid unnecessary decoration

Teacher explanations, anticipated responses, scaffolds, pacing guidance, and follow-up questions belong in speaker notes rather than on the slide.

A slide may contain more text when students must directly read or analyze that text, but the amount should still remain manageable.

## 7. Required Slide Storyboard Fields

Every slide entry in the storyboard should include:

- slide number
- slide title
- instructional purpose
- student-visible content
- teacher actions
- student actions
- speaker notes
- ELD supports
- check for understanding
- visual direction
- estimated timing
- transition to the next slide

Fields that do not apply may be marked “Not applicable,” but they should not be silently omitted.

## 8. Speaker Notes Standards

Speaker notes should provide usable teaching guidance rather than generic commentary.

They may include:

- exact questions to ask
- concise explanations
- anticipated student responses
- likely misconceptions
- follow-up prompts
- pacing guidance
- differentiation
- pronunciation support
- sensitive-content guidance
- transitions
- reminders about materials or activity pages

Speaker notes should not read like a scripted lecture unless exact wording is pedagogically useful.

## 9. ELD and Accessibility Standards

Every lesson should include appropriate language supports without reducing intellectual rigor.

Possible supports include:

- student-friendly definitions
- visuals and gestures
- sentence frames
- word banks
- structured partner talk
- rehearsal time before whole-class sharing
- chunked directions
- modeled responses
- cognates when useful
- pronunciation guidance
- multiple ways to demonstrate understanding

Supports should be targeted to the actual language demands of the lesson.

TeacherOS should distinguish between:

- supports appropriate for all learners
- supports for developing multilingual learners
- extensions for advanced learners

## 10. Visual and Image Standards

Visuals must serve an instructional purpose.

Useful purposes include:

- establishing setting
- clarifying vocabulary
- supporting comprehension
- illustrating relationships
- organizing information
- representing sequence
- providing cultural or historical context
- supporting analysis

Images should be:

- age-appropriate for middle school
- respectful and culturally accurate
- visually consistent
- free from stereotypes
- relevant to the lesson
- uncluttered
- suitable for a 16:9 classroom presentation

TeacherOS should specify exact visual direction rather than requesting a generic “relevant image.”

## 11. Presentation Renderer Build Rules

The Presentation Renderer Prompt must:

- provide the exact slide sequence
- distinguish visible slide text from speaker notes
- include design requirements
- include visual directions
- preserve lesson timing and instructional flow
- prohibit the invention of curriculum content
- prohibit combining or deleting required activities without permission
- request editable slides
- request consistent formatting
- instruct the presentation renderer to keep student-facing text concise
- require a final slide-count and content check

The presentation renderer should function as a builder, not as the primary instructional designer.

## 12. Quality Assurance

Before a lesson is considered complete, confirm:

- all source materials were reviewed
- all required lesson components are represented
- objectives match the curriculum
- slide order supports the lesson sequence
- speaker notes are usable
- ELD supports match the lesson demands
- visuals are appropriate
- checks for understanding are included
- assessment matches the objective
- homework is accurate
- the presentation renderer did not invent or omit required content
- the final presentation is readable and classroom-ready

## 13. Permanent Lesson Storage

Every completed lesson remains permanently stored in its own folder.

A new lesson must never overwrite a previous lesson.

Each lesson folder should ultimately contain:

- lesson blueprint
- curriculum fidelity checklist
- slide storyboard
- Presentation Renderer Prompt
- speaker notes
- image directions
- ELD supports
- assessment materials
- final slide deck
- revision notes

## 14. Continuous Improvement

TeacherOS should improve through classroom use.

After each lesson, the teacher may record:

- what worked
- where students struggled
- timing problems
- successful discussion questions
- useful ELD supports
- slides that should be revised
- presentation-renderer errors
- reusable routines or visuals

Successful patterns should be moved into the shared Design_System or Templates folders for future reuse.

## 15. Non-Negotiable Principles

1. Curriculum fidelity comes before visual novelty.
2. Instructional purpose comes before decoration.
3. Slides support teaching; they do not replace teaching.
4. Student-facing content stays clear and manageable.
5. Teacher guidance belongs in speaker notes.
6. ELD supports preserve rigor.
7. Required content is never silently removed.
8. Uncertainty is identified rather than guessed.
9. Every lesson is saved permanently.
10. The system improves through evidence and classroom feedback.
