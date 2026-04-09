"""
Pydantic models matching the Dala bulk-import JSON schema.
Validates scraper output before writing to disk.
"""

from __future__ import annotations
from pydantic import BaseModel, Field, field_validator
import re


class SectionSchema(BaseModel):
    sectionNumber: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)
    keyProvisions: list[str] = Field(default_factory=list)
    applicableDocumentTypes: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class ActSchema(BaseModel):
    name: str = Field(..., min_length=1)
    shortName: str = Field(..., min_length=1)
    actNumber: str = Field(..., min_length=1)
    country: str = Field(..., pattern=r"^[A-Z]{2}$")
    category: str
    effectiveDate: str
    lastAmended: str = Field(default="")
    description: str = Field(..., min_length=10)
    sections: list[SectionSchema] = Field(..., min_length=1)

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        allowed = {"consumer", "rental", "employment", "credit", "insurance", "general"}
        if v.lower() not in allowed:
            raise ValueError(f"category must be one of {allowed}, got '{v}'")
        return v.lower()

    @field_validator("effectiveDate")
    @classmethod
    def validate_date(cls, v: str) -> str:
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", v):
            raise ValueError(f"effectiveDate must be YYYY-MM-DD, got '{v}'")
        return v

    @field_validator("country")
    @classmethod
    def validate_country(cls, v: str) -> str:
        allowed = {"ZA", "GB", "US", "AU", "IN"}
        if v not in allowed:
            raise ValueError(f"country must be one of {allowed}, got '{v}'")
        return v