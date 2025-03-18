import json
import random
import time

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium_stealth import stealth


def search_cardconduit(cardname):
    url = f"https://cardconduit.com/buylist?cardname={cardname}&set_code=&price_lte=&price_gte=&sort=name-asc&finish=&page=1"

    options = Options()
    options.add_argument("--disable-gpu")
    options.add_argument("--headless")  # Add this line
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    service = Service(
        "C:/Users/beauju/Downloads/chromedriver-win64/chromedriver.exe"
    )  # Replace with your chromedriver path
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

    try:
        driver.get(url)
        time.sleep(random.uniform(3, 5))  # Random delay

        # Scroll down
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(random.uniform(2, 4))  # Random delay

        # Wait for the content to load
        WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.CSS_SELECTOR, "pre")))

        # Extract the JSON data
        json_element = driver.find_element(By.CSS_SELECTOR, "pre")
        json_text = json_element.text
        data = json.loads(json_text)

        # Process and display results
        print(f"Search results for '{cardname}':\n")
        for card in data["data"]:
            print(f"Name: {card['card']['name']}")
            print(f"Set: {card['card']['set']['name']} ({card['card']['set']['code']})")
            print(f"Number: {card['card']['number']}")
            print(f"Condition: {card['condition']}")
            print(f"Price: ${card['amount']:.2f}")
            print(f"Foil: {'Yes' if card['is_foil'] else 'No'}")
            print("---")

    except Exception as e:
        print(f"An error occurred: {e}")

    finally:
        driver.quit()


# Example usage
search_cardconduit("fireball")
