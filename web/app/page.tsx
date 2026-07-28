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
  failed_stage: string | null;
  stages: GenerationStage[];
  validation_result: string | null;
  slide_count: number;
  warnings: string[];
  errors: string[];
  blocking_findings: {
    code: string;
    severity: "error" | "warning" | "info";
    message: string;
    slide_id: string | null;
  }[];
  kind?: "lesson" | "teaching_package";
  agenda?: {
    order: number;
    official: string;
    student_friendly: string;
    duration: number | null;
  }[];
  objectives?: {
    official: string;
    student_friendly: string;
    meaning_preserved: boolean;
  }[];
  teaching_steps?: number;
  questions?: number;
  student_slides?: number;
};

type PastedLessonSource = {
  source_id: string;
  grade: string;
  unit: string;
  lesson_number: number;
  lesson_title: string;
  teacher_guide_page_start: number | null;
  teacher_guide_page_end: number | null;
  teacher_guide_text: string;
  student_reader_text: string | null;
  activity_book_text: string | null;
  source_notes: string | null;
};

type PastedLessonAnalysis = {
  playbook: {
    playbook_id: string;
    source_id: string;
    lesson_metadata: {
      grade: string;
      unit: string;
      lesson_number: number;
      lesson_title: string;
      teacher_guide_page_start: number | null;
      teacher_guide_page_end: number | null;
    };
    lesson_summary: string | null;
    instructional_days: number[];
    objectives: string[];
    essential_question: string | null;
    success_criteria: string[];
    materials: string[];
    vocabulary: { term: string }[];
    activities: {
      activity_id: string;
      title: string;
      instructional_day: number | null;
      duration_minutes: number | null;
      purpose: string | null;
      teacher_script: string[];
      questions: { prompt: string }[];
      source_references: {
        source_type: string;
        page_start: number | null;
        page_end: number | null;
        activity_reference: string | null;
      }[];
    }[];
    homework: string[];
    assessment: string[];
    source_references: {
      source_type: string;
      page_start: number | null;
      page_end: number | null;
      activity_reference: string | null;
    }[];
  };
  warnings: { code: string; message: string; field: string | null }[];
  unclassified_sections: string[];
  extraction_summary: {
    detected_activity_count: number;
    detected_day_count: number;
    detected_reference_count: number;
    confidence_by_field: Record<string, number>;
  };
};

type PlaybookEnrichment = {
  enrichment_id: string;
  status: "success" | "partial" | "failed";
  enriched_playbook: PastedLessonAnalysis["playbook"];
  grounding_report: {
    source_backed_fields: string[];
    inferred_fields: string[];
    omitted_unsupported_fields: string[];
    added_teacher_guidance: string[];
    source_coverage_by_activity: {
      activity_id: string;
      fully_retained: boolean;
    }[];
  };
  warnings: { code: string; message: string; field: string | null }[];
  unsupported_claims: {
    field_path: string;
    claim: string;
    reason: string;
  }[];
  provider_metadata: {
    provider_name: string;
    model_name: string;
  } | null;
  baseline_preserved: boolean;
  failure_reason: string | null;
};

type ApprovedEnrichment = {
  enrichment_id: string;
  source_id: string;
  enriched_playbook: PastedLessonAnalysis["playbook"];
  teacher_approval_status: "approved";
};

type PresentationReference = {
  source_type: string;
  page_start: number | null;
  page_end: number | null;
  section: string | null;
  activity_reference: string | null;
};

type PresentationBuildResult = {
  presentation_spec: {
    presentation_id: string;
    lesson_title: string;
    presentation_title: string;
    estimated_total_minutes: number;
    theme: { name: string };
    validation_status: string;
    approval_status: string;
    slides: {
      slide_id: string;
      slide_number: number;
      instructional_day: number | null;
      activity_id: string | null;
      slide_type: string;
      layout_type: string;
      title: string;
      estimated_minutes: number | null;
      required: boolean;
      student_facing_content: {
        element_id: string;
        element_type: string;
        text: string | null;
        items: string[];
        label: string | null;
        grounding_label: string;
      }[];
      speaker_notes: {
        purpose: string | null;
        teacher_script: string[];
        teacher_actions: string[];
        anticipated_responses: string[];
        misconception_support: string[];
        checks_for_understanding: string[];
        transition_language: string | null;
        pacing_notes: string | null;
      };
      source_references: PresentationReference[];
      grounding_labels: string[];
      eld_supports: string[];
      visual_spec: {
        visual_type: string;
        description: string | null;
        image_prompt: string | null;
        alt_text: string | null;
      } | null;
    }[];
  };
  warnings: { code: string; message: string }[];
  missing_sections: string[];
  source_coverage: {
    expected_reference_count: number;
    retained_reference_count: number;
    complete: boolean;
  };
  activity_coverage: {
    activity_id: string;
    covered: boolean;
    slide_ids: string[];
  }[];
  validation_report: {
    status: string;
    valid: boolean;
    issues: {
      code: string;
      severity: string;
      message: string;
      slide_id: string | null;
      activity_id: string | null;
    }[];
  };
};

type RendererInstructionResult = {
  instruction_package: {
    package_id: string;
    presentation_id: string;
    approval_status: "pending" | "approved";
    renderer_contract_version: string;
    canvas: {
      width: number;
      height: number;
      units: string;
      aspect_ratio: string;
    };
    theme: {
      theme_id: string;
      heading_font_family: string;
      body_font_family: string;
      background_colors: string[];
      heading_color: string;
      body_color: string;
      accent_colors: string[];
    };
    slides: {
      slide_id: string;
      slide_number: number;
      slide_type: string;
      layout_type: string;
      timing: number | null;
      required: boolean;
      sequence_group: string | null;
      text_blocks: {
        block_id: string;
        role: string;
        text: string;
        x: number;
        y: number;
        width: number;
        height: number;
        font_family: string;
        font_size: number;
        color: string;
        source_reference: PresentationReference | null;
        grounding_label: string;
      }[];
      visual_blocks: {
        block_id: string;
        visual_type: string;
        description: string;
        x: number;
        y: number;
        width: number;
        height: number;
        alt_text: string | null;
        required: boolean;
        grounding_label: string;
      }[];
      notes_payload: {
        purpose: string | null;
        teacher_script: string[];
        teacher_actions: string[];
        anticipated_responses: string[];
        misconception_support: string[];
        checks_for_understanding: string[];
        transition_language: string | null;
        pacing_notes: string | null;
        plain_text_fallback: string;
      };
      source_references: PresentationReference[];
      grounding_labels: string[];
    }[];
    asset_manifest: {
      asset_id: string;
      slide_id: string;
      asset_type: string;
      description: string;
      status: string;
    }[];
    font_manifest: {
      family: string;
      roles: string[];
      fallback_families: string[];
    }[];
    validation_report: {
      status: string;
      valid: boolean;
      expected_slide_count: number;
      represented_slide_count: number;
      issues: {
        code: string;
        severity: string;
        message: string;
        slide_id: string | null;
      }[];
    };
  };
  warnings: {
    code: string;
    message: string;
    slide_id: string | null;
    block_id: string | null;
  }[];
  unsupported_features: {
    code: string;
    message: string;
    slide_id: string | null;
  }[];
  overflow_risks: {
    code: string;
    message: string;
    slide_id: string | null;
    block_id: string | null;
  }[];
};

const API_BASE =
  process.env.NEXT_PUBLIC_TEACHEROS_API_URL || "http://127.0.0.1:8765";
const GAMMA_URL =
  process.env.NEXT_PUBLIC_GAMMA_URL || "https://gamma.app";

function durationLabel(duration: number | null) {
  return duration ? `${duration} min` : "Duration not listed";
}

function stageLabel(stage: string | null) {
  if (!stage) return "Generation";
  return stage
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
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
  const [copyStatus, setCopyStatus] = useState("");
  const [view, setView] = useState<
    "catalog" | "generation" | "complete" | "pasted"
  >("catalog");
  const [pastedForm, setPastedForm] = useState({
    grade: "8",
    unit: "1",
    lesson_number: "1",
    lesson_title: "",
    teacher_guide_page_start: "",
    teacher_guide_page_end: "",
    teacher_guide_text: "",
    student_reader_text: "",
    activity_book_text: "",
    source_notes: "",
  });
  const [pastedSource, setPastedSource] =
    useState<PastedLessonSource | null>(null);
  const [pastedAnalysis, setPastedAnalysis] =
    useState<PastedLessonAnalysis | null>(null);
  const [pastedStatus, setPastedStatus] = useState("");
  const [enrichment, setEnrichment] =
    useState<PlaybookEnrichment | null>(null);
  const [enrichmentLoading, setEnrichmentLoading] = useState(false);
  const [enrichmentOptions, setEnrichmentOptions] = useState({
    detail_level: "comprehensive",
    include_teacher_scripts: true,
    include_possible_student_responses: true,
    include_misconceptions: true,
    include_eld_supports: true,
    include_checks_for_understanding: true,
    include_transition_language: true,
    include_teacher_reflection: true,
    preserve_original_wording: true,
    strict_grounding: true,
  });
  const [approvedEnrichments, setApprovedEnrichments] = useState<
    ApprovedEnrichment[]
  >([]);
  const [selectedApprovedEnrichment, setSelectedApprovedEnrichment] =
    useState("");
  const [presentationResult, setPresentationResult] =
    useState<PresentationBuildResult | null>(null);
  const [presentationLoading, setPresentationLoading] = useState(false);
  const [presentationStatus, setPresentationStatus] = useState("");
  const [presentationOptions, setPresentationOptions] = useState({
    target_slide_count: "",
    maximum_slide_count: "",
    detail_level: "comprehensive",
    include_agenda: true,
    include_objectives: true,
    include_vocabulary: true,
    include_eld_supports: true,
    include_teacher_only_slides: false,
    include_homework: true,
    include_exit_ticket: true,
    include_visual_prompts: true,
    preferred_theme_id: "teacheros_classroom",
    split_long_activities: true,
    strict_required_section_coverage: true,
  });
  const [approvedPresentationSpecs, setApprovedPresentationSpecs] = useState<
    PresentationBuildResult["presentation_spec"][]
  >([]);
  const [selectedPresentationSpec, setSelectedPresentationSpec] = useState("");
  const [rendererResult, setRendererResult] =
    useState<RendererInstructionResult | null>(null);
  const [rendererLoading, setRendererLoading] = useState(false);
  const [rendererStatus, setRendererStatus] = useState("");

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
    fetch(`${API_BASE}/api/playbook-enrichments`)
      .then((response) => response.ok ? response.json() : { enrichments: [] })
      .then((payload) => {
        const values: ApprovedEnrichment[] = payload.enrichments || [];
        setApprovedEnrichments(values);
        setSelectedApprovedEnrichment(
          (current) => current || values[0]?.enrichment_id || "",
        );
      })
      .catch(() => setApprovedEnrichments([]));
    fetch(`${API_BASE}/api/presentation-specs`)
      .then((response) => response.ok
        ? response.json() : { presentation_specs: [] })
      .then((payload) => {
        const values: PresentationBuildResult["presentation_spec"][] =
          payload.presentation_specs || [];
        setApprovedPresentationSpecs(values);
        setSelectedPresentationSpec(
          (current) => current || values[0]?.presentation_id || "",
        );
      })
      .catch(() => setApprovedPresentationSpecs([]));
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
        failed_stage: "generation_start",
        stages: [],
        validation_result: null,
        slide_count: 0,
        warnings: [],
        errors: [payload.error || "Unable to start lesson generation."],
        blocking_findings: [],
      });
      return;
    }
    setJobId(payload.job_id);
  }

  async function generateTeachingPackage() {
    if (!curriculum || !selectedUnit || !lesson) return;
    setView("generation");
    setJob(null);
    const response = await fetch(
      `${API_BASE}/api/teaching-package/generate`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          curriculum_name: curriculum.name,
          grade: selectedUnit.grade,
          unit: selectedUnit.number,
          lesson_number: lesson.number,
        }),
      },
    );
    const payload = await response.json();
    if (!response.ok) {
      setJob({
        job_id: "",
        request_id: "",
        state: "failed",
        progress: 0,
        current_stage: "Unable to start",
        failed_stage: "teaching_package_start",
        stages: [],
        validation_result: null,
        slide_count: 0,
        warnings: [],
        errors: [payload.error || "Unable to start teaching package."],
        blocking_findings: [],
        kind: "teaching_package",
      });
      return;
    }
    setJobId(payload.job_id);
  }

  function updatePastedField(field: string, value: string) {
    setPastedForm((current) => ({ ...current, [field]: value }));
    setPastedSource(null);
    setPastedAnalysis(null);
    setEnrichment(null);
    setPastedStatus("");
  }

  async function savePastedSource() {
    setPastedStatus("Saving source…");
    setPastedAnalysis(null);
    try {
      const response = await fetch(`${API_BASE}/api/pasted-lessons`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...pastedForm,
          lesson_number: Number(pastedForm.lesson_number),
        }),
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.error || "Unable to save pasted lesson.");
      }
      setPastedSource(payload);
      setPastedStatus("Source saved exactly as provided.");
    } catch (error) {
      setPastedStatus(
        error instanceof Error ? error.message : "Unable to save source.",
      );
    }
  }

  async function analyzePastedSource() {
    if (!pastedSource) return;
    setPastedStatus("Running deterministic baseline analysis…");
    try {
      const response = await fetch(
        `${API_BASE}/api/pasted-lessons/${pastedSource.source_id}/analyze`,
        { method: "POST", headers: { "Content-Type": "application/json" } },
      );
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.error || "Unable to analyze pasted lesson.");
      }
      setPastedAnalysis(payload);
      setEnrichment(null);
      setPastedStatus("Analysis ready for review. Nothing has been invented.");
    } catch (error) {
      setPastedStatus(
        error instanceof Error ? error.message : "Analysis failed.",
      );
    }
  }

  async function savePastedPlaybook() {
    if (!pastedSource || !pastedAnalysis) return;
    setPastedStatus("Saving preliminary Teacher Playbook…");
    try {
      const response = await fetch(
        `${API_BASE}/api/pasted-lessons/${pastedSource.source_id}/playbook`,
        { method: "POST", headers: { "Content-Type": "application/json" } },
      );
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.error || "Unable to save Teacher Playbook.");
      }
      setPastedStatus(`Teacher Playbook saved: ${payload.playbook_id}`);
    } catch (error) {
      setPastedStatus(
        error instanceof Error ? error.message : "Unable to save playbook.",
      );
    }
  }

  async function enrichPastedPlaybook() {
    if (!pastedSource || !pastedAnalysis) return;
    setEnrichmentLoading(true);
    setPastedStatus("Creating a source-grounded enrichment preview…");
    try {
      const response = await fetch(
        `${API_BASE}/api/pasted-lessons/${pastedSource.source_id}/enrich`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(enrichmentOptions),
        },
      );
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.error || "Unable to enrich playbook.");
      }
      setEnrichment(payload);
      setPastedStatus(
        payload.status === "failed"
          ? "Enrichment failed. The baseline remains available."
          : "Enrichment preview ready. Review it before approval.",
      );
    } catch (error) {
      setPastedStatus(
        error instanceof Error ? error.message : "Enrichment failed.",
      );
    } finally {
      setEnrichmentLoading(false);
    }
  }

  async function approveEnrichment() {
    if (!enrichment || enrichment.status === "failed") return;
    setPastedStatus("Saving teacher-approved enrichment…");
    try {
      const response = await fetch(
        `${API_BASE}/api/playbook-enrichments/${enrichment.enrichment_id}/approve`,
        { method: "POST", headers: { "Content-Type": "application/json" } },
      );
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.error || "Unable to approve enrichment.");
      }
      setPastedStatus(`Approved enrichment saved: ${payload.enrichment_id}`);
      setApprovedEnrichments((current) => [
        ...current.filter(
          (value) => value.enrichment_id !== payload.enrichment_id
        ),
        payload,
      ]);
      setSelectedApprovedEnrichment(payload.enrichment_id);
    } catch (error) {
      setPastedStatus(
        error instanceof Error ? error.message : "Approval failed.",
      );
    }
  }

  async function buildPresentationSpec() {
    if (!selectedApprovedEnrichment) return;
    setPresentationLoading(true);
    setPresentationStatus("Building deterministic presentation plan…");
    try {
      const options = {
        ...presentationOptions,
        target_slide_count:
          presentationOptions.target_slide_count
            ? Number(presentationOptions.target_slide_count) : null,
        maximum_slide_count:
          presentationOptions.maximum_slide_count
            ? Number(presentationOptions.maximum_slide_count) : null,
      };
      const response = await fetch(
        `${API_BASE}/api/teacher-playbooks/${selectedApprovedEnrichment}/presentation-spec`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(options),
        },
      );
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.error || "Unable to build presentation plan.");
      }
      setPresentationResult(payload);
      setPresentationStatus(
        payload.validation_report.valid
          ? "Presentation plan is valid and ready for teacher review."
          : "Presentation plan needs attention before approval.",
      );
    } catch (error) {
      setPresentationStatus(
        error instanceof Error ? error.message : "Planning failed.",
      );
    } finally {
      setPresentationLoading(false);
    }
  }

  async function approvePresentationSpec() {
    if (!presentationResult?.validation_report.valid) return;
    const presentationId =
      presentationResult.presentation_spec.presentation_id;
    setPresentationStatus("Saving approved presentation specification…");
    try {
      const response = await fetch(
        `${API_BASE}/api/presentation-specs/${presentationId}/approve`,
        { method: "POST", headers: { "Content-Type": "application/json" } },
      );
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.error || "Unable to approve presentation plan.");
      }
      setPresentationResult((current) => current ? {
        ...current,
        presentation_spec: payload,
      } : current);
      setPresentationStatus(
        `Approved presentation specification saved: ${presentationId}`,
      );
      setApprovedPresentationSpecs((current) => [
        ...current.filter(
          (value) => value.presentation_id !== payload.presentation_id,
        ),
        payload,
      ]);
      setSelectedPresentationSpec(payload.presentation_id);
    } catch (error) {
      setPresentationStatus(
        error instanceof Error ? error.message : "Approval failed.",
      );
    }
  }

  async function buildRendererInstructions() {
    if (!selectedPresentationSpec) return;
    setRendererLoading(true);
    setRendererStatus("Compiling provider-neutral renderer instructions…");
    try {
      const response = await fetch(
        `${API_BASE}/api/presentation-specs/${selectedPresentationSpec}/renderer-package`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({}),
        },
      );
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(
          payload.error || "Unable to compile renderer instructions.",
        );
      }
      setRendererResult(payload);
      setRendererStatus(
        payload.validation_report.valid
          ? "Renderer instructions are valid and ready for review."
          : "Renderer instructions need attention before approval.",
      );
    } catch (error) {
      setRendererStatus(
        error instanceof Error ? error.message : "Compilation failed.",
      );
    } finally {
      setRendererLoading(false);
    }
  }

  async function approveRendererInstructions() {
    if (!rendererResult?.instruction_package.validation_report.valid) return;
    const packageId = rendererResult.instruction_package.package_id;
    setRendererStatus("Rebuilding, validating, and saving instructions…");
    try {
      const response = await fetch(
        `${API_BASE}/api/renderer-packages/${packageId}/approve`,
        { method: "POST", headers: { "Content-Type": "application/json" } },
      );
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(
          payload.error || "Unable to approve renderer instructions.",
        );
      }
      setRendererResult((current) => current ? {
        ...current,
        instruction_package: payload,
      } : current);
      setRendererStatus(`Approved renderer package saved: ${packageId}`);
    } catch (error) {
      setRendererStatus(
        error instanceof Error ? error.message : "Approval failed.",
      );
    }
  }

  async function movePresentationSlide(
    index: number,
    direction: -1 | 1,
  ) {
    if (!presentationResult) return;
    const slides = presentationResult.presentation_spec.slides;
    const target = index + direction;
    if (target < 0 || target >= slides.length) return;
    const reordered = [...slides];
    [reordered[index], reordered[target]] = [
      reordered[target], reordered[index],
    ];
    setPresentationStatus("Checking instructional sequence…");
    try {
      const response = await fetch(
        `${API_BASE}/api/presentation-specs/${
          presentationResult.presentation_spec.presentation_id
        }/reorder`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            ordered_slide_ids: reordered.map((slide) => slide.slide_id),
          }),
        },
      );
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(
          payload.error || "That move would break instructional order.",
        );
      }
      setPresentationResult(payload);
      setPresentationStatus("Slide order updated and revalidated.");
    } catch (error) {
      setPresentationStatus(
        error instanceof Error
          ? error.message : "That move is not allowed.",
      );
    }
  }

  async function publishTeachingPackage(
    target: "google-doc" | "google-slides",
  ) {
    if (!lesson) return;
    const response = await fetch(
      `${API_BASE}/api/teaching-package/publish`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          lesson_number: lesson.number,
          target,
        }),
      },
    );
    const payload = await response.json();
    if (response.ok && payload.url) {
      window.open(payload.url, "_blank", "noopener,noreferrer");
    } else {
      setCopyStatus(payload.error || "Google publishing is unavailable.");
    }
  }

  async function openOutput(target: "folder" | "bundle") {
    if (!job?.request_id) return;
    await fetch(`${API_BASE}/api/open`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ request_id: job.request_id, target }),
    });
  }

  async function copyGammaPrompt() {
    if (!job?.request_id) return;
    setCopyStatus("Copying…");
    try {
      const response = await fetch(
        `${API_BASE}/api/artifacts/${job.request_id}/gamma`,
      );
      if (!response.ok) throw new Error("Gamma prompt is unavailable.");
      const prompt = await response.text();
      try {
        await navigator.clipboard.writeText(prompt);
      } catch {
        const fallback = await fetch(`${API_BASE}/api/clipboard`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ request_id: job.request_id }),
        });
        if (!fallback.ok) throw new Error("Clipboard access is unavailable.");
      }
      setCopyStatus("Gamma prompt copied");
    } catch {
      setCopyStatus("Unable to copy prompt");
    }
  }

  function openGamma() {
    window.open(GAMMA_URL, "_blank", "noopener,noreferrer");
  }

  function generateAnother() {
    setJobId("");
    setJob(null);
    setCopyStatus("");
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
            <span>Version 0.2</span>
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
          <button
            className={`curriculum-item pasted-workspace-link ${
              view === "pasted" ? "active" : ""
            }`}
            onClick={() => {
              setView("pasted");
              setPastedStatus("");
            }}
            data-testid="pasted-lesson-workspace"
          >
            <span className="curriculum-monogram">+</span>
            <span>
              <strong>Paste a lesson</strong>
              <small>Build a preliminary playbook</small>
            </span>
          </button>
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
                    <button
                      className="secondary-button"
                      onClick={generateTeachingPackage}
                      data-testid="generate-teaching-package"
                    >
                      Generate Teaching Package
                    </button>
                    <p className="button-note">
                      Creates a validated Teacher Companion and synchronized
                      student slides from existing Lesson Intelligence.
                    </p>
                  </aside>
                )}
              </div>
            </>
          )}

          {!loading && !connectionError && view === "pasted" && (
            <div
              className="pasted-lesson-workspace"
              data-testid="pasted-lesson-view"
            >
              <div className="page-heading">
                <div>
                  <span className="eyebrow">Pasted lesson intake</span>
                  <h1>Build a preliminary Teacher Playbook</h1>
                  <p>
                    Paste one lesson exactly as provided. TeacherOS saves the
                    original source separately from deterministic extracted
                    information and flags anything it cannot classify.
                  </p>
                </div>
              </div>

              <section className="pasted-form-card">
                <div className="form-grid">
                  <label>
                    Grade
                    <input
                      value={pastedForm.grade}
                      onChange={(event) =>
                        updatePastedField("grade", event.target.value)
                      }
                    />
                  </label>
                  <label>
                    Unit
                    <input
                      value={pastedForm.unit}
                      onChange={(event) =>
                        updatePastedField("unit", event.target.value)
                      }
                    />
                  </label>
                  <label>
                    Lesson number
                    <input
                      type="number"
                      min="1"
                      value={pastedForm.lesson_number}
                      onChange={(event) =>
                        updatePastedField(
                          "lesson_number",
                          event.target.value,
                        )
                      }
                    />
                  </label>
                  <label className="wide-field">
                    Lesson title
                    <input
                      value={pastedForm.lesson_title}
                      onChange={(event) =>
                        updatePastedField(
                          "lesson_title",
                          event.target.value,
                        )
                      }
                      placeholder="Enter the exact lesson title"
                    />
                  </label>
                  <label>
                    Teacher Guide start page
                    <input
                      type="number"
                      min="1"
                      value={pastedForm.teacher_guide_page_start}
                      onChange={(event) =>
                        updatePastedField(
                          "teacher_guide_page_start",
                          event.target.value,
                        )
                      }
                    />
                  </label>
                  <label>
                    Teacher Guide end page
                    <input
                      type="number"
                      min="1"
                      value={pastedForm.teacher_guide_page_end}
                      onChange={(event) =>
                        updatePastedField(
                          "teacher_guide_page_end",
                          event.target.value,
                        )
                      }
                    />
                  </label>
                </div>

                <label className="text-source-field">
                  Teacher Guide text
                  <span>Required · preserved exactly</span>
                  <textarea
                    value={pastedForm.teacher_guide_text}
                    onChange={(event) =>
                      updatePastedField(
                        "teacher_guide_text",
                        event.target.value,
                      )
                    }
                    placeholder="Paste the complete lesson text here."
                    rows={16}
                  />
                </label>
                <div className="optional-source-grid">
                  <label className="text-source-field">
                    Student Reader text
                    <span>Optional</span>
                    <textarea
                      value={pastedForm.student_reader_text}
                      onChange={(event) =>
                        updatePastedField(
                          "student_reader_text",
                          event.target.value,
                        )
                      }
                      rows={7}
                    />
                  </label>
                  <label className="text-source-field">
                    Activity Book text
                    <span>Optional</span>
                    <textarea
                      value={pastedForm.activity_book_text}
                      onChange={(event) =>
                        updatePastedField(
                          "activity_book_text",
                          event.target.value,
                        )
                      }
                      rows={7}
                    />
                  </label>
                </div>
                <label className="text-source-field">
                  Source notes
                  <span>Optional</span>
                  <textarea
                    value={pastedForm.source_notes}
                    onChange={(event) =>
                      updatePastedField("source_notes", event.target.value)
                    }
                    rows={3}
                  />
                </label>
                <div className="pasted-actions">
                  <button
                    className="primary-button"
                    onClick={savePastedSource}
                    disabled={
                      !pastedForm.lesson_title.trim()
                      || !pastedForm.teacher_guide_text
                    }
                    data-testid="save-pasted-source"
                  >
                    Save Source
                  </button>
                  <button
                    className="secondary-button"
                    onClick={analyzePastedSource}
                    disabled={!pastedSource}
                    data-testid="analyze-pasted-source"
                  >
                    Run Baseline Analysis
                  </button>
                  <button
                    className="secondary-button"
                    onClick={savePastedPlaybook}
                    disabled={!pastedAnalysis}
                    data-testid="save-preliminary-playbook"
                  >
                    Save Preliminary Playbook
                  </button>
                  <button
                    className="secondary-button"
                    onClick={enrichPastedPlaybook}
                    disabled={!pastedAnalysis || enrichmentLoading}
                    data-testid="enrich-playbook"
                  >
                    {enrichmentLoading ? "Enriching…" : "Enrich Playbook"}
                  </button>
                </div>
                {pastedAnalysis && (
                  <fieldset className="enrichment-options">
                    <legend>Enrichment options</legend>
                    <label>
                      Detail
                      <select
                        value={enrichmentOptions.detail_level}
                        onChange={(event) => setEnrichmentOptions((current) => ({
                          ...current,
                          detail_level: event.target.value,
                        }))}
                      >
                        <option value="comprehensive">Comprehensive</option>
                        <option value="focused">Focused</option>
                      </select>
                    </label>
                    {[
                      ["include_teacher_scripts", "Teacher scripts"],
                      ["include_possible_student_responses", "Student responses"],
                      ["include_misconceptions", "Misconceptions"],
                      ["include_eld_supports", "ELD supports"],
                      ["include_checks_for_understanding", "Checks for understanding"],
                      ["include_transition_language", "Transitions"],
                      ["include_teacher_reflection", "Teacher reflection"],
                    ].map(([key, label]) => (
                      <label key={key}>
                        <input
                          type="checkbox"
                          checked={
                            enrichmentOptions[
                              key as keyof typeof enrichmentOptions
                            ] as boolean
                          }
                          onChange={(event) =>
                            setEnrichmentOptions((current) => ({
                              ...current,
                              [key]: event.target.checked,
                            }))
                          }
                        />
                        {label}
                      </label>
                    ))}
                    <p>
                      Original wording and strict source grounding are always
                      enabled for teacher review.
                    </p>
                  </fieldset>
                )}
                {pastedStatus && (
                  <p className="pasted-status" role="status">
                    {pastedStatus}
                  </p>
                )}
              </section>

              {pastedSource && (
                <section className="source-review-panel">
                  <div>
                    <span className="eyebrow">Original source text</span>
                    <h2>{pastedSource.lesson_title}</h2>
                    <p>
                      Grade {pastedSource.grade} · Unit {pastedSource.unit} ·
                      Lesson {pastedSource.lesson_number}
                    </p>
                  </div>
                  <pre>{pastedSource.teacher_guide_text}</pre>
                </section>
              )}

              {pastedAnalysis && (
                <section className="analysis-review">
                  <div className="review-heading">
                    <div>
                      <span className="eyebrow">
                        Extracted structured information
                      </span>
                      <h2>Preliminary Teacher Playbook</h2>
                    </div>
                    <div className="analysis-stats">
                      <span>
                        <strong>
                          {
                            pastedAnalysis.extraction_summary
                              .detected_day_count
                          }
                        </strong>
                        days
                      </span>
                      <span>
                        <strong>
                          {
                            pastedAnalysis.extraction_summary
                              .detected_activity_count
                          }
                        </strong>
                        activities
                      </span>
                      <span>
                        <strong>
                          {
                            pastedAnalysis.extraction_summary
                              .detected_reference_count
                          }
                        </strong>
                        references
                      </span>
                    </div>
                  </div>

                  <div className="analysis-grid">
                    <article>
                      <h3>Objectives</h3>
                      {pastedAnalysis.playbook.objectives.length ? (
                        <ul>
                          {pastedAnalysis.playbook.objectives.map((value) => (
                            <li key={value}>{value}</li>
                          ))}
                        </ul>
                      ) : (
                        <p className="missing-copy">Not found in source.</p>
                      )}
                    </article>
                    <article>
                      <h3>Essential question</h3>
                      <p>
                        {pastedAnalysis.playbook.essential_question || (
                          <span className="missing-copy">
                            Not found in source.
                          </span>
                        )}
                      </p>
                    </article>
                    <article>
                      <h3>Success criteria</h3>
                      {pastedAnalysis.playbook.success_criteria.length ? (
                        <ul>
                          {pastedAnalysis.playbook.success_criteria.map(
                            (value) => <li key={value}>{value}</li>,
                          )}
                        </ul>
                      ) : (
                        <p className="missing-copy">Not found in source.</p>
                      )}
                    </article>
                    <article>
                      <h3>Materials</h3>
                      <p>
                        {pastedAnalysis.playbook.materials.join(" · ") || (
                          <span className="missing-copy">
                            Not found in source.
                          </span>
                        )}
                      </p>
                    </article>
                    <article>
                      <h3>Vocabulary</h3>
                      <div className="tag-list">
                        {pastedAnalysis.playbook.vocabulary.map((value) => (
                          <span key={value.term}>{value.term}</span>
                        ))}
                      </div>
                      {!pastedAnalysis.playbook.vocabulary.length && (
                        <p className="missing-copy">Not found in source.</p>
                      )}
                    </article>
                    <article>
                      <h3>Source references</h3>
                      <ul>
                        {pastedAnalysis.playbook.source_references.map(
                          (reference, index) => (
                            <li key={`${reference.source_type}-${index}`}>
                              {reference.source_type.replaceAll("_", " ")}
                              {reference.page_start !== null
                                ? ` pp. ${reference.page_start}${
                                    reference.page_end !== reference.page_start
                                      ? `–${reference.page_end}`
                                      : ""
                                  }`
                                : ""}
                              {reference.activity_reference
                                ? ` · ${reference.activity_reference}`
                                : ""}
                            </li>
                          ),
                        )}
                      </ul>
                    </article>
                  </div>

                  <div className="activity-review-list">
                    <h3>Activities</h3>
                    {pastedAnalysis.playbook.activities.map(
                      (activity, index) => (
                        <article key={activity.activity_id}>
                          <div className="activity-review-header">
                            <span>{String(index + 1).padStart(2, "0")}</span>
                            <div>
                              <h4>{activity.title}</h4>
                              <p>
                                {activity.instructional_day
                                  ? `Day ${activity.instructional_day}`
                                  : "Day not identified"}
                                {" · "}
                                {activity.duration_minutes !== null
                                  ? `${activity.duration_minutes} minutes`
                                  : "Timing not identified"}
                              </p>
                            </div>
                          </div>
                          {activity.purpose && (
                            <p>
                              <strong>Purpose:</strong> {activity.purpose}
                            </p>
                          )}
                          {activity.questions.map((question) => (
                            <p key={question.prompt}>
                              <strong>Question:</strong> {question.prompt}
                            </p>
                          ))}
                        </article>
                      ),
                    )}
                    {!pastedAnalysis.playbook.activities.length && (
                      <p className="missing-copy">
                        No timed activity headings were identified.
                      </p>
                    )}
                  </div>

                  <div className="review-alert-grid">
                    <article className="warning-panel">
                      <h3>Warnings and missing information</h3>
                      {pastedAnalysis.warnings.length ? (
                        <ul>
                          {pastedAnalysis.warnings.map((warning) => (
                            <li key={warning.code}>
                              <code>{warning.code}</code>
                              <span>{warning.message}</span>
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <p>No baseline extraction warnings.</p>
                      )}
                    </article>
                    <article className="unclassified-panel">
                      <h3>Unclassified source text</h3>
                      {pastedAnalysis.unclassified_sections.length ? (
                        <pre>
                          {pastedAnalysis.unclassified_sections.join("\n")}
                        </pre>
                      ) : (
                        <p>All nonblank source lines were classified.</p>
                      )}
                    </article>
                  </div>
                </section>
              )}
              {pastedAnalysis && enrichment && (
                <section
                  className="enrichment-review"
                  data-testid="enrichment-review"
                >
                  <div className="review-heading">
                    <div>
                      <span className="eyebrow">Teacher review required</span>
                      <h2>Baseline and enriched playbook</h2>
                      <p>
                        Source-backed facts stay unchanged. Added guidance is
                        labeled “Generated guidance — review.”
                      </p>
                    </div>
                    <span className={`enrichment-state ${enrichment.status}`}>
                      {enrichment.status}
                    </span>
                  </div>
                  <div className="enrichment-comparison">
                    <article>
                      <h3>Deterministic baseline</h3>
                      {pastedAnalysis.playbook.activities.map((activity) => (
                        <div key={activity.activity_id}>
                          <h4>{activity.title}</h4>
                          <p>{activity.purpose || "No purpose extracted."}</p>
                        </div>
                      ))}
                    </article>
                    <article>
                      <h3>Enriched preview</h3>
                      {enrichment.enriched_playbook.activities.map((activity) => (
                        <div key={activity.activity_id}>
                          <h4>{activity.title}</h4>
                          <p>{activity.purpose || "No purpose extracted."}</p>
                          {activity.teacher_script.map((line) => (
                            <p className="generated-guidance" key={line}>
                              {line}
                            </p>
                          ))}
                        </div>
                      ))}
                    </article>
                  </div>
                  <div className="review-alert-grid">
                    <article className="grounding-panel">
                      <h3>Grounding report</h3>
                      <p>
                        {enrichment.grounding_report.source_backed_fields.length}
                        {" "}source-backed fields ·{" "}
                        {enrichment.grounding_report.inferred_fields.length}
                        {" "}inferred fields
                      </p>
                      <p>
                        {enrichment.grounding_report.source_coverage_by_activity
                          .filter((value) => value.fully_retained).length}
                        {" "}activities retain all source references
                      </p>
                    </article>
                    <article className="warning-panel">
                      <h3>Warnings and rejected claims</h3>
                      {enrichment.unsupported_claims.map((claim) => (
                        <p key={`${claim.field_path}-${claim.claim}`}>
                          <strong>{claim.field_path}</strong>: {claim.reason}
                        </p>
                      ))}
                      {enrichment.warnings.map((warning) => (
                        <p key={`${warning.code}-${warning.field}`}>
                          <strong>{warning.code}</strong>: {warning.message}
                        </p>
                      ))}
                      {!enrichment.unsupported_claims.length
                        && !enrichment.warnings.length && <p>No warnings.</p>}
                    </article>
                  </div>
                  {enrichment.status === "failed" ? (
                    <p className="fallback-message">
                      {enrichment.failure_reason} The preliminary playbook above
                      remains usable and unchanged.
                    </p>
                  ) : (
                    <button
                      className="primary-button"
                      onClick={approveEnrichment}
                      data-testid="approve-enrichment"
                    >
                      Approve and Save Enriched Playbook
                    </button>
                  )}
                </section>
              )}
              <section
                className="presentation-planner"
                data-testid="presentation-spec-planner"
              >
                <div className="review-heading">
                  <div>
                    <span className="eyebrow">Presentation planning</span>
                    <h2>Build a renderer-neutral slide specification</h2>
                    <p>
                      Select a teacher-approved enriched playbook. This creates
                      a structured plan only; it does not render slides.
                    </p>
                  </div>
                </div>
                <div className="presentation-config">
                  <label className="wide-field">
                    Approved enriched playbook
                    <select
                      value={selectedApprovedEnrichment}
                      onChange={(event) => {
                        setSelectedApprovedEnrichment(event.target.value);
                        setPresentationResult(null);
                      }}
                      data-testid="approved-playbook-select"
                    >
                      <option value="">Select an approved playbook</option>
                      {approvedEnrichments.map((value) => (
                        <option
                          value={value.enrichment_id}
                          key={value.enrichment_id}
                        >
                          Grade {value.enriched_playbook.lesson_metadata.grade}
                          {" · Unit "}
                          {value.enriched_playbook.lesson_metadata.unit}
                          {" · Lesson "}
                          {value.enriched_playbook.lesson_metadata.lesson_number}
                          {" · "}
                          {value.enriched_playbook.lesson_metadata.lesson_title}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Target slides
                    <input
                      type="number"
                      min="1"
                      value={presentationOptions.target_slide_count}
                      onChange={(event) =>
                        setPresentationOptions((current) => ({
                          ...current,
                          target_slide_count: event.target.value,
                        }))
                      }
                      placeholder="Optional"
                    />
                  </label>
                  <label>
                    Maximum slides
                    <input
                      type="number"
                      min="1"
                      value={presentationOptions.maximum_slide_count}
                      onChange={(event) =>
                        setPresentationOptions((current) => ({
                          ...current,
                          maximum_slide_count: event.target.value,
                        }))
                      }
                      placeholder="Optional"
                    />
                  </label>
                  <label>
                    Detail
                    <select
                      value={presentationOptions.detail_level}
                      onChange={(event) =>
                        setPresentationOptions((current) => ({
                          ...current,
                          detail_level: event.target.value,
                        }))
                      }
                    >
                      <option value="comprehensive">Comprehensive</option>
                      <option value="focused">Focused</option>
                    </select>
                  </label>
                </div>
                <div className="presentation-option-grid">
                  {[
                    ["include_agenda", "Agenda"],
                    ["include_objectives", "Objectives"],
                    ["include_vocabulary", "Vocabulary"],
                    ["include_eld_supports", "ELD supports"],
                    ["include_homework", "Homework"],
                    ["include_exit_ticket", "Exit ticket"],
                    ["include_visual_prompts", "Visual direction"],
                  ].map(([key, label]) => (
                    <label key={key}>
                      <input
                        type="checkbox"
                        checked={
                          presentationOptions[
                            key as keyof typeof presentationOptions
                          ] as boolean
                        }
                        onChange={(event) =>
                          setPresentationOptions((current) => ({
                            ...current,
                            [key]: event.target.checked,
                          }))
                        }
                      />
                      {label}
                    </label>
                  ))}
                </div>
                {!approvedEnrichments.length && (
                  <p className="missing-copy">
                    Approve an enriched playbook before planning a presentation.
                  </p>
                )}
                <div className="pasted-actions">
                  <button
                    className="primary-button"
                    onClick={buildPresentationSpec}
                    disabled={
                      !selectedApprovedEnrichment || presentationLoading
                    }
                    data-testid="build-presentation-spec"
                  >
                    {presentationLoading
                      ? "Building plan…"
                      : "Generate Presentation Specification"}
                  </button>
                </div>
                {presentationStatus && (
                  <p className="pasted-status" role="status">
                    {presentationStatus}
                  </p>
                )}

                {presentationResult && (
                  <div
                    className="presentation-review"
                    data-testid="presentation-spec-review"
                  >
                    <div className="presentation-summary">
                      <span>
                        <strong>
                          {presentationResult.presentation_spec.slides.length}
                        </strong>
                        slides
                      </span>
                      <span>
                        <strong>
                          {
                            presentationResult.presentation_spec
                              .estimated_total_minutes
                          }
                        </strong>
                        minutes
                      </span>
                      <span>
                        <strong>
                          {
                            presentationResult.activity_coverage.filter(
                              (value) => value.covered,
                            ).length
                          }
                        </strong>
                        activities covered
                      </span>
                      <span>
                        <strong>
                          {presentationResult.source_coverage.complete
                            ? "Complete" : "Incomplete"}
                        </strong>
                        source coverage
                      </span>
                    </div>
                    <p className="locked-order-note">
                      Instructional-day and activity order is protected. Slides
                      cannot be reordered into an invalid lesson sequence.
                    </p>
                    <div className="slide-spec-list">
                      {presentationResult.presentation_spec.slides.map(
                        (slide, slideIndex) => (
                          <article key={slide.slide_id}>
                            <header>
                              <span>
                                {String(slide.slide_number).padStart(2, "0")}
                              </span>
                              <div>
                                <small>
                                  {slide.slide_type.replaceAll("_", " ")}
                                  {" · "}
                                  {slide.layout_type.replaceAll("_", " ")}
                                </small>
                                <h3>{slide.title}</h3>
                                <p>
                                  {slide.instructional_day
                                    ? `Day ${slide.instructional_day} · `
                                    : ""}
                                  {slide.estimated_minutes !== null
                                    ? `${slide.estimated_minutes} min`
                                    : "Structural slide"}
                                </p>
                              </div>
                              {slide.required && <b>Required</b>}
                              <div className="slide-order-actions">
                                <button
                                  onClick={() =>
                                    movePresentationSlide(slideIndex, -1)
                                  }
                                  disabled={
                                    slideIndex === 0
                                    || presentationResult.presentation_spec
                                      .approval_status === "approved"
                                  }
                                  aria-label={`Move ${slide.title} earlier`}
                                >
                                  ↑
                                </button>
                                <button
                                  onClick={() =>
                                    movePresentationSlide(slideIndex, 1)
                                  }
                                  disabled={
                                    slideIndex
                                      === presentationResult.presentation_spec
                                        .slides.length - 1
                                    || presentationResult.presentation_spec
                                      .approval_status === "approved"
                                  }
                                  aria-label={`Move ${slide.title} later`}
                                >
                                  ↓
                                </button>
                              </div>
                            </header>
                            <div className="slide-review-grid">
                              <section>
                                <h4>Student-facing content</h4>
                                {slide.student_facing_content.map((element) => (
                                  <div key={element.element_id}>
                                    <small>
                                      {element.element_type.replaceAll("_", " ")}
                                      {" · "}
                                      {element.grounding_label.replaceAll("_", " ")}
                                    </small>
                                    {element.text && <p>{element.text}</p>}
                                    {!!element.items.length && (
                                      <ul>
                                        {element.items.map((item) => (
                                          <li key={item}>{item}</li>
                                        ))}
                                      </ul>
                                    )}
                                  </div>
                                ))}
                              </section>
                              <section>
                                <h4>Speaker notes</h4>
                                {slide.speaker_notes.purpose && (
                                  <p>{slide.speaker_notes.purpose}</p>
                                )}
                                {slide.speaker_notes.teacher_script.map(
                                  (line) => <p key={line}>{line}</p>,
                                )}
                                {slide.speaker_notes.transition_language && (
                                  <p>
                                    <strong>Transition:</strong>{" "}
                                    {slide.speaker_notes.transition_language}
                                  </p>
                                )}
                              </section>
                              <section>
                                <h4>Sources and visual direction</h4>
                                {slide.source_references.map(
                                  (reference, index) => (
                                    <p key={`${reference.source_type}-${index}`}>
                                      {reference.source_type.replaceAll("_", " ")}
                                      {reference.page_start !== null
                                        ? ` pp. ${reference.page_start}${
                                            reference.page_end
                                              !== reference.page_start
                                              ? `–${reference.page_end}`
                                              : ""
                                          }`
                                        : ""}
                                      {reference.activity_reference
                                        ? ` · ${reference.activity_reference}`
                                        : ""}
                                    </p>
                                  ),
                                )}
                                {slide.visual_spec?.description && (
                                  <p>{slide.visual_spec.description}</p>
                                )}
                                <div className="tag-list">
                                  {slide.grounding_labels.map((label) => (
                                    <span key={label}>
                                      {label.replaceAll("_", " ")}
                                    </span>
                                  ))}
                                </div>
                              </section>
                            </div>
                          </article>
                        ),
                      )}
                    </div>
                    <div className="review-alert-grid">
                      <article className="grounding-panel">
                        <h3>Coverage</h3>
                        <p>
                          {presentationResult.activity_coverage.filter(
                            (value) => value.covered,
                          ).length}
                          /{presentationResult.activity_coverage.length}
                          {" "}required activities represented
                        </p>
                        <p>
                          {
                            presentationResult.source_coverage
                              .retained_reference_count
                          }
                          /{
                            presentationResult.source_coverage
                              .expected_reference_count
                          }
                          {" "}source references retained
                        </p>
                        {!!presentationResult.missing_sections.length && (
                          <p>
                            Missing:{" "}
                            {presentationResult.missing_sections.join(", ")}
                          </p>
                        )}
                      </article>
                      <article className="warning-panel">
                        <h3>Validation</h3>
                        <p>
                          Status:{" "}
                          {presentationResult.validation_report.status}
                        </p>
                        {presentationResult.validation_report.issues.map(
                          (issue) => (
                            <p key={`${issue.code}-${issue.slide_id}`}>
                              <strong>{issue.code}</strong>: {issue.message}
                            </p>
                          ),
                        )}
                        {presentationResult.warnings.map((warning) => (
                          <p key={warning.code}>
                            <strong>{warning.code}</strong>: {warning.message}
                          </p>
                        ))}
                      </article>
                    </div>
                    <button
                      className="primary-button"
                      onClick={approvePresentationSpec}
                      disabled={
                        !presentationResult.validation_report.valid
                        || presentationResult.presentation_spec
                          .approval_status === "approved"
                      }
                      data-testid="approve-presentation-spec"
                    >
                      {presentationResult.presentation_spec.approval_status
                        === "approved"
                        ? "Presentation Specification Approved"
                        : "Approve and Save Presentation Specification"}
                    </button>
                  </div>
                )}
              </section>
              <section
                className="renderer-instruction-planner"
                data-testid="renderer-instruction-planner"
              >
                <div className="review-heading">
                  <div>
                    <span className="eyebrow">Renderer handoff</span>
                    <h2>Compile renderer-neutral instructions</h2>
                    <p>
                      Convert an approved Presentation Specification into a
                      coordinate-based instruction package. This review does
                      not create or publish a presentation.
                    </p>
                  </div>
                </div>
                <label className="renderer-spec-select">
                  Approved Presentation Specification
                  <select
                    value={selectedPresentationSpec}
                    onChange={(event) => {
                      setSelectedPresentationSpec(event.target.value);
                      setRendererResult(null);
                      setRendererStatus("");
                    }}
                    data-testid="approved-presentation-select"
                  >
                    <option value="">Select an approved specification</option>
                    {approvedPresentationSpecs.map((value) => (
                      <option
                        value={value.presentation_id}
                        key={value.presentation_id}
                      >
                        Lesson {value.presentation_title}
                        {" · "}{value.slides.length} slides
                      </option>
                    ))}
                  </select>
                </label>
                {!approvedPresentationSpecs.length && (
                  <p className="missing-copy">
                    Approve a Presentation Specification before compiling
                    renderer instructions.
                  </p>
                )}
                <button
                  className="primary-button"
                  onClick={buildRendererInstructions}
                  disabled={!selectedPresentationSpec || rendererLoading}
                  data-testid="build-renderer-instructions"
                >
                  {rendererLoading
                    ? "Compiling instructions…"
                    : "Build Renderer Instruction Package"}
                </button>
                {rendererStatus && (
                  <p className="pasted-status" role="status">
                    {rendererStatus}
                  </p>
                )}

                {rendererResult && (
                  <div
                    className="renderer-instruction-review"
                    data-testid="renderer-instruction-review"
                  >
                    <div className="presentation-summary">
                      <span>
                        <strong>
                          {
                            rendererResult.instruction_package
                              .validation_report.represented_slide_count
                          }
                          /{
                            rendererResult.instruction_package
                              .validation_report.expected_slide_count
                          }
                        </strong>
                        slides preserved
                      </span>
                      <span>
                        <strong>
                          {rendererResult.instruction_package.canvas.width}
                          {" × "}
                          {rendererResult.instruction_package.canvas.height}
                        </strong>
                        {rendererResult.instruction_package.canvas.units}
                      </span>
                      <span>
                        <strong>
                          {rendererResult.instruction_package
                            .asset_manifest.filter(
                              (asset) => asset.status !== "not_required",
                            ).length}
                        </strong>
                        unresolved assets
                      </span>
                      <span>
                        <strong>{rendererResult.overflow_risks.length}</strong>
                        overflow warnings
                      </span>
                    </div>
                    <div className="renderer-contract-summary">
                      <p>
                        <strong>Contract:</strong>{" "}
                        {
                          rendererResult.instruction_package
                            .renderer_contract_version
                        }
                      </p>
                      <p>
                        <strong>Theme:</strong>{" "}
                        {rendererResult.instruction_package.theme.theme_id}
                        {" · "}
                        {
                          rendererResult.instruction_package.theme
                            .heading_font_family
                        }
                        {" / "}
                        {
                          rendererResult.instruction_package.theme
                            .body_font_family
                        }
                      </p>
                      <p>
                        <strong>Fonts:</strong>{" "}
                        {rendererResult.instruction_package.font_manifest
                          .map((font) => font.family).join(", ")}
                      </p>
                    </div>
                    <div className="renderer-slide-list">
                      {rendererResult.instruction_package.slides.map(
                        (slide) => {
                          const slideAssets =
                            rendererResult.instruction_package.asset_manifest
                              .filter(
                                (asset) => asset.slide_id === slide.slide_id,
                              );
                          const slideWarnings =
                            rendererResult.overflow_risks.filter(
                              (warning) =>
                                warning.slide_id === slide.slide_id,
                            );
                          return (
                            <article key={slide.slide_id}>
                              <header>
                                <span>
                                  {String(slide.slide_number).padStart(2, "0")}
                                </span>
                                <div>
                                  <small>
                                    {slide.slide_type.replaceAll("_", " ")}
                                    {" · "}
                                    {slide.layout_type.replaceAll("_", " ")}
                                  </small>
                                  <h3>{slide.text_blocks[0]?.text}</h3>
                                  <p>
                                    {slide.timing !== null
                                      ? `${slide.timing} min`
                                      : "Structural slide"}
                                    {slide.sequence_group
                                      ? ` · ${slide.sequence_group}`
                                      : ""}
                                  </p>
                                </div>
                                {slide.required && <b>Required</b>}
                              </header>
                              <div className="renderer-review-grid">
                                <section>
                                  <h4>Text blocks and coordinates</h4>
                                  {slide.text_blocks.map((block) => (
                                    <div
                                      className="instruction-block"
                                      key={block.block_id}
                                    >
                                      <small>
                                        {block.role.replaceAll("_", " ")}
                                        {" · "}
                                        {block.x}, {block.y} · {block.width}
                                        {" × "}{block.height} in
                                      </small>
                                      <p>{block.text}</p>
                                      <code>
                                        {block.font_family} {block.font_size}pt
                                        {" · "}{block.grounding_label}
                                      </code>
                                    </div>
                                  ))}
                                </section>
                                <section>
                                  <h4>Visuals and assets</h4>
                                  {slide.visual_blocks.map((block) => (
                                    <div
                                      className="instruction-block"
                                      key={block.block_id}
                                    >
                                      <small>
                                        {block.visual_type.replaceAll("_", " ")}
                                        {" · "}
                                        {block.x}, {block.y} · {block.width}
                                        {" × "}{block.height} in
                                      </small>
                                      <p>{block.description}</p>
                                      <code>Alt: {block.alt_text}</code>
                                    </div>
                                  ))}
                                  {slideAssets.map((asset) => (
                                    <p key={asset.asset_id}>
                                      <strong>
                                        {asset.asset_type.replaceAll("_", " ")}
                                      </strong>
                                      {" · "}{asset.status.replaceAll("_", " ")}
                                      <br />{asset.description}
                                    </p>
                                  ))}
                                </section>
                                <section>
                                  <h4>Speaker notes</h4>
                                  <pre>
                                    {slide.notes_payload.plain_text_fallback}
                                  </pre>
                                </section>
                                <section>
                                  <h4>Sources and grounding</h4>
                                  {slide.source_references.map(
                                    (reference, index) => (
                                      <p
                                        key={`${reference.source_type}-${index}`}
                                      >
                                        {reference.source_type
                                          .replaceAll("_", " ")}
                                        {reference.page_start !== null
                                          ? ` pp. ${reference.page_start}${
                                              reference.page_end
                                                !== reference.page_start
                                                ? `–${reference.page_end}`
                                                : ""
                                            }`
                                          : ""}
                                      </p>
                                    ),
                                  )}
                                  <div className="tag-list">
                                    {slide.grounding_labels.map((label) => (
                                      <span key={label}>
                                        {label.replaceAll("_", " ")}
                                      </span>
                                    ))}
                                  </div>
                                  {slideWarnings.map((warning) => (
                                    <p
                                      className="overflow-warning"
                                      key={`${warning.code}-${warning.block_id}`}
                                    >
                                      <strong>{warning.code}</strong>:{" "}
                                      {warning.message}
                                    </p>
                                  ))}
                                </section>
                              </div>
                            </article>
                          );
                        },
                      )}
                    </div>
                    <div className="review-alert-grid">
                      <article className="grounding-panel">
                        <h3>Package validation</h3>
                        <p>
                          Status:{" "}
                          {
                            rendererResult.instruction_package
                              .validation_report.status
                          }
                        </p>
                        <p>
                          Exact slide count:{" "}
                          {rendererResult.instruction_package.validation_report
                            .expected_slide_count ===
                            rendererResult.instruction_package.validation_report
                              .represented_slide_count
                            ? "preserved" : "mismatch"}
                        </p>
                      </article>
                      <article className="warning-panel">
                        <h3>Warnings and unsupported features</h3>
                        {rendererResult.warnings.map((warning) => (
                          <p key={`${warning.code}-${warning.slide_id}`}>
                            <strong>{warning.code}</strong>: {warning.message}
                          </p>
                        ))}
                        {!rendererResult.warnings.length && <p>No warnings.</p>}
                      </article>
                    </div>
                    <button
                      className="primary-button"
                      onClick={approveRendererInstructions}
                      disabled={
                        !rendererResult.instruction_package.validation_report
                          .valid
                        || rendererResult.instruction_package.approval_status
                          === "approved"
                      }
                      data-testid="approve-renderer-instructions"
                    >
                      {rendererResult.instruction_package.approval_status
                        === "approved"
                        ? "Renderer Instructions Approved"
                        : "Approve and Save Renderer Instructions"}
                    </button>
                  </div>
                )}
              </section>
            </div>
          )}

          {view === "generation" && (
            <div className="generation-view" data-testid="generation-view">
              <div className="generation-copy">
                <span className="eyebrow">
                  {job?.kind === "teaching_package"
                    ? "Generating teaching package"
                    : "Generating lesson"}
                </span>
                <h1>{lesson?.title}</h1>
                <p>
                  TeacherOS is building from the imported curriculum. You can
                  leave this screen open while it works.
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
                    <div className="failure-stage">
                      <span>Failed stage</span>
                      <b>{stageLabel(job.failed_stage)}</b>
                    </div>
                    {(job.blocking_findings || []).length > 0 ? (
                      <div className="finding-list">
                        {(job.blocking_findings || []).map((finding) => (
                          <article key={`${finding.code}-${finding.slide_id || ""}`}>
                            <div>
                              <code>{finding.code}</code>
                              <span>{finding.severity}</span>
                            </div>
                            <p>{finding.message}</p>
                          </article>
                        ))}
                      </div>
                    ) : (
                      <p>{job.errors.join(" ")}</p>
                    )}
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
              <h1>
                {job.kind === "teaching_package"
                  ? "Teaching Package Generated Successfully"
                  : "Lesson Generated Successfully"}
              </h1>
              {job.kind === "teaching_package" ? (
                <>
                  <p>
                    {job.student_slides || 0} student slides ·{" "}
                    {job.questions || 0} required questions ·{" "}
                    {job.validation_result === "pass_with_warnings"
                      ? "Validated with review notes"
                      : "Validation passed"}
                  </p>
                  <div className="gamma-handoff">
                    <span className="eyebrow">Lesson at a glance</span>
                    <ol>
                      {(job.agenda || []).map((item) => (
                        <li key={item.order}>
                          {item.official}
                          {item.duration !== null
                            ? ` · ${item.duration} min`
                            : ""}
                        </li>
                      ))}
                    </ol>
                  </div>
                  <div className="gamma-handoff">
                    <span className="eyebrow">Objectives</span>
                    <ol>
                      {(job.objectives || []).map((item, index) => (
                        <li key={`${index}-${item.official}`}>
                          <strong>{item.official}</strong>
                          <br />
                          Student-friendly: {item.student_friendly}
                        </li>
                      ))}
                    </ol>
                    <p>
                      {job.teaching_steps || 0} teaching steps ·{" "}
                      {job.questions || 0} discussion questions ·{" "}
                      {job.student_slides || 0} synchronized slides
                    </p>
                  </div>
                  <div className="complete-actions">
                    <a
                      className="secondary-button action-link"
                      href={`${API_BASE}/api/teaching-package/artifacts/${lesson?.number}/teacher_companion.md`}
                      target="_blank"
                      rel="noreferrer"
                    >
                      Review Teacher Companion
                    </a>
                    <a
                      className="secondary-button action-link"
                      href={`${API_BASE}/api/teaching-package/artifacts/${lesson?.number}/student_slides.md`}
                      target="_blank"
                      rel="noreferrer"
                    >
                      Review Student Slides
                    </a>
                    <a
                      className="primary-button action-link"
                      href={`${API_BASE}/api/teaching-package/artifacts/${lesson?.number}/teacher_companion.md?download=1`}
                      download="teacher_companion.md"
                    >
                      Download Teacher Companion
                    </a>
                    <a
                      className="secondary-button action-link"
                      href={`${API_BASE}/api/teaching-package/artifacts/${lesson?.number}/student_slides.md?download=1`}
                      download="student_slides.md"
                    >
                      Download Student Slides
                    </a>
                    <button
                      className="secondary-button"
                      onClick={() => publishTeachingPackage("google-doc")}
                    >
                      Publish to Google Docs
                    </button>
                    <button
                      className="secondary-button"
                      onClick={() => publishTeachingPackage("google-slides")}
                    >
                      Publish to Google Slides
                    </button>
                    <button className="text-button" onClick={generateAnother}>
                      Generate Again
                    </button>
                  </div>
                  {copyStatus && (
                    <span className="copy-status" role="status">
                      {copyStatus}
                    </span>
                  )}
                </>
              ) : (
                <>
              <p>
                {job.slide_count} slides prepared ·{" "}
                {job.validation_result === "pass_with_warnings"
                  ? "Validated with review notes"
                  : "Validation passed"}
              </p>
              <div className="gamma-handoff">
                <span className="eyebrow">Fastest path to presentation</span>
                <ol>
                  <li>Click Copy Gamma Prompt</li>
                  <li>Click Open Gamma</li>
                  <li>Open Gamma Agent</li>
                  <li>Paste the prompt</li>
                  <li>Generate the presentation</li>
                </ol>
              </div>
              <div className="complete-actions">
                <button
                  className="primary-button"
                  onClick={copyGammaPrompt}
                  data-testid="copy-gamma-prompt"
                >
                  Copy Gamma Prompt
                </button>
                {copyStatus && (
                  <span className="copy-status" role="status">
                    {copyStatus}
                  </span>
                )}
                <a
                  className="secondary-button action-link"
                  href={`${API_BASE}/api/artifacts/${job.request_id}/gamma?download=1`}
                  download="GammaDeckPrompt.md"
                  data-testid="download-gamma-prompt"
                >
                  Download Gamma Prompt
                </a>
                <button
                  className="secondary-button"
                  onClick={openGamma}
                  data-testid="open-gamma"
                >
                  Open Gamma
                </button>
                <button
                  className="secondary-button"
                  onClick={() => openOutput("folder")}
                >
                  Open Output Folder
                </button>
                <button
                  className="secondary-button"
                  onClick={() => openOutput("bundle")}
                >
                  Open Renderer Prompt Bundle
                </button>
                <button className="text-button" onClick={generateAnother}>
                  Generate Again
                </button>
              </div>
              {job.warnings.length > 0 && (
                <p className="review-note">
                  {job.warnings.length} review notes are included with the
                  generated lesson.
                </p>
              )}
                </>
              )}
            </div>
          )}
        </section>
      </div>
    </main>
  );
}
