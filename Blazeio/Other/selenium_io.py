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
from selenium.common.exceptions import WebDriverException, NoSuchElementException, TimeoutException, ElementNotInteractableException, StaleElementReferenceException, SessionNotCreatedException

class Fetchresponse(io.ddict):
    def json(app):
        return io.loads(app.body)

class _FetchAPI:
    __slots__ = ("instance",)
    def __init__(app, instance):
        app.instance = instance

    def __getattr__(app, method: str):
        async def api(url, *args, **kwargs):
            async with app.instance.__cond__:
                return await app.fetch(url, method.upper(), *args, **kwargs)
        return api

    async def fetch(app, url: str, method: str, headers: (dict, None) = None, body: any = None, json: dict = None):
        if not headers:
            headers = {}

        if json:
            body = io.dumps(json, indent=0)
            headers["content-type"] = "application/json"

        if body:
            if not "content-length" in headers:
                headers["content-length"] = str(len(body))
        
        while True:
            try:
                resp = await io.to_thread(app.instance.execute_script, "const options = { method: '%s', headers: %s, credentials: 'include', mode: 'cors' };\n%s\n\nreturn await fetch('%s', options).then(async response => ({ ok: response.ok, status: response.status, statusText: response.statusText, headers: Object.fromEntries(response.headers.entries()), body: await response.text(), url: response.url }));" % (method, io.dumps(headers or {}, indent=0), ("options.body = %s;" % io.dumps(body, indent=0)) if body else "", url))
                break
            except TimeoutException:
                ...

        return Fetchresponse(resp)

class Chrome(webdriver.Chrome):
    def __init__(app, driver_options: tuple = ("--headless", "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.7339.51 Safari/537.36", "--no-sandbox", "--disable-dev-shm-usage", "--disable-blink-features=AutomationControlled", ("excludeSwitches", ["enable-automation"]), ("useAutomationExtension", False), "--disable-infobars", "--disable-popup-blocking", "--disable-save-password-bubble", "--disable-extensions", "--disable-gpu", "--disable-web-security", "--disable-notifications", "--disable-default-apps", "--disable-translate", "--disable-logging") if io.os_name != "NT" else ("--headless", "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.7339.51 Safari/537.36",), *args, **kwargs):
        app.__dynamic_methods__, app.__driver_args__, app.__driver_kwargs__, app.__driver_options__ = io.ddict(fetch = _FetchAPI), args, kwargs, driver_options
        app.__cond__ = io.ioCondition()

    def __getattr__(app, key, *args):
        if (value := app.__dynamic_methods__.get(key)):
            return value(app)
        return super().__getattr__(key, *args)

    def get_driver_options(app):
        if io.debug_mode:
            options = webdriver.ChromeOptions()
        else:
            options = Options()

        for option in app.__driver_options__:
            if isinstance(option, str):
                options.add_argument(option)
            elif isinstance(option, tuple):
                options.add_experimental_option(option[0], option[1])

        return options
    
    async def __aenter__(app):
        caps = DesiredCapabilities.CHROME
        caps['goog:loggingPrefs'] = {'performance': 'ALL'}

        if io.debug_mode:
            kwargs = io.ddict(options=await io.to_thread(app.get_driver_options), desired_capabilities=caps)
        else:
            kwargs = io.ddict(service=Service(ChromeDriverManager().install()), options=await io.to_thread(app.get_driver_options), desired_capabilities=caps)

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

    async def get(app, *args, **kwargs):
        return await io.to_thread(super().get, *args, **kwargs)

    async def get_request(app, cond):
        for log in await io.to_thread(app.get_log, 'performance'):
                if "Network.requestWillBeSentExtraInfo" in str(log["message"]):
                    log = io.loads(log["message"])
                    if cond(log):
                        return log

if __name__ == "__main__":
    ...
