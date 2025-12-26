import os
import time
import json
import random
import logging
import threading
from http import HTTPStatus
from typing import Optional, Dict, Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry


logger = logging.getLogger("session_manager")
if not logger.handlers:
    h = logging.StreamHandler()
    h.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    logger.addHandler(h)
logger.setLevel(logging.INFO)


DEFAULT_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 Edg/128.0.0.0",
]


BASE_DIR = os.path.dirname(os.path.dirname(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, ".."))
COOKIES_DIR = os.path.join(PROJECT_ROOT, "data", "cookies")
os.makedirs(COOKIES_DIR, exist_ok=True)

# Random delay
def _random_human_delay():
    if random.random() < 0.10:
        return random.uniform(6.0, 12.0)
    return random.uniform(1.0, 5.0)


class ScraperSession:
    #Sesion navigator-like with proxy, cookies, headers y retries.

    def __init__(
        self,
        session_id: str,
        user_agent: str,
        proxy: Optional[str] = None,
        persist_cookies: bool = True,
        max_retries: int = 3,
        backoff_factor: float = 0.5,
        include_sec_fetch: bool = False,
    ):
        self.session_id = session_id
        self.user_agent = user_agent
        self.proxy = proxy
        self.persist_cookies = persist_cookies
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.include_sec_fetch = include_sec_fetch

        self.session = requests.Session()

        if self.proxy:
            self.session.proxies.update({"http": self.proxy, "https": self.proxy})

        base_headers = {
            "User-Agent": self.user_agent,
            "Accept": "*/*",
            "Accept-Language": "es-ES,es;q=0.9",
            "Connection": "keep-alive",
        }
        self.session.headers.update(base_headers)

        retry_strategy = Retry(total=0)
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

        self.cookie_file = os.path.join(COOKIES_DIR, f"session_{self.session_id}.json")
        self.cookie_lock = threading.Lock()

        if self.persist_cookies:
            self._load_cookies_from_disk()

    # ------------------------------ Cookies ------------------------------

    def _save_cookies_to_disk(self):
        try:
            with self.cookie_lock:
                cookies = requests.utils.dict_from_cookiejar(self.session.cookies)
                with open(self.cookie_file, "w", encoding="utf-8") as fh:
                    json.dump(cookies, fh)
        except:
            pass

    def _load_cookies_from_disk(self):
        if os.path.exists(self.cookie_file):
            try:
                with open(self.cookie_file, "r", encoding="utf-8") as fh:
                    cookies = json.load(fh)
                jar = requests.utils.cookiejar_from_dict(cookies)
                self.session.cookies = jar
            except:
                pass

    # ------------------------------ NEW: raw request ------------------------------

    def raw_get(self, url, timeout=20, **kwargs) -> requests.Response:
        """
        Directly returns the Response object
        """
        return self.session.get(url, timeout=timeout, **kwargs)

    # ------------------------------ High-level GET ------------------------------

    def get(self, url, timeout=20, **kwargs):
        """
        Version with retries and human delay.
        """
        for attempt in range(self.max_retries):
            try:
                resp = self.session.get(url, timeout=timeout, **kwargs)
                return {"status": resp.status_code, "ok": resp.status_code == 200, "content": resp.content}
            except Exception as e:
                time.sleep(self.backoff_factor * (attempt + 1))
        return {"status": None, "ok": False, "error": "failed"}


class SessionManager:

    def __init__(self, user_agents_file: Optional[str] = None, rotate_every: int = 5, proxy: Optional[str] = None):
        self.rotate_every = rotate_every
        self._load_user_agents(user_agents_file)
        self._global_request_count = 0
        self._session_idx = 0
        self._sessions = {}
        self.proxy = proxy
        self.current_session = None

    # ------------------------------ Utilities ------------------------------

    def _load_user_agents(self, file_path: Optional[str]):
        self.user_agents = DEFAULT_USER_AGENTS.copy()
        if file_path and os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as fh:
                    lines = [l.strip() for l in fh if l.strip()]
                if lines:
                    self.user_agents = lines + self.user_agents
            except:
                pass

    def _pick_user_agent(self):
        idx = (self._global_request_count // self.rotate_every) % len(self.user_agents)
        self._global_request_count += 1
        return self.user_agents[idx]

    # ------------------------------ FIX: new _create_session() ------------------------------

    def _create_session(self):
        """
        Create new ScraperSession (for get_current_session)
        """
        ua = self._pick_user_agent()
        sid = str(self._session_idx)
        self._session_idx += 1

        s = ScraperSession(
            session_id=sid,
            user_agent=ua,
            proxy=self.proxy,
            persist_cookies=True,
        )

        self._sessions[sid] = s
        return s

    # ------------------------------ API for main.py ------------------------------

    def get_current_session(self):
        if self.current_session is None:
            self.current_session = self._create_session()
        return self.current_session

    def create_new_session(self):
        self.current_session = self._create_session()
        return self.current_session
