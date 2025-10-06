from playwright.sync_api import sync_playwright, expect

def run_verification():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # The Gradio app runs on this default URL
        page.goto("http://127.0.0.1:7860")

        # Wait for the main title to be visible to ensure the page has loaded
        expect(page.get_by_role("heading", name="Reuniones de trabajo")).to_be_visible(timeout=10000)

        # Find the "Nueva Carpeta" button and the input field
        new_folder_button = page.get_by_role("button", name="➕ Nueva Carpeta")
        new_folder_input = page.get_by_placeholder("Nombre de la carpeta...")

        # Initially, the input field should not be visible
        expect(new_folder_input).not_to_be_visible()

        # Click the button to reveal the input field
        new_folder_button.click()

        # Now, the input field should be visible
        expect(new_folder_input).to_be_visible()

        # Take a screenshot of the page with the visible input field
        page.screenshot(path="jules-scratch/verification/verification_fix.png")

        browser.close()

if __name__ == "__main__":
    run_verification()