from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()

    # Go to a real search engine
    page.goto("https://duckduckgo.com")

    # Find the search box and type into it
    page.fill("input[name='q']", "AI agents in Python")

    # Press Enter to submit
    page.keyboard.press("Enter")

    # Wait for results to load
    page.wait_for_timeout(2000)

    # Print the page title after search
    print("Page title after search:", page.title())

    page.wait_for_timeout(3000)
    browser.close()