"""
ArXiv Paper Scraper for Agentic AI
Scrapes papers from arXiv about agentic AI and saves them to Google Drive.
"""

import csv
import json
from datetime import UTC, datetime
from pathlib import Path

import arxiv


class ArxivScraper:
    """Scrapes papers from arXiv API about agentic AI."""

    SEARCH_QUERY = "Artificial Intelligence"  # Very simple query for testing
    MAX_RESULTS = 100

    def __init__(self, max_results: int = MAX_RESULTS):
        """
        Initialize the ArXiv scraper.

        Args:
            max_results: Maximum number of papers to retrieve
        """
        self.max_results = max_results
        self.papers = []

    def fetch_papers(self, search_query: str | None = None) -> list[dict]:
        """
        Fetch papers from arXiv API.

        Args:
            search_query: Custom search query. Uses default if None.

        Returns:
            List of paper dictionaries
        """
        query = search_query or self.SEARCH_QUERY

        try:
            # Create the search client with rate limiting
            client = arxiv.Client()
            search = arxiv.Search(
                query=query,
                max_results=self.max_results,
                sort_by=arxiv.SortCriterion.SubmittedDate,
                sort_order=arxiv.SortOrder.Descending,
            )

            # Fetch results with error handling
            for result in client.results(search):
                paper = {
                    "title": result.title,
                    "authors": [author.name for author in result.authors],
                    "published": result.published.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "summary": result.summary.replace("\n", " "),
                    "arxiv_id": result.entry_id.split("/abs/")[-1],
                    "pdf_url": str(result.pdf_url),
                    "arxiv_url": result.entry_id,
                    "categories": result.categories,
                    "primary_category": result.primary_category,
                    "updated": result.updated.strftime("%Y-%m-%dT%H:%M:%SZ")
                    if result.updated
                    else None,
                }
                self.papers.append(paper)

            print(f"Successfully fetched {len(self.papers)} papers from arXiv")
            return self.papers

        except arxiv.ArxivError as e:
            print(f"Error fetching papers from arXiv: {e}")
            return []

    def save_to_json(self, filepath: str) -> None:
        """Save papers to JSON file."""
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.papers, f, indent=2, ensure_ascii=False)
        print(f"Papers saved to {filepath}")

    def save_to_csv(self, filepath: str) -> None:
        """Save papers to CSV file."""
        if not self.papers:
            print("No papers to save")
            return

        keys = self.papers[0].keys()
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            for paper in self.papers:
                # Convert authors and categories lists to strings for CSV
                paper_row = paper.copy()
                paper_row["authors"] = "; ".join(paper_row["authors"])
                paper_row["categories"] = "; ".join(paper_row["categories"])
                writer.writerow(paper_row)
        print(f"Papers saved to {filepath}")


def main():
    """Main function to scrape papers and upload to Google Drive."""
    # Step 1: Scrape papers from arXiv
    print("=" * 60)
    print("Starting ArXiv paper scraping...")
    print("=" * 60)

    scraper = ArxivScraper(max_results=10)  # Reduced for testing
    scraper.fetch_papers()

    if not scraper.papers:
        print("No papers found. Exiting.")
        return

    # Step 2: Save papers locally
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    data_folder = Path(r"C:\Users\jrodw\Documents\Research Papers")
    json_file = data_folder / f"agentic_ai_papers_{timestamp}.json"
    csv_file = data_folder / f"agentic_ai_papers_{timestamp}.csv"

    scraper.save_to_json(str(json_file))
    scraper.save_to_csv(str(csv_file))

    # Step 3: Upload to Google Drive
    print("\n" + "=" * 60)
    print("Starting Google Drive upload...")
    print("=" * 60)

    print("\n" + "=" * 60)
    print("✓ Scraping complete!")
    print("=" * 60)
    print(f"Total papers scraped: {len(scraper.papers)}")


if __name__ == "__main__":
    main()
