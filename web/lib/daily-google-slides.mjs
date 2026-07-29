export const GOOGLE_SLIDES_PROGRESS = [
  "Creating presentation…",
  "Rendering slides…",
  "Adding speaker notes…",
  "Saving to Google Drive…",
];

export function canCreateDailyGoogleSlides(dailyPackage, loading) {
  return Boolean(dailyPackage?.slide_outline?.length && !loading);
}

export async function createDailyGoogleSlides(fetcher, apiBase, packageId) {
  let response;
  try {
    response = await fetcher(
      `${apiBase}/api/daily-lessons/${packageId}/google-slides`,
      {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: "{}",
      },
    );
  } catch {
    throw new Error(
      "Cannot reach the TeacherOS backend to create Google Slides.",
    );
  }
  let payload;
  try {
    payload = await response.json();
  } catch {
    throw new Error("TeacherOS returned an invalid Google Slides response.");
  }
  if (!response.ok) {
    throw new Error(payload.error || "Google Slides creation failed.");
  }
  if (
    payload.status !== "created"
    || typeof payload.presentation_id !== "string"
    || typeof payload.presentation_url !== "string"
    || typeof payload.slide_count !== "number"
  ) {
    throw new Error("TeacherOS returned an invalid Google Slides response.");
  }
  return payload;
}
