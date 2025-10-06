from playwright.sync_api import sync_playwright, expect

def run_verification():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # The Gradio app runs on this default URL
        page.goto("http://127.0.0.1:7860")

        # Wait for the main title to be visible to ensure the page has loaded
        expect(page.get_by_role("heading", name="Reuniones de trabajo")).to_be_visible(timeout=10000)

        # Wait for the sidebar to load its content
        expect(page.locator(".folder-list")).to_contain_text("Contenido", timeout=5000)

        # Take a screenshot of the entire page
        page.screenshot(path="jules-scratch/verification/verification.png")

        browser.close()

if __name__ == "__main__":
    run_verification()