/**
 * API client for the History Tales backend.
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface GenerateParams {
  video_length_minutes: number;
  era_focus?: string;
  geo_focus?: string;
  topic_seed?: string;
  tone: string;
  sensitivity_level: string;
  nonlinear_open: boolean;
  previous_format_tag?: string;
}

export interface RunSummary {
  run_id: string;
  status: "running" | "completed" | "failed";
  created_at: string;
  completed_at?: string;
  video_length_minutes: number;
  era_focus?: string;
  geo_focus?: string;
  topic_seed?: string;
  tone: string;
  title?: string;
  format_tag?: string;
  topic_score?: number;
  word_count?: number;
  target_words?: number;
  emotional_intensity?: number;
  sensory_density?: number;
  source_count?: number;
  claim_count?: number;
  qc_pass?: boolean;
  qc_issues: string[];
}

export interface RunDetail extends RunSummary {
  final_script?: string;
  sources_log: Record<string, unknown>[];
  claims: Record<string, unknown>[];
  qc_report?: Record<string, unknown>;
  errors: string[];
}

export interface NodeProgress {
  run_id: string;
  node: string;
  status: "started" | "completed" | "failed";
  node_index: number;
  total_nodes: number;
  message: string;
  timestamp: string;
  data?: Record<string, unknown>;
}

export interface HealthStatus {
  status: string;
  version: string;
  pipeline_nodes: number;
  models: Record<string, string>;
}

// ---------------------------------------------------------------------------
// API Functions
// ---------------------------------------------------------------------------

export async function checkHealth(): Promise<HealthStatus> {
  const res = await fetch(`${API_URL}/health`);
  if (!res.ok) throw new Error(`Health check failed: ${res.statusText}`);
  return res.json();
}

export async function startGeneration(
  params: GenerateParams
): Promise<{ run_id: string; stream_url: string; result_url: string }> {
  const res = await fetch(`${API_URL}/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || "Failed to start generation");
  }
  return res.json();
}

export async function listRuns(limit = 20): Promise<RunSummary[]> {
  const res = await fetch(`${API_URL}/runs?limit=${limit}`);
  if (!res.ok) throw new Error(`Failed to list runs: ${res.statusText}`);
  return res.json();
}

export async function getRun(runId: string): Promise<RunDetail> {
  const res = await fetch(`${API_URL}/runs/${runId}`);
  if (!res.ok) throw new Error(`Failed to get run: ${res.statusText}`);
  return res.json();
}

export function streamRun(
  runId: string,
  callbacks: {
    onProgress: (event: NodeProgress) => void;
    onComplete: () => void;
    onError: (error: string) => void;
  }
): () => void {
  const evtSource = new EventSource(`${API_URL}/runs/${runId}/stream`);

  evtSource.addEventListener("node_progress", (e) => {
    try {
      const data: NodeProgress = JSON.parse(e.data);
      callbacks.onProgress(data);
    } catch {
      // skip malformed events
    }
  });

  evtSource.addEventListener("complete", () => {
    callbacks.onComplete();
    evtSource.close();
  });

  evtSource.addEventListener("error", (e) => {
    if (evtSource.readyState === EventSource.CLOSED) {
      callbacks.onError("Connection closed");
    }
    evtSource.close();
  });

  evtSource.onerror = () => {
    // EventSource will auto-reconnect; we let it try a few times
  };

  // Return cleanup function
  return () => evtSource.close();
}

export function getExportScriptUrl(runId: string): string {
  return `${API_URL}/runs/${runId}/export/script`;
}

export function getExportSourcesUrl(runId: string): string {
  return `${API_URL}/runs/${runId}/export/sources`;
}
