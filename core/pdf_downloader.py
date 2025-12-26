import os
import time
import random
import re


class PDFDownloader:
    """
    Generic PDF Downloader
    -----------------------
    - Download any .pdf URL using SessionManager
    - Manage Blocks (403/429)
    - Save valid PDFs in /downloads/
    """

    def __init__(self, session_manager, output_dir="downloads/"):
        self.session_manager = session_manager
        self.output_dir = output_dir

        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def sanitize_filename(self, url):
        """Generates a valid file name based on the URL."""
        name = url.split("/")[-1]
        name = re.sub(r"[^A-Za-z0-9._-]", "_", name)
        return name

    def save_pdf(self, content, filename):
        """Save and storage PDF in disk."""
        filepath = os.path.join(self.output_dir, filename)
        with open(filepath, "wb") as f:
            f.write(content)
        return filepath

    def fetch_pdf(self, url, max_retries=3):
        """
        Make RAW request using ScraperSession.raw_get()
        Manage blocks (403/429) and retries.
        """
        session = self.session_manager.get_current_session()

        for attempt in range(max_retries):
            try:
                response = session.raw_get(url, timeout=20, allow_redirects=True)

                # Correct PDF
                if response.status_code == 200 and b"%PDF" in response.content[:10]:
                    return ("pdf", response.content)

                # Not found
                if response.status_code == 404:
                    return ("not_found", None)

                # WAF / Rate Limit
                if response.status_code in (403, 429):
                    print(f"[WARN] WAF/RATE-LIMIT ({response.status_code}) in {url}")

                    if attempt == max_retries - 1:
                        return ("blocked", None)

                    time.sleep(random.uniform(1.5, 3.5))
                    continue

                # Other errors
                return ("error", response.status_code)

            except Exception as e:
                print(f"[ERROR] {e}")
                time.sleep(random.uniform(1.0, 2.0))

        return ("error", None)

    def download(self, url):
        """General control of the unloader."""
        if not url.lower().endswith(".pdf"):
            print(f"[ERROR] Invalid URL (no PDF): {url}")
            return None

        status, data = self.fetch_pdf(url)

        if status == "pdf":
            filename = self.sanitize_filename(url)
            path = self.save_pdf(data, filename)
            print(f"[OK] PDF saved → {path}")
            return path

        if status == "not_found":
            print(f"[INFO] 404 Not Found → {url}")
            return None

        if status == "blocked":
            print("[WARN] PDF blocked by WAF")
            return "blocked"

        print(f"[ERROR] Unexpected error downloading {url}")
        return None
