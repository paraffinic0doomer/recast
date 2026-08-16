# RECAST — Frontend

Next.js dashboard for RECAST. See the [root README](../README.md) for the full
project, architecture and setup.

## Run

```bash
npm install
printf 'NEXT_PUBLIC_API_URL=http://localhost:8000\n' > .env.local
npm run dev
```

Open <http://localhost:3000>. The backend must be running on port 8000 — see
[`../backend`](../backend).

## Commands

| Command | Purpose |
|---------|---------|
| `npm run dev` | Development server |
| `npm run build` | Production build (also type-checks) |
| `npm run start` | Serve the production build |
| `npm run lint` | ESLint |

## Layout

```
src/
├── app/          Pages: / (dashboard), /projects/[id], error + not-found
├── components/   UploadDropzone, PipelineSteps, ProjectSummary,
│                 ContentDnaView, BestMomentsPanel, ShortsSection,
│                 CampaignPanel, CampaignScoreCard, ThumbnailSection, ui/*
├── lib/          API client, campaign export/stats, utils
└── types/        Shared types mirroring the backend schemas
```

`NEXT_PUBLIC_API_URL` is the only client-visible environment variable. API keys
live server-side in `backend/.env` and never reach the browser.
