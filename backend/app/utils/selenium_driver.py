import logging
import os

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium_stealth import stealth

homedir = os.path.expanduser("~")
CHROME_DRIVER_PATH = f"{homedir}/Downloads/chromedriver-win64/chromedriver.exe"

logging.getLogger("selenium").setLevel(logging.WARNING)


class SeleniumDriver:
    @staticmethod
    def get_driver(use_headless=True):
        options = Options()
        if use_headless:
            options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        # SUPPRESS some error coming from chrome
        options.add_argument("--log-level=3")
        options.add_experimental_option(
            "excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)

        # Uncomment the following line when ready to use proxy rotation
        # proxy = CardDataManager.rotate_proxy()
        # if proxy:
        #     options.add_argument(f'--proxy-server={proxy}')

        service = Service(CHROME_DRIVER_PATH)
        driver = webdriver.Chrome(service=service, options=options)

        stealth(
            driver,
            languages=["en-US", "en"],
            vendor="Google Inc.",
            platform="Win32",
            webgl_vendor="Intel Inc.",
            renderer="Intel Iris OpenGL Engine",
            fix_hairline=True,
        )

        return driver
