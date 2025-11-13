"""Command-line interface for SEC Filing Connector."""

import json
import sys
import argparse
from pathlib import Path
from datetime import date
from sec_connector.client import SECClient
from sec_connector.models import FilingFilter


def load_fixture_data() -> tuple[dict, dict]:
    """
    Load test fixture data from JSON files.

    Returns:
        Tuple of (companies_data, filings_data)
    """
    fixtures_dir = Path(__file__).parent.parent / "tests" / "fixtures"

    companies_file = fixtures_dir / "company_tickers.json"
    filings_file = fixtures_dir / "filings_sample.json"

    if not companies_file.exists():
        print(f"Error: Companies fixture not found at {companies_file}", file=sys.stderr)
        sys.exit(1)

    if not filings_file.exists():
        print(f"Error: Filings fixture not found at {filings_file}", file=sys.stderr)
        sys.exit(1)

    with open(companies_file, 'r') as f:
        companies_data = json.load(f)

    with open(filings_file, 'r') as f:
        filings_data = json.load(f)

    return companies_data, filings_data


def format_table(filings: list) -> str:
    """
    Format filings as a simple text table.

    Args:
        filings: List of Filing objects

    Returns:
        Formatted table string
    """
    if not filings:
        return "No filings found."

    lines = []
    lines.append("-" * 100)
    lines.append(f"{'Form Type':<12} {'Filing Date':<15} {'Company':<40} {'Accession #':<25}")
    lines.append("-" * 100)

    for filing in filings:
        lines.append(
            f"{filing.form_type:<12} "
            f"{filing.filing_date.isoformat():<15} "
            f"{filing.company_name[:38]:<40} "
            f"{filing.accession_number:<25}"
        )

    lines.append("-" * 100)
    lines.append(f"Total: {len(filings)} filing(s)")

    return "\n".join(lines)


def main():
    """
    Main CLI entry point.

    Usage:
        python -m sec_connector.cli AAPL --form 10-K --limit 5
        python -m sec_connector.cli MSFT --form 10-Q --date-from 2023-01-01 --json
    """
    parser = argparse.ArgumentParser(
        description="SEC Filing Connector - Search and filter SEC EDGAR filings",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s AAPL --form 10-K --limit 5
  %(prog)s MSFT --form 10-Q --date-from 2023-01-01
  %(prog)s TSLA --limit 10 --json
        """
    )

    parser.add_argument(
        'ticker',
        type=str,
        help='Company ticker symbol (e.g., AAPL, MSFT, TSLA)'
    )

    parser.add_argument(
        '--form',
        type=str,
        action='append',
        dest='form_types',
        help='Filter by form type (can be specified multiple times). Example: --form 10-K --form 10-Q'
    )

    parser.add_argument(
        '--date-from',
        type=str,
        help='Filter filings from this date (YYYY-MM-DD format)'
    )

    parser.add_argument(
        '--date-to',
        type=str,
        help='Filter filings until this date (YYYY-MM-DD format)'
    )

    parser.add_argument(
        '--limit',
        type=int,
        default=10,
        help='Maximum number of results to return (default: 10)'
    )

    parser.add_argument(
        '--json',
        action='store_true',
        help='Output results as JSON instead of table'
    )

    parser.add_argument(
        '--download',
        type=str,
        metavar='FILENAME',
        help='Download the first matching filing to specified file'
    )

    args = parser.parse_args()

    try:
        # Load fixture data
        companies_data, filings_data = load_fixture_data()

        # Initialize client
        client = SECClient(companies_data)
        client.add_filings_data(filings_data)

        # Lookup company
        try:
            company = client.lookup_company(args.ticker)
            if not args.json:
                print(f"Company: {company.name} ({company.ticker})")
                print(f"CIK: {company.cik}")
                print()
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

        # Parse date filters
        date_from = None
        date_to = None

        if args.date_from:
            try:
                date_from = date.fromisoformat(args.date_from)
            except ValueError:
                print(f"Error: Invalid date format for --date-from: {args.date_from}", file=sys.stderr)
                print("Use YYYY-MM-DD format", file=sys.stderr)
                sys.exit(1)

        if args.date_to:
            try:
                date_to = date.fromisoformat(args.date_to)
            except ValueError:
                print(f"Error: Invalid date format for --date-to: {args.date_to}", file=sys.stderr)
                print("Use YYYY-MM-DD format", file=sys.stderr)
                sys.exit(1)

        # Create filter
        filing_filter = FilingFilter(
            form_types=args.form_types,
            date_from=date_from,
            date_to=date_to,
            limit=args.limit
        )

        # Get filings
        filings = client.list_filings(company.cik, filing_filter)

        # Handle download if requested
        if args.download:
            if not filings:
                print("Error: No filings found to download", file=sys.stderr)
                sys.exit(1)

            print(f"Downloading filing: {filings[0].form_type} from {filings[0].filing_date}")
            print(f"Accession: {filings[0].accession_number}")

            try:
                content = client.download_filing(filings[0].accession_number, company.cik)
                with open(args.download, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f"Successfully downloaded to: {args.download}")
                print(f"Size: {len(content)} characters")
            except Exception as e:
                print(f"Error downloading filing: {e}", file=sys.stderr)
                sys.exit(1)
            return

        # Output results
        if args.json:
            output = {
                "company": company.model_dump(),
                "filings": [f.model_dump(mode='json') for f in filings],
                "count": len(filings)
            }
            print(json.dumps(output, indent=2, default=str))
        else:
            print(format_table(filings))

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
