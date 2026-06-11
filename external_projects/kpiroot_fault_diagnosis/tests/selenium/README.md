# Phase 3 Selenium Tests

These tests exercise the Online-Boutique frontend as black-box functional tests.

## Test Cases

- Home page lists products.
- Product detail page for `OLJCESPC7Z` renders `Sunglasses`.
- Product can be added to the cart with quantity `2`.
- Checkout completes and shows confirmation/tracking information.

## Run

Make sure the frontend is available at `http://127.0.0.1:8088`.

```powershell
cd D:\Study\SoftwareTesting
.\FinalProject\.conda\python.exe -m pytest .\FinalProject\tests\selenium -v
```

Useful environment variables:

- `ONLINE_BOUTIQUE_URL`: defaults to `http://127.0.0.1:8088`.
- `SELENIUM_BROWSER`: `edge` by default; `chrome` is also supported.
- `SELENIUM_HEADLESS`: `1` by default. Set to `0` to show the browser.
- `PHASE3_SCREENSHOT_DIR`: defaults to `FinalProject/data/phase3/selenium/screenshots`.
- `SELENIUM_DRIVER_PATH`: optional explicit path to `msedgedriver.exe` or `chromedriver.exe`.
- `SELENIUM_BROWSER_BINARY`: optional explicit path to browser executable.

Example with visible Edge:

```powershell
$env:SELENIUM_BROWSER = "edge"
$env:SELENIUM_HEADLESS = "0"
.\FinalProject\.conda\python.exe -m pytest .\FinalProject\tests\selenium -v
```

Example with explicit Edge driver:

```powershell
$env:SELENIUM_DRIVER_PATH = "D:\tools\msedgedriver.exe"
$env:SELENIUM_BROWSER_BINARY = "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
.\FinalProject\.conda\python.exe -m pytest .\FinalProject\tests\selenium -v
```

The `online_boutique_smoke.side` file can also be opened with Selenium IDE for
manual demonstration, matching the style of lab3.

## Outputs

The runner stores functional screenshots in:

```text
FinalProject/data/phase3/selenium/screenshots/
```

It also stores page-load and interaction-response timing metrics in:

```text
FinalProject/data/phase3/selenium/timing_metrics.csv
```
