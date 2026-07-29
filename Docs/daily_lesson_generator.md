# Daily Lesson Generator

The Daily Lesson Generator is an opt-in, one-action workspace for teachers who
need an immediately usable teaching plan and copyable slide prompts from one
pasted lesson. It runs beside the existing automated presentation pipeline and
does not feed PowerPoint, Gamma, Google Slides publishing, CanonicalLesson, or
production lesson generation.

## Workflow

1. Open **Daily Lesson Generator**.
2. Enter grade, unit, lesson number, exact lesson title, and the Teacher Guide
   page range.
3. Paste the complete Teacher Guide lesson text.
4. Optionally paste Student Reader and Activity Book text.
5. Select **Generate Playbook & Slide Prompts**.
6. Review the three tabs: **Teacher Playbook**, **Slide Outline**, and
   **Gemini Prompts**.

## Local provider configuration

Gemini is the default live provider. Store its key only in your local
environment or an ignored `.env` file:

```shell
export GEMINI_API_KEY="your-local-key"
```

The default Gemini model is `gemini-3.6-flash`. A different Daily workflow
model can be selected locally with `TEACHEROS_DAILY_GEMINI_MODEL`.

OpenAI remains an optional fallback when `OPENAI_API_KEY` is configured. To
choose a provider explicitly, set `TEACHEROS_DAILY_PROVIDER` to `gemini` or
`openai`. Explicit selection requires the matching key.

Never add API keys to source files, committed configuration, lesson text, or
saved Daily lesson packages. Environment files are ignored by the repository.

The operation first runs the existing deterministic pasted-lesson analyzer.
That baseline supplies the source identity, activity IDs, and allowed source
references. A provider then creates a structured teaching playbook. TeacherOS
validates its identity, activities, and references before saving it. Only after
the playbook is safely stored does the provider derive a lesson-specific slide
outline.

If slide generation fails, the completed playbook remains available. A later
failure never overwrites an already completed saved package.

## Teacher Playbook

The playbook explains the lesson rather than merely repeating it. Where the
source supports the information, it includes objectives, success criteria,
agenda, materials, vocabulary, activity-by-activity coaching, teacher language,
question purpose, possible responses, misconceptions, ELD supports, checks for
understanding, transitions, exit ticket, homework, and reflection.

Curriculum facts and exact references are preserved. Generated instructional
coaching is visibly labeled for teacher review. Unsupported information is
omitted or listed as unavailable.

## Slide outline and prompts

The slide count and sequence come from the completed playbook and may differ
between lessons. Each outline item identifies its purpose, activity, layout,
student-facing summary, visual direction, and source references.

Each Gemini prompt is self-contained and repeats the complete visual language.
It contains exact student-facing text, layout and visual directions, source
references, and speaker notes. Teacher actions, anticipated answers,
misconception support, checks for understanding, timing, and transitions remain
in speaker notes and are not placed on the visible slide.

To use the prompts:

1. Open the **Gemini Prompts** tab.
2. Select **Copy Gemini Prompt** for one slide.
3. Open Gemini inside your presentation editor.
4. Paste the prompt and generate one slide.
5. Repeat for the remaining numbered prompts.

## Copy and export

- **Copy Complete Teacher Playbook** copies the full Markdown playbook.
- **Copy All Gemini Prompts** copies every prompt with clear numbered
  separators.
- **Copy Gemini Prompt** copies one self-contained slide prompt.
- **Copy Speaker Notes** copies only that slide's notes.
- **Export Playbook as Markdown** downloads `teacher_playbook.md`.
- **Export Slide Prompts as Markdown** downloads
  `gemini_slide_prompts.md`.

Runtime packages are stored atomically under the ignored
`output/daily_lesson_generator/` directory. Raw provider responses, API keys,
and credentials are not saved.

## Optional Google Slides publishing

After reviewing a nonempty Slide Outline, a teacher can select **Create Google
Slides Deck**. This separate action loads the saved package and never calls the
lesson provider or regenerates the Playbook, outline, or Gemini prompts.

The publisher reuses TeacherOS desktop OAuth with the `presentations` and
`drive.file` scopes. Enable the Google Slides and Google Drive APIs, place the
ignored desktop OAuth client at `credentials.json`, and keep the ignored local
authorization token at `token.json`. The first publishing action opens Google
authorization when a valid token is unavailable.

To move a new deck into a Drive folder accessible to the OAuth application,
configure:

```shell
export TEACHEROS_DAILY_GOOGLE_DRIVE_FOLDER_ID="your-folder-id"
```

Without that setting, the private presentation remains in the authenticated
user's default Drive location. TeacherOS never changes sharing permissions.

## Grounding rules

The workflow never permits a provider to change the source identity, introduce
unknown activity IDs, or add structured source references that were not found
by deterministic analysis. Prompts explicitly prohibit invented page numbers,
assignments, quotations, story facts, answer keys, covers, pages, maps,
screenshots, and document images.

## Current limitations

- A configured AI provider is required for generation.
- Teachers must review generated coaching before classroom use.
- The deterministic baseline can only protect references it detects in the
  pasted material.
- Google publishing uses editable shapes and text only; it does not generate or
  upload images in this phase.
- Saved packages can be reopened through the local API; the initial UI focuses
  on the current package rather than a package library.
