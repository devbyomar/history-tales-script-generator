"use client";

import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Clock, FileText } from "lucide-react";
import type { RunSummary } from "@/lib/api";

interface RunHistoryProps {
  runs: RunSummary[];
  onSelectRun: (runId: string) => void;
  selectedRunId?: string;
}

export function RunHistory({
  runs,
  onSelectRun,
  selectedRunId,
}: RunHistoryProps) {
  if (runs.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <span className="text-primary">📋</span>
            Run History
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground italic">
            No runs yet. Generate your first script!
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-lg flex items-center gap-2">
          <span className="text-primary">📋</span>
          Run History
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-2 max-h-[400px] overflow-y-auto">
          {runs.map((run) => (
            <button
              key={run.run_id}
              onClick={() => onSelectRun(run.run_id)}
              className={`w-full text-left rounded-lg border p-3 transition-all hover:bg-accent/50 ${
                selectedRunId === run.run_id
                  ? "border-primary/50 bg-primary/5"
                  : "border-border"
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">
                    {run.title || "Generating..."}
                  </p>
                  <div className="flex items-center gap-2 mt-1">
                    <span className="text-xs text-muted-foreground flex items-center gap-1">
                      <Clock className="h-3 w-3" />
                      {run.video_length_minutes}min
                    </span>
                    {run.word_count && (
                      <span className="text-xs text-muted-foreground flex items-center gap-1">
                        <FileText className="h-3 w-3" />
                        {run.word_count.toLocaleString()} words
                      </span>
                    )}
                  </div>
                </div>
                <Badge
                  variant={
                    run.status === "completed"
                      ? "success"
                      : run.status === "failed"
                      ? "destructive"
                      : "default"
                  }
                  className="ml-2"
                >
                  {run.status}
                </Badge>
              </div>
            </button>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
