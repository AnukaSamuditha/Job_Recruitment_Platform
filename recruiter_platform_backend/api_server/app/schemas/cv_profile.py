"""JSON-schema–backed résumé fields for LlamaParse structured extraction."""

from __future__ import annotations

from pydantic import BaseModel, Field


class WorkExperienceItem(BaseModel):
    company: str = Field(default="", description="Employer or client organization name.")
    job_title: str = Field(default="", description="Role or job title.")
    location: str = Field(default="", description="City, region, or remote.")
    start_date: str = Field(
        default="",
        description="Start date as written on the CV (e.g. Jan 2020, 2019).",
    )
    end_date: str = Field(
        default="",
        description="End date or 'Present' / current if still in role.",
    )
    highlights: list[str] = Field(
        default_factory=list,
        description="Key achievements or responsibilities as short bullet strings.",
    )


class EducationItem(BaseModel):
    institution: str = Field(default="", description="School or university name.")
    degree: str = Field(default="", description="Degree or qualification (e.g. B.Sc., MBA).")
    field_of_study: str = Field(default="", description="Major, concentration, or subject.")
    end_date: str = Field(default="", description="Graduation or expected end date as on CV.")


class CertificationItem(BaseModel):
    name: str = Field(default="", description="Certification or license name.")
    issuer: str = Field(default="", description="Issuing body if stated.")
    year: str = Field(default="", description="Year obtained if stated.")


class LanguageItem(BaseModel):
    name: str = Field(default="", description="Language name.")
    proficiency: str = Field(
        default="",
        description="Level if stated (e.g. Native, B2, Professional).",
    )


class CvStructuredProfile(BaseModel):
    """Exact fields LlamaParse must populate from the CV PDF."""

    full_name: str = Field(default="", description="Candidate full name as on the CV.")
    email: str = Field(default="", description="Primary email if visible.")
    phone: str = Field(default="", description="Primary phone if visible.")
    location: str = Field(default="", description="City, country, or 'Remote' if indicated.")
    headline: str = Field(
        default="",
        description="One-line professional headline or current title line under the name.",
    )
    summary: str = Field(
        default="",
        description="Professional summary, objective, or profile paragraph if present.",
    )
    skills: list[str] = Field(
        default_factory=list,
        description="Technical and soft skills as separate short strings.",
    )
    work_experience: list[WorkExperienceItem] = Field(
        default_factory=list,
        description="Work history in reverse chronological order when possible.",
    )
    education: list[EducationItem] = Field(
        default_factory=list,
        description="Formal education entries.",
    )
    certifications: list[CertificationItem] = Field(
        default_factory=list,
        description="Professional certifications and licenses.",
    )
    languages: list[LanguageItem] = Field(
        default_factory=list,
        description="Spoken or written languages and proficiency.",
    )
    years_experience_total: float | None = Field(
        default=None,
        description="Total years of professional experience if inferable, else null.",
    )

    def to_parse_notes(self) -> str:
        """Compact text for downstream LangGraph agents."""
        lines = [
            f"Name: {self.full_name or '—'}",
            f"Headline: {self.headline or '—'}",
            f"Location: {self.location or '—'}",
            f"Email: {self.email or '—'} | Phone: {self.phone or '—'}",
            f"Summary: {(self.summary or '—')[:800]}",
            f"Skills ({len(self.skills)}): {', '.join(self.skills[:40]) or '—'}",
        ]
        for i, w in enumerate(self.work_experience[:8], start=1):
            lines.append(
                f"Job {i}: {w.job_title} @ {w.company} ({w.start_date}–{w.end_date}) "
                f"— {'; '.join(w.highlights[:4]) or '—'}"
            )
        for i, e in enumerate(self.education[:5], start=1):
            lines.append(
                f"Education {i}: {e.degree} {e.field_of_study} — {e.institution} ({e.end_date})"
            )
        if self.years_experience_total is not None:
            lines.append(f"Approx. years experience: {self.years_experience_total}")
        return "\n".join(lines)
