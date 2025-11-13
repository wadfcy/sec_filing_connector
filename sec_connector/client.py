"""Core SEC client for company lookup and filing retrieval."""

from typing import Any
from datetime import date
import httpx
from sec_connector.models import Company, Filing, FilingFilter


class SECClient:
    """Client for interacting with SEC filing data."""

    def __init__(self, companies_data: dict[str, dict[str, Any]], user_agent: str = "SEC Connector/0.1.0"):
        """
        Initialize with company ticker->info mapping.

        Args:
            companies_data: Dictionary mapping ticker symbols to company info
                          (must contain 'cik_str' and 'title' keys)
            user_agent: User agent string for SEC API requests (required by SEC)
        """
        self._companies = companies_data
        self._filings: dict[str, list[dict[str, Any]]] = {}
        self._user_agent = user_agent
        self._base_url = "https://www.sec.gov/Archives/edgar/data"

    def add_filings_data(self, filings_data: dict[str, list[dict[str, Any]]]) -> None:
        """
        Add filings data for companies.

        Args:
            filings_data: Dictionary mapping CIK to list of filing dictionaries
        """
        self._filings = filings_data

    def lookup_company(self, ticker: str) -> Company:
        """
        Find company by ticker symbol.

        Args:
            ticker: Stock ticker symbol (case-insensitive)

        Returns:
            Company object with ticker, CIK, and name

        Raises:
            ValueError: If ticker is not found or is invalid
        """
        if not ticker or not ticker.strip():
            raise ValueError("Ticker cannot be empty")

        ticker = ticker.strip().upper()

        if ticker not in self._companies:
            raise ValueError(f"Company with ticker '{ticker}' not found")

        company_info = self._companies[ticker]

        # Extract CIK and pad to 10 digits
        cik_raw = str(company_info.get('cik_str', ''))
        if not cik_raw:
            raise ValueError(f"No CIK found for ticker '{ticker}'")

        cik = cik_raw.zfill(10)

        # Extract company name
        name = company_info.get('title', '')
        if not name:
            raise ValueError(f"No company name found for ticker '{ticker}'")

        return Company(ticker=ticker, cik=cik, name=name)

    def list_filings(self, cik: str, filters: FilingFilter) -> list[Filing]:
        """
        Get filings for a CIK, applying filters.

        Applies the following filters in order:
        - Filter by form_types (if provided)
        - Filter by date range (if provided)
        - Sort by date descending
        - Limit results

        Args:
            cik: Company CIK number (10-digit zero-padded string)
            filters: FilingFilter object with filtering criteria

        Returns:
            List of Filing objects matching the criteria

        Raises:
            ValueError: If CIK is not found or invalid
        """
        if not cik or not cik.strip():
            raise ValueError("CIK cannot be empty")

        cik = cik.strip()

        # Ensure CIK is zero-padded to 10 digits if it's numeric
        if cik.isdigit():
            cik = cik.zfill(10)

        if cik not in self._filings:
            # Return empty list if no filings found for this CIK
            return []

        raw_filings = self._filings[cik]
        filings: list[Filing] = []

        # Convert raw filing dicts to Filing objects
        for raw_filing in raw_filings:
            try:
                # Parse the filing date
                filing_date_str = raw_filing.get('filing_date', '')
                if isinstance(filing_date_str, str):
                    filing_date = date.fromisoformat(filing_date_str)
                elif isinstance(filing_date_str, date):
                    filing_date = filing_date_str
                else:
                    continue  # Skip invalid dates

                filing = Filing(
                    cik=cik,
                    company_name=raw_filing.get('company_name', ''),
                    form_type=raw_filing.get('form_type', ''),
                    filing_date=filing_date,
                    accession_number=raw_filing.get('accession_number', '')
                )
                filings.append(filing)
            except (ValueError, KeyError):
                # Skip invalid filings
                continue

        # Apply form type filter
        if filters.form_types:
            form_types_upper = [ft.upper() for ft in filters.form_types]
            filings = [f for f in filings if f.form_type.upper() in form_types_upper]

        # Apply date range filter
        if filters.date_from:
            filings = [f for f in filings if f.filing_date >= filters.date_from]

        if filters.date_to:
            filings = [f for f in filings if f.filing_date <= filters.date_to]

        # Sort by filing date descending (newest first)
        filings.sort(key=lambda f: f.filing_date, reverse=True)

        # Apply limit
        return filings[:filters.limit]

    def download_filing(self, accession_number: str, cik: str) -> str:
        """
        Download a filing document from SEC EDGAR.

        Args:
            accession_number: Filing accession number (e.g., "0000320193-24-000123")
            cik: Company CIK number (10-digit zero-padded string)

        Returns:
            Filing document content as string

        Raises:
            ValueError: If accession number or CIK is invalid
            httpx.HTTPError: If download fails
        """
        if not accession_number or not accession_number.strip():
            raise ValueError("Accession number cannot be empty")

        if not cik or not cik.strip():
            raise ValueError("CIK cannot be empty")

        # Clean inputs
        accession_number = accession_number.strip()
        cik = cik.strip().lstrip('0')  # Remove leading zeros for URL

        # Format accession number for URL (remove dashes)
        accession_no_dashes = accession_number.replace('-', '')

        # Construct SEC EDGAR URL
        # Format: https://www.sec.gov/Archives/edgar/data/{cik}/{accession_no_dashes}/{accession_number}.txt
        url = f"{self._base_url}/{cik}/{accession_no_dashes}/{accession_number}.txt"

        # Make request with required User-Agent header
        headers = {"User-Agent": self._user_agent}

        try:
            with httpx.Client() as client:
                response = client.get(url, headers=headers, timeout=30.0)
                response.raise_for_status()
                return response.text
        except httpx.HTTPStatusError as e:
            raise ValueError(f"Failed to download filing: HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise ValueError(f"Failed to download filing: {str(e)}") from e
