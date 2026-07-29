# TeacherOS

TeacherOS is a local lesson-production workspace. It transforms authorized
curriculum or a pasted lesson into structured lesson materials, practical
teacher guidance, student-facing slide content, and editable Google Slides.

The project is designed to keep instructional decisions separate from
presentation rendering. Teachers remain responsible for reviewing generated
guidance and approving materials before classroom use.

## What it does

A typical TeacherOS workflow is:

1. A teacher registers curriculum files stored on their computer or pastes a
   lesson into the Daily Lesson Generator.
2. TeacherOS prepares the source, identifies lesson structure, and checks
   available references.
3. It produces teacher-facing guidance, an ordered slide outline, and
   renderer-ready content.
4. The teacher reviews the result.
5. TeacherOS can create an editable Google Slides deck with student-facing
   content on slides and teacher guidance in speaker notes.

Curriculum files, local indexes, credentials, and generated lesson materials
remain on the user's computer. TeacherOS is not intended to be exposed as a
public web service.

## Current features

The repository currently includes:

- A Daily Lesson Generator for one pasted lesson.
- A structured Teacher Playbook with objectives, pacing, vocabulary, activity
  guidance, checks for understanding, and teacher coaching.
- An ordered Slide Outline with student-facing content separated from speaker
  notes.
- Copyable Gemini prompts for individual slides.
- Editable Google Slides publishing through local Google OAuth.
- Curriculum registration, lesson-boundary indexing, and exact lesson
  extraction.
- Structured lesson packages and renderer instruction models.
- Deterministic validation that checks identity, ordering, source references,
  and required content.
- A local web interface for lesson intake, review, generation, and publishing.
- Automated Python and web test suites that do not make live provider calls.

The repository also contains experimental and compatibility paths for
renderer-neutral prompts, PowerPoint, Gamma handoff, and deeper curriculum
intelligence. Their technical details are documented under `Docs/`.

## How to use it

TeacherOS targets Python 3.12 and Node.js 22.13 or newer.

### 1. Clone the repository

```bash
git clone https://github.com/RuanEsterhuyse/TeacherOS.git
cd TeacherOS
```

### 2. Create and activate a Python environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

On Windows PowerShell:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
```

### 3. Install Python dependencies

```bash
python -m pip install -r requirements.txt
```

### 4. Create local environment configuration

```bash
cp .env.example .env
```

TeacherOS can start without an API key. Live lesson generation requires at
least one configured provider key:

```text
GEMINI_API_KEY=your-local-key
OPENAI_API_KEY=
```

Gemini is the default provider for the Daily Lesson Generator. OpenAI remains
an optional fallback. Never commit `.env` or place a real key in
`.env.example`.

### 5. Install web dependencies

```bash
cd web
npm install
cd ..
```

### 6. Start the Python backend

From the repository root:

```bash
set -a
source .env
set +a
PYTHONPATH=. .venv/bin/python -m app.interface_server
```

The backend listens only on `http://127.0.0.1:8765`.

### 7. Start the web interface

In a second terminal:

```bash
cd web
npm run dev
```

Open:

```text
http://localhost:3000/
```

The fastest workflow for trying TeacherOS is to open the Daily Lesson
Generator, paste one complete lesson, generate the Teacher Playbook and Slide
Outline, review them, and then create the Google Slides deck.

### Google Slides setup

Google publishing is optional. To enable it:

1. Create or select a project in Google Cloud.
2. Enable the Google Slides API and Google Drive API.
3. Configure the OAuth consent screen.
4. Create an OAuth client with application type **Desktop app**.
5. Download the client credentials as `credentials.json` in the repository
   root, or configure the supported publisher with another local path.
6. Keep `credentials.json` and generated token files local and ignored.
7. Select the Google Slides publishing action in TeacherOS and complete the
   browser authentication flow when prompted.

TeacherOS does not make a new presentation public or change its sharing
permissions. The deck remains private to the authenticated Google account
unless the user changes sharing in Google Drive.

For curriculum registration and direct CLI commands, see the
[operational command reference](Docs/TeacherOS_Architecture.md#operational-command-reference).

## What is still being developed

TeacherOS is under active development. Current areas of work include:

- Better Teacher Companion Guide review and publishing workflows.
- Deeper Student Reader retrieval and evidence integration.
- Activity Book retrieval and answer-support integration.
- More polished slide layouts, approved visual assets, and presentation
  quality checks.
- Curriculum adapters beyond the current CKLA-focused implementation.
- More explicit teacher approval, revision, and publishing workflows.
- Stronger reusable lesson storage and classroom feedback workflows.

These items describe direction, not completed features.

## Privacy and licensing

TeacherOS runs locally. Do not expose its backend port through a public host,
tunnel, or reverse proxy.

Users must provide curriculum and instructional resources they are authorized
to use. This repository does not include curriculum PDFs, trade books, private
curriculum indexes, local databases, API keys, OAuth credentials, tokens, or
generated lesson outputs.

Generated materials may contain information derived from user-provided
curriculum. Users are responsible for reviewing, storing, and sharing those
materials according to the applicable licenses and school policies.

See:

- [Content and curriculum licensing](CONTENT_LICENSES.md)
- [Security policy](SECURITY.md)
- [Software license](LICENSE)

## Documentation

The most useful technical references are:

- [TeacherOS architecture and operational commands](Docs/TeacherOS_Architecture.md)
- [Daily Lesson Generator](Docs/daily_lesson_generator.md)
- [Pasted lesson workflow](Docs/pasted_lesson_workflow.md)
- [Teacher Companion specification](Docs/teacher_companion_spec.md)
- [Presentation specification](Docs/presentation_spec.md)
- [Editable PowerPoint renderer](Docs/powerpoint_instruction_renderer.md)

The `Docs/` directory contains additional contracts and implementation notes
for contributors working on specific pipeline stages.

## Testing

Run the public Python suite from the repository root:

```bash
python -m pytest
```

Curriculum-dependent production tests skip automatically when registered
private fixtures are unavailable. Public unit and integration tests remain
active.

Run the web tests:

```bash
cd web
npm test
```

Run a production web build:

```bash
cd web
npm run build
```

Automated tests use deterministic fake providers and do not make live AI or
Google API calls.

## Project status

TeacherOS is an active local development and portfolio project. It demonstrates
curriculum ingestion, structured instructional generation, validation,
teacher-facing workflow design, and editable presentation publishing.

It is not currently offered as a hosted service. Teachers should review all
generated lesson guidance and presentation content before classroom use.
