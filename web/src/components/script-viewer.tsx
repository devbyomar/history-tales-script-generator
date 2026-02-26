"use client";

import { useState } from "react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Download,
  FileText,
  BookOpen,
  Shield,
  BarChart3,
  Copy,
  Check,
  Mic,
  Zap,
} from "lucide-react";
import {
  getExportScriptUrl,
  getExportSourcesUrl,
  getExportElevenlabsV3Url,
  getExportElevenlabsFlashUrl,
} from "@/lib/api";
import type { RunDetail } from "@/lib/api";

interface ScriptViewerProps {
  run: RunDetail;
}

export function ScriptViewer({ run }: ScriptViewerProps) {
  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="text-lg flex items-center gap-2">
              <span className="text-primary">📜</span>
              {run.title || "Generated Script"}
            </CardTitle>
            <div className="flex items-center gap-2 mt-2">
              {run.format_tag && (
                <Badge variant="outline">{run.format_tag}</Badge>
              )}
              {run.qc_pass !== undefined && (
                <Badge variant={run.qc_pass ? "success" : "destructive"}>
                  QC {run.qc_pass ? "Pass" : "Fail"}
                </Badge>
              )}
              {run.word_count && (
                <Badge variant="secondary">
                  {run.word_count.toLocaleString()} words
                </Badge>
              )}
              {run.topic_score && (
                <Badge variant="secondary">
                  Score: {run.topic_score.toFixed(1)}
                </Badge>
              )}
            </div>
          </div>
          <div className="flex gap-2 flex-wrap">
            <Button
              variant="outline"
              size="sm"
              onClick={() => window.open(getExportScriptUrl(run.run_id))}
            >
              <Download className="h-3.5 w-3.5 mr-1.5" />
              Script
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => window.open(getExportSourcesUrl(run.run_id))}
            >
              <Download className="h-3.5 w-3.5 mr-1.5" />
              Sources
            </Button>
            {run.script_elevenlabs_v3 && (
              <Button
                variant="outline"
                size="sm"
                onClick={() =>
                  window.open(getExportElevenlabsV3Url(run.run_id))
                }
              >
                <Download className="h-3.5 w-3.5 mr-1.5" />
                v3
              </Button>
            )}
            {run.script_elevenlabs_flash && (
              <Button
                variant="outline"
                size="sm"
                onClick={() =>
                  window.open(getExportElevenlabsFlashUrl(run.run_id))
                }
              >
                <Download className="h-3.5 w-3.5 mr-1.5" />
                Flash
              </Button>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <Tabs defaultValue="script" className="w-full">
          <TabsList className="w-full justify-start flex-wrap h-auto gap-1">
            <TabsTrigger value="script" className="gap-1.5">
              <FileText className="h-3.5 w-3.5" />
              Script
            </TabsTrigger>
            <TabsTrigger value="elevenlabs-v3" className="gap-1.5">
              <Mic className="h-3.5 w-3.5" />
              ElevenLabs v3
            </TabsTrigger>
            <TabsTrigger value="elevenlabs-flash" className="gap-1.5">
              <Zap className="h-3.5 w-3.5" />
              ElevenLabs Flash
            </TabsTrigger>
            <TabsTrigger value="sources" className="gap-1.5">
              <BookOpen className="h-3.5 w-3.5" />
              Sources ({run.source_count || 0})
            </TabsTrigger>
            <TabsTrigger value="qc" className="gap-1.5">
              <Shield className="h-3.5 w-3.5" />
              QC Report
            </TabsTrigger>
            <TabsTrigger value="stats" className="gap-1.5">
              <BarChart3 className="h-3.5 w-3.5" />
              Stats
            </TabsTrigger>
          </TabsList>

          {/* Script Tab */}
          <TabsContent value="script" className="mt-4">
            <div className="max-h-[600px] overflow-y-auto rounded-lg border bg-background/50 p-6">
              <div className="script-content prose prose-invert max-w-none">
                {run.final_script ? (
                  run.final_script.split("\n").map((line, i) => {
                    if (line.startsWith("### "))
                      return (
                        <h3 key={i}>{line.replace("### ", "")}</h3>
                      );
                    if (line.startsWith("## "))
                      return (
                        <h2 key={i}>{line.replace("## ", "")}</h2>
                      );
                    if (line.startsWith("# "))
                      return (
                        <h1 key={i}>{line.replace("# ", "")}</h1>
                      );
                    if (line.startsWith("> "))
                      return (
                        <blockquote key={i}>
                          {line.replace("> ", "")}
                        </blockquote>
                      );
                    if (line.trim() === "") return <br key={i} />;
                    return <p key={i}>{line}</p>;
                  })
                ) : (
                  <p className="text-muted-foreground italic">
                    No script generated yet.
                  </p>
                )}
              </div>
            </div>
          </TabsContent>

          {/* ElevenLabs v3 Tab */}
          <TabsContent value="elevenlabs-v3" className="mt-4">
            <ElevenLabsPanel
              content={run.script_elevenlabs_v3}
              label="ElevenLabs v3"
              description="Optimised for Eleven v3 — audio tags for emotional direction, emphasis via CAPS, ellipsis-based pauses. No SSML."
            />
          </TabsContent>

          {/* ElevenLabs Flash Tab */}
          <TabsContent value="elevenlabs-flash" className="mt-4">
            <ElevenLabsPanel
              content={run.script_elevenlabs_flash}
              label="ElevenLabs Flash / Turbo"
              description="Optimised for Flash v2.5, Turbo v2.5, and Multilingual v2 — SSML break tags for pacing, aggressive text normalisation. No audio tags."
            />
          </TabsContent>

          {/* Sources Tab */}
          <TabsContent value="sources" className="mt-4">
            <div className="max-h-[600px] overflow-y-auto space-y-2">
              {run.sources_log.length > 0 ? (
                run.sources_log.map((source: any, i: number) => (
                  <div
                    key={i}
                    className="flex items-center justify-between rounded-lg border bg-background/50 p-3"
                  >
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate">
                        {source.name}
                      </p>
                      <p className="text-xs text-muted-foreground truncate">
                        {source.url}
                      </p>
                    </div>
                    <div className="flex items-center gap-2 ml-3">
                      <Badge variant="outline" className="text-xs">
                        {source.source_type || "—"}
                      </Badge>
                      <Badge
                        variant={
                          source.credibility_score >= 0.7
                            ? "success"
                            : "secondary"
                        }
                        className="text-xs"
                      >
                        {((source.credibility_score || 0) * 100).toFixed(0)}%
                      </Badge>
                    </div>
                  </div>
                ))
              ) : (
                <p className="text-muted-foreground text-sm italic p-4">
                  No sources logged.
                </p>
              )}
            </div>
          </TabsContent>

          {/* QC Report Tab */}
          <TabsContent value="qc" className="mt-4">
            <div className="rounded-lg border bg-background/50 p-4 space-y-4">
              {run.qc_report ? (
                <>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    <StatCard
                      label="Word Count"
                      value={
                        run.qc_report.word_count?.toLocaleString() || "—"
                      }
                      target={`Target: ${run.target_words?.toLocaleString()}`}
                      ok={run.qc_report.word_count_in_range as boolean}
                    />
                    <StatCard
                      label="Emotional"
                      value={`${run.emotional_intensity?.toFixed(1) || "—"}/100`}
                      target="Min: 75"
                      ok={(run.emotional_intensity || 0) >= 75}
                    />
                    <StatCard
                      label="Sensory"
                      value={`${run.sensory_density?.toFixed(1) || "—"}/100`}
                      target="Min: 70"
                      ok={(run.sensory_density || 0) >= 70}
                    />
                    <StatCard
                      label="Sources"
                      value={String(run.source_count || 0)}
                      target="Min: 3 domains"
                      ok={(run.qc_report.independent_domains as number) >= 3}
                    />
                  </div>

                  {run.qc_issues.length > 0 && (
                    <div className="space-y-2">
                      <h4 className="text-sm font-medium text-muted-foreground">
                        Issues
                      </h4>
                      {run.qc_issues.map((issue, i) => (
                        <div
                          key={i}
                          className="flex items-start gap-2 text-sm text-destructive/80"
                        >
                          <span>⚠️</span>
                          <span>{issue}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </>
              ) : (
                <p className="text-muted-foreground text-sm italic">
                  No QC report available.
                </p>
              )}
            </div>
          </TabsContent>

          {/* Stats Tab */}
          <TabsContent value="stats" className="mt-4">
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
              <StatCard
                label="Video Length"
                value={`${run.video_length_minutes} min`}
                target=""
              />
              <StatCard
                label="Tone"
                value={run.tone.replace(/-/g, " ")}
                target=""
              />
              <StatCard
                label="Format"
                value={run.format_tag || "—"}
                target=""
              />
              <StatCard
                label="Sources"
                value={String(run.source_count || 0)}
                target=""
              />
              <StatCard
                label="Claims"
                value={String(run.claim_count || 0)}
                target=""
              />
              <StatCard
                label="Topic Score"
                value={run.topic_score?.toFixed(1) || "—"}
                target="Min: 78"
                ok={(run.topic_score || 0) >= 78}
              />
            </div>
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  );
}

function ElevenLabsPanel({
  content,
  label,
  description,
}: {
  content?: string;
  label: string;
  description: string;
}) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    if (!content) return;
    try {
      await navigator.clipboard.writeText(content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback for older browsers
      const textarea = document.createElement("textarea");
      textarea.value = content;
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand("copy");
      document.body.removeChild(textarea);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  if (!content) {
    return (
      <div className="rounded-lg border bg-background/50 p-6">
        <p className="text-muted-foreground italic text-sm">
          No {label} script available yet.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-xs text-muted-foreground max-w-[70%]">
          {description}
        </p>
        <Button
          variant={copied ? "default" : "outline"}
          size="sm"
          onClick={handleCopy}
          className="shrink-0"
        >
          {copied ? (
            <>
              <Check className="h-3.5 w-3.5 mr-1.5" />
              Copied!
            </>
          ) : (
            <>
              <Copy className="h-3.5 w-3.5 mr-1.5" />
              Copy to Clipboard
            </>
          )}
        </Button>
      </div>
      <div className="max-h-[600px] overflow-y-auto rounded-lg border bg-background/50 p-6">
        <pre className="whitespace-pre-wrap text-sm leading-relaxed text-foreground/90 font-mono">
          {content}
        </pre>
      </div>
      <p className="text-xs text-muted-foreground text-right">
        {content.split(/\s+/).filter(Boolean).length.toLocaleString()} words
      </p>
    </div>
  );
}

function StatCard({
  label,
  value,
  target,
  ok,
}: {
  label: string;
  value: string;
  target: string;
  ok?: boolean;
}) {
  return (
    <div className="rounded-lg border bg-card p-3">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p
        className={`text-lg font-semibold mt-0.5 ${
          ok === true
            ? "text-green-400"
            : ok === false
            ? "text-red-400"
            : "text-foreground"
        }`}
      >
        {value}
      </p>
      {target && (
        <p className="text-xs text-muted-foreground mt-0.5">{target}</p>
      )}
    </div>
  );
}
