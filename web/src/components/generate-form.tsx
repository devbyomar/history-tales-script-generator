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
  const [previousFormat, setPreviousFormat] = useState("");

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
        previous_format_tag: previousFormat || undefined,
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
      previousFormat,
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

          {/* Previous Format */}
          <div className="space-y-2">
            <Label>Previous Format (for rotation)</Label>
            <Select value={previousFormat} onValueChange={setPreviousFormat}>
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
