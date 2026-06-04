from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOCAL_LIB = ROOT / ".tools" / "python_lib"
if LOCAL_LIB.exists():
    sys.path.insert(0, str(LOCAL_LIB))

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


BASE_URL = "http://127.0.0.1:8080"
OUT_DIR = ROOT / "outputs_selenium"


def now_ms() -> float:
    return time.perf_counter() * 1000


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    options = Options()
    options.binary_location = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1366,900")
    options.add_argument("--no-sandbox")

    result: dict[str, object] = {"base_url": BASE_URL, "steps": []}
    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 20)
    try:
        t0 = now_ms()
        driver.get(BASE_URL + "/")
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        home_ms = now_ms() - t0
        body_text = driver.find_element(By.TAG_NAME, "body").text
        assert "Online Boutique" in body_text or "Products" in body_text
        driver.save_screenshot(str(OUT_DIR / "selenium_home.png"))
        result["steps"].append({"name": "open_home", "status": "passed", "latency_ms": round(home_ms, 2)})

        product_links = driver.find_elements(By.CSS_SELECTOR, "a[href*='/product/']")
        assert product_links, "No product links found on home page"
        product_href = product_links[0].get_attribute("href")
        t1 = now_ms()
        product_links[0].click()
        wait.until(lambda d: "/product/" in d.current_url)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        product_ms = now_ms() - t1
        driver.save_screenshot(str(OUT_DIR / "selenium_product.png"))
        result["steps"].append(
            {
                "name": "open_product",
                "status": "passed",
                "latency_ms": round(product_ms, 2),
                "product_href": product_href,
                "current_url": driver.current_url,
            }
        )

        t2 = now_ms()
        driver.get(BASE_URL + "/cart")
        wait.until(lambda d: "/cart" in d.current_url)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        cart_ms = now_ms() - t2
        driver.save_screenshot(str(OUT_DIR / "selenium_cart.png"))
        result["steps"].append({"name": "open_cart", "status": "passed", "latency_ms": round(cart_ms, 2)})

        result["status"] = "passed"
    except Exception as exc:
        result["status"] = "failed"
        result["error"] = str(exc)
        driver.save_screenshot(str(OUT_DIR / "selenium_failure.png"))
        raise
    finally:
        driver.quit()
        (OUT_DIR / "selenium_result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
