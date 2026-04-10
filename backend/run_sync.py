from scrapers.saanich import SaanichScraper
from scrapers.perfectmind import PerfectMindScraper
from scrapers.perfectmind_sources import PERFECTMIND_SOURCES
from scrapers.oakbay_pdf import OakBayPDFScraper
from scrapers.wspr import WSPRScraper
from models import init_db

def run_all():
    print("=== Starting ClubHub Sync ===")
    init_db()

    # 1. Saanich
    saanich = SaanichScraper()
    saanich.scrape()

    for source in PERFECTMIND_SOURCES:
        scraper = PerfectMindScraper(**source)
        scraper.scrape()

    oakbay_pdf = OakBayPDFScraper()
    oakbay_pdf.scrape()

    wspr = WSPRScraper()
    wspr.scrape()

    print("=== Sync Complete ===")

if __name__ == "__main__":
    run_all()
