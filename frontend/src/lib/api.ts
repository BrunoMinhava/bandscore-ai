// Cliente tipado da API local do BandScore AI (FastAPI em 127.0.0.1:8765).

declare global {
  interface Window {
    bandscore?: {
      openFiles: (
        filters: { name: string; extensions: string[] }[]
      ) => Promise<string[]>;
      newWindow: () => void;
      platform: string;
    };
  }
}

export const API_BASE = "http://127.0.0.1:8765";

export interface Page {
  id: number;
  index: number;
  status: string;
  original_url: string;
  processed_url: string;
  report: {
    warnings?: string[];
    steps?: string[];
    skew_angle?: number;
    staves?: number;
    error?: string;
  };
}

export interface Project {
  id: number;
  name: string;
  composer: string;
  ensemble: string;
  source_type: string;
  status: string;
  created_at: string;
  updated_at: string;
  pages: Page[];
}

export interface Capabilities {
  audiveris: string | null;
  musescore: string | null;
  tesseract: string | null;
  device: string;
  onnxruntime: boolean;
  torch: boolean;
  models: string[];
}

export interface PartInfo {
  id: string;
  name: string;
  raw_name: string;
  canonical: string;
  confidence: number;
  measures: number;
  is_percussion: boolean;
}

export interface DoubtfulMeasure {
  measure: number;
  notes: number;
  min_confidence: number;
}

export interface ScoreSummary {
  title: string;
  composer: string;
  pages: number;
  parts: PartInfo[];
  doubtful_measures: Record<string, DoubtfulMeasure[]>;
}

export interface RecognitionResult extends ScoreSummary {
  doubts: number;
  warning?: string | null;
}

export interface Progress {
  idle?: boolean;
  phase?: string;
  phase_label?: string;
  done?: number;
  total?: number;
  percent?: number;
  elapsed_seconds?: number;
  eta_seconds?: number | null;
  finished?: boolean;
  error?: string | null;
  result?: RecognitionResult | null;
}

export interface Doubt {
  note_id: string;
  part: string;
  part_id: string;
  measure: number;
  pitch: string | null;
  confidence: number;
  alternatives: { pitch: string; probability: number }[];
}

export interface ValidationIssue {
  severity: "erro" | "aviso";
  type: string;
  part: string;
  measure: number | null;
  message: string;
}

export interface ValidationReport {
  ok: boolean;
  issues: ValidationIssue[];
  summary: Record<string, number>;
}

export interface PreprocessOptions {
  perspective: boolean;
  shadows: boolean;
  denoise: boolean;
  contrast: boolean;
  deskew: boolean;
  split_double_pages: boolean;
}

export interface ExportedFile {
  name: string;
  url: string;
}

export interface LibraryEntry {
  id: number;
  title: string;
  composer: string;
  ensemble: string;
  year: number | null;
  publisher: string;
  difficulty: string;
  instruments: string[];
  tags: string;
  project_id: number | null;
}

async function j<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(API_BASE + path, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? JSON.stringify(body);
    } catch {
      /* corpo não-JSON */
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

export const fileUrl = (u: string) => (u ? API_BASE + u : "");

export const api = {
  capabilities: () => j<Capabilities>("/api/system/capabilities"),

  recentProjects: () => j<Project[]>("/api/projects/recent"),
  createProject: (body: {
    name: string;
    composer?: string;
    source_type?: string;
  }) => j<Project>("/api/projects", { method: "POST", body: JSON.stringify(body) }),
  getProject: (id: number) => j<Project>(`/api/projects/${id}`),
  deleteProject: (id: number) =>
    j<{ ok: boolean }>(`/api/projects/${id}`, { method: "DELETE" }),

  importPaths: (id: number, paths: string[]) =>
    j<Project>(`/api/imports/${id}/paths`, {
      method: "POST",
      body: JSON.stringify({ paths }),
    }),
  importUpload: async (id: number, files: FileList): Promise<Project> => {
    const form = new FormData();
    Array.from(files).forEach((f) => form.append("files", f));
    const res = await fetch(`${API_BASE}/api/imports/${id}/upload`, {
      method: "POST",
      body: form,
    });
    if (!res.ok) throw new Error((await res.json()).detail ?? res.statusText);
    return res.json();
  },

  startRecognition: (id: number, options: PreprocessOptions) =>
    j<{ started: boolean; pages: number }>(`/api/recognize/${id}/start`, {
      method: "POST",
      body: JSON.stringify(options),
    }),
  progress: (id: number) => j<Progress>(`/api/recognize/${id}/progress`),
  acceptAllDoubts: (id: number) =>
    j<{ accepted: number }>(`/api/recognize/${id}/accept-all`, { method: "POST" }),

  score: (id: number) => j<ScoreSummary>(`/api/score/${id}`),
  musicxmlUrl: (id: number, partId?: string) =>
    `${API_BASE}/api/score/${id}/musicxml${partId ? `?part_id=${partId}` : ""}`,
  midiUrl: (id: number) => `${API_BASE}/api/score/${id}/midi`,
  validate: (id: number) => j<ValidationReport>(`/api/score/${id}/validate`),
  updatePart: (id: number, partId: string, name: string) =>
    j<{ id: string; name: string; canonical: string }>(
      `/api/score/${id}/part/${partId}`,
      { method: "PATCH", body: JSON.stringify({ name }) }
    ),
  undo: (id: number) => j<{ ok: boolean }>(`/api/score/${id}/undo`, { method: "POST" }),

  exportScore: (
    id: number,
    body: { formats: string[]; part_ids?: string[]; separate?: boolean }
  ) =>
    j<{ files: ExportedFile[] }>(`/api/export/${id}`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  library: (params: Record<string, string>) =>
    j<LibraryEntry[]>(
      `/api/library?${new URLSearchParams(
        Object.fromEntries(Object.entries(params).filter(([, v]) => v))
      )}`
    ),
};
