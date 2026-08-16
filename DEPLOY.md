# Deploying RECAST to Render

Two services, defined in [`render.yaml`](./render.yaml):

| Service | Runtime | Why |
| --- | --- | --- |
| `recast-api` | **Docker** | The pipeline shells out to `ffmpeg`/`ffprobe`, which Render's native Python runtime does not include. |
| `recast-web` | Node | Plain `next build` / `next start`. |

---

## Before you start: read this

**Persistent storage is not optional.** RECAST writes uploads, extracted audio,
rendered clips, thumbnails, subtitles and a SQLite database to disk. Render's
filesystem is ephemeral — without a disk, **every deploy and every restart wipes
all projects**. Render disks require a paid instance type, so `render.yaml` sets
`plan: starter` on the API.

If you deploy the API on **Free**, expect:

- all data lost on each redeploy and on every wake-from-sleep,
- the service sleeping after ~15 minutes idle, with a slow cold start,
- 512 MB RAM, which FFmpeg re-encoding a 1080p clip will strain.

For a live demo, put at least the API on Starter.

---

## 1. Put the project in Git

The project is not currently a repository. **Initialise it inside `recast/`, not
`E:\Recast`** — `E:\Recast\keys.txt` sits one level up and must never be
committed.

```bash
cd E:\Recast\recast
git init
git add .
git commit -m "RECAST"
```

Confirm no secrets were staged. All three must print nothing:

```bash
git ls-files | grep -E "groq_keys.txt|\.env$|keys.txt"
```

`.gitignore` already excludes `backend/.env`, `backend/groq_keys.txt` and
everything under `backend/storage/`.

Then push:

```bash
git remote add origin https://github.com/<you>/recast.git
git branch -M main
git push -u origin main
```

> Rotate your Groq keys at <https://console.groq.com/keys> before making the
> repo public. Several were pasted into chat during development.

## 2. Create the Blueprint

1. Render Dashboard → **New** → **Blueprint**.
2. Connect the repository. Render finds `render.yaml` at the root.
3. It will show **recast-api** and **recast-web**. Click **Apply**.

Render prompts for the three variables marked `sync: false`. Two of them are
each other's URL, so fill them in this order.

## 3. Set the API variables

On **recast-api** → Environment:

| Key | Value |
| --- | --- |
| `GROQ_API_KEYS` | Your keys, comma-separated: `gsk_aaa,gsk_bbb,gsk_ccc` |
| `CORS_ORIGINS` | Leave blank for now — set in step 5. |

`groq_keys.txt` is deliberately not in the image, so the pool reads
`GROQ_API_KEYS` instead. Rotation and cooldown behave identically.

Let the API finish deploying and copy its URL, e.g.
`https://recast-api.onrender.com`. Check it:

```bash
curl https://recast-api.onrender.com/api/health
```

You should get `"status": "ok"` plus an `ai` block reporting your key count.

## 4. Set the frontend variable

On **recast-web** → Environment:

| Key | Value |
| --- | --- |
| `NEXT_PUBLIC_API_URL` | `https://recast-api.onrender.com` (no trailing slash) |

**This is inlined into the JavaScript bundle at build time, not read at
runtime.** Changing it later requires a new build ("Clear build cache & deploy"),
not a restart. Getting this wrong is the single most common failure: the site
loads, and every request goes to `localhost:8000`.

Deploy, then copy the frontend URL, e.g. `https://recast-web.onrender.com`.

## 5. Close the CORS loop

Back on **recast-api** → Environment:

| Key | Value |
| --- | --- |
| `CORS_ORIGINS` | `https://recast-web.onrender.com` |

Save — the API restarts automatically. Comma-separate to allow more than one
origin. Without this the browser blocks every API call and the UI shows
"Backend unreachable" while `curl` works fine.

## 6. Verify

Open the frontend and check, in order:

1. Sidebar shows **AI Engine ● Ready** — the browser can reach the API and keys are loaded.
2. Upload a short clip (start with something under ~50 MB).
3. The pipeline advances Upload → Understanding → Finding Moments.
4. **Generate campaign** produces six platforms.
5. Generate a short — this is the FFmpeg path, and the slowest step on a small instance.

---

## Configuration reference

Everything below has a working default; set it only to change behaviour.

| Variable | Default | Notes |
| --- | --- | --- |
| `GROQ_API_KEYS` | — | Comma-separated pool. **Required.** |
| `CORS_ORIGINS` | `http://localhost:3000` | Comma-separated frontend origins. |
| `TRANSCRIPTION_BACKEND` | `groq` (set in blueprint) | `local` needs faster-whisper, which the deploy image omits. |
| `ANALYSIS_BACKEND` | `groq` | |
| `GROQ_ANALYSIS_MODEL` | `llama-3.3-70b-versatile` | |
| `GROQ_TRANSCRIPTION_MODEL` | `whisper-large-v3-turbo` | |
| `DATABASE_URL` | SQLite on the disk | Point at Postgres if you outgrow one instance. |
| `BURN_SUBTITLES` | `true` | Captions burned into generated shorts. |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Frontend only. **Build-time.** |

---

## Known constraints on Render

**Keep the API at one instance.** State lives in two places that do not survive
horizontal scaling: SQLite on a single mounted disk, and the API-key cooldown
pool, which is per-process and in-memory.

**Uploads are limited by the proxy, not the app.** The app accepts 500 MB, but a
large upload over a slow link can exceed Render's request limits. Demo with
short clips. Everything after the upload runs as a background task, so only the
upload itself is a long-lived request.

**Background tasks die with the instance.** Processing runs in-process via
FastAPI `BackgroundTasks`. If the instance restarts mid-pipeline the project is
left in a running state; the **Retry** button on the project page resumes from
the last completed stage without re-uploading.

**Groq's token cap is what will actually stop your demo.** Observed during
development: all 11 keys rate-limited within the same second, and the 429 named
a single organisation with `Used 99607 / Limit 100000` tokens per day. That is
consistent with the cap being enforced **per organisation, not per key** — if
so, extra keys from the same Groq account add no headroom and you need keys
from separate accounts. This was not confirmed key-by-key, so treat it as a
strong hypothesis and verify before relying on a large pool. When the pool is
exhausted the UI says so explicitly, with the wait time, in the sidebar and
next to the affected buttons.

**Groq caps audio uploads at 25 MB.** Long videos can exceed this after audio
extraction; the API returns a clear error rather than failing silently.

---

## Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| UI loads, sidebar says **AI Engine ● Offline**, `curl` to the API works | `CORS_ORIGINS` doesn't match the frontend origin exactly | Include the scheme, no trailing slash. Check the browser console for the blocked origin. |
| Requests go to `localhost:8000` in production | `NEXT_PUBLIC_API_URL` was set after the build | Set it, then **Clear build cache & deploy** on recast-web. |
| Sidebar says **Rate limited** | Groq daily token cap | Wait for the stated time, or add keys from a different Groq account. |
| Upload works, processing fails immediately | FFmpeg missing | The API must be the Docker service, not Python runtime. |
| All projects vanished after a deploy | No persistent disk | The API needs a paid plan with the disk mounted at `/app/storage`. |
| Build fails: `Dockerfile not found` | Path resolution with `rootDir` | In the dashboard set Dockerfile path to `backend/Dockerfile` and context to `backend`. |
| Build fails on `pydantic-core` wheels | Python version drift | The image pins `python:3.12-slim`; don't move to 3.14, which has no prebuilt wheel. |
| First request after idle takes ~a minute | Free-tier spin-down | Upgrade the instance, or warm it before demoing. |

---

## Local check before pushing

The image builds and runs. Verified locally:

```bash
cd recast/backend
docker build -t recast-api .
docker run --rm -p 8000:9000 -e PORT=9000 -e GROQ_API_KEYS=gsk_xxx recast-api
curl http://localhost:8000/api/health
```

Confirmed in the built image (916 MB):

| Check | Result |
| --- | --- |
| FFmpeg present | `ffmpeg`/`ffprobe` 7.1.5 |
| App loads | 28 routes registered |
| faster-whisper excluded | absent, and transcription still resolves to Groq |
| `$PORT` respected | bound to 9000 when Render assigns it |
| Keys from env | `GROQ_API_KEYS` picked up without `groq_keys.txt` |
| `CORS_ORIGINS` honoured | correct `access-control-allow-origin` returned |
| Storage path | `uploads/ audio/ clips/ thumbnails/ subtitles/ recast.db` created under `/app/storage`, matching the disk mount |
| Graceful shutdown | `exec` makes uvicorn PID 1, so SIGTERM exits 0 rather than being killed |
