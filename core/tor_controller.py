import requests
import random
import time
from stem import Signal
from stem.control import Controller

TOR_SOCKS_PROXY = "socks5h://127.0.0.1:9050"
TOR_CONTROL_PORT = 9051
TOR_PASSWORD = "" #Add your TOR password HERE!


class TorController:
    """
    TOR driver with high robustness:
    - NEWNYM + retries with backoff
    - 3 services to resolve IP
    - Rotation with valid IP verification
    - Controlled failure if no IP obtained after 3 rotations
    """

    def __init__(self):
        self.session = None
        self.user_agent = None

    # REFRESH IP
    def refresh_ip(self):
        """Request a new IP controlling failures."""
        print("\n[TOR] Starting IP refresh...")

        new_ip = self._rotate_until_valid_ip(max_rotations=3)
        return new_ip

    # PUBLIC: Rotate IP
    def rotate_ip(self):
        """Rotate the IP ensuring you get a valid IP."""
        print("\n[TOR] Requesting IP rotation...")

        new_ip = self._rotate_until_valid_ip(max_rotations=3)
        return new_ip

    # INTERNAL: Rotate repeatedly until you get a valid public IP
    def _rotate_until_valid_ip(self, max_rotations=3):
        """
        Rotate IP until you get a valid one.
        If more than `max_rotations` → returns None.
        """

        for attempt in range(1, max_rotations + 1):
            print(f"[TOR] Rotation {attempt}/{max_rotations}")

            if not self._newnym_with_retry():
                print("[TOR] ERROR: NEWNYM failed repeatedly.")
            else:
                print("[TOR] NEWNYM sent. Waiting for stabilization...")
                time.sleep(3)

            ip = self.get_current_ip()

            if ip:
                print(f"[TOR] Current TOR IP: {ip}\n")
                return ip

            print("[TOR] Could not get IP after rotation.")

        print("\n[CRITICAL] ❌ Could not get an IP from TOR after 3 attempts.")
        print("[CRITICAL] Finalizing scraping system.\n")
        return None

    # NEWNYM with retries
    def _newnym_with_retry(self, retries=3, base_delay=2):
        """
        Exponential retries:
        - Delay: 2s → 4s → 8s
        """
        for attempt in range(1, retries + 1):
            print(f"[TOR] Sending NEWNYM ({attempt}/{retries})...")

            if self._send_newnym():
                print("[TOR] NEWNYM sent successfully.")
                return True

            wait_time = base_delay * (2 ** (attempt - 1))
            print(f"[TOR] NEWNYM fail. Retrying on {wait_time}s...")
            time.sleep(wait_time)

        return False

    # Send NEWNYM signal to control port
    def _send_newnym(self):
        try:
            with Controller.from_port(port=TOR_CONTROL_PORT) as controller:
                controller.authenticate(password=TOR_PASSWORD)
                controller.signal(Signal.NEWNYM)
                return True
        except Exception as e:
            print(f"[TOR-ERROR] NEWNYM error: {e}")
            return False

    # Get IP
    def get_current_ip(self, retries=3):
        """
        Try to get IP using 3 services:
        - api.ipify.org
        - check.torproject.org
        - ifconfig.me

        Makes global retries if all fail.
        """

        services = [
            "https://api.ipify.org",
            "https://check.torproject.org/api/ip",
            "https://ifconfig.me/ip"
        ]

        for attempt in range(1, retries + 1):
            print(f"[TOR] Resolving IP (Tried {attempt}/{retries})...")

            for url in services:
                try:
                    r = requests.get(
                        url,
                        proxies={"http": TOR_SOCKS_PROXY, "https": TOR_SOCKS_PROXY},
                        timeout=10
                    )
                    ip_text = r.text.strip()

                    # check.torproject.org return JSON and filter:
                    if "ip" in ip_text and "{" in ip_text:
                        try:
                            ip_text = r.json().get("IP", None)
                        except:
                            pass

                    if ip_text and len(ip_text) >= 7:
                        return ip_text

                except Exception:
                    pass  # Ignore error, go to next service

            print("[TOR] Could not get IP. Retrying...")
            time.sleep(2)

        print("[TOR] FAILED: Could not obtain IP after multiple attempts.\n")
        return None

    # Create scraping sesion
    def create_session(self, user_agent):
        self.user_agent = user_agent
        self.session = requests.Session()

        self.session.proxies = {
            "http": TOR_SOCKS_PROXY,
            "https": TOR_SOCKS_PROXY
        }

        self.session.headers.update({
            "User-Agent": user_agent,
            "Accept-Language": "es-ES,es;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept": "*/*",
            "Connection": "keep-alive",
            "DNT": "1",
        })

    # Human delay
    def human_delay(self):
        time.sleep(random.uniform(2, 9))

    # Test 5 requests (debug)
    def run_5_requests(self, urls):
        if not self.session:
            raise RuntimeError("You must create a session first.")

        results = []

        for url in urls:
            print(f"[REQUEST] {url}")

            try:
                r = self.session.get(url, timeout=20)
                results.append({
                    "url": url,
                    "status": r.status_code,
                    "ok": (r.status_code == 200)
                })
                print(f" → Status: {r.status_code}")

            except Exception as e:
                print(f"[ERROR] {e}")
                results.append({
                    "url": url,
                    "status": None,
                    "ok": False,
                    "error": str(e)
                })

            self.human_delay()

        return results
