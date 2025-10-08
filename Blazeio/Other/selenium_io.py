# Blazeio.Other.selenium_io
import Blazeio as io

if io.debug_mode:
    from selenium import webdriver
    from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
else:
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from webdriver_manager.chrome import ChromeDriverManager
    from selenium.webdriver.common.desired_capabilities import DesiredCapabilities

from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

class Chrome(webdriver.Chrome):
    def __init__(app, *args, **kwargs):
        app.__driver_args__, app.__driver_kwargs__ = args, kwargs

    async def __aenter__(app):
        caps = DesiredCapabilities.CHROME
        caps['goog:loggingPrefs'] = {'performance': 'ALL'}

        if io.debug_mode:
            kwargs = io.ddict(options=app.get_driver_options(), desired_capabilities=caps)
        else:
            kwargs = io.ddict(service=Service(ChromeDriverManager().install()), options=app.get_driver_options(), desired_capabilities=caps)

        await io.to_thread(super().__init__, *app.__driver_args__, **app.__driver_kwargs__, **kwargs)

        await io.to_thread(app.execute_cdp_cmd, "Page.addScriptToEvaluateOnNewDocument", {
            "source": """
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            """
        })

        return app

    async def __aexit__(app, *args):
        await app.quit()
        return False

    async def save_screenshot(app, *args):
        await io.plog.yellow("saving screenshot...")
        await io.to_thread(super().save_screenshot, *args)
        await io.plog.b_yellow("saved screenshot...")

    async def quit(app):
        await io.to_thread(super().quit)

    def get_driver_options(app):
        if io.debug_mode:
            options = webdriver.ChromeOptions()
        else:
            options = Options()

        options.add_argument("--headless")
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.7339.51 Safari/537.36")

        # return options
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        options.add_argument("--disable-infobars")
        options.add_argument("--disable-popup-blocking")
        options.add_argument("--disable-save-password-bubble")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-gpu")
        
        options.add_argument("--disable-web-security")
        options.add_argument("--disable-notifications")
        options.add_argument("--disable-default-apps")
        options.add_argument("--disable-translate")
        options.add_argument("--disable-logging")
        return options
    
    async def get(app, *args, **kwargs):
        return await io.to_thread(super().get, *args, **kwargs)

    async def browser_fetch(app, url, method='GET', headers=None, data=None):
        script = """
        const options = {
            method: '%s',
            headers: %s,
            credentials: 'include',  // This is key - includes all cookies
            mode: 'cors'
        };
        
        %s  // Add body if provided
        
        return await fetch('%s', options)
            .then(async response => ({
                ok: response.ok,
                status: response.status,
                statusText: response.statusText,
                headers: Object.fromEntries(response.headers.entries()),
                body: await response.text(),
                url: response.url
            }));
        """ % (
            method,
            io.dumps(headers or {}),
            f"options.body = {io.dumps(data, indent=0)};" if data else "",
            url
        )

        return await io.to_thread(app.execute_script, script)

if __name__ == "__main__":
    ...
