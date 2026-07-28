import fs from "node:fs/promises";
import path from "node:path";
import {
  FileBlob,
  Presentation,
  PresentationFile,
} from "@oai/artifact-tool";

const [inputPath, outputPath, manifestPath, previewDirectory] =
  process.argv.slice(2);
const payload = JSON.parse(await fs.readFile(inputPath, "utf8"));
const pkg = payload.instruction_package;
const options = payload.options;
const PX = 96;
const W = Math.round(pkg.canvas.width * PX);
const H = Math.round(pkg.canvas.height * PX);
const COLORS = {
  cream: "#F7F4EE",
  aqua: "#67C7D8",
  teal: "#3B97A8",
  coral: "#E97F7C",
  charcoal: "#2E2E2E",
  gray: "#D9D9D9",
  white: "#FFFFFF",
};
const presentation = Presentation.create({ slideSize: { width: W, height: H } });
const rendered = [];
const notesTexts = [];
const shapeCounts = [];

function px(value) { return value * PX; }
function addShape(slide, geometry, name, position, fill, line, shadow) {
  return slide.shapes.add({
    geometry,
    name,
    position,
    fill,
    line: line || { style: "solid", fill: "none", width: 0 },
    ...(shadow ? { shadow } : {}),
  });
}
function addText(slide, name, text, position, style) {
  const box = addShape(
    slide, "textbox", name, position, "none",
    { style: "solid", fill: "none", width: 0 },
  );
  box.text = text;
  box.text.style = style;
  return box;
}
function notesText(slide, visual) {
  const notes = slide.notes_payload;
  const parts = [notes.plain_text_fallback];
  if (slide.source_references.length) {
    parts.push("[Sources]\n" + slide.source_references.map((ref) => {
      let value = ref.source_type.replaceAll("_", " ");
      if (ref.page_start !== null) {
        value += ` pp. ${ref.page_start}`;
        if (ref.page_end !== ref.page_start) value += `–${ref.page_end}`;
      }
      if (ref.activity_reference) value += ` · ${ref.activity_reference}`;
      return `- ${value}`;
    }).join("\n"));
  }
  if (slide.grounding_labels.length) {
    parts.push("[Grounding]\n" + slide.grounding_labels.join(", "));
  }
  if (visual?.image_prompt) {
    parts.push("[Unresolved visual prompt]\n" + visual.image_prompt);
  }
  return parts.filter(Boolean).join("\n\n");
}

for (const instruction of pkg.slides) {
  const slide = presentation.slides.add();
  slide.background.fill = COLORS.cream;
  addShape(slide, "roundRect", `lesson-label-${instruction.slide_id}`,
    { left: 64, top: 34, width: 220, height: 34 },
    COLORS.aqua, { style: "solid", fill: COLORS.aqua, width: 1 });
  addText(slide, `lesson-label-text-${instruction.slide_id}`,
    `LESSON · ${instruction.slide_number}`,
    { left: 80, top: 39, width: 190, height: 24 },
    { fontSize: 13, bold: true, color: COLORS.charcoal,
      fontFamily: "Arial", alignment: "center" });
  addShape(slide, "rect", `coral-accent-${instruction.slide_id}`,
    { left: 64, top: 84, width: 8, height: 64 },
    COLORS.coral, { style: "solid", fill: COLORS.coral, width: 0 });

  const titleBlock = instruction.text_blocks[0];
  const titleSize = instruction.layout_type === "title" ? 48 : 34;
  addText(slide, `title-${instruction.slide_id}`, titleBlock.text,
    {
      left: Math.max(88, px(titleBlock.x)),
      top: Math.max(82, px(titleBlock.y)),
      width: Math.min(px(titleBlock.width), W - 120),
      height: Math.max(72, px(titleBlock.height)),
    },
    { fontSize: titleSize, bold: true, color: COLORS.charcoal,
      fontFamily: "Georgia", alignment: titleBlock.alignment || "left" });

  const visual = instruction.visual_blocks[0];
  const visualFrame = visual ? {
    left: px(visual.x), top: px(visual.y),
    width: px(visual.width), height: px(visual.height),
  } : null;
  const contentBlocks = instruction.text_blocks.slice(1);
  for (const block of contentBlocks) {
    const pos = {
      left: px(block.x), top: px(block.y),
      width: px(block.width), height: px(block.height),
    };
    const overlapsVisualVertically = visualFrame
      && pos.top < visualFrame.top + visualFrame.height
      && pos.top + pos.height > visualFrame.top;
    if (
      overlapsVisualVertically
      && pos.left < visualFrame.left
      && pos.left + pos.width > visualFrame.left
    ) {
      pos.width = Math.max(160, visualFrame.left - pos.left - 28);
    }
    const card = block.role !== "body" || contentBlocks.length > 1;
    if (card) {
      addShape(slide, "roundRect", `card-${block.block_id}`,
        { left: pos.left - 14, top: pos.top - 10,
          width: pos.width + 28, height: pos.height + 20 },
        COLORS.white, { style: "solid", fill: COLORS.gray, width: 1 },
        "shadow-sm");
    }
    const isQuestion = block.role === "question";
    if (isQuestion) {
      addShape(slide, "rect", `callout-${block.block_id}`,
        { left: pos.left - 14, top: pos.top - 10, width: 7,
          height: pos.height + 20 },
        COLORS.coral, { style: "solid", fill: COLORS.coral, width: 0 });
    }
    addText(slide, `text-${block.block_id}`, block.text, pos, {
      fontSize: Math.max(
        options.minimum_body_font_size,
        Math.min(block.font_size, isQuestion ? 28 : 22),
      ),
      bold: isQuestion || ["callout", "vocabulary"].includes(block.role),
      color: block.color || COLORS.charcoal,
      fontFamily: block.role === "title" ? "Georgia" : "Arial",
      alignment: block.alignment || "left",
    });
  }

  const asset = pkg.asset_manifest.find((item) =>
    item.slide_id === instruction.slide_id);
  const localAsset = asset ? options.local_assets[asset.asset_id] : null;
  if (visual) {
    const frame = visualFrame;
    if (localAsset) {
      const blob = await FileBlob.load(localAsset);
      const image = slide.images.add({
        blob, position: frame,
        fit: visual.crop_behavior === "cover" ? "cover" : "contain",
        alt: visual.alt_text || visual.description,
      });
      image.name = `asset-${asset.asset_id}`;
    } else {
      addShape(slide, "roundRect", `placeholder-${visual.block_id}`, frame,
        COLORS.white, { style: "solid", fill: COLORS.teal, width: 2 });
      addShape(slide, "ellipse", `placeholder-dot-${visual.block_id}`,
        { left: frame.left + 28, top: frame.top + 28, width: 22, height: 22 },
        COLORS.coral, { style: "solid", fill: COLORS.coral, width: 0 });
      addText(slide, `placeholder-label-${visual.block_id}`,
        visual.visual_type.replaceAll("_", " ").toUpperCase(),
        { left: frame.left + 28, top: frame.top + 66,
          width: frame.width - 56, height: 32 },
        { fontSize: 14, bold: true, color: COLORS.teal,
          fontFamily: "Arial" });
      addText(slide, `placeholder-copy-${visual.block_id}`,
        visual.description,
        { left: frame.left + 28, top: frame.top + 110,
          width: frame.width - 56, height: frame.height - 138 },
        { fontSize: 18, color: COLORS.charcoal, fontFamily: "Arial" });
    }
  }

  addText(slide, `footer-${instruction.slide_id}`,
    `${pkg.theme.theme_id}  ·  ${String(instruction.slide_number).padStart(2, "0")}`,
    { left: 64, top: H - 34, width: W - 128, height: 18 },
    { fontSize: 10, color: "#666666", fontFamily: "Arial",
      alignment: "right" });
  const notes = notesText(instruction, visual);
  slide.speakerNotes.textFrame.setText(notes);
  slide.speakerNotes.setVisible(true);
  notesTexts.push(notes);
  rendered.push(instruction.slide_id);
  shapeCounts.push(slide.shapes.items.length + slide.images.items.length);
}

await fs.mkdir(path.dirname(outputPath), { recursive: true });
const pptx = await PresentationFile.exportPptx(presentation);
await pptx.save(outputPath);

if (options.render_previews && previewDirectory) {
  await fs.mkdir(previewDirectory, { recursive: true });
  for (const [index, slide] of presentation.slides.items.entries()) {
    const blob = await presentation.export({ slide, format: "png", scale: 1 });
    await fs.writeFile(
      path.join(previewDirectory, `slide-${String(index + 1).padStart(2, "0")}.png`),
      new Uint8Array(await blob.arrayBuffer()),
    );
  }
  const montage = await presentation.export({
    format: "webp", montage: true, scale: 1,
  });
  await fs.writeFile(
    path.join(previewDirectory, "contact-sheet.webp"),
    new Uint8Array(await montage.arrayBuffer()),
  );
}

const reopened = await PresentationFile.importPptx(
  await FileBlob.load(outputPath),
);
const inspection = await reopened.inspect({
  kind: "slide,textbox,shape,image,notes", maxChars: 1000000,
});
const importedNotes = reopened.slides.items.map((slide) =>
  slide.speakerNotes.textFrame.text || "");
await fs.writeFile(manifestPath, JSON.stringify({
  slide_count: reopened.slides.items.length,
  rendered_slide_ids: rendered,
  shape_counts: shapeCounts,
  notes_verified: importedNotes.length === notesTexts.length
    && importedNotes.every((text, index) => text.includes(notesTexts[index])),
  expected_titles: pkg.slides.map((slide) => slide.text_blocks[0].text),
  inspection: inspection.ndjson,
}, null, 2) + "\n");
