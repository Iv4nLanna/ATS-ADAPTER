import json
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

import httpx
from openai import OpenAI

from app.core.config import settings


PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "system_prompt.txt"
SYSTEM_PROMPT = PROMPT_PATH.read_text(encoding="utf-8")

JOB_ANALYSIS_PROMPT = """
You are an ATS requirement extractor.
Return strict JSON only:
{
  "must_have_hard_skills": ["..."],
  "nice_to_have_hard_skills": ["..."],
  "action_verbs": ["..."],
  "ats_keywords": ["..."]
}
Rules:
- Keep only explicit technical requirements from the job description.
- Separate must-have vs nice-to-have when the text clearly indicates it.
- action_verbs must be strong verbs from responsibilities.
- Keep concise, deduplicated, no markdown.
""".strip()

RESUME_FACTS_PROMPT = """
You extract factual resume data only.
Return strict JSON only:
{
  "language": "pt-BR or en",
  "personal_info": {
    "full_name": "...",
    "email": "... or null",
    "phone": "... or null",
    "location": "... or null",
    "linkedin": "... or null",
    "portfolio": "... or null"
  },
  "hard_skills": ["..."],
  "soft_skills": ["..."],
  "experience": [
    {
      "company": "...",
      "title": "...",
      "period": "...",
      "location": "... or null",
      "highlights": ["factual bullet from resume"]
    }
  ],
  "education": ["..."],
  "languages": ["..."],
  "certifications": ["..."]
}
Rules:
- Extract literal facts only, do not optimize text.
- Never invent company, title, dates, metrics, or skills.
- If unknown, return null or empty string/list.
- No markdown.
""".strip()

PIPELINE_GUARD_PROMPT = """
### CONTROLE DE QUALIDADE DO PIPELINE
- Recebera: job_description, job_requirements, resume_facts e evidence_chunks.
- Use apenas resume_facts/evidence_chunks para reescrever.
- Nao invente empresas, cargos, datas, skills ou certificacoes.
- Se faltar requisito da vaga, coloque em warnings/gap_analysis.
- Responda apenas JSON valido.
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

SECTION_PATTERNS: Dict[str, List[str]] = {
    "summary": [r"^resumo$", r"^resumo profissional$", r"^summary$", r"^professional summary$"],
    "experience": [
        r"^experiencia$",
        r"^experiencia profissional$",
        r"^experience$",
        r"^work experience$",
        r"^professional experience$",
    ],
    "skills": [r"^habilidades$", r"^competencias$", r"^skills$", r"^technical skills$"],
    "education": [r"^educacao$", r"^formacao$", r"^education$", r"^academic background$"],
    "certifications": [r"^certificacoes$", r"^certifications$"],
    "languages": [r"^idiomas$", r"^languages$"],
    "projects": [r"^projetos$", r"^projects$"],
}

SECTION_SCORE_BONUS = {
    "header": 1,
    "summary": 2,
    "experience": 4,
    "skills": 3,
    "projects": 2,
    "education": 1,
    "certifications": 1,
    "languages": 1,
    "other": 0,
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


def _normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _to_clean_list(value: Any) -> List[str]:
    if isinstance(value, list):
        items = value
    elif isinstance(value, str):
        items = [part.strip() for part in re.split(r"[,\n;]", value)]
    else:
        items = []
    return [_normalize_text(item) for item in items if _normalize_text(item)]


def _dedupe(items: List[str]) -> List[str]:
    result: List[str] = []
    seen: set[str] = set()
    for item in items:
        key = _normalize_term_key(item)
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(item.strip())
    return result


def _normalize_term_key(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (text or "").lower())


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[a-zA-Z0-9+#.-]{2,}", (text or "").lower())


def _keywords_from_text(text: str) -> set[str]:
    return {token for token in _tokenize(text) if token not in STOPWORDS}


def _term_in_text(term: str, text: str) -> bool:
    term = (term or "").strip()
    if not term:
        return False
    pattern = re.escape(term.lower())
    return bool(re.search(rf"\b{pattern}\b", (text or "").lower()))


def _match_section_heading(line: str) -> str | None:
    candidate = re.sub(r"[^a-zA-Z0-9 ]+", "", (line or "").strip().lower())
    candidate = re.sub(r"\s+", " ", candidate).strip()
    if not candidate or len(candidate) > 40:
        return None

    for section, patterns in SECTION_PATTERNS.items():
        for pattern in patterns:
            if re.match(pattern, candidate):
                return section
    return None


def _split_resume_sections(resume_text: str) -> List[Dict[str, str]]:
    lines = (resume_text or "").splitlines()
    if not lines:
        return []

    sections: List[Dict[str, str]] = []
    current_section = "header"
    buffer: List[str] = []

    def flush() -> None:
        nonlocal buffer, current_section
        content = "\n".join(buffer).strip()
        if content:
            sections.append({"section": current_section, "text": content})
        buffer = []

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            if buffer and buffer[-1] != "":
                buffer.append("")
            continue

        maybe_section = _match_section_heading(line)
        if maybe_section:
            flush()
            current_section = maybe_section
            continue

        buffer.append(line)

    flush()

    if not sections:
        stripped = (resume_text or "").strip()
        if stripped:
            return [{"section": "other", "text": stripped}]
    return sections


def _chunk_text_with_overlap(text: str, max_chars: int, min_chars: int, overlap_chars: int) -> List[str]:
    stripped = (text or "").strip()
    if not stripped:
        return []
    if len(stripped) <= max_chars:
        return [stripped]

    chunks: List[str] = []
    cursor = 0
    text_len = len(stripped)

    while cursor < text_len:
        hard_end = min(text_len, cursor + max_chars)
        end = hard_end

        if hard_end < text_len:
            boundary = stripped.rfind("\n", cursor + min_chars, hard_end)
            if boundary == -1:
                boundary = stripped.rfind(". ", cursor + min_chars, hard_end)
            if boundary == -1:
                boundary = stripped.rfind(" ", cursor + min_chars, hard_end)
            if boundary != -1:
                end = boundary + 1

        if end <= cursor:
            end = hard_end

        chunk = stripped[cursor:end].strip()
        if chunk:
            chunks.append(chunk)

        if end >= text_len:
            break

        next_cursor = max(0, end - overlap_chars)
        if next_cursor <= cursor:
            next_cursor = end
        cursor = next_cursor

    if len(chunks) >= 2 and len(chunks[-1]) < min_chars:
        chunks[-2] = f"{chunks[-2]}\n{chunks[-1]}".strip()
        chunks = chunks[:-1]

    return chunks


def _build_resume_chunks(resume_text: str) -> List[Dict[str, str]]:
    sections = _split_resume_sections(resume_text)
    max_chars = max(400, settings.resume_chunk_max_chars)
    min_chars = max(120, settings.resume_chunk_min_chars)
    overlap_chars = max(40, min(settings.resume_chunk_overlap_chars, max_chars // 2))

    chunks: List[Dict[str, str]] = []
    for section_index, section_data in enumerate(sections):
        section_name = section_data["section"]
        section_chunks = _chunk_text_with_overlap(
            text=section_data["text"],
            max_chars=max_chars,
            min_chars=min_chars,
            overlap_chars=overlap_chars,
        )
        for chunk_index, chunk_text in enumerate(section_chunks):
            chunks.append(
                {
                    "id": f"S{section_index + 1}C{chunk_index + 1}",
                    "section": section_name,
                    "text": chunk_text,
                }
            )

    if not chunks:
        stripped = (resume_text or "").strip()
        if stripped:
            chunks.append({"id": "S1C1", "section": "other", "text": stripped})

    return chunks


def _rank_chunks(
    chunks: List[Dict[str, str]],
    job_description: str,
    job_requirements: Dict[str, List[str]],
) -> List[Tuple[int, int]]:
    job_keywords = _keywords_from_text(job_description)
    must_terms = _keywords_from_text(" ".join(job_requirements.get("must_have_hard_skills") or []))
    nice_terms = _keywords_from_text(" ".join(job_requirements.get("nice_to_have_hard_skills") or []))
    verb_terms = _keywords_from_text(" ".join(job_requirements.get("action_verbs") or []))

    ranked: List[Tuple[int, int]] = []
    for index, chunk in enumerate(chunks):
        chunk_keywords = _keywords_from_text(chunk["text"])
        must_overlap = len(chunk_keywords & must_terms)
        nice_overlap = len(chunk_keywords & nice_terms)
        verb_overlap = len(chunk_keywords & verb_terms)
        generic_overlap = len(chunk_keywords & job_keywords)
        section_bonus = SECTION_SCORE_BONUS.get(chunk["section"], 0)

        score = (must_overlap * 6) + (nice_overlap * 3) + (verb_overlap * 2) + generic_overlap + section_bonus
        ranked.append((index, score))

    ranked.sort(key=lambda item: (item[1], -item[0]), reverse=True)
    return ranked


def _select_chunks_for_facts(chunks: List[Dict[str, str]]) -> List[Dict[str, str]]:
    if not chunks:
        return []

    limit = max(3, min(len(chunks), settings.resume_chunk_max_selected + 2))
    selected_indexes: List[int] = []
    covered_sections: set[str] = set()

    for index, chunk in enumerate(chunks):
        section = chunk["section"]
        if section not in covered_sections:
            selected_indexes.append(index)
            covered_sections.add(section)
        if len(selected_indexes) >= limit:
            break

    for index in range(len(chunks)):
        if len(selected_indexes) >= limit:
            break
        if index not in selected_indexes:
            selected_indexes.append(index)

    return [chunks[index] for index in sorted(selected_indexes)]


def _select_chunks_for_optimization(
    chunks: List[Dict[str, str]],
    ranked_scores: List[Tuple[int, int]],
) -> List[Dict[str, str]]:
    if not chunks:
        return []

    max_selected = max(1, settings.resume_chunk_max_selected)
    selected_indexes: List[int] = []

    preferred_sections = {"header", "summary", "experience", "skills"}
    for index, chunk in enumerate(chunks):
        if chunk["section"] in preferred_sections:
            selected_indexes.append(index)
            preferred_sections.discard(chunk["section"])
        if len(selected_indexes) >= max_selected:
            break

    for index, _ in ranked_scores:
        if len(selected_indexes) >= max_selected:
            break
        if index not in selected_indexes:
            selected_indexes.append(index)

    return [chunks[index] for index in sorted(set(selected_indexes))]


def _format_chunks_for_prompt(chunks: List[Dict[str, str]]) -> List[Dict[str, str]]:
    return [{"chunk_id": chunk["id"], "section": chunk["section"], "text": chunk["text"]} for chunk in chunks]


def _call_openai_compatible(
    *,
    api_key: str,
    model: str,
    payload: Dict[str, Any],
    system_prompt: str,
    temperature: float,
    base_url: str | None = None,
) -> str:
    client = OpenAI(api_key=api_key, base_url=base_url)
    completion = client.chat.completions.create(
        model=model,
        temperature=temperature,
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


def _call_gemini(payload: Dict[str, Any], system_prompt: str, temperature: float) -> str:
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
            "temperature": temperature,
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


def _call_model_raw(payload: Dict[str, Any], system_prompt: str, temperature: float) -> str:
    provider = settings.ai_provider.lower()

    if provider == "groq":
        if not settings.groq_api_key:
            raise RuntimeError("GROQ_API_KEY nao configurada no backend.")
        return _call_openai_compatible(
            api_key=settings.groq_api_key,
            model=settings.groq_model,
            payload=payload,
            system_prompt=system_prompt,
            temperature=temperature,
            base_url="https://api.groq.com/openai/v1",
        )
    if provider == "gemini":
        return _call_gemini(payload=payload, system_prompt=system_prompt, temperature=temperature)
    if provider == "openai":
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY nao configurada no backend.")
        return _call_openai_compatible(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            payload=payload,
            system_prompt=system_prompt,
            temperature=temperature,
        )
    if provider == "openrouter":
        if not settings.openrouter_api_key:
            raise RuntimeError("OPENROUTER_API_KEY nao configurada no backend.")
        return _call_openai_compatible(
            api_key=settings.openrouter_api_key,
            model=settings.openrouter_model,
            payload=payload,
            system_prompt=system_prompt,
            temperature=temperature,
            base_url="https://openrouter.ai/api/v1",
        )
    raise RuntimeError(
        "AI_PROVIDER "
        f"'{settings.ai_provider}' nao suportado. Use: groq, gemini, openai ou openrouter."
    )


def _call_model_json_with_retry(
    *,
    payload: Dict[str, Any],
    system_prompt: str,
    validator: Callable[[Dict[str, Any]], Dict[str, Any]],
    stage_name: str,
    temperature: float | None = None,
) -> Dict[str, Any]:
    retries = max(0, settings.ai_json_max_retries)
    final_temperature = settings.ai_temperature if temperature is None else temperature
    current_payload = payload
    last_error = "unknown validation error"
    raw_response = ""

    for attempt in range(retries + 1):
        raw_response = _call_model_raw(
            payload=current_payload,
            system_prompt=system_prompt,
            temperature=final_temperature,
        )
        try:
            parsed = _safe_json_loads(raw_response)
        except Exception as exc:
            last_error = f"invalid_json: {exc}"
        else:
            try:
                return validator(parsed)
            except Exception as exc:
                last_error = f"schema_validation: {exc}"

        if attempt < retries:
            current_payload = {
                "original_input": payload,
                "previous_response": _strip_code_fence(raw_response)[:8000],
                "validation_error": last_error,
                "instruction": (
                    "Corrija a resposta para JSON estrito valido seguindo exatamente o schema "
                    "definido no system prompt. Sem markdown."
                ),
            }

    raise RuntimeError(
        f"Falha na etapa '{stage_name}' apos {retries + 1} tentativa(s): {last_error}. "
        f"Ultima resposta bruta: {_strip_code_fence(raw_response)[:600]}"
    )


def _validate_job_requirements(data: Dict[str, Any]) -> Dict[str, List[str]]:
    must_have = _to_clean_list(data.get("must_have_hard_skills") or data.get("hard_skills"))
    nice_to_have = _to_clean_list(data.get("nice_to_have_hard_skills"))
    action_verbs = _to_clean_list(data.get("action_verbs"))
    ats_keywords = _to_clean_list(data.get("ats_keywords"))

    result = {
        "must_have_hard_skills": _dedupe(must_have),
        "nice_to_have_hard_skills": _dedupe(nice_to_have),
        "action_verbs": _dedupe(action_verbs),
        "ats_keywords": _dedupe(ats_keywords),
    }
    if not any(result.values()):
        raise ValueError("job requirements vazio")
    return result


def _validate_resume_facts(data: Dict[str, Any]) -> Dict[str, Any]:
    personal_raw = data.get("personal_info") if isinstance(data.get("personal_info"), dict) else {}
    personal_info = {
        "full_name": _normalize_text(personal_raw.get("full_name")),
        "email": _normalize_text(personal_raw.get("email")),
        "phone": _normalize_text(personal_raw.get("phone")),
        "location": _normalize_text(personal_raw.get("location")),
        "linkedin": _normalize_text(personal_raw.get("linkedin")),
        "portfolio": _normalize_text(personal_raw.get("portfolio")),
    }

    experiences: List[Dict[str, Any]] = []
    for item in data.get("experience") or data.get("experiences") or []:
        if not isinstance(item, dict):
            continue
        experiences.append(
            {
                "company": _normalize_text(item.get("company")),
                "title": _normalize_text(item.get("title")),
                "period": _normalize_text(item.get("period")),
                "location": _normalize_text(item.get("location")),
                "highlights": _dedupe(_to_clean_list(item.get("highlights") or item.get("bullets"))),
            }
        )

    result = {
        "language": _normalize_text(data.get("language")),
        "personal_info": personal_info,
        "hard_skills": _dedupe(_to_clean_list(data.get("hard_skills"))),
        "soft_skills": _dedupe(_to_clean_list(data.get("soft_skills"))),
        "experience": experiences,
        "education": _dedupe(_to_clean_list(data.get("education"))),
        "languages": _dedupe(_to_clean_list(data.get("languages"))),
        "certifications": _dedupe(_to_clean_list(data.get("certifications"))),
    }
    return result


def _validate_optimization_payload(data: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("resposta final nao e objeto")
    if not any(key in data for key in ("optimized_resume", "professional_summary", "experience")):
        raise ValueError("resposta final sem campos de curriculo otimizado")
    return data


def _compose_period(item: Dict[str, Any]) -> str:
    period = _normalize_text(item.get("period"))
    if period:
        return period
    start = _normalize_text(item.get("start_date"))
    end = _normalize_text(item.get("end_date"))
    if start and end:
        return f"{start} - {end}"
    return start or end


def _extract_candidate_experience(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    container = data.get("optimized_resume") if isinstance(data.get("optimized_resume"), dict) else {}
    source = container.get("experience") if container else data.get("experience")
    source = source if isinstance(source, list) else []

    results: List[Dict[str, Any]] = []
    for item in source:
        if not isinstance(item, dict):
            continue
        results.append(
            {
                "company": _normalize_text(item.get("company")),
                "title": _normalize_text(item.get("title")),
                "period": _compose_period(item),
                "bullets": _dedupe(_to_clean_list(item.get("bullets") or item.get("description_bullets"))),
            }
        )
    return results


def _extract_candidate_summary(data: Dict[str, Any]) -> str:
    if isinstance(data.get("optimized_resume"), dict):
        summary = _normalize_text(data["optimized_resume"].get("professional_summary"))
        if summary:
            return summary
    return _normalize_text(data.get("professional_summary"))


def _find_factual_match(
    candidate_exp: Dict[str, Any],
    factual_experience: List[Dict[str, Any]],
    used_indexes: set[int],
    fallback_index: int,
) -> Tuple[Dict[str, Any] | None, int | None]:
    target_title = _normalize_term_key(candidate_exp.get("title", ""))
    target_company = _normalize_term_key(candidate_exp.get("company", ""))

    for index, item in enumerate(factual_experience):
        if index in used_indexes:
            continue
        title_key = _normalize_term_key(item.get("title", ""))
        company_key = _normalize_term_key(item.get("company", ""))
        if title_key and company_key and title_key == target_title and company_key == target_company:
            return item, index

    for index, item in enumerate(factual_experience):
        if index in used_indexes:
            continue
        company_key = _normalize_term_key(item.get("company", ""))
        if target_company and company_key == target_company:
            return item, index

    if fallback_index < len(factual_experience):
        return factual_experience[fallback_index], fallback_index
    return None, None


def _build_default_summary(
    resume_facts: Dict[str, Any],
    matched_skills: List[str],
    job_requirements: Dict[str, List[str]],
) -> str:
    titles = [item.get("title") for item in resume_facts.get("experience", []) if item.get("title")]
    companies = [item.get("company") for item in resume_facts.get("experience", []) if item.get("company")]
    title_text = ", ".join(_dedupe(titles)[:2])
    company_text = ", ".join(_dedupe(companies)[:2])
    skills_text = ", ".join((matched_skills or resume_facts.get("hard_skills") or [])[:6])

    if title_text and company_text and skills_text:
        return (
            f"Profissional com experiencia como {title_text}, atuando em {company_text}. "
            f"Domina {skills_text} e aplica boas praticas para entrega de resultados."
        )
    if title_text and skills_text:
        return f"Profissional com experiencia em {title_text}, com foco tecnico em {skills_text}."

    must = ", ".join(job_requirements.get("must_have_hard_skills", [])[:4])
    if must:
        return f"Perfil tecnico com experiencia comprovada e aderencia parcial aos requisitos de {must}."

    return "Profissional com experiencia tecnica e historico consistente de entrega em ambientes corporativos."


def _normalize_output(
    model_data: Dict[str, Any],
    *,
    resume_facts: Dict[str, Any],
    job_requirements: Dict[str, List[str]],
    selected_chunks: List[Dict[str, str]],
    total_chunks: int,
) -> Dict[str, Any]:
    factual_experience = resume_facts.get("experience") or []
    candidate_experience = _extract_candidate_experience(model_data)

    normalized_experience: List[Dict[str, Any]] = []
    used_indexes: set[int] = set()

    for idx, candidate_item in enumerate(candidate_experience):
        factual_item, factual_index = _find_factual_match(
            candidate_item,
            factual_experience=factual_experience,
            used_indexes=used_indexes,
            fallback_index=idx,
        )
        if factual_index is not None:
            used_indexes.add(factual_index)

        company = candidate_item.get("company") or ""
        title = candidate_item.get("title") or ""
        period = candidate_item.get("period") or ""
        bullets = candidate_item.get("bullets") or []

        if factual_item:
            company = factual_item.get("company") or company
            title = factual_item.get("title") or title
            period = factual_item.get("period") or period
            if not bullets:
                bullets = factual_item.get("highlights") or []

        normalized_experience.append(
            {
                "title": _normalize_text(title),
                "company": _normalize_text(company),
                "period": _normalize_text(period),
                "bullets": _dedupe(_to_clean_list(bullets)),
            }
        )

    if not normalized_experience:
        for factual_item in factual_experience:
            normalized_experience.append(
                {
                    "title": _normalize_text(factual_item.get("title")),
                    "company": _normalize_text(factual_item.get("company")),
                    "period": _normalize_text(factual_item.get("period")),
                    "bullets": _dedupe(_to_clean_list(factual_item.get("highlights"))),
                }
            )

    evidence_text = "\n".join(chunk["text"] for chunk in selected_chunks)
    fact_skill_pool = resume_facts.get("hard_skills") or []
    fact_skill_keys = {_normalize_term_key(skill): skill for skill in fact_skill_pool}
    required_skills = (
        (job_requirements.get("must_have_hard_skills") or [])
        + (job_requirements.get("nice_to_have_hard_skills") or [])
        + (job_requirements.get("ats_keywords") or [])
    )
    required_skills = _dedupe(required_skills)

    candidate_skills = _dedupe(
        _to_clean_list(
            model_data.get("hard_skills")
            or model_data.get("hard_skills_found")
            or model_data.get("skills")
        )
    )
    candidate_skills += [skill for skill in required_skills if _term_in_text(skill, evidence_text)]

    filtered_skills: List[str] = []
    for skill in _dedupe(candidate_skills):
        key = _normalize_term_key(skill)
        if key in fact_skill_keys or _term_in_text(skill, evidence_text):
            filtered_skills.append(fact_skill_keys.get(key) or skill)

    if not filtered_skills:
        filtered_skills = [skill for skill in required_skills if _term_in_text(skill, evidence_text)]
    if not filtered_skills:
        filtered_skills = fact_skill_pool[:12]

    model_verbs = _dedupe(_to_clean_list(model_data.get("action_verbs")))
    target_verbs = _dedupe(job_requirements.get("action_verbs") or [])
    target_verb_keys = {_normalize_term_key(verb) for verb in target_verbs}
    action_verbs = [verb for verb in model_verbs if _normalize_term_key(verb) in target_verb_keys]
    if not action_verbs:
        action_verbs = target_verbs[:12]

    missing_skills = [
        skill
        for skill in job_requirements.get("must_have_hard_skills", [])
        if not (_term_in_text(skill, evidence_text) or _normalize_term_key(skill) in fact_skill_keys)
    ]
    gap_analysis = model_data.get("gap_analysis") if isinstance(model_data.get("gap_analysis"), dict) else {}
    missing_from_model = _to_clean_list(gap_analysis.get("missing_hard_skills"))
    warnings = _dedupe(_to_clean_list(model_data.get("warnings")) + missing_from_model + missing_skills)

    summary = _extract_candidate_summary(model_data)
    if not summary:
        summary = _build_default_summary(
            resume_facts=resume_facts,
            matched_skills=filtered_skills,
            job_requirements=job_requirements,
        )

    model_change_log = _dedupe(_to_clean_list(model_data.get("change_log")))
    selected_ids = ", ".join(chunk["id"] for chunk in selected_chunks) or "none"
    change_log = [
        *model_change_log,
        "Pipeline ATS aplicado em 3 etapas: requisitos da vaga, fatos do curriculo e reescrita.",
        f"Chunking por secao aplicado: {len(selected_chunks)}/{total_chunks} chunks enviados a IA.",
        f"Chunks usados na otimizacao: {selected_ids}.",
    ]

    return {
        "hard_skills": _dedupe(filtered_skills)[:20],
        "action_verbs": action_verbs[:20],
        "optimized_resume": {
            "professional_summary": summary,
            "experience": normalized_experience,
        },
        "warnings": warnings[:20],
        "change_log": _dedupe(change_log),
    }


def optimize_resume(resume_text: str, job_description: str) -> Dict[str, Any]:
    job_requirements = _call_model_json_with_retry(
        payload={"job_description": job_description},
        system_prompt=JOB_ANALYSIS_PROMPT,
        validator=_validate_job_requirements,
        stage_name="job_requirements",
        temperature=0.1,
    )

    chunks = _build_resume_chunks(resume_text)
    factual_chunks = _select_chunks_for_facts(chunks)
    resume_facts = _call_model_json_with_retry(
        payload={
            "resume_chunks": _format_chunks_for_prompt(factual_chunks),
            "job_requirements_hint": job_requirements,
        },
        system_prompt=RESUME_FACTS_PROMPT,
        validator=_validate_resume_facts,
        stage_name="resume_facts",
        temperature=0.05,
    )

    ranked_scores = _rank_chunks(
        chunks=chunks,
        job_description=job_description,
        job_requirements=job_requirements,
    )
    selected_chunks = _select_chunks_for_optimization(chunks=chunks, ranked_scores=ranked_scores)
    selected_for_prompt = _format_chunks_for_prompt(selected_chunks)

    final_payload = {
        "job_description": job_description,
        "job_requirements": job_requirements,
        "resume_facts": resume_facts,
        "evidence_chunks": selected_for_prompt,
        "chunking": {
            "enabled": True,
            "total_chunks": len(chunks),
            "selected_chunks": len(selected_chunks),
        },
    }

    final_prompt = f"{SYSTEM_PROMPT}\n\n{PIPELINE_GUARD_PROMPT}"
    optimized_raw = _call_model_json_with_retry(
        payload=final_payload,
        system_prompt=final_prompt,
        validator=_validate_optimization_payload,
        stage_name="resume_optimization",
        temperature=0.15,
    )

    return _normalize_output(
        optimized_raw,
        resume_facts=resume_facts,
        job_requirements=job_requirements,
        selected_chunks=selected_chunks,
        total_chunks=len(chunks),
    )
