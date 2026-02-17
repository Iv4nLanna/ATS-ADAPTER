from typing import List

from pydantic import BaseModel, Field


class ExperienceItem(BaseModel):
    title: str = Field(default="")
    company: str = Field(default="")
    period: str = Field(default="")
    bullets: List[str] = Field(default_factory=list)


class OptimizedResume(BaseModel):
    professional_summary: str = Field(default="")
    experience: List[ExperienceItem] = Field(default_factory=list)


class OptimizeResponse(BaseModel):
    hard_skills: List[str] = Field(default_factory=list)
    action_verbs: List[str] = Field(default_factory=list)
    optimized_resume: OptimizedResume
    warnings: List[str] = Field(default_factory=list)
    change_log: List[str] = Field(default_factory=list)
    original_resume_text: str = Field(default="")


class ExportPdfRequest(BaseModel):
    name: str = Field(default="Candidato")
    contact: str = Field(default="")
    optimized_resume: OptimizedResume
