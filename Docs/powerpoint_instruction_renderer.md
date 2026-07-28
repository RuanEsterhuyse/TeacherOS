# Editable PowerPoint Renderer

Phase 3F converts one approved, valid `RendererInstructionPackage` into an
editable `.pptx`. It is isolated from Gamma, Google Slides, CanonicalLesson,
and production generation.

## Architecture

The Python service validates identity, options, local assets, output paths,
and the finished Office package. A temporary Node workspace runs
`@oai/artifact-tool` 2.8.33 to create standard editable PowerPoint objects.
The exact approved package is reloaded server-side before rendering.

Outputs are stored beneath the ignored `output/powerpoint_renderer/` tree:

- `decks/` contains `.pptx` files.
- `metadata/` contains validated render results.
- `notes/` contains plain-text speaker-note fallbacks.
- `previews/` contains optional local-only slide PNGs and contact sheets.

## Compatibility strategy

The renderer uses a 1280 × 720 internal canvas, exactly corresponding to the
13.333 × 7.5-inch instruction canvas at 96 DPI. It uses editable text boxes,
rectangles, rounded rectangles, circles, solid fills, simple borders, and
basic shadows. It does not use SmartArt, macros, linked media, embedded fonts,
or advanced PowerPoint-only effects.

Google Slides may substitute fonts, slightly alter text wrapping, simplify
shadows, or change image crops. The renderer uses Georgia for editorial
headings and Arial for body, labels, and footers because they substitute
predictably. Fonts are never embedded or distributed.

## Design system and layouts

All twenty Phase 3E layouts are accepted. The visual system consistently uses
warm cream backgrounds, aqua lesson labels, charcoal headings, coral accents,
white rounded cards, gray borders, generous margins, and restrained shadows.
Every Phase 3E block remains independent and editable.

## Visuals and assets

Unresolved visuals become polished editable placeholder frames containing a
short type label and concise description. Full image prompts remain in notes.
Only explicitly mapped PNG or JPEG files are embedded. Files are never
searched for, downloaded, or generated, and every embedded asset receives a
digest in the render report.

## Notes and grounding

The renderer writes native PowerPoint speaker notes and reopens the exported
deck to verify them. If verification fails, the result reports
`fallback_only`; the complete deterministic notes fallback is always written.
Sources, grounding labels, and unresolved visual prompts are included in
presenter notes, not on the student canvas.

## Overflow and validation

The renderer never deletes, truncates, merges, or splits required content.
It preserves Phase 3E capacity warnings and maintains a 16-point minimum.
After export, validation checks the Office ZIP package, exact slide count and
order, dimensions, titles, editable object presence, external relationships,
and native notes.

## API

- `POST /api/renderer-packages/{package_id}/powerpoint`
- `GET /api/powerpoint-renders`
- `GET /api/powerpoint-renders/{render_id}`
- `GET /api/powerpoint-renders/{render_id}/download`
- `POST /api/powerpoint-renders/{render_id}/validate`

Download resolution is restricted to validated metadata and the renderer's
own `decks/` directory.

## Manual visual review

Generate the synthetic fixture with `render_previews: true`, inspect every PNG
at full size, then inspect `contact-sheet.webp` for deck-level consistency.
Optional LibreOffice/PDF inspection is development-only. Preview images,
contact sheets, PDFs, and PPTX files remain ignored and must never be
committed.
