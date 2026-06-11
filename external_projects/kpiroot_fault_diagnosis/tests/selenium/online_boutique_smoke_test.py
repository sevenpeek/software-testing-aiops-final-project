from pathlib import Path
from datetime import datetime, timezone
import csv
import os
import time

import pytest
from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait


BASE_URL = os.getenv("ONLINE_BOUTIQUE_URL", "http://127.0.0.1:8088").rstrip("/")
PRODUCT_ID = os.getenv("ONLINE_BOUTIQUE_PRODUCT_ID", "OLJCESPC7Z")
PRODUCT_NAME = os.getenv("ONLINE_BOUTIQUE_PRODUCT_NAME", "Sunglasses")
SCREENSHOT_DIR = Path(
    os.getenv(
        "PHASE3_SCREENSHOT_DIR",
        "FinalProject/data/phase3/selenium/screenshots",
    )
)
METRICS_PATH = Path(
    os.getenv(
        "PHASE3_SELENIUM_METRICS",
        "FinalProject/data/phase3/selenium/timing_metrics.csv",
    )
)


def _init_metrics_file() -> None:
    METRICS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with METRICS_PATH.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["timestamp_utc", "test_case", "metric_name", "metric_type", "value_ms", "details"])


_init_metrics_file()


def _headless_enabled() -> bool:
    return os.getenv("SELENIUM_HEADLESS", "1").lower() not in {"0", "false", "no"}


def _build_driver():
    browser = os.getenv("SELENIUM_BROWSER", "edge").lower()
    driver_path = os.getenv("SELENIUM_DRIVER_PATH", "").strip()
    browser_binary = os.getenv("SELENIUM_BROWSER_BINARY", "").strip()

    if browser == "chrome":
        options = ChromeOptions()
        if browser_binary:
            options.binary_location = browser_binary
        if _headless_enabled():
            options.add_argument("--headless=new")
        options.add_argument("--window-size=1440,1000")
        options.add_argument("--disable-gpu")
        service = ChromeService(executable_path=driver_path) if driver_path else ChromeService()
        return webdriver.Chrome(service=service, options=options)

    if browser == "edge":
        options = EdgeOptions()
        if browser_binary:
            options.binary_location = browser_binary
        if _headless_enabled():
            options.add_argument("--headless=new")
        options.add_argument("--window-size=1440,1000")
        options.add_argument("--disable-gpu")
        service = EdgeService(executable_path=driver_path) if driver_path else EdgeService()
        return webdriver.Edge(service=service, options=options)

    raise ValueError(f"Unsupported SELENIUM_BROWSER={browser!r}; use edge or chrome.")


@pytest.fixture()
def driver():
    try:
        instance = _build_driver()
    except WebDriverException as exc:
        pytest.fail(
            "Failed to start Selenium WebDriver. Make sure Edge/Chrome and its driver "
            f"are available. Details: {exc}"
        )
    yield instance
    instance.quit()


@pytest.fixture()
def wait(driver):
    return WebDriverWait(driver, 20)


def save_screenshot(driver, filename: str) -> None:
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    driver.save_screenshot(str(SCREENSHOT_DIR / filename))


def record_metric(test_case: str, metric_name: str, metric_type: str, value_ms: float, details: str = "") -> None:
    with METRICS_PATH.open("a", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(
            [
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
                test_case,
                metric_name,
                metric_type,
                round(value_ms, 2),
                details,
            ]
        )


def wait_for_page_load(driver, wait) -> None:
    wait.until(lambda active_driver: active_driver.execute_script("return document.readyState") == "complete")


def navigation_duration_ms(driver) -> float:
    duration = driver.execute_script(
        """
        const entries = performance.getEntriesByType('navigation');
        if (entries && entries.length > 0) {
            return entries[0].duration;
        }
        const timing = performance.timing;
        return timing.loadEventEnd - timing.navigationStart;
        """
    )
    return float(duration)


def page_contains(driver, text: str) -> bool:
    try:
        return text in driver.page_source
    except WebDriverException:
        return False


def test_home_page_lists_products(driver, wait):
    driver.get(BASE_URL + "/")
    wait_for_page_load(driver, wait)
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "body")))

    product_links = driver.find_elements(By.CSS_SELECTOR, "a[href*='/product/']")
    assert product_links, "home page should contain product links"
    assert PRODUCT_NAME in driver.page_source
    record_metric(
        "test_home_page_lists_products",
        "home_page_load_ms",
        "page_load",
        navigation_duration_ms(driver),
        BASE_URL + "/",
    )

    save_screenshot(driver, "01_selenium_home_page.png")


def test_product_detail_page(driver, wait):
    driver.get(f"{BASE_URL}/product/{PRODUCT_ID}")
    wait_for_page_load(driver, wait)
    wait.until(EC.text_to_be_present_in_element((By.TAG_NAME, "body"), PRODUCT_NAME))

    add_to_cart = driver.find_element(By.XPATH, "//button[normalize-space()='Add To Cart']")
    quantity = Select(driver.find_element(By.ID, "quantity"))

    assert add_to_cart.is_displayed()
    assert quantity.first_selected_option.get_attribute("value") == "1"
    record_metric(
        "test_product_detail_page",
        "product_detail_page_load_ms",
        "page_load",
        navigation_duration_ms(driver),
        f"{BASE_URL}/product/{PRODUCT_ID}",
    )

    save_screenshot(driver, "02_selenium_product_detail.png")


def test_add_to_cart(driver, wait):
    driver.get(f"{BASE_URL}/product/{PRODUCT_ID}")
    wait_for_page_load(driver, wait)
    wait.until(EC.text_to_be_present_in_element((By.TAG_NAME, "body"), PRODUCT_NAME))

    Select(driver.find_element(By.ID, "quantity")).select_by_visible_text("2")
    started_at = time.perf_counter()
    driver.find_element(By.XPATH, "//button[normalize-space()='Add To Cart']").click()

    wait.until(EC.url_contains("/cart"))
    wait.until(EC.text_to_be_present_in_element((By.TAG_NAME, "body"), "Cart (2)"))
    record_metric(
        "test_add_to_cart",
        "add_to_cart_interaction_ms",
        "interaction",
        (time.perf_counter() - started_at) * 1000,
        "Select quantity 2, click Add To Cart, wait until cart page is ready",
    )

    assert PRODUCT_NAME in driver.page_source
    assert "Place Order" in driver.page_source

    save_screenshot(driver, "03_selenium_cart_with_product.png")


def test_checkout_flow(driver, wait):
    driver.get(f"{BASE_URL}/product/{PRODUCT_ID}")
    wait_for_page_load(driver, wait)
    wait.until(EC.text_to_be_present_in_element((By.TAG_NAME, "body"), PRODUCT_NAME))
    driver.find_element(By.XPATH, "//button[normalize-space()='Add To Cart']").click()

    wait.until(EC.url_contains("/cart"))
    wait.until(EC.text_to_be_present_in_element((By.TAG_NAME, "body"), "Place Order"))
    started_at = time.perf_counter()
    driver.find_element(By.XPATH, "//button[normalize-space()='Place Order']").click()

    wait.until(lambda active_driver: page_contains(active_driver, "Your order is complete!"))
    assert "Confirmation #" in driver.page_source
    assert "Tracking #" in driver.page_source
    record_metric(
        "test_checkout_flow",
        "checkout_submit_interaction_ms",
        "interaction",
        (time.perf_counter() - started_at) * 1000,
        "Click Place Order and wait until confirmation page is ready",
    )

    save_screenshot(driver, "04_selenium_order_complete.png")
