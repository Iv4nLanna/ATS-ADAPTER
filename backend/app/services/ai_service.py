import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

import httpx
from openai import OpenAI

from app.core.config import settings


PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "system_prompt.txt"
SYSTEM_PROMPT = PROMPT_PATH.read_text(encoding="utf-8")

JOB_ANALYSIS_PROMPT = """
You extract ATS job requirements from a job description.
Return strict JSON only in this format:
{
  "hard_skills": ["..."],
  "action_verbs": ["..."]
}
Rules:
- hard_skills: only explicit technical tools/tech/methods/certifications in the vacancy.
- action_verbs: strong action verbs used in responsibilities.
- Keep concise and deduplicated.
- Do not include soft skills unless explicitly technical.
- No markdown.
""".strip()

STOPWORDS = {
    "a",
    "o",
    "e",
    "de",
    "da",
    "do",
    "das",
    "dos",
    "em",
    "para",
    "com",
    "por",
    "no",
    "na",
    "nos",
    "nas",
    "the",
    "and",
    "for",
    "with",
    "to",
    "in",
    "on",
    "at",
    "of",
    "or",
    "as",
    "is",
    "are",
}


def _strip_code_fence(text: str) -> str:
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z]*\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def _safe_json_loads(text: str) -> Dict[str, Any]:
    cleaned = _strip_code_fence(text)
    return json.loads(cleaned or "{}")


def _normalize_output(data: Dict[str, Any]) -> Dict[str, Any]:
    data = data or {}
    optimized_resume = data.get("optimized_resume") or {}

    experiences = optimized_resume.get("experience") or []
    normalized_experiences = []
    for item in experiences:
        if not isinstance(item, dict):
            continue
        normalized_experiences.append(
            {
                "title": item.get("title") or "",
                "company": item.get("company") or "",
                "period": item.get("period") or "",
                "bullets": item.get("bullets") or [],
            }
        )

    return {
        "hard_skills": data.get("hard_skills") or [],
        "action_verbs": data.get("action_verbs") or [],
        "optimized_resume": {
            "professional_summary": optimized_resume.get("professional_summary") or "",
            "experience": normalized_experiences,
        },
        "warnings": data.get("warnings") or [],
        "change_log": data.get("change_log") or [],
    }


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[a-zA-Z0-9+#.-]{2,}", (text or "").lower())


def _keywords_from_text(text: str) -> set[str]:
    return {token for token in _tokenize(text) if token not in STOPWORDS}


def _split_long_paragraph(paragraph: str, max_chars: int) -> List[str]:
    if len(paragraph) <= max_chars:
        return [paragraph]

    words = paragraph.split()
    parts: List[str] = []
    current: List[str] = []

    for word in words:
        candidate = (" ".join(current + [word])).strip()
        if candidate and len(candidate) > max_chars and current:
            parts.append(" ".join(current).strip())
            current = [word]
        else:
            current.append(word)

    if current:
        parts.append(" ".join(current).strip())

    return [p for p in parts if p]


def _chunk_resume_text(resume_text: str) -> List[str]:
    max_chars = max(400, settings.resume_chunk_max_chars)
    min_chars = max(120, settings.resume_chunk_min_chars)

    raw_paragraphs = [p.strip() for p in re.split(r"\n\s*\n", resume_text or "") if p.strip()]
    if not raw_paragraphs:
        stripped = (resume_text or "").strip()
        return [stripped] if stripped else []

    paragraphs: List[str] = []
    for paragraph in raw_paragraphs:
        paragraphs.extend(_split_long_paragraph(paragraph, max_chars=max_chars))

    chunks: List[str] = []
    buffer: List[str] = []
    buffer_len = 0

    for paragraph in paragraphs:
        separator = 2 if buffer else 0
        if buffer and buffer_len + separator + len(paragraph) > max_chars:
            chunk_text = "\n\n".join(buffer).strip()
            if chunk_text:
                chunks.append(chunk_text)
            buffer = [paragraph]
            buffer_len = len(paragraph)
        else:
            buffer.append(paragraph)
            buffer_len += separator + len(paragraph)

    if buffer:
        chunks.append("\n\n".join(buffer).strip())

    if len(chunks) >= 2 and len(chunks[-1]) < min_chars:
        chunks[-2] = (chunks[-2] + "\n\n" + chunks[-1]).strip()
        chunks = chunks[:-1]

    return [chunk for chunk in chunks if chunk]


def _rank_chunks(
    chunks: List[str],
    job_description: str,
    hard_skills: List[str],
    action_verbs: List[str],
) -> List[Tuple[int, int]]:
    job_keywords = _keywords_from_text(job_description)
    required_terms = _keywords_from_text(" ".join(hard_skills + action_verbs))

    ranked: List[Tuple[int, int]] = []
    for index, chunk in enumerate(chunks):
        chunk_keywords = _keywords_from_text(chunk)

        required_overlap = len(chunk_keywords & required_terms)
        job_overlap = len(chunk_keywords & job_keywords)

        heading_bonus = 0
        lowered = chunk.lower()
        if any(h in lowered for h in ["resumo", "summary", "experiencia", "experience"]):
            heading_bonus = 2

        score = (required_overlap * 4) + job_overlap + heading_bonus
        ranked.append((index, score))

    ranked.sort(key=lambda item: (item[1], -item[0]), reverse=True)
    return ranked


def _select_relevant_chunks(
    chunks: List[str],
    ranked_scores: List[Tuple[int, int]],
) -> List[str]:
    if not chunks:
        return []

    max_selected = max(1, settings.resume_chunk_max_selected)
    selected_indexes: List[int] = []

    # Keep first chunk to preserve base profile context.
    selected_indexes.append(0)

    for index, _ in ranked_scores:
        if index not in selected_indexes:
            selected_indexes.append(index)
        if len(selected_indexes) >= max_selected:
            break

    selected_indexes = sorted(set(selected_indexes))
    return [chunks[index] for index in selected_indexes]


def _call_openai_compatible(
    *,
    api_key: str,
    model: str,
    payload: Dict[str, Any],
    system_prompt: str,
    base_url: str | None = None,
) -> str:
    client = OpenAI(api_key=api_key, base_url=base_url)
    completion = client.chat.completions.create(
        model=model,
        temperature=0.1,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
    )
    return completion.choices[0].message.content or "{}"


def _extract_gemini_json_text(response_body: Dict[str, Any]) -> str:
    candidates = response_body.get("candidates") or []
    for candidate in candidates:
        content = candidate.get("content") or {}
        for part in content.get("parts") or []:
            text = part.get("text")
            if text:
                return text
    return ""


def _call_gemini(payload: Dict[str, Any], system_prompt: str) -> str:
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY nao configurada no backend.")

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{settings.gemini_model}:generateContent"
    )
    body = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": [
            {
                "role": "user",
                "parts": [{"text": json.dumps(payload, ensure_ascii=False)}],
            }
        ],
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json",
        },
    }

    with httpx.Client(timeout=settings.ai_timeout_seconds) as client:
        response = client.post(url, params={"key": settings.gemini_api_key}, json=body)
        response.raise_for_status()
        response_body = response.json()

    content = _extract_gemini_json_text(response_body)
    if not content:
        raise RuntimeError("Gemini retornou resposta vazia ou fora do formato esperado.")
    return content


def _call_model_json(payload: Dict[str, Any], system_prompt: str) -> Dict[str, Any]:
    provider = settings.ai_provider.lower()

    if provider == "groq":
        if not settings.groq_api_key:
            raise RuntimeError("GROQ_API_KEY nao configurada no backend.")
        content = _call_openai_compatible(
            api_key=settings.groq_api_key,
            model=settings.groq_model,
            payload=payload,
            system_prompt=system_prompt,
            base_url="https://api.groq.com/openai/v1",
        )
    elif provider == "gemini":
        content = _call_gemini(payload=payload, system_prompt=system_prompt)
    elif provider == "openai":
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY nao configurada no backend.")
        content = _call_openai_compatible(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            payload=payload,
            system_prompt=system_prompt,
        )
    elif provider == "openrouter":
        if not settings.openrouter_api_key:
            raise RuntimeError("OPENROUTER_API_KEY nao configurada no backend.")
        content = _call_openai_compatible(
            api_key=settings.openrouter_api_key,
            model=settings.openrouter_model,
            payload=payload,
            system_prompt=system_prompt,
            base_url="https://openrouter.ai/api/v1",
        )
    else:
        raise RuntimeError(
            "AI_PROVIDER "
            f"'{settings.ai_provider}' nao suportado. Use: groq, gemini, openai ou openrouter."
        )

    return _safe_json_loads(content)


def _extract_job_requirements(job_description: str) -> Dict[str, List[str]]:
    payload = {"job_description": job_description}
    parsed = _call_model_json(payload=payload, system_prompt=JOB_ANALYSIS_PROMPT)

    hard_skills = parsed.get("hard_skills") or []
    action_verbs = parsed.get("action_verbs") or []

    return {
        "hard_skills": [str(item).strip() for item in hard_skills if str(item).strip()],
        "action_verbs": [str(item).strip() for item in action_verbs if str(item).strip()],
    }


def optimize_resume(resume_text: str, job_description: str) -> Dict[str, Any]:
    requirements = _extract_job_requirements(job_description=job_description)

    chunks = _chunk_resume_text(resume_text)
    ranked_scores = _rank_chunks(
        chunks=chunks,
        job_description=job_description,
        hard_skills=requirements["hard_skills"],
        action_verbs=requirements["action_verbs"],
    )
    selected_chunks = _select_relevant_chunks(chunks=chunks, ranked_scores=ranked_scores)

    condensed_resume_text = "\n\n[CHUNK]\n\n".join(selected_chunks) if selected_chunks else resume_text

    payload = {
        "job_description": job_description,
        "resume_text": condensed_resume_text,
        "pre_extracted_job_requirements": requirements,
        "chunking": {
            "enabled": True,
            "total_chunks": len(chunks),
            "selected_chunks": len(selected_chunks),
        },
    }

    optimized = _call_model_json(payload=payload, system_prompt=SYSTEM_PROMPT)

    # Guarantee these keys exist and prefer deterministic extraction from step 1.
    optimized["hard_skills"] = requirements["hard_skills"]
    optimized["action_verbs"] = requirements["action_verbs"]

    normalized = _normalize_output(optimized)
    normalized["change_log"] = [
        *normalized["change_log"],
        f"Chunking aplicado: {len(selected_chunks)}/{len(chunks)} chunks selecionados por relevancia.",
    ]
    return normalized
