# RECAST — Technical Notes

Implementation detail behind the [main README](../README.md): backend
contracts, validation rules, failure behaviour and the reasoning behind each
design decision.

## Implementation status

Phase 7 — the full pipeline. Upload one video and RECAST transcribes it, derives
a structured **Content DNA**, selects and scores the strongest **short-form
moments**, renders each as a real **vertical 9:16 MP4** with a thumbnail, and
writes a **six-platform campaign** (YouTube, Instagram, TikTok, Facebook,
LinkedIn, X), **3 thumbnail concepts**, and an **AI quality score** with
actionable recommendations — presented in a polished dashboard with a
one-click campaign export.

Transcription and analysis both run on **Groq** by default (fast, free tier).
Both can also run fully offline — faster-whisper for transcription, Ollama for
analysis — see [Transcription backends](#transcription-backends) and
[Analysis backends](#analysis-backends).

Pipeline: `upload → store → extract metadata (ffprobe) → 16kHz mono audio (ffmpeg)
→ transcribe (Whisper)`.

**No API key is required.** Transcription runs locally by default via
faster-whisper.

## Stack

- **Frontend**: Next.js (App Router, TypeScript), Tailwind CSS, shadcn/ui
- **Backend**: FastAPI, SQLAlchemy, SQLite
- **Transcription**: faster-whisper (local, default) or the OpenAI Whisper API
- **AI**: OpenAI API (content analysis not wired up yet)
- **Media**: FFmpeg / ffprobe

## Project structure

```
recast/
├── frontend/
│   └── src/
│       ├── app/          # pages: / (dashboard), /projects/[id]
│       ├── components/   # UploadDropzone, PipelineSteps, TranscriptPanel,
│       │                 #   ContentDnaView, BestMomentsPanel, ShortsSection,
│       │                 #   CampaignPanel, ThumbnailSection,
│       │                 #   CampaignScoreCard, ProjectCard, ui/*
│       ├── lib/          # api client, utils
│       └── types/        # shared TypeScript types
├── backend/
│   ├── app/
│   │   ├── api/          # FastAPI routers: health, projects, upload
│   │   ├── core/         # config, database, logging
│   │   ├── models/       # SQLAlchemy models
│   │   ├── schemas/      # Pydantic request/response schemas
│   │   ├── services/     # media (ffmpeg), transcription, pipeline orchestration
│   │   └── main.py
│   ├── storage/          # uploads, audio, clips, thumbnails, sqlite db (gitignored)
│   └── tests/            # pytest suite
├── sample_data/          # local test videos (gitignored)
├── .env.example
└── .gitignore
```

## Quick start

**Requires:** Python 3.12, Node.js 20+, FFmpeg on PATH (`ffmpeg` and `ffprobe`),
and a free Groq API key from <https://console.groq.com/keys>.

### 1. Backend

```bash
cd backend
py -3.12 -m venv .venv
source .venv/Scripts/activate      # Windows Git Bash
# (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
cp ../.env.example .env            # then paste your GROQ_API_KEY
uvicorn app.main:app --reload --port 8000
```

### 2. Frontend

```bash
cd frontend
npm install
printf 'NEXT_PUBLIC_API_URL=http://localhost:8000
' > .env.local
npm run dev
```

Open <http://localhost:3000>. API docs at <http://localhost:8000/docs>.

### 3. (Optional) Seed a ready-made demo project

Runs the real pipeline end to end against a generated narrated sample, so the
app has polished content before a demo:

```bash
cd backend && source .venv/Scripts/activate
python scripts/seed_demo.py                  # ~45s
python scripts/seed_demo.py --video mine.mp4 # or use your own footage
```

It prints the project URL when finished.

## Environment variables

`backend/.env` — everything is server-side; no key ever reaches the browser.

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `GROQ_API_KEY` | **Yes** | — | Powers analysis, moments, campaign, scoring |
| `TRANSCRIPTION_BACKEND` | No | `groq` | `groq` \| `local` \| `openai` \| `auto` |
| `ANALYSIS_BACKEND` | No | `groq` | `groq` \| `local` \| `openai` \| `auto` |
| `GROQ_ANALYSIS_MODEL` | No | `llama-3.3-70b-versatile` | Text model |
| `GROQ_TRANSCRIPTION_MODEL` | No | `whisper-large-v3-turbo` | Speech model |
| `WHISPER_MODEL_SIZE` | No | `base` | Local Whisper size, if used |
| `OPENAI_API_KEY` | No | — | Only for the OpenAI backends |
| `OLLAMA_HOST` / `OLLAMA_MODEL` | No | `localhost:11434` / `llama3.2:3b` | Only for the local LLM backend |
| `IMAGE_GENERATION_BACKEND` | No | *(empty)* | No image API wired up; thumbnails render from real frames |
| `DATABASE_URL` | No | `sqlite:///./storage/recast.db` | SQLite path |
| `CORS_ORIGINS` | No | `http://localhost:3000` | Allowed frontend origins |
| `FFMPEG_BIN` / `FFPROBE_BIN` | No | `ffmpeg` / `ffprobe` | Override if not on PATH |

`frontend/.env.local`

| Variable | Required | Default |
|----------|----------|---------|
| `NEXT_PUBLIC_API_URL` | No | `http://localhost:8000` |

## Demo flow (2 minutes)

RECAST tells one story: **one video in, an entire campaign out.**

| # | Beat | What to show | ~Time |
|---|------|--------------|-------|
| 1 | **Upload** | Drag a video onto the dropzone. It navigates straight to the project. | 10s |
| 2 | **AI Understands** | The Progress timeline moves through *Upload → AI Understands*. Point at the Content DNA row: topic, audience, tone, core message. | 25s |
| 3 | **Finds Best Moments** | Scroll to **Best Moments** — ranked clips with score breakdowns and "Why this works". | 20s |
| 4 | **Creates Shorts** | **Generate All Shorts** → real vertical 9:16 clips play inline. | 20s |
| 5 | **Adapts to Platforms** | Hit the big **Generate Campaign** button, then click across the six tabs. Contrast the terse TikTok caption with the long-form LinkedIn post. | 30s |
| 6 | **Campaign Ready** | The green banner: *"Everything is ready to publish."* Hit **Download campaign** and open the file. | 15s |

**Tip:** run `seed_demo.py` beforehand so a finished project is already on the
dashboard. Demo the pre-seeded one, and kick off a live upload only if there is
time — a fresh run takes ~45s end to end.

## Known limitations

- **Groq free tier caps at 100k tokens/day.** Heavy repeated demoing can exhaust
  it; the app degrades gracefully (partial campaigns, named failures) rather than
  crashing. A paid tier or `ANALYSIS_BACKEND=local` avoids it.
- **Clip rendering is CPU-bound**, roughly 18s per short, and runs sequentially.
  Generate shorts before presenting.
- **Hosted transcription caps uploads at 25MB** (~25 min of video after FLAC
  compression). Longer videos need `TRANSCRIPTION_BACKEND=local`.
- **No image generation API is wired up**, so thumbnails are render-ready specs
  composed over real extracted frames rather than AI-generated artwork.
- **No authentication.** Every project is visible to anyone with the URL; this is
  a local hackathon build, not a multi-tenant service.
- **Background tasks are in-process.** Restarting the API mid-run loses that run;
  the project is preserved and can be retried.
- **Fewer than 3 moments** can be returned on short videos, where overlap
  suppression legitimately collapses near-duplicates.
- **Publishing is not implemented** — RECAST prepares content; you still post it.

## Recommended README screenshots

1. **Landing page** with the upload dropzone, stat tiles and a project card —
   sets up "one video in".
2. **Progress timeline** mid-run, with *AI Understands* spinning — proves it is
   really working, not canned.
3. **Best Moments** card showing score bars and "Why this works" — the most
   novel screen.
4. **Shorts grid** with three 9:16 previews — the most visual proof.
5. **Campaign tabs side by side** (TikTok vs LinkedIn) — the differentiation
   claim, evidenced.
6. **Campaign Score** dial with the improvements list — shows self-critique.
7. **Campaign ready banner** — the payoff line, "Everything is ready to publish."

## API

| Method | Path             | Description                                   |
|--------|------------------|------------------------------------------------|
| GET    | `/api/health`    | Service health + whether OpenAI is configured  |
| POST   | `/api/projects`  | Create a project shell (`{ "title"?: string }`)|
| GET    | `/api/projects`  | List all projects                              |
| GET    | `/api/projects/{id}` | Get full project detail                    |
| DELETE | `/api/projects/{id}` | Delete a project and its video             |
| POST   | `/api/upload`    | Attach a video to a project (multipart: `project_id`, `video`) |
| POST   | `/api/projects/{id}/process` | Start the media pipeline (runs in the background) |
| GET    | `/api/projects/{id}/transcript` | Transcript with timestamped segments |
| POST   | `/api/projects/{id}/analyze` | Build Content DNA from the transcript (background) |
| GET    | `/api/projects/{id}/content-dna` | The structured Content DNA |
| POST   | `/api/projects/{id}/moments` | Detect the best short-form moments (background) |
| GET    | `/api/projects/{id}/moments` | Ranked best moments with score breakdowns |
| POST   | `/api/projects/{id}/clips` | Render a moment as a short (`{"moment_id": "m1"}`) |
| GET    | `/api/projects/{id}/clips` | List rendered clips |
| GET    | `/api/projects/{id}/clips/{clip_id}/download` | Download a clip as an attachment |
| POST   | `/api/projects/{id}/campaign` | Generate the campaign (`?platform=tiktok` for one) |
| GET    | `/api/projects/{id}/campaign` | The generated campaign + score |
| POST   | `/api/projects/{id}/thumbnails` | Generate 3 thumbnail concepts |
| GET    | `/api/projects/{id}/thumbnails` | The thumbnail concepts |
| POST   | `/api/projects/{id}/evaluate` | Re-run the AI quality evaluation |
| GET    | `/api/projects/{id}/evaluation` | Quality scores + improvements |

Upload flow: create a project, then upload a video against its `project_id`.
Accepted formats: `.mp4 .mov .avi .mkv .webm`, up to 500MB (validated on both
client and server).

## Transcription backends

Selected with `TRANSCRIPTION_BACKEND` in `backend/.env`:

| Value | Behaviour |
|-------|-----------|
| `auto` (default) | Prefer Groq, then local Whisper, then OpenAI |
| `groq` | Groq hosted `whisper-large-v3-turbo`. Requires `GROQ_API_KEY` |
| `local` | faster-whisper on this machine. Free, offline, no upload limit |
| `openai` | OpenAI Whisper API. Requires `OPENAI_API_KEY` |

Measured on a 5-minute video (this machine, CPU only, no GPU):

| Backend | Time | Speed |
|---------|------|-------|
| `local` (base, int8) | 127s | 2.4x realtime |
| `groq` (whisper-large-v3-turbo) | **9.6s** | **32x realtime** |

Audio is converted to FLAC before upload, which halves the payload and roughly
doubles the video length that fits under Groq's 25MB cap (~25 min). Above that
limit the error tells you to switch to `TRANSCRIPTION_BACKEND=local`, which has
no size limit.

The local backend downloads its model on first run (~140MB for `base`) and caches
it. Tune accuracy vs. speed with `WHISPER_MODEL_SIZE`
(`tiny`/`base`/`small`/`medium`/`large-v3`).

If no backend is available the run fails with a clear error — it never fabricates
a transcript.

> **Why not the browser's built-in speech API?** It only transcribes live
> microphone input rather than uploaded files, returns no segment timestamps
> (needed later to cut clips), and keeps the transcript on the client when the
> server needs it for analysis.

## Transcript format

`GET /api/projects/{id}/transcript` returns:

```json
{
  "project_id": "…",
  "text": "Welcome back to the channel…",
  "language": "en",
  "duration": 40.588,
  "segments": [
    { "start": 0.0, "end": 8.0, "text": "Welcome back to the channel…" }
  ]
}
```

Returns `404` if the transcript is not ready yet, and `409` with the failure
reason if processing failed.

## Error handling & retry

If transcription fails, the project and its uploaded video are preserved and the
status becomes `failed` with the reason stored in `error_message`. The UI shows
the reason plus a **Retry processing** button that re-runs the pipeline without
re-uploading (`POST /api/projects/{id}/process` again).

## API key safety

The OpenAI key is read server-side only, from `backend/.env` via pydantic-settings.
It is never sent to the frontend: the browser bundle contains no key, and the only
client-visible env var is `NEXT_PUBLIC_API_URL`.

## Content DNA

Content DNA is the **single source of truth** for everything generated later.
Platform generators (YouTube, Instagram, TikTok, LinkedIn, X) consume
`ContentDNA + transcript` — they never re-derive their own understanding of the
video. `key_topics` is likewise derived from the DNA rather than computed
separately.

`GET /api/projects/{id}/content-dna` returns:

```json
{
  "project_id": "…",
  "content_dna": {
    "primary_topic": "Repurposing video content",
    "secondary_topics": ["Automation"],
    "audience": "Content creators",
    "tone": "Educational",
    "content_type": "Explainer",
    "core_message": "One video can become an entire campaign.",
    "key_points": ["…"],
    "important_concepts": ["…"],
    "entities": ["RECAST"],
    "keywords": ["…"],
    "hooks": ["…"],
    "cta": "Subscribe for more",
    "key_moments": [
      {"timestamp": 8.0, "title": "The problem", "description": "why it matters"}
    ]
  }
}
```

It is validated with Pydantic before being stored, which also:

- coerces sloppy model output (a list where a string was expected)
- de-duplicates and trims keyword/topic lists
- normalises absent CTAs (`"none"`, `"N/A"`, `""`) to `null`
- **drops hallucinated timestamps** that fall beyond the video's duration

## Analysis backends

Selected with `ANALYSIS_BACKEND` in `backend/.env`:

| Value | Behaviour |
|-------|-----------|
| `auto` (default) | Prefer Groq, then Ollama, then OpenAI |
| `groq` | Groq chat completions. Fast, free tier, no download. Requires `GROQ_API_KEY` |
| `local` | Ollama on this machine. Free, offline, but needs a ~2GB model download |
| `openai` | OpenAI chat completions. Requires `OPENAI_API_KEY` |

**Groq is the default setup here** — `llama-3.3-70b-versatile` returns a full
Content DNA in ~2s with no local model. Get a key at
<https://console.groq.com/keys> and set `GROQ_API_KEY` in `backend/.env`.

Optional local setup (no API key at all):

```bash
winget install Ollama.Ollama      # or https://ollama.com/download
ollama pull llama3.2:3b
```

The model is downloaded **once, onto the machine running the backend** — visitors
to the web app never download it.

To store models on a different drive, set `OLLAMA_MODELS` before Ollama starts:

```powershell
[Environment]::SetEnvironmentVariable("OLLAMA_MODELS", "E:\ollama\models", "User")
```

Restart Ollama afterwards so it picks up the new location. This machine is
already configured to keep models on `E:\ollama\models`.

If no backend is available, analysis fails with an actionable message; it never
fabricates a Content DNA.

## Best moments

Moments are selected from `transcript + Content DNA` and returned strongest-first:

```json
{
  "start": 43.859997,
  "end": 69.96,
  "title": "Finding the Solution",
  "hook": "So what is the fix?",
  "reason": "Directly addresses the problem stated earlier.",
  "score": 86,
  "scores": {
    "hook_strength": 85,
    "information_value": 95,
    "standalone_quality": 85,
    "emotional_interest": 80
  }
}
```

### Timestamps are never invented

The model is not allowed to produce timestamps at all. Instead:

1. **Python** groups consecutive transcript segments into candidate windows
   (12-75s), always starting and ending on real segment boundaries
2. The **LLM** picks and scores windows **by numeric id**, never by time
3. Ids map back to the original window; an unknown id is discarded rather than
   guessed, and if no id is valid the run fails instead of inventing a range
4. Overlapping picks are suppressed (intersection-over-shorter-clip > 0.5)
5. The top 3-5 survivors are returned

Window bounds are stored unrounded so downstream code can join a moment back to
its transcript segments by exact equality.

The overall `score` is always recomputed as the mean of the four components --
models routinely emit an overall score that contradicts their own breakdown.

Note: fewer than 3 moments can be returned for short videos, where overlap
suppression legitimately removes near-duplicate windows. Padding the list would
mean shipping weaker or duplicate clips.

## Short video generation

`POST /api/projects/{id}/clips` with `{"moment_id": "m1"}` renders a real MP4:

```json
{
  "clip_id": "abc123_m1",
  "video_url": "/media/clips/abc123_m1.mp4",
  "thumbnail_url": "/media/thumbnails/abc123_m1.jpg"
}
```

(plus `title`, `hook`, `score`, `duration`, `width`, `height`, `vertical`.)

### Reframing

| Source | Behaviour |
|--------|-----------|
| Already ~9:16 | No reframe. Stream-copied when the cut is accurate, avoiding a needless re-encode |
| Landscape / square | 1080x1920 canvas: footage scaled to fit, centred over a blurred zoomed copy of itself |

The blurred-background approach means **nothing is cropped** — faces and on-screen
text at the edges survive, which a centre-crop would destroy.

### Avoiding unnecessary re-encoding

When no reframing is needed, a `-c copy` cut is attempted first. Stream copy can
only cut on keyframes, so the result is verified against the requested duration
and discarded if it drifted more than 0.75s. Sources with dense keyframes are
copied (fast, lossless); sparse ones fall back to re-encoding so the clip starts
on the right word.

Quality: `libx264 -crf 20 -preset veryfast`, AAC 128k, `+faststart` for
progressive playback.

### Thumbnails

A JPEG frame is grabbed from the **midpoint** of each clip (edges are often fades
or black) and used as the `poster` for the preview player.

### Downloads

`<a download>` is ignored by browsers for cross-origin URLs, and the API runs on
a different port to the app — so a plain link to `/media/clips/...` would *play*
the video instead of saving it. The download endpoint sets
`Content-Disposition: attachment` with a filename derived from the moment title.

## Project statuses

`pending → uploaded → processing → transcribing → transcribed → analyzing → analyzed
→ detecting_moments → moments_ready`, plus `generating` and `completed`
(reserved for later phases) and `failed`.

## Testing

```bash
cd backend && source .venv/Scripts/activate && python -m pytest
```

The suite blocks outbound network calls to LLM providers. Services resolve their
own backend via `get_analysis_service()`, so patching the wrong module silently
produces a test that calls Groq for real — slow, flaky, billable, and asserting
against whatever the model happened to say. The guard turns that into an
immediate, obvious failure. Storage is redirected to a temp directory so test
runs never write into the repo.

## Next phase

Campaign export/packaging (download the whole campaign as a bundle), plus
optional direct publishing.

## Multi-platform campaign

Each platform gets its **own spec, own prompt and own LLM call** — six calls, not
one prompt producing six variations. The spec fixes what actually differs:

| Platform | Tone | Length | Hook strategy | CTA strategy |
|----------|------|--------|---------------|--------------|
| YouTube | Informative, search-aware | 150-300 word description | Outcome/number in title | Soft, end of description |
| Instagram | Warm, first-person | 80-150 words, line-broken | First line must survive truncation | Invite a comment/save |
| TikTok | Casual, lowercase | Under 150 chars | Pattern interrupt, curiosity gap | Native: follow for part 2 |
| Facebook | Plain-spoken | 60-120 words | Relatable problem, assumes no context | Direct question |
| LinkedIn | Professional, insight-led | 150-250 words | Counter-intuitive observation | Peer discussion |
| X | Terse, declarative | Under 280 chars | Flat claim, no throat-clearing | Minimal or none |

Real output from one run shows the difference clearly:

- **TikTok**: `one video, multiple platforms, zero stress`
- **LinkedIn**: `The manual process of cutting clips, writing captions, and rewriting content for each platform is not only time-consuming but also inefficient.`

Every field is validated against real platform limits (X 280, YouTube title 100,
LinkedIn 3000, Instagram 2200), with hashtags normalised, de-duplicated and
capped per platform (Instagram 30, TikTok 8, Facebook/LinkedIn 5).

### YouTube chapters

Chapters are built in Python from Content DNA key-moment timestamps — never from
model output. YouTube only renders chapters that start at `0:00`, number at least
3, and are 10s+ apart, so anything failing those rules is dropped rather than
shipped broken.

### Partial failures

Platforms are generated independently. If one fails (rate limit, malformed JSON),
the rest are still saved and the failure is named in `error_message` — a partial
campaign beats losing five good ones. `POST .../campaign?platform=x` retries just
that platform, leaving the others untouched.

### Campaign score

A transparent, deterministic 0-100 score (not model-generated): platform coverage
(50), Content DNA richness (25), clip-worthy moments (15), and completeness of
high-effort assets like 3 titles / chapters / an X thread (10).

## Thumbnail concepts

Three distinct concepts are generated from Content DNA plus the strongest
moments. Each carries a headline, visual concept, subject placement, emotional
angle, why it attracts attention, and a recommended use case.

**No image-generation API is available** — Groq offers no image models and no
OpenAI key is set. Rather than shipping abstract mockups, RECAST extracts a
**real frame** from the video at each concept's timestamp and the frontend
composes the headline over it using the spec's text position and accent colour.
The preview therefore shows actual footage.

`image_generation_available` is returned on the endpoint and
`IMAGE_GENERATION_BACKEND` is the single setting to flip when an image API is
wired up.

Timestamps are chosen the same way as moments: the model picks a frame **by id**
from options built from real moment timestamps, so a concept can never reference
a time that does not exist. An unusable id falls back to spreading across the
available frames rather than dropping the concept.

### Isolation

Thumbnails are an add-on and are deliberately non-fatal: if generation fails, the
project keeps its previous status, campaign and score untouched, and
`GET /thumbnails` returns an empty list rather than an error. There is a test
asserting exactly that.

## Campaign quality scoring

Two scores, measuring different things:

| Score | What it measures | How |
|-------|------------------|-----|
| `campaign_score` | **Completeness** — platforms covered, DNA richness, assets present | Deterministic formula |
| `evaluation.overall` | **Quality** — is the copy actually good? | AI evaluator |

They diverge usefully. A real run scored **95 completeness** (all six platforms
generated) but **75 quality** (weak platform adaptation and CTAs) — the campaign
was complete but not yet good.

Evaluated dimensions: content quality, platform adaptation, hook strength, source
consistency, SEO quality, CTA quality — each 0-100, with `overall` **always
recomputed** as their mean, since models routinely state an overall that
contradicts their own breakdown.

The evaluator is prompted to be hard to impress (average is the 60s) and to
return 3-5 improvements that name a concrete change. Real output:

> **[HIGH] Facebook and LinkedIn CTAs** — Replace the open-ended questions with
> more specific and actionable CTAs, such as 'Download our guide to efficient
> video repurposing'

### Scoring never blocks generation

Evaluation runs after the campaign is saved and is wrapped in a deliberately
broad `except Exception`. Any failure — expected or not — logs a warning and
leaves the campaign, its completeness score and its status untouched;
`GET /evaluation` then returns `evaluation: null` rather than an error. Two tests
cover this: one for a clean `EvaluationError`, one for an unexpected crash.

## Application flow

```
Landing → Upload → Processing → Content DNA → Best Moments
        → Shorts → Campaign → Final Results
```

The project page opens with a summary showing the project name, source video,
status, Content DNA at a glance, and a funnel of what was produced:

```
1 VIDEO → 1 CONTENT DNA → 3 SHORTS → 6 PLATFORM POSTS → 27 CONTENT ASSETS
```

Counts are real. "Content assets" counts each discrete deliverable — every
YouTube title, the description, chapters, keyword and tag sets, each caption,
hook, CTA and hashtag set, plus every rendered short and thumbnail concept.

### Campaign ready

When a campaign completes, the summary turns into a **Campaign ready** state —
"Everything is ready to publish" — with **Copy all** and **Download campaign**.
The export is assembled client-side into a plain-text file containing the
Content DNA, all six platforms, thumbnail concepts, shorts and the suggested
improvements. No backend round-trip.

## Storage layout

```
backend/storage/
├── uploads/      source videos
├── audio/        extracted 16kHz mono WAV
├── clips/        rendered vertical shorts
└── thumbnails/   clip poster frames
```

All are gitignored. Tests redirect these to a temp directory so a test run never
writes into the repo.
