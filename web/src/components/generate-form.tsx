"use client";

import { useState, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Loader2, Play } from "lucide-react";
import type { GenerateParams } from "@/lib/api";

const TONES = [
  { value: "cinematic-serious", label: "Cinematic Serious" },
  { value: "investigative", label: "Investigative" },
  { value: "fast-paced", label: "Fast-Paced" },
  { value: "somber", label: "Somber" },
  { value: "restrained", label: "Restrained" },
  { value: "urgent", label: "Urgent" },
  { value: "claustrophobic", label: "Claustrophobic" },
  { value: "reflective", label: "Reflective" },
];

const SENSITIVITY_LEVELS = [
  { value: "general audiences", label: "General Audiences" },
  { value: "teen", label: "Teen" },
  { value: "mature", label: "Mature" },
];

const FORMATS = [
  { value: "", label: "Auto (rotation)" },
  { value: "Countdown", label: "Countdown" },
  { value: "One Room", label: "One Room" },
  { value: "Two Truths", label: "Two Truths" },
  { value: "Chain Reaction", label: "Chain Reaction" },
  { value: "Impossible Choice", label: "Impossible Choice" },
  { value: "Hunt", label: "Hunt" },
];

const GEO_SCOPES = [
  { value: "", label: "Auto" },
  { value: "single_city", label: "Single City" },
  { value: "region", label: "Region" },
  { value: "country", label: "Country" },
  { value: "theater", label: "Theater" },
  { value: "global", label: "Global" },
];

const MOBILITY_MODES = [
  { value: "", label: "Auto" },
  { value: "fixed_site", label: "Fixed Site" },
  { value: "route_based", label: "Route Based" },
  { value: "multi_site", label: "Multi-Site" },
  { value: "theater_wide", label: "Theater Wide" },
];

interface GenerateFormProps {
  onSubmit: (params: GenerateParams) => void;
  isLoading: boolean;
}

export function GenerateForm({ onSubmit, isLoading }: GenerateFormProps) {
  const [videoLength, setVideoLength] = useState(12);
  const [eraFocus, setEraFocus] = useState("");
  const [geoFocus, setGeoFocus] = useState("");
  const [topicSeed, setTopicSeed] = useState("");
  const [tone, setTone] = useState("cinematic-serious");
  const [sensitivity, setSensitivity] = useState("general audiences");
  const [nonlinearOpen, setNonlinearOpen] = useState(true);
  const [format, setFormat] = useState("");
  const [lens, setLens] = useState("");
  const [lensStrength, setLensStrength] = useState(0.6);
  const [geoScope, setGeoScope] = useState("");
  const [geoAnchor, setGeoAnchor] = useState("");
  const [mobilityMode, setMobilityMode] = useState("");

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      onSubmit({
        video_length_minutes: videoLength,
        era_focus: eraFocus || undefined,
        geo_focus: geoFocus || undefined,
        topic_seed: topicSeed || undefined,
        tone,
        sensitivity_level: sensitivity,
        nonlinear_open: nonlinearOpen,
        requested_format_tag: format && format !== "none" ? format : undefined,
        narrative_lens: lens || undefined,
        lens_strength: lens ? lensStrength : undefined,
        geo_scope: geoScope || undefined,
        geo_anchor: geoAnchor || undefined,
        mobility_mode: mobilityMode || undefined,
      });
    },
    [
      videoLength,
      eraFocus,
      geoFocus,
      topicSeed,
      tone,
      sensitivity,
      nonlinearOpen,
      format,
      lens,
      lensStrength,
      geoScope,
      geoAnchor,
      mobilityMode,
      onSubmit,
    ]
  );

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg flex items-center gap-2">
          <span className="text-primary">⚡</span>
          Generate Script
        </CardTitle>
        <CardDescription>
          Configure your documentary script parameters
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Video Length */}
          <div className="space-y-2">
            <Label htmlFor="videoLength">
              Video Length{" "}
              <span className="text-muted-foreground font-normal">
                ({videoLength} min → ~{videoLength * 155} words)
              </span>
            </Label>
            <div className="flex items-center gap-3">
              <Input
                id="videoLength"
                type="range"
                min={5}
                max={60}
                value={videoLength}
                onChange={(e) => setVideoLength(Number(e.target.value))}
                className="flex-1"
              />
              <Input
                type="number"
                min={5}
                max={60}
                value={videoLength}
                onChange={(e) => setVideoLength(Number(e.target.value))}
                className="w-20"
              />
            </div>
          </div>

          {/* Era & Geo Focus */}
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-2">
              <Label htmlFor="era">Era Focus</Label>
              <Input
                id="era"
                placeholder="e.g., World War II"
                value={eraFocus}
                onChange={(e) => setEraFocus(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="geo">Geographic Focus</Label>
              <Input
                id="geo"
                placeholder="e.g., Western Europe"
                value={geoFocus}
                onChange={(e) => setGeoFocus(e.target.value)}
              />
            </div>
          </div>

          {/* Topic Seed */}
          <div className="space-y-2">
            <Label htmlFor="topicSeed">Topic Seed</Label>
            <Input
              id="topicSeed"
              placeholder="e.g., The night before D-Day"
              value={topicSeed}
              onChange={(e) => setTopicSeed(e.target.value)}
            />
          </div>

          {/* Tone & Sensitivity */}
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-2">
              <Label>Tone</Label>
              <Select value={tone} onValueChange={setTone}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {TONES.map((t) => (
                    <SelectItem key={t.value} value={t.value}>
                      {t.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Sensitivity</Label>
              <Select value={sensitivity} onValueChange={setSensitivity}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {SENSITIVITY_LEVELS.map((s) => (
                    <SelectItem key={s.value} value={s.value}>
                      {s.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* Format */}
          <div className="space-y-2">
            <Label>Format</Label>
            <Select value={format} onValueChange={setFormat}>
              <SelectTrigger>
                <SelectValue placeholder="Auto (rotation)" />
              </SelectTrigger>
              <SelectContent>
                {FORMATS.map((f) => (
                  <SelectItem key={f.value || "auto"} value={f.value || "none"}>
                    {f.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Nonlinear Open */}
          <div className="flex items-center gap-3">
            <input
              type="checkbox"
              id="nonlinear"
              checked={nonlinearOpen}
              onChange={(e) => setNonlinearOpen(e.target.checked)}
              className="rounded border-input"
            />
            <Label htmlFor="nonlinear">Use nonlinear opening</Label>
          </div>

          {/* ── Advanced: Narrative Lens ── */}
          <details className="space-y-3 rounded-lg border border-border/50 p-3">
            <summary className="cursor-pointer text-sm font-medium text-muted-foreground">
              Advanced Options
            </summary>
            <div className="space-y-4 pt-2">
              {/* Narrative Lens */}
              <div className="space-y-2">
                <Label htmlFor="lens">Narrative Lens</Label>
                <Input
                  id="lens"
                  placeholder="e.g., civilians, medics, logistics"
                  value={lens}
                  onChange={(e) => setLens(e.target.value)}
                />
              </div>

              {/* Lens Strength */}
              {lens && (
                <div className="space-y-2">
                  <Label htmlFor="lensStrength">
                    Lens Strength{" "}
                    <span className="text-muted-foreground font-normal">
                      ({lensStrength.toFixed(1)})
                    </span>
                  </Label>
                  <Input
                    id="lensStrength"
                    type="range"
                    min={0}
                    max={1}
                    step={0.1}
                    value={lensStrength}
                    onChange={(e) => setLensStrength(Number(e.target.value))}
                  />
                </div>
              )}

              {/* Geo Scope & Mobility */}
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-2">
                  <Label>Geo Scope</Label>
                  <Select value={geoScope} onValueChange={setGeoScope}>
                    <SelectTrigger>
                      <SelectValue placeholder="Auto" />
                    </SelectTrigger>
                    <SelectContent>
                      {GEO_SCOPES.map((g) => (
                        <SelectItem key={g.value || "auto"} value={g.value || "none"}>
                          {g.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>Mobility</Label>
                  <Select value={mobilityMode} onValueChange={setMobilityMode}>
                    <SelectTrigger>
                      <SelectValue placeholder="Auto" />
                    </SelectTrigger>
                    <SelectContent>
                      {MOBILITY_MODES.map((m) => (
                        <SelectItem key={m.value || "auto"} value={m.value || "none"}>
                          {m.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              {/* Geo Anchor */}
              <div className="space-y-2">
                <Label htmlFor="geoAnchor">Geo Anchor</Label>
                <Input
                  id="geoAnchor"
                  placeholder="e.g., Tempelhof Airport, Ludendorff Bridge"
                  value={geoAnchor}
                  onChange={(e) => setGeoAnchor(e.target.value)}
                />
              </div>
            </div>
          </details>

          {/* Submit */}
          <Button
            type="submit"
            className="w-full"
            size="lg"
            disabled={isLoading}
          >
            {isLoading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Generating...
              </>
            ) : (
              <>
                <Play className="mr-2 h-4 w-4" />
                Generate Documentary Script
              </>
            )}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
