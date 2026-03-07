"use client";

import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  CheckCircle2,
  Circle,
  Loader2,
  XCircle,
  Zap,
  Search,
  BookOpen,
  PenTool,
  Shield,
  Brain,
  FileCheck,
  Flag,
  StopCircle,
} from "lucide-react";
import type { NodeProgress } from "@/lib/api";

const NODE_ICONS: Record<string, React.ReactNode> = {
  topic_discovery: <Search className="h-4 w-4" />,
  topic_scoring: <Zap className="h-4 w-4" />,
  research_fetch: <BookOpen className="h-4 w-4" />,
  claims_extraction: <BookOpen className="h-4 w-4" />,
  cross_check: <FileCheck className="h-4 w-4" />,
  timeline_builder: <BookOpen className="h-4 w-4" />,
  emotional_extraction: <Brain className="h-4 w-4" />,
  outline: <PenTool className="h-4 w-4" />,
  hard_guardrails: <Shield className="h-4 w-4" />,
  script_generation: <PenTool className="h-4 w-4" />,
  fact_tighten: <FileCheck className="h-4 w-4" />,
  retention_pass: <Zap className="h-4 w-4" />,
  script_quality_scores: <Brain className="h-4 w-4" />,
  quality_check: <FileCheck className="h-4 w-4" />,
  finalize: <Flag className="h-4 w-4" />,
};

const NODE_TIERS: Record<string, "fast" | "creative" | "none"> = {
  topic_discovery: "fast",
  topic_scoring: "fast",
  research_fetch: "none",
  claims_extraction: "fast",
  cross_check: "fast",
  timeline_builder: "fast",
  emotional_extraction: "fast",
  outline: "creative",
  hard_guardrails: "none",
  script_generation: "fast",
  fact_tighten: "fast",
  retention_pass: "fast",
  script_quality_scores: "fast",
  quality_check: "fast",
  finalize: "none",
};

const ALL_NODES = [
  "topic_discovery",
  "topic_scoring",
  "research_fetch",
  "claims_extraction",
  "cross_check",
  "timeline_builder",
  "emotional_extraction",
  "outline",
  "hard_guardrails",
  "script_generation",
  "fact_tighten",
  "retention_pass",
  "script_quality_scores",
  "quality_check",
  "finalize",
];

interface PipelineTrackerProps {
  events: NodeProgress[];
  isRunning: boolean;
  isFailed: boolean;
  isCancelled?: boolean;
  onCancel?: () => void;
}

export function PipelineTracker({
  events,
  isRunning,
  isFailed,
  isCancelled = false,
  onCancel,
}: PipelineTrackerProps) {
  const completedNodes = new Set(
    events
      .filter((e) => e.status === "completed" && e.node !== "__complete__")
      .map((e) => e.node)
  );

  const lastEvent = events.filter(
    (e) => e.node !== "__complete__" && e.node !== "__error__"
  );
  const currentNode = lastEvent.length > 0 ? lastEvent[lastEvent.length - 1].node : null;

  const progress = (completedNodes.size / ALL_NODES.length) * 100;

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg flex items-center gap-2">
            <span className="text-primary">🔄</span>
            Pipeline Progress
          </CardTitle>
          <div className="flex items-center gap-2">
            {isRunning && onCancel && (
              <Button
                variant="destructive"
                size="sm"
                onClick={onCancel}
                className="h-7 px-3 text-xs"
              >
                <StopCircle className="h-3.5 w-3.5 mr-1" />
                Cancel
              </Button>
            )}
            <Badge
              variant={
                isFailed
                  ? "destructive"
                  : isCancelled
                  ? "secondary"
                  : completedNodes.size === ALL_NODES.length
                  ? "success"
                  : "default"
              }
            >
              {isFailed
                ? "Failed"
                : isCancelled
                ? "Cancelled"
                : completedNodes.size === ALL_NODES.length
                ? "Complete"
                : isRunning
                ? `${completedNodes.size}/${ALL_NODES.length}`
                : "Idle"}
            </Badge>
          </div>
        </div>
        <Progress value={progress} className="mt-2" />
      </CardHeader>
      <CardContent>
        <div className="space-y-1">
          {ALL_NODES.map((node) => {
            const isCompleted = completedNodes.has(node);
            const isCurrent =
              isRunning && currentNode === node && !isCompleted;
            const isPending = !isCompleted && !isCurrent;
            const tier = NODE_TIERS[node];

            // Find event data for this node
            const nodeEvent = events.find(
              (e) => e.node === node && e.status === "completed"
            );

            return (
              <div
                key={node}
                className={`flex items-center gap-3 rounded-md px-3 py-2 transition-all ${
                  isCurrent
                    ? "bg-primary/10 border border-primary/20"
                    : isCompleted
                    ? "opacity-80"
                    : "opacity-40"
                } ${isCurrent ? "node-enter" : ""}`}
              >
                {/* Status icon */}
                <div className="flex-shrink-0">
                  {isCompleted ? (
                    <CheckCircle2 className="h-4 w-4 text-green-500" />
                  ) : isCurrent ? (
                    <Loader2 className="h-4 w-4 text-primary animate-spin" />
                  ) : (isFailed || isCancelled) && isPending ? (
                    <XCircle className="h-4 w-4 text-destructive/50" />
                  ) : (
                    <Circle className="h-4 w-4 text-muted-foreground/30" />
                  )}
                </div>

                {/* Node icon */}
                <div
                  className={`flex-shrink-0 ${
                    isCurrent ? "text-primary" : "text-muted-foreground"
                  }`}
                >
                  {NODE_ICONS[node]}
                </div>

                {/* Label */}
                <span
                  className={`text-sm flex-1 ${
                    isCurrent ? "text-foreground font-medium" : ""
                  }`}
                >
                  {nodeEvent?.message ||
                    node
                      .replace(/_/g, " ")
                      .replace(/\b\w/g, (l) => l.toUpperCase())}
                </span>

                {/* Tier badge */}
                {tier !== "none" && (
                  <Badge
                    variant="outline"
                    className={`text-[10px] px-1.5 py-0 ${
                      tier === "creative"
                        ? "border-purple-500/30 text-purple-400"
                        : "border-blue-500/30 text-blue-400"
                    }`}
                  >
                    {tier}
                  </Badge>
                )}

                {/* Extra data */}
                {nodeEvent?.data && (
                  <span className="text-xs text-muted-foreground">
                    {nodeEvent.data.candidate_count
                      ? `${nodeEvent.data.candidate_count} topics`
                      : nodeEvent.data.sources_found
                      ? `${nodeEvent.data.sources_found} sources`
                      : nodeEvent.data.claims_extracted
                      ? `${nodeEvent.data.claims_extracted} claims`
                      : nodeEvent.data.word_count
                      ? `${nodeEvent.data.word_count} words`
                      : nodeEvent.data.qc_pass !== undefined
                      ? nodeEvent.data.qc_pass
                        ? "✅ Pass"
                        : "❌ Fail"
                      : null}
                  </span>
                )}
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}
