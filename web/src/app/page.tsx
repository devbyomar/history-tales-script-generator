"use client";

import { useState, useCallback, useEffect } from "react";
import { GenerateForm } from "@/components/generate-form";
import { PipelineTracker } from "@/components/pipeline-tracker";
import { ScriptViewer } from "@/components/script-viewer";
import { RunHistory } from "@/components/run-history";
import {
  startGeneration,
  streamRun,
  listRuns,
  getRun,
  cancelRun,
  type GenerateParams,
  type NodeProgress,
  type RunDetail,
  type RunSummary,
} from "@/lib/api";

export default function HomePage() {
  const [isLoading, setIsLoading] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [isFailed, setIsFailed] = useState(false);
  const [isCancelled, setIsCancelled] = useState(false);
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const [events, setEvents] = useState<NodeProgress[]>([]);
  const [currentRun, setCurrentRun] = useState<RunDetail | null>(null);
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [error, setError] = useState<string | null>(null);

  // Load run history on mount
  useEffect(() => {
    listRuns()
      .then(setRuns)
      .catch(() => {
        // API not available yet — that's fine
      });
  }, []);

  const handleGenerate = useCallback(async (params: GenerateParams) => {
    setIsLoading(true);
    setIsRunning(true);
    setIsFailed(false);
    setIsCancelled(false);
    setEvents([]);
    setCurrentRun(null);
    setError(null);
    setActiveRunId(null);

    try {
      const { run_id } = await startGeneration(params);
      setActiveRunId(run_id);

      setIsLoading(false);

      // Stream progress events
      const cleanup = streamRun(run_id, {
        onProgress: (event) => {
          setEvents((prev) => [...prev, event]);
        },
        onComplete: async () => {
          setIsRunning(false);
          setActiveRunId(null);
          // Fetch the completed run
          try {
            const run = await getRun(run_id);
            setCurrentRun(run);
            // Refresh run history
            const updatedRuns = await listRuns();
            setRuns(updatedRuns);
          } catch (e) {
            setError("Failed to fetch completed run");
          }
        },
        onCancelled: async () => {
          setIsRunning(false);
          setIsCancelled(true);
          setActiveRunId(null);
          // Refresh run history
          try {
            const updatedRuns = await listRuns();
            setRuns(updatedRuns);
          } catch (e) {
            // ignore
          }
        },
        onError: (errorMsg) => {
          setIsRunning(false);
          setIsFailed(true);
          setActiveRunId(null);
          setError(errorMsg);
          setIsLoading(false);
        },
      });

      // Cleanup on unmount
      return () => cleanup();
    } catch (e: any) {
      setIsLoading(false);
      setIsRunning(false);
      setIsFailed(true);
      setActiveRunId(null);
      setError(e.message || "Failed to start generation");
    }
  }, []);

  const handleSelectRun = useCallback(async (runId: string) => {
    try {
      const run = await getRun(runId);
      setCurrentRun(run);
      setEvents([]);
      setIsRunning(false);
      setIsFailed(run.status === "failed");
      setIsCancelled(run.status === "cancelled");
    } catch (e) {
      setError("Failed to load run");
    }
  }, []);

  const handleCancel = useCallback(async () => {
    if (!activeRunId) return;
    try {
      await cancelRun(activeRunId);
    } catch (e: any) {
      setError(e.message || "Failed to cancel run");
    }
  }, [activeRunId]);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
      {/* Left Panel: Form + History */}
      <div className="lg:col-span-4 space-y-6">
        <GenerateForm onSubmit={handleGenerate} isLoading={isLoading} />
        <RunHistory
          runs={runs}
          onSelectRun={handleSelectRun}
          selectedRunId={currentRun?.run_id}
        />
      </div>

      {/* Right Panel: Tracker + Results */}
      <div className="lg:col-span-8 space-y-6">
        {/* Error Banner */}
        {error && (
          <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4">
            <p className="text-sm text-destructive">{error}</p>
          </div>
        )}

        {/* Pipeline Tracker (visible during runs) */}
        {(isRunning || events.length > 0) && (
          <PipelineTracker
            events={events}
            isRunning={isRunning}
            isFailed={isFailed}
            isCancelled={isCancelled}
            onCancel={handleCancel}
          />
        )}

        {/* Script Viewer (visible when run is complete) */}
        {currentRun && currentRun.status === "completed" && (
          <ScriptViewer run={currentRun} />
        )}

        {/* Empty State */}
        {!isRunning && !currentRun && events.length === 0 && (
          <div className="flex items-center justify-center min-h-[400px] rounded-lg border border-dashed border-border/50">
            <div className="text-center space-y-3">
              <span className="text-5xl">🎬</span>
              <h2 className="text-xl font-semibold text-muted-foreground">
                Ready to Generate
              </h2>
              <p className="text-sm text-muted-foreground/70 max-w-md">
                Configure your documentary parameters on the left and hit
                Generate. Watch the 16-node AI pipeline work in real-time.
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
