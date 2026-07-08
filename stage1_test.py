from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    # Launch a browser window (headless=False means you SEE it open)
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()

    # Navigate to a website
    page.goto("https://example.com")

    # Print the page title
    print("Page title:", page.title())

    # Extract all visible text from the page
    print("Page text:", page.inner_text("body"))

    # Wait a few seconds so you can see the browser before it closes
    page.wait_for_timeout(3000)

    browser.close()