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

from logging import basicConfig, getLogger, ERROR
from warnings import filterwarnings

basicConfig(level=ERROR)
getLogger('selenium').setLevel(ERROR)
getLogger('urllib3').setLevel(ERROR)
getLogger('chardet').setLevel(ERROR)

filterwarnings("ignore", category=DeprecationWarning)

defaults = io.ddict(
    chrome_options = ("--headless", "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.7339.51 Safari/537.36", "--no-sandbox", "--disable-dev-shm-usage", "--disable-blink-features=AutomationControlled", ("excludeSwitches", ["enable-automation"]), ("excludeSwitches", ["enable-logging"]), ("useAutomationExtension", False), "--disable-infobars", "--disable-popup-blocking", "--disable-save-password-bubble", "--disable-extensions", "--disable-gpu", "--disable-web-security", "--disable-notifications", "--disable-default-apps", "--disable-translate", "--disable-logging", "--disable-renderer-backgrounding", "--disable-images", "--disable-background-timer-throttling", "--disable-backgrounding-occluded-windows", "--aggressive-cache-discard","--memory-pressure-off","--max_old_space_size=100","--disable-features=VizDisplayCompositor","--disable-software-rasterizer","--disable-component-extensions-with-background-pages","--disable-client-side-phishing-detection","--disable-crash-reporter","--disable-ipc-flooding-protection", "--log-level=3", "--disable-http2", "--disable-quic", "--disable-features=UseHttp2", "--enable-features=UseHttp1.1", ("excludeSwitches", ["enable-http2"]), ("prefs", {"profile.managed_default_content_settings.images": 2, "profile.managed_default_content_settings.stylesheets": 2}), "--blink-settings=imagesEnabled=false"),
    desired_capabilities = {'goog:loggingPrefs': {'performance': 'ALL'}, 'pageLoadStrategy': 'eager'}
)

utils = io.ddict(sync = io.ioCondition())

class Fetchresponse(io.ddict):
    def json(app):
        if app.body:
            try:
                return io.loads(app.body)
            except io.JSONDecodeError:
                ...

class _FetchAPI:
    __slots__ = ("instance",)
    def __init__(app, instance):
        app.instance = instance

    def __getattr__(app, method: str):
        def api(url, *args, **kwargs): return app.fetch(url, method.upper(), *args, **kwargs)
        return api

    async def fetch(app, url: str, method: str, headers: (dict, None) = None, body: any = None, json: dict = None, retries: int = 3):
        if not headers:
            headers = {}

        if json:
            body = io.dumps(json, indent=0)
            headers["content-type"] = "application/json"

        if body:
            if not "content-length" in headers:
                headers["content-length"] = str(len(body))

        for i in range(retries):
            try:
                resp = await app.instance.execute_script("const options = { method: '%s', headers: %s, credentials: 'include', mode: 'cors' };\n%s\n\nreturn await fetch('%s', options).then(async response => ({ ok: response.ok, status: response.status, statusText: response.statusText, headers: Object.fromEntries(response.headers.entries()), body: await response.text(), url: response.url }));" % (method, io.dumps(headers or {}, indent=0), ("options.body = %s;" % io.dumps(body, indent=0)) if body else "", url))
                break
            except TimeoutException:
                ...

        return Fetchresponse(resp)

class Chrome(webdriver.Chrome):
    def __init__(app, driver_options: tuple = defaults.chrome_options, desired_capabilities: dict = defaults.desired_capabilities, *args, **kwargs):
        app.__dynamic_methods__, app.__driver_args__, app.__driver_kwargs__, app.__driver_options__, app.__desired_capabilities__ = io.ddict(fetch = _FetchAPI), args, kwargs, driver_options, desired_capabilities

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
        async with utils.sync:
            caps = DesiredCapabilities.CHROME.copy()
            caps.update(app.__desired_capabilities__)
    
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
        await io.to_thread(super().save_screenshot, *args)

    def quit(app):
        return io.to_thread(super().quit)

    def get(app, *args, **kwargs):
        return io.to_thread(super().get, *args, **kwargs)

    def execute_script(app, *args, **kwargs):
        return io.to_thread(super().execute_script, *args, **kwargs)

    def get_log(app, *args, **kwargs):
        return io.to_thread(super().get_log, *args, **kwargs)

    async def get_request(app, cond):
        for log in await app.get_log('performance'):
                if "Network.requestWillBeSentExtraInfo" in str(log["message"]):
                    log = io.loads(log["message"])
                    if cond(log):
                        return log

if __name__ == "__main__":
    ...
