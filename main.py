import sys
import logging
from scraper import open_browser_and_login, scrape_post_comments
from exporter import export_to_excel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("linkedin_leads")


def main():
    
    print()
    print("=" * 55)
    print("  LinkedIn Post Comment Lead Extractor")
    print("=" * 55)
    print()

    print("Opening LinkedIn login page")
    print("Log-in in the browser window.\n")

    try:
        pw, browser, page = open_browser_and_login(headless=False, slow_mo=100)
    except TimeoutError:
        logger.error("Login timed out. Try again.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Browser launch failed: {e}")
        sys.exit(1)

    print()
    print("Login successful\n")

    print("Enter the LinkedIn post URL")

    post_url = input("  Post URL: ").strip()

    if not post_url:
        logger.error("No URL provided. Exit")
        browser.close()
        pw.stop()
        sys.exit(1)

    if "linkedin.com" not in post_url:
        logger.warning("Not looking like a valid linkedin url")

    print()
    print("Scraping comments\n")

    output_path = "output/linkedin_leads.xlsx"

    try:
        leads = scrape_post_comments(
            page=page,
            post_url=post_url,
            max_scrolls=50,
            scroll_delay=2.0,
        )
    except Exception as e:
        logger.error(f"Scraping failed: {e}")
        browser.close()
        pw.stop()
        sys.exit(1)

    if not leads:
        print("No comments found.")
        print("The post may have no comments.")
        browser.close()
        pw.stop()
        sys.exit(0)

    saved_path = export_to_excel(leads, output_path)

    browser.close()
    pw.stop()

    print()
    print("=" * 55)
    print(f"Extracted {len(leads)} comments.")
    print(f"Saved to: {saved_path}")
    print("=" * 55)
    print()


if __name__ == "__main__":
    main()
