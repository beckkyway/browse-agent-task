import os

from browser_use import Browser
from browser_use.browser.browser import BrowserConfig
from browser_use.browser.context import BrowserContextConfig

SESSION_FILE = os.path.join('browser_profile', 'session.json')


def create_browser() -> Browser:
    """Create browser with persistent session and browser-use default timings."""
    session_exists = os.path.exists(SESSION_FILE)
    return Browser(config=BrowserConfig(
        headless=False,
        keep_alive=True,
        new_context_config=BrowserContextConfig(
            keep_alive=True,
            cookies_file=SESSION_FILE if session_exists else None,
            highlight_elements=True,
            # Using browser-use defaults (fast):
            # wait_between_actions=0.5
            # minimum_wait_page_load_time=0.25
            # wait_for_network_idle_page_load_time=0.5
            # maximum_wait_page_load_time=5.0
        )
    ))
