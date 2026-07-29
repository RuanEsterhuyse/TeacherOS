import assert from "node:assert/strict";
import test from "node:test";

import {
  DAILY_PROVIDER_CONFIGURATION_MESSAGE,
  DAILY_PROVIDER_CONNECTION_MESSAGE,
  canGenerateDailyLesson,
  fetchDailyProviderStatus,
  normalizeDailyProviderStatus,
  submitDailyLesson,
} from "../lib/daily-provider.mjs";
import {
  canCreateDailyGoogleSlides,
  createDailyGoogleSlides,
  GOOGLE_SLIDES_PROGRESS,
} from "../lib/daily-google-slides.mjs";

const readyForm = {
  loading: false,
  lessonTitle: "Evidence Lesson",
  teacherGuideText: "Complete source text.",
};

for (const provider of ["gemini", "openai"]) {
  test(`Generate is enabled when ${provider} is available`, () => {
    assert.equal(canGenerateDailyLesson({
      ...readyForm,
      providerStatus: {
        available: true,
        provider,
        model: "test-model",
        message: "Configured.",
      },
    }), true);
  });
}

test("Generate is disabled when neither provider is available", () => {
  assert.equal(canGenerateDailyLesson({
    ...readyForm,
    providerStatus: {
      available: false,
      provider: null,
      model: null,
      message: DAILY_PROVIDER_CONFIGURATION_MESSAGE,
    },
  }), false);
});

test("provider status response shape is compatible with the UI", () => {
  assert.deepEqual(normalizeDailyProviderStatus({
    available: true,
    provider: "gemini",
    model: "gemini-3.6-flash",
    message: "Gemini is configured for live lesson generation.",
  }), {
    available: true,
    provider: "gemini",
    model: "gemini-3.6-flash",
    message: "Gemini is configured for live lesson generation.",
  });
});

test("provider status connection failure is explicit", async () => {
  await assert.rejects(
    fetchDailyProviderStatus(async () => {
      throw new TypeError("fetch failed");
    }, "http://127.0.0.1:8765"),
    new RegExp(DAILY_PROVIDER_CONNECTION_MESSAGE.replaceAll(".", "\\.")),
  );
});

test("frontend submits Daily Lesson generation to the local backend", async () => {
  let observed;
  const result = await submitDailyLesson(async (url, options) => {
    observed = { url, options };
    return {
      ok: true,
      json: async () => ({ package_id: "daily-package-1", status: "complete" }),
    };
  }, "http://127.0.0.1:8765", {
    lesson_title: "Evidence Lesson",
    teacher_guide_text: "Complete source text.",
  });

  assert.equal(
    observed.url,
    "http://127.0.0.1:8765/api/daily-lessons/generate",
  );
  assert.equal(observed.options.method, "POST");
  assert.equal(
    JSON.parse(observed.options.body).lesson_title,
    "Evidence Lesson",
  );
  assert.equal(result.status, "complete");
});

test("Google Slides action is available only for a completed outline", () => {
  assert.equal(canCreateDailyGoogleSlides({slide_outline: [{}]}, false), true);
  assert.equal(canCreateDailyGoogleSlides({slide_outline: []}, false), false);
  assert.equal(canCreateDailyGoogleSlides(null, false), false);
});

test("Google Slides action is disabled while loading", () => {
  assert.equal(canCreateDailyGoogleSlides({slide_outline: [{}]}, true), false);
  assert.deepEqual(GOOGLE_SLIDES_PROGRESS, [
    "Creating presentation…",
    "Rendering slides…",
    "Adding speaker notes…",
    "Saving to Google Drive…",
  ]);
});

test("Google Slides frontend action returns a successful deck", async () => {
  let observed;
  const result = await createDailyGoogleSlides(async (url, options) => {
    observed = {url, options};
    return {
      ok: true,
      json: async () => ({
        status: "created",
        presentation_id: "deck-1",
        presentation_url: (
          "https://docs.google.com/presentation/d/deck-1/edit"
        ),
        title: "Evidence Lesson",
        slide_count: 2,
        warnings: [],
      }),
    };
  }, "http://127.0.0.1:8765", "package-1");

  assert.equal(
    observed.url,
    "http://127.0.0.1:8765/api/daily-lessons/package-1/google-slides",
  );
  assert.equal(observed.options.method, "POST");
  assert.equal(result.presentation_id, "deck-1");
});

test("Google Slides frontend action exposes backend errors", async () => {
  await assert.rejects(
    createDailyGoogleSlides(async () => ({
      ok: false,
      json: async () => ({
        error: "Google OAuth authorization is missing or revoked.",
      }),
    }), "http://127.0.0.1:8765", "package-1"),
    /missing or revoked/,
  );
});
