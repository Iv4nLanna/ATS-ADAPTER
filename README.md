# ATS Adapter

ATS Adapter is a full-stack application that optimizes resumes for ATS (Applicant Tracking Systems) using low-cost or free LLM providers (Groq, Gemini, OpenRouter, optional OpenAI).

The platform receives a resume PDF + job description, extracts and cleans text, applies keyword-aware chunking, rewrites key sections with factual constraints, and returns editable output for final export in ATS-friendly format.

## Why this project

Recruiters and ATS platforms prioritize keyword alignment, clear structure, and objective wording. ATS Adapter helps candidates improve resume relevance without fabricating data.

## Core features

- Resume PDF upload and text extraction
- Job description parsing for hard skills and action verbs
- Resume optimization focused on:
  - `professional_summary`
  - `experience`
- Anti-hallucination prompt constraints (truth-preserving rewrites)
- Chunking + relevance ranking for better results on smaller/free models
- Side-by-side original vs optimized editor in frontend
- ATS-friendly PDF export (single-column, standard font, minimal styling)

## Architecture

- `backend/` FastAPI API, AI orchestration, PDF/text services
- `frontend/` React (Vite) UI for upload, editing, and export

### Optimization pipeline

1. User uploads resume PDF and job description.
2. Backend extracts and cleans resume text.
3. AI step 1 extracts `hard_skills` and `action_verbs` from job description.
4. Resume is chunked and ranked by relevance.
5. Only top chunks are sent to AI step 2 for final optimization.
6. API returns structured JSON for frontend editing.
7. User downloads ATS-friendly PDF.

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

Chunking controls:

- `RESUME_CHUNK_MAX_CHARS=1100`
- `RESUME_CHUNK_MIN_CHARS=260`
- `RESUME_CHUNK_MAX_SELECTED=6`

## API endpoints

- `GET /api/health`
- `POST /api/optimize-cv` (multipart)
  - `resume_pdf` (PDF)
  - `job_description` (text)
- `POST /api/export-pdf` (JSON)
  - `name`
  - `contact`
  - `optimized_resume`

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

## Roadmap

- Add score-based ATS gap analysis dashboard
- Add multilingual optimization templates
- Add provider fallback routing and retries
- Add resume version history and comparison

## Keywords

`ats`, `ats-optimizer`, `resume-optimizer`, `cv-optimizer`, `resume-parser`, `job-matching`, `keyword-optimization`, `fastapi`, `react`, `llm`, `groq`, `gemini`, `openrouter`, `prompt-engineering`, `recruitment-tech`, `career-tools`

## Suggested GitHub topics

`ats` `resume-optimizer` `cv` `fastapi` `react` `llm` `groq` `openrouter` `gemini` `prompt-engineering`

## License

MIT (recommended)
