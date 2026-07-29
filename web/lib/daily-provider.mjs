export const DAILY_PROVIDER_CONFIGURATION_MESSAGE =
  "Configure GEMINI_API_KEY or OPENAI_API_KEY for live lesson generation.";

export const DAILY_PROVIDER_CONNECTION_MESSAGE =
  "Cannot reach the TeacherOS backend at http://127.0.0.1:8765.";

export function normalizeDailyProviderStatus(payload) {
  if (
    typeof payload !== "object"
    || payload === null
    || typeof payload.available !== "boolean"
  ) {
    throw new Error("TeacherOS returned an invalid provider-status response.");
  }
  const provider = payload.provider === "gemini" || payload.provider === "openai"
    ? payload.provider
    : null;
  if (payload.available && provider === null) {
    throw new Error("TeacherOS returned an invalid provider-status response.");
  }
  return {
    available: payload.available,
    provider,
    model: typeof payload.model === "string" ? payload.model : null,
    message: typeof payload.message === "string"
      ? payload.message
      : payload.available
        ? `${provider} is configured for live lesson generation.`
        : DAILY_PROVIDER_CONFIGURATION_MESSAGE,
  };
}

export async function fetchDailyProviderStatus(fetcher, apiBase) {
  let response;
  try {
    response = await fetcher(`${apiBase}/api/daily-lessons/provider-status`);
  } catch {
    throw new Error(DAILY_PROVIDER_CONNECTION_MESSAGE);
  }
  if (!response.ok) {
    throw new Error(DAILY_PROVIDER_CONNECTION_MESSAGE);
  }
  return normalizeDailyProviderStatus(await response.json());
}

export function canGenerateDailyLesson({
  providerStatus,
  loading,
  lessonTitle,
  teacherGuideText,
}) {
  return Boolean(
    providerStatus?.available
    && !loading
    && lessonTitle.trim()
    && teacherGuideText.trim(),
  );
}

export async function submitDailyLesson(fetcher, apiBase, payload) {
  let response;
  try {
    response = await fetcher(`${apiBase}/api/daily-lessons/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch {
    throw new Error(DAILY_PROVIDER_CONNECTION_MESSAGE);
  }
  let result;
  try {
    result = await response.json();
  } catch {
    throw new Error("TeacherOS returned an invalid generation response.");
  }
  if (!response.ok) {
    throw new Error(result.error || "Daily lesson generation failed.");
  }
  return result;
}
