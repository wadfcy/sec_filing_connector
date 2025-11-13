"""Tests for SEC Filing Connector."""

import json
import pytest
from pathlib import Path
from datetime import date
from pydantic import ValidationError
from unittest.mock import Mock, patch
import httpx

from sec_connector.models import Company, Filing, FilingFilter
from sec_connector.client import SECClient


# Fixtures
@pytest.fixture
def companies_data():
    """Load company ticker data from fixture."""
    fixture_path = Path(__file__).parent / "fixtures" / "company_tickers.json"
    with open(fixture_path, 'r') as f:
        return json.load(f)


@pytest.fixture
def filings_data():
    """Load filings data from fixture."""
    fixture_path = Path(__file__).parent / "fixtures" / "filings_sample.json"
    with open(fixture_path, 'r') as f:
        return json.load(f)


@pytest.fixture
def client(companies_data, filings_data):
    """Create SECClient with test data."""
    client = SECClient(companies_data)
    client.add_filings_data(filings_data)
    return client


# Model Tests
class TestModels:
    """Tests for Pydantic data models."""

    def test_company_model_valid(self):
        """Test that Company model validates correct data."""
        company = Company(ticker="AAPL", cik="0000320193", name="Apple Inc.")
        assert company.ticker == "AAPL"
        assert company.cik == "0000320193"
        assert company.name == "Apple Inc."

    def test_company_model_empty_ticker(self):
        """Test that Company model rejects empty ticker."""
        with pytest.raises(ValidationError):
            Company(ticker="", cik="0000320193", name="Apple Inc.")

    def test_company_model_empty_cik(self):
        """Test that Company model rejects empty CIK."""
        with pytest.raises(ValidationError):
            Company(ticker="AAPL", cik="", name="Apple Inc.")

    def test_company_model_ticker_normalization(self):
        """Test that ticker is normalized to uppercase."""
        company = Company(ticker="aapl", cik="0000320193", name="Apple Inc.")
        assert company.ticker == "AAPL"

    def test_filing_model_valid(self):
        """Test that Filing model validates correct data."""
        filing = Filing(
            cik="0000320193",
            company_name="Apple Inc.",
            form_type="10-K",
            filing_date=date(2024, 11, 1),
            accession_number="0000320193-24-000123"
        )
        assert filing.form_type == "10-K"
        assert filing.filing_date == date(2024, 11, 1)

    def test_filing_model_empty_form_type(self):
        """Test that Filing model rejects empty form type."""
        with pytest.raises(ValidationError):
            Filing(
                cik="0000320193",
                company_name="Apple Inc.",
                form_type="",
                filing_date=date(2024, 11, 1),
                accession_number="0000320193-24-000123"
            )

    def test_filing_filter_defaults(self):
        """Test FilingFilter default values."""
        filter = FilingFilter()
        assert filter.form_types is None
        assert filter.date_from is None
        assert filter.date_to is None
        assert filter.limit == 10

    def test_filing_filter_invalid_limit(self):
        """Test that FilingFilter rejects non-positive limit."""
        with pytest.raises(ValidationError):
            FilingFilter(limit=0)

        with pytest.raises(ValidationError):
            FilingFilter(limit=-1)


# Company Lookup Tests
class TestCompanyLookup:
    """Tests for company lookup functionality."""

    def test_lookup_valid_ticker(self, client):
        """Test lookup with valid ticker returns Company."""
        company = client.lookup_company("AAPL")
        assert isinstance(company, Company)
        assert company.ticker == "AAPL"
        assert company.cik == "0000320193"
        assert company.name == "Apple Inc."

    def test_lookup_case_insensitive(self, client):
        """Test that ticker lookup is case-insensitive."""
        company = client.lookup_company("aapl")
        assert company.ticker == "AAPL"

    def test_lookup_invalid_ticker(self, client):
        """Test that invalid ticker raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            client.lookup_company("INVALID")

    def test_lookup_empty_ticker(self, client):
        """Test that empty ticker raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            client.lookup_company("")

    def test_cik_zero_padding(self, client):
        """Test that CIK is zero-padded to 10 digits."""
        company = client.lookup_company("AAPL")
        assert len(company.cik) == 10
        assert company.cik == "0000320193"

        company = client.lookup_company("MSFT")
        assert len(company.cik) == 10
        assert company.cik == "0000789019"


# Filing Filtering Tests
class TestFilingFiltering:
    """Tests for filing filtering functionality."""

    def test_list_filings_no_filters(self, client):
        """Test that no filters returns all filings (limited)."""
        filter = FilingFilter(limit=100)
        filings = client.list_filings("0000320193", filter)

        assert len(filings) == 10  # Should return all 10 AAPL filings
        assert all(isinstance(f, Filing) for f in filings)

    def test_list_filings_form_type_filter(self, client):
        """Test filtering by form type."""
        filter = FilingFilter(form_types=["10-K"])
        filings = client.list_filings("0000320193", filter)

        assert len(filings) == 3  # AAPL has 3 10-K filings
        assert all(f.form_type == "10-K" for f in filings)

    def test_list_filings_multiple_form_types(self, client):
        """Test filtering by multiple form types."""
        filter = FilingFilter(form_types=["10-K", "10-Q"])
        filings = client.list_filings("0000320193", filter)

        assert len(filings) == 8  # AAPL has 3 10-K + 5 10-Q filings
        assert all(f.form_type in ["10-K", "10-Q"] for f in filings)

    def test_list_filings_date_from_filter(self, client):
        """Test filtering by date_from."""
        filter = FilingFilter(date_from=date(2024, 1, 1))
        filings = client.list_filings("0000320193", filter)

        assert all(f.filing_date >= date(2024, 1, 1) for f in filings)

    def test_list_filings_date_to_filter(self, client):
        """Test filtering by date_to."""
        filter = FilingFilter(date_to=date(2024, 6, 1))
        filings = client.list_filings("0000320193", filter)

        assert all(f.filing_date <= date(2024, 6, 1) for f in filings)

    def test_list_filings_date_range_filter(self, client):
        """Test filtering by date range."""
        filter = FilingFilter(
            date_from=date(2024, 1, 1),
            date_to=date(2024, 8, 31)
        )
        filings = client.list_filings("0000320193", filter)

        assert all(
            date(2024, 1, 1) <= f.filing_date <= date(2024, 8, 31)
            for f in filings
        )

    def test_list_filings_sorted_by_date_descending(self, client):
        """Test that results are sorted by date descending (newest first)."""
        filter = FilingFilter(limit=100)
        filings = client.list_filings("0000320193", filter)

        # Check that dates are in descending order
        for i in range(len(filings) - 1):
            assert filings[i].filing_date >= filings[i + 1].filing_date

    def test_list_filings_limit_respected(self, client):
        """Test that limit is respected."""
        filter = FilingFilter(limit=3)
        filings = client.list_filings("0000320193", filter)

        assert len(filings) == 3

    def test_list_filings_combined_filters(self, client):
        """Test combining multiple filters."""
        filter = FilingFilter(
            form_types=["10-Q"],
            date_from=date(2024, 1, 1),
            limit=2
        )
        filings = client.list_filings("0000320193", filter)

        assert len(filings) == 2
        assert all(f.form_type == "10-Q" for f in filings)
        assert all(f.filing_date >= date(2024, 1, 1) for f in filings)
        # Check sorted descending
        assert filings[0].filing_date >= filings[1].filing_date

    def test_list_filings_nonexistent_cik(self, client):
        """Test that nonexistent CIK returns empty list."""
        filter = FilingFilter()
        filings = client.list_filings("9999999999", filter)

        assert filings == []

    def test_list_filings_no_matches(self, client):
        """Test that no matches returns empty list."""
        filter = FilingFilter(form_types=["NONEXISTENT"])
        filings = client.list_filings("0000320193", filter)

        assert filings == []

    def test_list_filings_different_companies(self, client):
        """Test filtering for different companies."""
        # Test Microsoft
        filter = FilingFilter(form_types=["10-K"])
        msft_filings = client.list_filings("0000789019", filter)
        assert len(msft_filings) == 2
        assert all(f.company_name == "Microsoft Corp" for f in msft_filings)

        # Test Tesla
        tsla_filings = client.list_filings("0001318605", filter)
        assert len(tsla_filings) == 1
        assert all(f.company_name == "Tesla, Inc." for f in tsla_filings)


# Edge Cases Tests
class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_cik_raises_error(self, client):
        """Test that empty CIK raises ValueError."""
        filter = FilingFilter()
        with pytest.raises(ValueError, match="cannot be empty"):
            client.list_filings("", filter)

    def test_whitespace_ticker(self, client):
        """Test that whitespace in ticker is handled."""
        company = client.lookup_company("  AAPL  ")
        assert company.ticker == "AAPL"

    def test_client_without_filings_data(self, companies_data):
        """Test client works without filings data."""
        client = SECClient(companies_data)
        company = client.lookup_company("AAPL")
        assert company.ticker == "AAPL"

        # Should return empty list when no filings data
        filter = FilingFilter()
        filings = client.list_filings(company.cik, filter)
        assert filings == []

    def test_form_type_case_insensitive(self, client):
        """Test that form type filtering is case-insensitive."""
        filter1 = FilingFilter(form_types=["10-k"])
        filings1 = client.list_filings("0000320193", filter1)

        filter2 = FilingFilter(form_types=["10-K"])
        filings2 = client.list_filings("0000320193", filter2)

        assert len(filings1) == len(filings2)
        assert len(filings1) == 3


# Download Tests
class TestDownload:
    """Tests for filing download functionality."""

    def test_download_filing_empty_accession_number(self, client):
        """Test that empty accession number raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            client.download_filing("", "0000320193")

    def test_download_filing_empty_cik(self, client):
        """Test that empty CIK raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            client.download_filing("0000320193-24-000123", "")

    @patch('httpx.Client')
    def test_download_filing_success(self, mock_client_class, client):
        """Test successful filing download."""
        # Mock response
        mock_response = Mock()
        mock_response.text = "MOCK FILING CONTENT"
        mock_response.raise_for_status = Mock()

        # Mock client
        mock_client = Mock()
        mock_client.get.return_value = mock_response
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client_class.return_value = mock_client

        # Test download
        content = client.download_filing("0000320193-24-000123", "0000320193")

        assert content == "MOCK FILING CONTENT"
        mock_client.get.assert_called_once()

        # Verify URL construction
        call_args = mock_client.get.call_args
        url = call_args[0][0]
        assert "320193" in url  # CIK without leading zeros
        assert "000032019324000123" in url  # Accession without dashes

    @patch('httpx.Client')
    def test_download_filing_http_error(self, mock_client_class, client):
        """Test download with HTTP error."""
        # Mock 404 response
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Not Found", request=Mock(), response=mock_response
        )

        # Mock client
        mock_client = Mock()
        mock_client.get.return_value = mock_response
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client_class.return_value = mock_client

        # Test that it raises ValueError with HTTP status
        with pytest.raises(ValueError, match="HTTP 404"):
            client.download_filing("0000320193-24-000123", "0000320193")

    @patch('httpx.Client')
    def test_download_filing_request_error(self, mock_client_class, client):
        """Test download with network error."""
        # Mock network error
        mock_client = Mock()
        mock_client.get.side_effect = httpx.RequestError("Connection failed")
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client_class.return_value = mock_client

        # Test that it raises ValueError with error message
        with pytest.raises(ValueError, match="Connection failed"):
            client.download_filing("0000320193-24-000123", "0000320193")

    @patch('httpx.Client')
    def test_download_filing_user_agent(self, mock_client_class, client):
        """Test that User-Agent header is set."""
        # Mock response
        mock_response = Mock()
        mock_response.text = "CONTENT"
        mock_response.raise_for_status = Mock()

        # Mock client
        mock_client = Mock()
        mock_client.get.return_value = mock_response
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client_class.return_value = mock_client

        # Download
        client.download_filing("0000320193-24-000123", "0000320193")

        # Verify User-Agent header was passed
        call_args = mock_client.get.call_args
        headers = call_args[1]['headers']
        assert 'User-Agent' in headers
        assert headers['User-Agent'] == "SEC Connector/0.1.0"
