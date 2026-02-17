from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from app.core.config import settings
from app.schemas.resume import ExportPdfRequest, OptimizeResponse
from app.services.ai_service import optimize_resume
from app.services.pdf_service import generate_ats_friendly_pdf_bytes
from app.services.text_service import clean_text, extract_pdf_text

app = FastAPI(title="ATS Optimizer API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/optimize-cv", response_model=OptimizeResponse)
async def optimize_cv(
    resume_pdf: UploadFile = File(...),
    job_description: str = Form(...),
):
    if resume_pdf.content_type not in {"application/pdf", "application/octet-stream"}:
        raise HTTPException(status_code=400, detail="Envie um arquivo PDF valido.")

    pdf_bytes = await resume_pdf.read()
    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="O arquivo PDF esta vazio.")

    resume_text = extract_pdf_text(pdf_bytes)
    if not resume_text:
        raise HTTPException(status_code=400, detail="Nao foi possivel extrair texto do PDF.")

    cleaned_job_description = clean_text(job_description)
    if not cleaned_job_description:
        raise HTTPException(status_code=400, detail="A descricao da vaga esta vazia.")

    try:
        optimized = optimize_resume(resume_text=resume_text, job_description=cleaned_job_description)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Falha ao processar com IA: {exc}") from exc

    optimized["original_resume_text"] = resume_text
    return optimized


@app.post("/api/export-pdf")
def export_pdf(payload: ExportPdfRequest):
    pdf_bytes = generate_ats_friendly_pdf_bytes(payload)
    headers = {"Content-Disposition": "attachment; filename=curriculo_ats.pdf"}
    return StreamingResponse(iter([pdf_bytes]), media_type="application/pdf", headers=headers)
