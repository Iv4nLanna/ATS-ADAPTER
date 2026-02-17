# ATS Adapter

ATS Adapter is a full-stack application to optimize resumes for ATS (Applicant Tracking Systems) using low-cost/free LLM providers (Groq, Gemini, OpenRouter, optional OpenAI).

It receives a resume PDF + job description, extracts and cleans text, applies **keyword-aware chunking**, rewrites strategic sections with factual constraints, and returns editable output for ATS-friendly PDF export.

## Why this project

Recruiters and ATS engines prioritize keyword alignment, clear structure, and objective language. ATS Adapter increases relevance **without inventing information**.

## Core features

- Resume PDF upload and extraction
- Hard skills + action verbs extraction from job description
- Optimization focused on:
  - `professional_summary`
  - `experience`
- Truth-preserving prompt constraints (anti-hallucination)
- **Chunking + relevance ranking** for better quality on smaller/free models
- Side-by-side editor (original vs optimized)
- ATS-friendly PDF export (single column, standard font, simple layout)

## Architecture

- `backend/` FastAPI API, AI orchestration, chunking/ranking, PDF/text services
- `frontend/` React (Vite) UI for upload, editing and export

## Technical vision

ATS Adapter is designed as a **quality-first optimization pipeline** for constrained models.

The technical strategy is:

1. Keep factual safety as a hard rule (no hallucinated experience).
2. Reduce prompt noise before generation.
3. Use deterministic preprocessing + selective context retrieval.
4. Preserve a stable JSON contract for frontend editing/export.

This makes the system robust for low-cost providers while keeping ATS output quality consistent.

## Chunking first (project differential)

Chunking is a core concept in this project.

Instead of sending the entire resume to a smaller model in one shot, ATS Adapter runs a 2-step pipeline:

1. Extract job requirements (`hard_skills`, `action_verbs`) from the vacancy.
2. Split resume text into chunks.
3. Score each chunk by relevance against vacancy keywords + extracted requirements.
4. Select only top-N chunks.
5. Send condensed context to the final optimization step.

### Chunking algorithm (high-level)

1. Normalize and split resume text into paragraph blocks.
2. Build chunks with size bounds (`min_chars`, `max_chars`).
3. Extract vacancy requirements (`hard_skills`, `action_verbs`).
4. Score each chunk by keyword overlap and section relevance.
5. Keep top-N chunks (`RESUME_CHUNK_MAX_SELECTED`) plus baseline context.
6. Generate optimized content from this reduced context.

The goal is to simulate a lightweight retrieval layer without extra infrastructure.

### Why this improves output quality

- Reduces context noise
- Prioritizes relevant experience blocks
- Lowers token usage and cost
- Improves consistency in free/smaller models
- Reduces overflow/truncation risk

### Chunking controls

- `RESUME_CHUNK_MAX_CHARS=1100`
- `RESUME_CHUNK_MIN_CHARS=260`
- `RESUME_CHUNK_MAX_SELECTED=6`

## Security (API key protection)

### Current safeguards

- Provider keys are loaded server-side via environment variables
- `.env` is ignored by git (`backend/.env`, `frontend/.env`)
- Session authentication via `POST /api/auth/login` + Bearer token
- In-memory rate limiting per IP/user (login, optimize, export)
- Optional Cloudflare Turnstile verification
- Optional backend request protection via `APP_API_KEY` + `x-api-key` header
- Input limits to reduce abuse:
  - `MAX_PDF_SIZE_MB`
  - `MAX_JOB_DESCRIPTION_CHARS`
- CORS restricted by `FRONTEND_ORIGIN`

### Recommended operational practices

- Never expose provider keys in frontend code
- Rotate provider keys regularly
- Revoke any leaked keys immediately
- Use different keys for dev/staging/prod
- Add reverse-proxy rate limiting in production (Nginx/Cloudflare)

### Practical key safety checklist

- Keep provider keys only in `backend/.env`
- Never place provider keys in `frontend/.env`
- Keep `AUTH_PASSWORD` strong and unique
- Enable captcha when exposing to the public internet
- Rotate keys if shared in chats/screenshots/logs
- Keep `.env.example` with placeholders only

## Tech stack

- Backend: FastAPI, pypdf, fpdf2, pydantic-settings
- Frontend: React, Vite
- LLM providers:
  - Groq (recommended)
  - Gemini
  - OpenRouter
  - OpenAI (optional)

## Run locally

### Backend

```bash
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend
npm install
copy .env.example .env
npm run dev -- --host 0.0.0.0 --port 5173
```

- Frontend: `http://localhost:5173`
- Backend: `http://localhost:8000`
- API docs: `http://localhost:8000/docs`

## Environment variables (backend)

Provider selection:

- `AI_PROVIDER=groq|gemini|openrouter|openai`
- `AI_TIMEOUT_SECONDS=90`

Security:

- `APP_API_KEY=` (optional)
- `MAX_PDF_SIZE_MB=5`
- `MAX_JOB_DESCRIPTION_CHARS=15000`
- `AUTH_ENABLED=true`
- `AUTH_USERNAME=admin`
- `AUTH_PASSWORD=change-me`
- `AUTH_TOKEN_TTL_MINUTES=480`
- `RATE_LIMIT_LOGIN_PER_MINUTE=10`
- `RATE_LIMIT_OPTIMIZE_PER_MINUTE=12`
- `RATE_LIMIT_EXPORT_PER_MINUTE=20`
- `CAPTCHA_ENABLED=false`
- `TURNSTILE_SECRET_KEY=`

Chunking:

- `RESUME_CHUNK_MAX_CHARS=1100`
- `RESUME_CHUNK_MIN_CHARS=260`
- `RESUME_CHUNK_MAX_SELECTED=6`

## API endpoints

- `GET /api/health`
- `POST /api/auth/login` (JSON)
  - `username`
  - `password`
  - `captcha_token` (optional, required only when captcha is enabled)
- `POST /api/optimize-cv` (multipart)
  - `resume_pdf` (PDF)
  - `job_description` (text)
  - `captcha_token` (optional, required only when captcha is enabled)
- `POST /api/export-pdf` (JSON)
  - `name`
  - `contact`
  - `optimized_resume`

Protected endpoints require:
- `Authorization: Bearer <access_token>`

## Expected output format

```json
{
  "hard_skills": ["Python", "FastAPI", "SQL"],
  "action_verbs": ["implement", "optimize", "collaborate"],
  "optimized_resume": {
    "professional_summary": "...",
    "experience": [
      {
        "title": "...",
        "company": "...",
        "period": "...",
        "bullets": ["...", "..."]
      }
    ]
  },
  "warnings": ["..."],
  "change_log": ["..."]
}
```

## Keywords

`ats`, `ats-optimizer`, `resume-optimizer`, `cv-optimizer`, `resume-parser`, `job-matching`, `keyword-optimization`, `resume-chunking`, `retrieval-ranking`, `fastapi`, `react`, `llm`, `groq`, `gemini`, `openrouter`, `prompt-engineering`, `recruitment-tech`, `career-tools`

## Suggested GitHub topics

`ats` `resume-optimizer` `cv` `fastapi` `react` `llm` `groq` `openrouter` `gemini` `prompt-engineering` `chunking`

## License

MIT (recommended)
