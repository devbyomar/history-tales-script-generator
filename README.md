# History Tales Script Generator

A production-ready LangGraph agent that autonomously generates high-retention, emotionally resonant, evidence-led history documentary scripts in a cinematic, human-centered style.

## Features

- **Autonomous Pipeline**: 16-node LangGraph workflow from topic discovery to final script
- **Evidence-Led Research**: Only credible, non-paywalled sources (Wikipedia API, National Archives, Library of Congress, etc.)
- **Retention Engineering**: Re-hooks every 60–120 seconds, escalating stakes, micro-payoff enforcement
- **Emotional Authenticity**: Extracts doubt, miscalculation, moral tension, internal conflict
- **Quality Assurance**: Emotional intensity meter, sensory density checks, cross-referencing
- **Length Control**: Precise word count targeting at 155 words/minute ±10%
- **Format Rotation**: Six narrative formats with rotation enforcement
- **Sources & Claims Log**: Full citation chain with confidence ratings

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your OpenAI API key
```

### 3. Run the Agent

```bash
python -m history_tales_agent.main \
  --video-length 12 \
  --era "World War II" \
  --geo "Western Europe" \
  --tone cinematic-serious
```

Or with a specific topic seed:

```bash
python -m history_tales_agent.main \
  --video-length 25 \
  --topic-seed "The night before D-Day" \
  --tone urgent
```

### 4. Run with Python API

```python
from history_tales_agent.main import run_agent

result = run_agent(
    video_length_minutes=12,
    era_focus="World War II",
    geo_focus="Western Europe",
    tone="cinematic-serious",
)

print(result["final_script"])
```

## Architecture

```
TopicDiscoveryNode
  → FormatRotationGuardNode
  → TopicScoringNode
  → ResearchFetchNode
  → SourceCredibilityNode
  → ClaimsExtractionNode
  → CrossCheckNode
  → TimelineBuilderNode
  → EmotionalArtifactExtractionNode
  → OutlineNode
  → ScriptGenerationNode
  → RetentionPassNode
  → EmotionalIntensityMeterNode
  → SensoryDensityCheckNode
  → QualityCheckNode
  → FinalizeNode
```

## Input Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `video_length_minutes` | ✅ | — | Target video duration |
| `era_focus` | ❌ | None | Historical era filter |
| `geo_focus` | ❌ | None | Geographic focus |
| `topic_seed` | ❌ | None | Starting topic idea |
| `tone` | ❌ | cinematic-serious | Narrative tone |
| `sensitivity_level` | ❌ | general audiences | Content sensitivity |
| `nonlinear_open` | ❌ | True | Use nonlinear opening |
| `previous_format_tag` | ❌ | None | For format rotation |

## Supported Tones

- `cinematic-serious` — Rich, measured prose with weight
- `investigative` — Question-driven, evidence-forward
- `fast-paced` — Short sentences, rapid cuts
- `somber` — Quiet gravity, restrained emotion
- `restrained` — Understated, deliberate
- `urgent` — Compressed time, pressure-forward
- `claustrophobic` — Tight spaces, limited options
- `reflective` — Philosophical, meaning-seeking

## Narrative Formats

- **Countdown** — Ticking clock structure
- **One Room** — Confined decision space
- **Hunt** — Pursuit and evasion
- **Impossible Choice** — No-win dilemma
- **Chain Reaction** — Cascading consequences
- **Two Truths** — Myth vs. reality

## Output Structure

```
output/
├── script.md              # Final documentary script
├── sources_claims_log.md  # Full citation chain
├── qc_report.md           # Quality check results
└── metadata.json          # Run metadata
```

## Project Structure

```
history_tales_agent/
├── __init__.py
├── main.py                # Entry point & CLI
├── config.py              # Configuration management
├── state.py               # Pydantic state schema
├── graph.py               # LangGraph workflow definition
├── nodes/                 # All 16 pipeline nodes
│   ├── __init__.py
│   ├── topic_discovery.py
│   ├── format_rotation_guard.py
│   ├── topic_scoring.py
│   ├── research_fetch.py
│   ├── source_credibility.py
│   ├── claims_extraction.py
│   ├── cross_check.py
│   ├── timeline_builder.py
│   ├── emotional_extraction.py
│   ├── outline.py
│   ├── script_generation.py
│   ├── retention_pass.py
│   ├── emotional_intensity.py
│   ├── sensory_density.py
│   ├── quality_check.py
│   └── finalize.py
├── prompts/               # All prompt templates
│   ├── __init__.py
│   └── templates.py
├── research/              # Research utilities
│   ├── __init__.py
│   ├── wikipedia_client.py
│   ├── archive_client.py
│   └── source_registry.py
├── scoring/               # Scoring logic
│   ├── __init__.py
│   └── topic_scorer.py
├── utils/                 # Shared utilities
│   ├── __init__.py
│   ├── llm.py
│   ├── retry.py
│   ├── cache.py
│   └── logging.py
└── output/                # Output formatters
    ├── __init__.py
    └── formatter.py
```

## Scaling Notes

- **Batch Processing**: Wrap `run_agent()` in async loop for bulk generation
- **Caching**: HTTP responses cached by default to `.cache/` — reduces API costs on reruns
- **Model Swapping**: Change `OPENAI_MODEL` in `.env` to use GPT-4o-mini for drafts
- **Parallel Research**: Research fetches run concurrently across sources
- **State Checkpointing**: LangGraph state can be persisted for resumption

## Monetization Extensions

- Add voice synthesis integration (ElevenLabs, Azure TTS)
- Add image/B-roll suggestion nodes for video production
- Add thumbnail title generation node
- Add SEO metadata generation (tags, description)
- Add multi-language translation node
- Add Patreon-tier extended cut generation (longer scripts with bonus sections)

## License

MIT