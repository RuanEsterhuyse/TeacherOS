"use client";

import { useEffect, useMemo, useState } from "react";

type Lesson = {
  number: number;
  title: string;
  duration: number | null;
  objectives: string[];
  vocabulary: string[];
  resources: {
    materials: string[];
    reader_pages: string[];
    activity_pages: string[];
    teacher_guide_pages: string | null;
  };
  generated: boolean;
};

type Unit = {
  grade: string;
  number: string;
  title: string;
  lesson_count: number;
  source_ready: boolean;
  lessons: Lesson[];
};

type Curriculum = {
  id: string;
  name: string;
  units: Unit[];
};

type GenerationStage = {
  id: string;
  label: string;
  complete: boolean;
};

type JobStatus = {
  job_id: string;
  request_id: string;
  state: "running" | "complete" | "failed";
  progress: number;
  current_stage: string;
  stages: GenerationStage[];
  validation_result: string | null;
  slide_count: number;
  warnings: string[];
  errors: string[];
};

const API_BASE =
  process.env.NEXT_PUBLIC_TEACHEROS_API_URL || "http://127.0.0.1:8765";

function durationLabel(duration: number | null) {
  return duration ? `${duration} min` : "Duration not listed";
}

export default function Home() {
  const [curricula, setCurricula] = useState<Curriculum[]>([]);
  const [selectedCurriculumId, setSelectedCurriculumId] = useState("");
  const [expandedUnit, setExpandedUnit] = useState("");
  const [selectedLessonNumber, setSelectedLessonNumber] = useState<number | null>(
    null,
  );
  const [loading, setLoading] = useState(true);
  const [connectionError, setConnectionError] = useState("");
  const [darkMode, setDarkMode] = useState(false);
  const [jobId, setJobId] = useState("");
  const [job, setJob] = useState<JobStatus | null>(null);
  const [view, setView] = useState<"catalog" | "generation" | "complete">(
    "catalog",
  );

  useEffect(() => {
    const savedMode = localStorage.getItem("teacheros-theme");
    const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    queueMicrotask(() =>
      setDarkMode(savedMode ? savedMode === "dark" : prefersDark),
    );
    fetch(`${API_BASE}/api/catalog`)
      .then((response) => {
        if (!response.ok) throw new Error("TeacherOS service is unavailable.");
        return response.json();
      })
      .then((payload) => {
        const nextCurricula: Curriculum[] = payload.curricula || [];
        setCurricula(nextCurricula);
        if (nextCurricula.length) {
          const firstCurriculum = nextCurricula[0];
          const firstUnit = firstCurriculum.units[0];
          setSelectedCurriculumId(firstCurriculum.id);
          if (firstUnit) {
            const unitKey = `${firstUnit.grade}-${firstUnit.number}`;
            setExpandedUnit(unitKey);
            setSelectedLessonNumber(firstUnit.lessons[0]?.number ?? null);
          }
        }
      })
      .catch((error) => setConnectionError(error.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    document.documentElement.dataset.theme = darkMode ? "dark" : "light";
    localStorage.setItem("teacheros-theme", darkMode ? "dark" : "light");
  }, [darkMode]);

  useEffect(() => {
    if (!jobId || view !== "generation") return;
    const poll = window.setInterval(async () => {
      try {
        const response = await fetch(`${API_BASE}/api/jobs/${jobId}`);
        const status: JobStatus = await response.json();
        setJob(status);
        if (status.state === "complete") {
          window.clearInterval(poll);
          setView("complete");
        }
        if (status.state === "failed") window.clearInterval(poll);
      } catch {
        // The next poll can recover from a brief local-service interruption.
      }
    }, 1200);
    return () => window.clearInterval(poll);
  }, [jobId, view]);

  const curriculum = useMemo(
    () => curricula.find((item) => item.id === selectedCurriculumId),
    [curricula, selectedCurriculumId],
  );
  const selectedUnit = useMemo(
    () =>
      curriculum?.units.find(
        (unit) => `${unit.grade}-${unit.number}` === expandedUnit,
      ),
    [curriculum, expandedUnit],
  );
  const lesson = useMemo(
    () =>
      selectedUnit?.lessons.find(
        (item) => item.number === selectedLessonNumber,
      ),
    [selectedUnit, selectedLessonNumber],
  );

  function selectCurriculum(next: Curriculum) {
    setSelectedCurriculumId(next.id);
    const firstUnit = next.units[0];
    if (!firstUnit) return;
    setExpandedUnit(`${firstUnit.grade}-${firstUnit.number}`);
    setSelectedLessonNumber(firstUnit.lessons[0]?.number ?? null);
    setView("catalog");
  }

  function selectUnit(unit: Unit) {
    const key = `${unit.grade}-${unit.number}`;
    setExpandedUnit((current) => (current === key ? "" : key));
    if (expandedUnit !== key) {
      setSelectedLessonNumber(unit.lessons[0]?.number ?? null);
    }
  }

  async function generateLesson() {
    if (!curriculum || !selectedUnit || !lesson) return;
    setView("generation");
    setJob(null);
    const response = await fetch(`${API_BASE}/api/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        curriculum_name: curriculum.name,
        grade: selectedUnit.grade,
        unit: selectedUnit.number,
        lesson_number: lesson.number,
      }),
    });
    const payload = await response.json();
    if (!response.ok) {
      setJob({
        job_id: "",
        request_id: "",
        state: "failed",
        progress: 0,
        current_stage: "Unable to start",
        stages: [],
        validation_result: null,
        slide_count: 0,
        warnings: [],
        errors: [payload.error || "Unable to start lesson generation."],
      });
      return;
    }
    setJobId(payload.job_id);
  }

  async function openOutput(target: "folder" | "bundle") {
    if (!job?.request_id) return;
    await fetch(`${API_BASE}/api/open`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ request_id: job.request_id, target }),
    });
  }

  function generateAnother() {
    setJobId("");
    setJob(null);
    setView("catalog");
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">
            T
          </span>
          <div>
            <strong>TeacherOS</strong>
            <span>Version 0.1</span>
          </div>
        </div>
        <div className="topbar-actions">
          <span className="engine-status">
            <i aria-hidden="true" /> Lesson engine ready
          </span>
          <button
            className="theme-toggle"
            onClick={() => setDarkMode((current) => !current)}
            aria-label={darkMode ? "Use light mode" : "Use dark mode"}
          >
            <span aria-hidden="true">{darkMode ? "Light" : "Dark"}</span>
          </button>
        </div>
      </header>

      <div className="workspace">
        <aside className="sidebar" aria-label="Curricula">
          <div className="sidebar-heading">
            <span>Curricula</span>
            <b>{curricula.length}</b>
          </div>
          {curricula.map((item) => (
            <button
              key={item.id}
              className={`curriculum-item ${
                item.id === selectedCurriculumId ? "active" : ""
              }`}
              onClick={() => selectCurriculum(item)}
            >
              <span className="curriculum-monogram">{item.name.slice(0, 2)}</span>
              <span>
                <strong>{item.name}</strong>
                <small>
                  {item.units.length} {item.units.length === 1 ? "unit" : "units"}
                </small>
              </span>
            </button>
          ))}
          <div className="sidebar-note">
            <span>Local curriculum library</span>
            <p>Source files stay on this computer.</p>
          </div>
        </aside>

        <section className="content">
          {loading && (
            <div className="state-card">
              <div className="loading-line" />
              <div className="loading-line short" />
            </div>
          )}

          {!loading && connectionError && (
            <div className="state-card error-card">
              <span className="eyebrow">Connection needed</span>
              <h1>Start the TeacherOS local service</h1>
              <p>
                The interface is ready, but it cannot reach the local curriculum
                library yet.
              </p>
              <code>python -m app.interface_server</code>
            </div>
          )}

          {!loading && !connectionError && view === "catalog" && curriculum && (
            <>
              <div className="page-heading">
                <div>
                  <span className="eyebrow">Curriculum library</span>
                  <h1>{curriculum.name}</h1>
                  <p>
                    Choose a unit and lesson. TeacherOS will preserve the source
                    curriculum and generate the complete lesson package.
                  </p>
                </div>
                <div className="heading-stat">
                  <strong>
                    {curriculum.units.reduce(
                      (total, unit) => total + unit.lesson_count,
                      0,
                    )}
                  </strong>
                  <span>lessons imported</span>
                </div>
              </div>

              <div className="catalog-layout">
                <div className="unit-list">
                  {curriculum.units.map((unit) => {
                    const unitKey = `${unit.grade}-${unit.number}`;
                    const expanded = expandedUnit === unitKey;
                    return (
                      <section className="unit-card" key={unitKey}>
                        <button
                          className="unit-header"
                          onClick={() => selectUnit(unit)}
                          aria-expanded={expanded}
                        >
                          <span className="unit-number">U{unit.number}</span>
                          <span className="unit-copy">
                            <small>Grade {unit.grade}</small>
                            <strong>{unit.title}</strong>
                            <em>{unit.lesson_count} lessons</em>
                          </span>
                          <span className="unit-readiness">
                            <i className={unit.source_ready ? "ready" : ""} />
                            {unit.source_ready ? "Sources ready" : "Check sources"}
                          </span>
                          <span className={`chevron ${expanded ? "open" : ""}`}>
                            ›
                          </span>
                        </button>
                        {expanded && (
                          <div className="lesson-list">
                            {unit.lessons.map((item) => (
                              <button
                                key={item.number}
                                className={`lesson-row ${
                                  selectedLessonNumber === item.number
                                    ? "selected"
                                    : ""
                                }`}
                                onClick={() =>
                                  setSelectedLessonNumber(item.number)
                                }
                              >
                                <span className="lesson-index">
                                  {String(item.number).padStart(2, "0")}
                                </span>
                                <span className="lesson-row-copy">
                                  <strong>{item.title}</strong>
                                  <small>{durationLabel(item.duration)}</small>
                                </span>
                                {item.generated && (
                                  <span className="generated-pill">Generated</span>
                                )}
                              </button>
                            ))}
                          </div>
                        )}
                      </section>
                    );
                  })}
                </div>

                {lesson && selectedUnit && (
                  <aside className="lesson-detail" data-testid="lesson-detail">
                    <div className="detail-topline">
                      <span>
                        Grade {selectedUnit.grade} · Unit {selectedUnit.number} ·
                        Lesson {lesson.number}
                      </span>
                      <b>{durationLabel(lesson.duration)}</b>
                    </div>
                    <h2>{lesson.title}</h2>

                    <div className="detail-section">
                      <h3>Objectives</h3>
                      <ul>
                        {lesson.objectives.slice(0, 4).map((objective) => (
                          <li key={objective}>{objective}</li>
                        ))}
                      </ul>
                      {lesson.objectives.length > 4 && (
                        <small className="more-label">
                          + {lesson.objectives.length - 4} additional objectives
                        </small>
                      )}
                    </div>

                    <div className="detail-section">
                      <h3>Vocabulary</h3>
                      <div className="tag-list">
                        {lesson.vocabulary.length ? (
                          lesson.vocabulary.slice(0, 8).map((term) => (
                            <span key={term}>{term}</span>
                          ))
                        ) : (
                          <p className="empty-copy">
                            Vocabulary appears here after the curriculum reading
                            stage.
                          </p>
                        )}
                      </div>
                      {lesson.vocabulary.length > 8 && (
                        <small className="more-label">
                          + {lesson.vocabulary.length - 8} more terms
                        </small>
                      )}
                    </div>

                    <div className="detail-section resources">
                      <h3>Resources</h3>
                      {lesson.resources.teacher_guide_pages && (
                        <span>
                          Teacher Guide pp. {lesson.resources.teacher_guide_pages}
                        </span>
                      )}
                      {lesson.resources.reader_pages.length > 0 && (
                        <span>
                          Reader pp. {lesson.resources.reader_pages.slice(0, 3).join(", ")}
                        </span>
                      )}
                      {lesson.resources.activity_pages.length > 0 && (
                        <span>
                          Activity Pages{" "}
                          {lesson.resources.activity_pages.slice(0, 4).join(", ")}
                        </span>
                      )}
                    </div>

                    <button
                      className="primary-button"
                      onClick={generateLesson}
                      data-testid="generate-lesson"
                    >
                      <span>Generate Lesson</span>
                      <i aria-hidden="true">→</i>
                    </button>
                    <p className="button-note">
                      Runs the complete TeacherOS lesson pipeline.
                    </p>
                  </aside>
                )}
              </div>
            </>
          )}

          {view === "generation" && (
            <div className="generation-view" data-testid="generation-view">
              <div className="generation-copy">
                <span className="eyebrow">Generating lesson</span>
                <h1>{lesson?.title}</h1>
                <p>
                  TeacherOS is building the lesson package from the imported
                  curriculum. You can leave this screen open while it works.
                </p>
              </div>
              <div className="progress-card">
                <div className="progress-header">
                  <div>
                    <span>Current step</span>
                    <strong>{job?.current_stage || "Starting TeacherOS"}</strong>
                  </div>
                  <b>{job?.progress || 4}%</b>
                </div>
                <div className="progress-track">
                  <i style={{ width: `${job?.progress || 4}%` }} />
                </div>
                <div className="stage-list">
                  {(job?.stages || []).map((stage) => (
                    <div className={stage.complete ? "done" : ""} key={stage.id}>
                      <span>{stage.complete ? "✓" : ""}</span>
                      <p>{stage.label}</p>
                    </div>
                  ))}
                  {!job && (
                    <div className="active-stage">
                      <span />
                      <p>Preparing lesson</p>
                    </div>
                  )}
                </div>
                {job?.state === "failed" && (
                  <div className="generation-error">
                    <strong>Generation stopped</strong>
                    <p>{job.errors.join(" ")}</p>
                    <button onClick={generateAnother}>Return to lesson</button>
                  </div>
                )}
              </div>
            </div>
          )}

          {view === "complete" && job && (
            <div className="complete-view" data-testid="complete-view">
              <div className="success-mark" aria-hidden="true">
                ✓
              </div>
              <span className="eyebrow">TeacherOS complete</span>
              <h1>Lesson Generated Successfully</h1>
              <p>
                {job.slide_count} slides prepared ·{" "}
                {job.validation_result === "pass_with_warnings"
                  ? "Validated with review notes"
                  : "Validation passed"}
              </p>
              <div className="complete-actions">
                <button
                  className="primary-button"
                  onClick={() => openOutput("folder")}
                >
                  Open Output Folder
                </button>
                <button
                  className="secondary-button"
                  onClick={() => openOutput("bundle")}
                >
                  Open RendererPromptBundle.md
                </button>
                <button className="text-button" onClick={generateAnother}>
                  Generate Another Lesson
                </button>
              </div>
              {job.warnings.length > 0 && (
                <p className="review-note">
                  {job.warnings.length} review notes are included with the
                  generated lesson.
                </p>
              )}
            </div>
          )}
        </section>
      </div>
    </main>
  );
}
