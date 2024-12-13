import os
import json
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import logging
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# Initialize logging
logging.basicConfig(level=logging.INFO)

# Load configuration from config.json
with open("config.json") as config_file:
    config = json.load(config_file)

# Function to scrape prices from eBay based on product name
def scrape_ebay(product_name):
    """
    Scrape eBay for product prices based on the product name.
    """
    search_url = f"https://www.ebay.com/sch/i.html?_nkw={product_name.replace(' ', '+')}&_sop=12"
    headers = {
        "User-Agent": config["user_agent"]
    }
    response = requests.get(search_url, headers=headers)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, 'html.parser')
    listings = soup.find_all("li", class_="s-item")

    prices = []
    for item in listings:
        price_tag = item.find("span", class_="s-item__price")
        if price_tag:
            price_text = price_tag.text.replace("$", "").replace(",", "").strip()
            try:
                prices.append(float(price_text))
            except ValueError:
                continue

    average_price = sum(prices) / len(prices) if prices else None
    return average_price

# Function to scrape prices from Amazon based on product name
def scrape_amazon(product_name):
    """
    Scrape Amazon for product prices based on the product name.
    """
    search_url = f"https://www.amazon.com/s?k={product_name.replace(' ', '+')}"
    headers = {
        "User-Agent": config["user_agent"]
    }
    response = requests.get(search_url, headers=headers)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, 'html.parser')
    listings = soup.find_all("span", class_="a-price-whole")

    prices = []
    for price_tag in listings:
        try:
            price_text = price_tag.text.replace(",", "").strip()
            prices.append(float(price_text))
        except ValueError:
            continue

    average_price = sum(prices) / len(prices) if prices else None
    return average_price

# Function to scrape prices from TCGPlayer based on product name
def scrape_tcgplayer(product_name):
    """
    Scrape TCGPlayer for product prices using a simulated browser session.
    """
    url = f"https://www.tcgplayer.com/search/all/product?q={product_name.replace(' ', '%20')}"
    driver = initialize_webdriver()

    prices = []
    try:
        driver.get(url)
        driver.implicitly_wait(10)
        price_elements = driver.find_elements(By.CLASS_NAME, "search-result__market-price")
        for element in price_elements:
            price_text = element.text.replace("$", "").strip()
            try:
                prices.append(float(price_text))
            except ValueError:
                continue
    finally:
        driver.quit()

    average_price = sum(prices) / len(prices) if prices else None
    return average_price

# Function to initialize WebDriver
def initialize_webdriver():
    """
    Initialize the Selenium WebDriver with appropriate options.
    """
    chrome_options = Options()
    chrome_options.add_argument(f"--user-data-dir={config['chrome_user_data_dir']}")
    # Specify the profile directory (Default, Profile 1, etc.)
    chrome_options.add_argument(f"--profile-directory={config['chrome_profile_directory']}")  
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--enable-automation")
    chrome_options.add_argument("--remote-debugging-port=9222")  # Enable debugging
    chrome_options.binary_location = config["chrome_binary_location"]
    os.environ["PYTHONWARNINGS"] = "ignore:chromedriver"

    # Debugging prints
    print("User Data Directory:", config['chrome_user_data_dir'])
    print("Profile Directory:", config['chrome_profile_directory'])
    print("Binary Location:", chrome_options.binary_location)

    try:
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
        logging.info("WebDriver initialized successfully with the existing Chrome profile.")
        return driver
    except Exception as e:
        logging.error(f"Error initializing WebDriver: {e}")
        raise

# Function to automate eBay sign-in and listing process using Selenium
def automate_ebay_listing():
    """
    Automate the eBay listing process using Selenium.
    Navigates through eBay's sign-in and listing creation process.
    """
    url_login = "https://signin.ebay.com/"
    url_prelist = "https://ebay.com/sl/prelist"

    driver = initialize_webdriver()

    try:
        # Step 1: Navigate to eBay sign-in page
        driver.get(url_login)
        driver.implicitly_wait(10)

        # Step 1.5: Pause if CAPTCHA is detected
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "captcha_class_name"))  # Replace with actual CAPTCHA element
            )
            print("CAPTCHA detected. Please solve it manually.")
            input("Press Enter after solving the CAPTCHA...")
        except Exception as e:
            print("No CAPTCHA detected, continuing...")

        # Step 2: Enter email and continue
        email_field = driver.find_element(By.ID, "userid")
        email_field.send_keys(config['ebay_email'])
        continue_button = driver.find_element(By.ID, "signin-continue-btn")
        continue_button.click()

        # Step 3: Enter password and sign in
        driver.implicitly_wait(10)
        password_field = driver.find_element(By.ID, "pass")
        password_field.send_keys(config['ebay_password'])
        sign_in_button = driver.find_element(By.ID, "sgnBt")
        sign_in_button.click()

        # Step 4: Navigate to pre-listing page
        driver.get(url_prelist)
        driver.implicitly_wait(10)

        # Step 5: Iterate through image files and create listings
        for filename in os.listdir(config['image_path']):
            if filename.endswith('.jpg') or filename.endswith('.png'):
                full_image_path = os.path.join(config['image_path'], filename)

                # Use the filename (or implement a better product detection logic)
                product_name = filename.split('.')[0]

                # Scrape prices from multiple platforms
                ebay_price = scrape_ebay(product_name)
                amazon_price = scrape_amazon(product_name)
                tcgplayer_price = scrape_tcgplayer(product_name)

                # Calculate the average price from all platforms
                prices = [price for price in [ebay_price, amazon_price, tcgplayer_price] if price is not None]
                average_price = sum(prices) / len(prices) if prices else None

                if average_price:
                    print(f"Average price for {product_name}: ${average_price}")

                # Enter product name
                product_name_field = driver.find_element(By.ID, "s0-1-1-24-7-@keyword-@box-@input-textbox")
                product_name_field.send_keys(product_name)
                search_button = driver.find_element(By.CLASS_NAME, "keyword-suggestion__button")
                search_button.click()

                # Continue without match
                driver.implicitly_wait(10)
                no_match_button = driver.find_element(By.CLASS_NAME, "prelist-radix__next-action")
                no_match_button.click()

                # Select condition
                driver.implicitly_wait(10)
                condition_button = driver.find_element(By.XPATH, "//button[@aria-pressed='true' and contains(@class, 'condition-button__selected')]")
                condition_button.click()

                # Enter detailed title
                driver.implicitly_wait(10)
                title_field = driver.find_element(By.ID, "c1-1-29-1-31[1]-29-1-31[4]-29-1-31[0]-29-1-31[2]-35-6-se-textbox")
                title_field.send_keys(product_name)

                # Add photo
                add_photo_button = driver.find_element(By.CLASS_NAME, "uploader-ui-ux__add-photos")
                add_photo_button.click()

                # Handle file upload dialog (OS-specific)
                driver.execute_script("arguments[0].style.display = 'block';", add_photo_button)
                file_input = driver.find_element(By.TAG_NAME, "input")
                file_input.send_keys(full_image_path)

                print(f"Listing created for {product_name} up to photo upload step successfully.")

    except Exception as e:
        print(f"An error occurred: {e}")

    finally:
        driver.quit()

# Automate the eBay listing
automate_ebay_listing()
