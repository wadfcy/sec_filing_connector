"""Data models for SEC filings and company information."""

from pydantic import BaseModel, field_validator
from datetime import date


class Company(BaseModel):
    """Represents a company with SEC filing information."""

    ticker: str
    cik: str
    name: str

    @field_validator('ticker')
    @classmethod
    def validate_ticker(cls, v: str) -> str:
        """Validate ticker is not empty."""
        if not v or not v.strip():
            raise ValueError("Ticker cannot be empty")
        return v.strip().upper()

    @field_validator('cik')
    @classmethod
    def validate_cik(cls, v: str) -> str:
        """Validate CIK is not empty."""
        if not v or not v.strip():
            raise ValueError("CIK cannot be empty")
        return v.strip()


class Filing(BaseModel):
    """Represents an SEC filing."""

    cik: str
    company_name: str
    form_type: str
    filing_date: date
    accession_number: str

    @field_validator('form_type')
    @classmethod
    def validate_form_type(cls, v: str) -> str:
        """Validate form type is not empty."""
        if not v or not v.strip():
            raise ValueError("Form type cannot be empty")
        return v.strip()

    @field_validator('accession_number')
    @classmethod
    def validate_accession_number(cls, v: str) -> str:
        """Validate accession number is not empty."""
        if not v or not v.strip():
            raise ValueError("Accession number cannot be empty")
        return v.strip()


class FilingFilter(BaseModel):
    """Filter criteria for SEC filings search."""

    form_types: list[str] | None = None
    date_from: date | None = None
    date_to: date | None = None
    limit: int = 10

    @field_validator('limit')
    @classmethod
    def validate_limit(cls, v: int) -> int:
        """Validate limit is positive."""
        if v <= 0:
            raise ValueError("Limit must be greater than 0")
        return v

    @field_validator('date_from', 'date_to')
    @classmethod
    def validate_dates(cls, v: date | None) -> date | None:
        """Validate dates are not in the future."""
        if v is not None and v > date.today():
            raise ValueError("Date cannot be in the future")
        return v
