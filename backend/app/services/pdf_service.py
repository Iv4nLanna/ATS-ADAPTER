from fpdf import FPDF

from app.schemas.resume import ExportPdfRequest


def _safe(text: str) -> str:
    return (text or "").encode("latin-1", "replace").decode("latin-1")


def generate_ats_friendly_pdf_bytes(payload: ExportPdfRequest) -> bytes:
    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, _safe(payload.name), new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", size=10)
    if payload.contact:
        pdf.multi_cell(0, 6, _safe(payload.contact), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Resumo Profissional", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", size=11)
    pdf.multi_cell(
        0,
        6,
        _safe(payload.optimized_resume.professional_summary),
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.ln(2)

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Experiencia Profissional", new_x="LMARGIN", new_y="NEXT")

    for exp in payload.optimized_resume.experience:
        title_line = " | ".join([part for part in [exp.title, exp.company] if part])

        pdf.set_font("Helvetica", "B", 11)
        if title_line:
            pdf.multi_cell(0, 6, _safe(title_line), new_x="LMARGIN", new_y="NEXT")

        if exp.period:
            pdf.set_font("Helvetica", "I", 10)
            pdf.multi_cell(0, 6, _safe(exp.period), new_x="LMARGIN", new_y="NEXT")

        pdf.set_font("Helvetica", size=11)
        for bullet in exp.bullets:
            pdf.multi_cell(0, 6, _safe(f"- {bullet}"), new_x="LMARGIN", new_y="NEXT")

        pdf.ln(1)

    content = pdf.output()
    if isinstance(content, bytearray):
        return bytes(content)
    if isinstance(content, bytes):
        return content
    return content.encode("latin-1", "replace")
