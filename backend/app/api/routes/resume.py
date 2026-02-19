from fastapi import APIRouter, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse

from app.api.dependencies.security import (
    enforce_captcha,
    enforce_export_rate_limit,
    enforce_optimize_rate_limit,
    enforce_optional_app_key,
    get_client_ip,
    validate_upload_limits,
)
from app.schemas.resume import ExportPdfRequest, OptimizeResponse
from app.services.ai_service import optimize_resume
from app.services.pdf_service import generate_ats_friendly_pdf_bytes
from app.services.text_service import clean_text, extract_pdf_text


router = APIRouter(prefix="/api", tags=["resume"])


@router.post("/optimize-cv", response_model=OptimizeResponse)
async def optimize_cv(
    request: Request,
    resume_pdf: UploadFile = File(...),
    job_description: str = Form(...),
    captcha_token: str | None = Form(default=None),
    x_api_key: str | None = Header(default=None, alias="x-api-key"),
):
    enforce_optional_app_key(x_api_key)

    ip = get_client_ip(request)
    enforce_optimize_rate_limit(ip)
    enforce_captcha(captcha_token, ip)

    if resume_pdf.content_type not in {"application/pdf", "application/octet-stream"}:
        raise HTTPException(status_code=400, detail="Envie um arquivo PDF valido.")

    pdf_bytes = await resume_pdf.read()
    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="O arquivo PDF esta vazio.")

    validate_upload_limits(pdf_bytes=pdf_bytes, job_description=job_description)

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


@router.post("/export-pdf")
def export_pdf(
    request: Request,
    payload: ExportPdfRequest,
    x_api_key: str | None = Header(default=None, alias="x-api-key"),
):
    enforce_optional_app_key(x_api_key)

    ip = get_client_ip(request)
    enforce_export_rate_limit(ip)

    pdf_bytes = generate_ats_friendly_pdf_bytes(payload)
    headers = {"Content-Disposition": "attachment; filename=curriculo_ats.pdf"}
    return StreamingResponse(iter([pdf_bytes]), media_type="application/pdf", headers=headers)
