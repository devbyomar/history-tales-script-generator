# History Tales Script Generator

A production-ready LangGraph agent that autonomously generates high-retention, emotionally resonant, evidence-led history documentary scripts in a cinematic, human-centered style.

## Features

- **Autonomous Pipeline**: 18-node LangGraph workflow from topic discovery to final script
- **Dual-Model Architecture**: Creative tier (GPT-5) for writing, fast tier (GPT-5.2) for analysis — configurable via env vars
- **Evidence-Led Research**: Only credible, non-paywalled sources (Wikipedia API, National Archives, Library of Congress, etc.)
- **Hard Guardrails**: Deterministic validation gates enforce entity provenance, word count, rehook cadence, tension escalation, and essay-block detection — no LLM hallucination can bypass these
- **Fact-Tighten Pass**: Two-stage script generation — draft → active fact-checking (unsourced specifics, fabricated names, contested claims, speculative details) with per-paragraph trace tags `[Beat Bxx | Claims Cxxx]` and 85% word-count floor guardrail
- **Retention Engineering**: Re-hooks every 60–120 seconds, escalating stakes, micro-payoff enforcement; surgery-only retention pass (no new entities or events)
- **Emotional Authenticity**: Extracts doubt, miscalculation, moral tension, internal conflict
- **Quality Assurance**: Emotional intensity meter, sensory density checks, cross-referencing, conditional QC→rewrite loop
- **Feedback Memory**: Agent learns from past runs — recurring QC issues and recommendations are injected into future prompts
- **Length Control**: Precise word count targeting at 155 words/minute ±10%, with expansion retry loop
- **Format Rotation**: Six narrative formats with rotation enforcement
- **Sources & Claims Log**: Full citation chain with confidence ratings
- **ElevenLabs TTS Output**: Auto-generates pure narration text with all structural labels, stage directions, and cross-cut markers stripped
- **Anti-Fabrication**: Strict rules preventing fictional/composite characters across all prompts

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

**Environment Variables:**

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | ✅ | — | Your OpenAI API key |
| `OPENAI_MODEL` | ❌ | `gpt-5` | Creative tier model (outline, story arc design) |
| `OPENAI_FAST_MODEL` | ❌ | — | Fast tier model for script writing and analytical nodes. Falls back to `OPENAI_MODEL` if unset |
| `OPENAI_TEMPERATURE` | ❌ | `0.7` | Base temperature for LLM calls |
| `MAX_REQUESTS_PER_MINUTE` | ❌ | `20` | Rate limiter ceiling |
| `MAX_TOKENS_PER_MINUTE` | ❌ | `150000` | Token rate limit |
| `ENABLE_CACHE` | ❌ | `true` | Cache HTTP responses to `.cache/` |
| `LOG_LEVEL` | ❌ | `INFO` | Logging verbosity |

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

Or with narrative lens and geographic controls:

```bash
python -m history_tales_agent.main \
  --video-length 15 \
  --era "Cold War" \
  --lens "civilians,logistics" \
  --lens-strength 0.7 \
  --geo-scope region \
  --geo-anchor "Tempelhof Airport" \
  --mobility route_based \
  --tone investigative
```

### 4. Run with Python API

```python
from history_tales_agent.main import run_agent

result = run_agent(
    video_length_minutes=12,
    era_focus="World War II",
    geo_focus="Western Europe",
    tone="cinematic-serious",
    narrative_lens="civilians",
    lens_strength=0.6,
    geo_scope="theater",
)

print(result["final_script"])
```

## Architecture

```
TopicDiscoveryNode          ← fast tier
  → FormatRotationGuardNode   (no LLM)
  → TopicScoringNode          ← fast tier
  → ResearchFetchNode         (no LLM)
  → SourceCredibilityNode     (no LLM)
  → ClaimsExtractionNode      ← fast tier (C001… IDs, named_entities, date_anchor, quote_candidate)
  → CrossCheckNode            ← fast tier (adds script_language per claim)
  → TimelineBuilderNode       ← fast tier (tension escalation validated deterministically)
  → EmotionalExtractionNode   ← fast tier
  → OutlineNode               ← creative tier + lessons injection (minute_range, rehook_plan)
  → HardGuardrailsNode        (no LLM — deterministic validation gate)
  → ScriptGenerationNode      ← fast tier + lessons injection (Stage A: draft)
  → FactTightenNode           ← fast tier (Stage B: trace tags + per-paragraph fact-checking)
  → RetentionPassNode         ← fast tier + lessons injection (surgery-only: no new entities)
  → EmotionalIntensityNode    ← fast tier
  → SensoryDensityCheckNode   ← fast tier
  → QualityCheckNode          ← fast tier (loops back to ScriptGeneration if QC fails, max 2 retries)
  → FinalizeNode              (no LLM — saves feedback to .memory/)
```

### Dual-Model Tiers

| Tier | Env Var | Used By | Why |
|------|---------|---------|-----|
| **Creative** | `OPENAI_MODEL` | Outline | Deep, nuanced story-arc design |
| **Fast** | `OPENAI_FAST_MODEL` | TopicDiscovery, Scoring, Claims, CrossCheck, Timeline, Emotional, ScriptGeneration, FactTighten, RetentionPass, Sensory, QC | Direct prose, structured JSON extraction — speed over literary flourish |

If `OPENAI_FAST_MODEL` is not set, all nodes fall back to `OPENAI_MODEL`.

### Feedback Memory (Cross-Run Learning)

After every run, the agent saves QC issues and recommendations to `.memory/`:

```
.memory/
├── feedback_log.jsonl      # Raw feedback from every run (append-only)
└── distilled_lessons.json  # Recurring patterns, word count trends, pass rate
```

On the next run, the **Outline**, **ScriptGeneration**, and **RetentionPass** nodes automatically load distilled lessons and prepend them to their prompts. The agent learns to:

- Avoid recurring issues (e.g., "scripts tend to run LONG at 158% of target")
- Follow past recommendations (e.g., "complete Act 3 before closing")
- Improve pass rate over successive runs

The `.memory/` directory is gitignored — each user's agent learns independently.

### Validation Gates (`validators.py`)

The pipeline uses **deterministic validators** that cannot be bypassed by LLM hallucination. These run at two checkpoints:

#### Pre-Script Gate (HardGuardrailsNode — between Outline and ScriptGeneration)

| Validator | Code | Severity | What it checks |
|-----------|------|----------|----------------|
| Outline word-sum | `OUTLINE_WORD_SUM_MISMATCH` | soft | Section word counts must sum to target ±10% |
| Open-loop resolution | `OPEN_LOOP_UNRESOLVED` | soft | Every open loop must resolve within 2 sections |
| Tension escalation | `TENSION_TOO_MANY_DIPS` | hard | At most 2 non-increasing tension transitions |
| Tension spike recovery | `TENSION_NO_SPIKE_AFTER_DIP` | soft | Any dip must recover +2 within 1 beat |
| Twist distribution | `TWIST_DISTRIBUTION_SKEWED` | soft | ≥50% of twists must fall in Act 2 range |
| No twists | `NO_TWISTS` | hard | Timeline must have at least one twist beat |

Any issues found are injected as feedback into the ScriptGeneration prompt.

#### Post-Script Gate (FactTightenNode — after draft generation)

| Validator | Code | Severity | What it checks |
|-----------|------|----------|----------------|
| Word count | `WORD_COUNT_UNDER` / `WORD_COUNT_OVER` | hard | Script must be within min_words–max_words |
| Entity provenance | `ENTITY_NOT_IN_CLAIMS` | hard | Every named human must appear in verified claims or timeline beats |
| Rehook cadence | `REHOOK_GAP` | soft | No stretch > 1.25× rehook interval without a re-hook signal |
| Essay blocks | `ESSAY_BLOCK` | hard | No 60+ word blocks with zero names, sensory cues, or decision verbs |

#### Retention Surgery Guard (RetentionPassNode)

| Validator | Code | Severity | What it checks |
|-----------|------|----------|----------------|
| No new entities | `RETENTION_NEW_ENTITY` | hard | Retention pass cannot introduce named humans not in the original script |

If the retention pass introduces new entities or violates word count, the original script is used instead.

#### Two-Stage Script Generation

Script generation is split into two stages:

1. **Stage A (ScriptGenerationNode)**: Writes the draft from outline + verified claims + script_language
2. **Stage B (FactTightenNode)**: Rewrites the draft and appends hidden trace tags per paragraph:
   ```
   The general ordered the advance. [Beat B03 | Claims C001,C012]
   ```
   These tags are stripped from `final_script` but available for audit via `extract_trace_tags()`.

#### Running Validator Tests

```bash
pytest tests/test_validators.py -v
```

41 tests cover all schemas, validators, trace-tag utilities, and integration scenarios.

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
| `narrative_lens` | ❌ | None | Narrative lens(es) — comma-separated (e.g. `civilians`, `medics,logistics`) |
| `lens_strength` | ❌ | 0.6 | How strongly the lens biases storytelling (0.0–1.0) |
| `geo_scope` | ❌ | None | Geographic scope (`single_city`, `region`, `country`, `theater`, `global`) |
| `geo_anchor` | ❌ | None | Physical focal point for spatial cohesion |
| `mobility_mode` | ❌ | None | Spatial narrative mode (`fixed_site`, `route_based`, `multi_site`, `theater_wide`) |

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
├── script.md              # Final documentary script (with structural labels)
├── script_elevenlabs.txt  # Pure narration text for ElevenLabs TTS
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
├── nodes/                 # All 18 pipeline nodes
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
│   ├── hard_guardrails.py
│   ├── script_generation.py
│   ├── fact_tighten.py
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
│   ├── llm.py             # Dual-model LLM wrapper with rate limiting
│   ├── feedback_memory.py # Cross-run learning system
│   ├── retry.py
│   ├── cache.py
│   └── logging.py
└── output/                # Output formatters
    ├── __init__.py
    ├── formatter.py              # Markdown output formatter
    └── elevenlabs_formatter.py   # ElevenLabs TTS text formatter
```

## Scaling Notes

- **Dual-Model**: Use a fast model (GPT-5.2) for script writing and analytical nodes, and a creative model (GPT-5) for story-arc design — balances speed, prose quality, and cost
- **Feedback Loop**: The more runs you do, the better the agent gets — feedback memory distills patterns automatically
- **Batch Processing**: Wrap `run_agent()` in async loop for bulk generation
- **Caching**: HTTP responses cached by default to `.cache/` — reduces API costs on reruns
- **Claims Capping**: Extraction limited to 5 sources × 10 claims (50 max) to prevent token bloat
- **QC Retry Loop**: Conditional loop back to ScriptGeneration (max 2 retries) if word count or quality fails
- **Parallel Research**: Research fetches run concurrently across sources
- **State Checkpointing**: LangGraph state can be persisted for resumption

## Monetization Extensions

- ✅ **Voice synthesis integration**: ElevenLabs TTS formatter outputs pure narration text (`script_elevenlabs.txt`)
- Add image/B-roll suggestion nodes for video production
- Add thumbnail title generation node
- Add SEO metadata generation (tags, description)
- Add multi-language translation node
- Add Patreon-tier extended cut generation (longer scripts with bonus sections)

## Web UI

A professional-grade web interface built with **Next.js 14** + **shadcn/ui** + **Tailwind CSS**, backed by a **FastAPI** server.

### Running Locally

```bash
# Terminal 1: Start the API server
uvicorn api.server:app --reload --port 8000

# Terminal 2: Start the frontend
cd web && npm install && npm run dev
```

Open http://localhost:3000 — the dashboard connects to the API at http://localhost:8000.

### Features

- **Generate Form**: Full parameter control (video length, era, geo, tone, sensitivity, format rotation, narrative lens, geo scope, mobility)
- **Live Pipeline Tracker**: Real-time 18-node progress with SSE streaming, tier badges (creative/fast), per-node data
- **Script Viewer**: Tabbed view — Script, Sources, QC Report, Stats — with markdown rendering
- **Export**: Download script as `.md` or sources as JSON
- **Run History**: Browse and reload past generation runs
- **Dark Theme**: Cinematic dark UI designed for content creators

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check + model info |
| `POST` | `/generate` | Start a pipeline run (returns `run_id`) |
| `GET` | `/runs/{id}/stream` | SSE stream of real-time node progress |
| `GET` | `/runs` | List recent runs |
| `GET` | `/runs/{id}` | Get full run details + script |
| `POST` | `/runs/{id}/cancel` | Cancel a running pipeline |
| `GET` | `/runs/{id}/export/script` | Download script as markdown |
| `GET` | `/runs/{id}/export/sources` | Download sources as JSON |

Interactive API docs at http://localhost:8000/docs (Swagger UI).

## Deployment

### Free Tier Hosting

| Service | Platform | Free Tier |
|---------|----------|-----------|
| **API** (FastAPI) | [Fly.io](https://fly.io) | 3 shared VMs, 256MB each |
| **Frontend** (Next.js) | [Vercel](https://vercel.com) | Unlimited static, 100GB bandwidth |

### Deploy the API (Fly.io)

```bash
# 1. Install flyctl
curl -L https://fly.io/install.sh | sh

# 2. Login & launch
flyctl auth login
flyctl launch   # Creates app from fly.toml

# 3. Set secrets (one-time)
flyctl secrets set OPENAI_API_KEY="sk-..."
flyctl secrets set OPENAI_MODEL="gpt-5"
flyctl secrets set OPENAI_FAST_MODEL="gpt-5.2"
flyctl secrets set CORS_ORIGINS="https://your-app.vercel.app,http://localhost:3000"

# 4. Deploy
flyctl deploy
```

### Deploy the Frontend (Vercel)

1. Go to [vercel.com/new](https://vercel.com/new)
2. Import repo: `devbyomar/history-tales-script-generator`
3. Set **Root Directory** to `web`
4. Add environment variable:
   - `NEXT_PUBLIC_API_URL` = `https://history-tales-api.fly.dev`
5. Click **Deploy**

### Or Use the Deploy Script

```bash
./deploy.sh --set-secrets   # First time (sets Fly.io secrets)
./deploy.sh                 # Subsequent deploys
```

## License

MIT