from pathlib import Path
from typing import Tuple, Optional
import os, re,io,base64,gzip
import asyncio
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
from readability import Document
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from PIL import Image

# Fix for Microsoft Store Python subprocess issues
if os.name == 'nt':  # Windows
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
 
def _find_edge_exe() -> Optional[str]:
    """Try to locate Edge; override by setting EDGE_PATH."""
    if os.getenv("EDGE_PATH") and Path(os.getenv("EDGE_PATH")).exists():
        return os.getenv("EDGE_PATH")
    candidates = []
    pf = os.environ.get("PROGRAMFILES")
    if pf:    candidates.append(Path(pf) / "Microsoft" / "Edge" / "Application" / "msedge.exe")
    pfx = os.environ.get("PROGRAMFILES(X86)")
    if pfx:   candidates.append(Path(pfx) / "Microsoft" / "Edge" / "Application" / "msedge.exe")
    local = os.environ.get("LOCALAPPDATA")
    if local: candidates.append(Path(local) / "Microsoft" / "Edge" / "Application" / "msedge.exe")
    for c in candidates:
        if c.exists(): return str(c)
    return None
 
def _try_click_common_cookie_buttons(page, timeout_ms=1500) -> bool:
    """
    Try the obvious 'accept' buttons (page + iframes).
    Returns True if something got clicked.
    """
    # Common button texts and multilingual variants (regex, partial match)
    name_patterns = [
        r"accept(\s+all)?", r"accept\s+cookies", r"allow\s+all", r"i\s*agree", r"agree",
        r"got\s*it", r"ok(ay)?", r"continue", r"consent", r"yes[, ]?i\s*agree",
        r"acept(ar|o)(\s+todo|\s+todas)?", r"accepter(\s+tout|\s+les\s+cookies)?",
        r"alle(s)?\s+akzeptieren|zustimmen", r"accetta(\s+tutto|\s+i\s+cookie)?",
        r"aceitar(\s+todos|\s+os\s+cookies)?", r"принять(\s+все)?|согласен",
        r"接受(全部)?|同意|允許|允许", r"同意する|同意して続行",
        r"acceptez?", r"accepteer", r"godta", r"tillåt|tillad", r"hyväksy",
    ]
    negative_words = re.compile(r"reject|decline|deny|manage|settings|custom|preferences|necessary|essential only|only necessary", re.I)
    # Common CMP selectors (OneTrust, Cookiebot, Quantcast, TrustArc, Didomi, Usercentrics)
    css_buttons = [
        "#onetrust-accept-btn-handler",
        "button[aria-label*='Accept']",
        "button[title*='Accept']",
        "#CybotCookiebotDialogBodyButtonAccept",
        "#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll",
        ".qc-cmp2-summary-buttons .qc-cmp2-accept-all",
        ".qc-cmp2-footer .qc-cmp2-accept-all",
        "#truste-consent-button, .trustarc-agree, .truste-button1",
        ".didomi-accept-button, #didomi-notice-agree-button",
        "button[data-testid='uc-accept-all-button']",
    ]
 
    # 1) By accessible role + (partial) name
    for pat in name_patterns:
        try:
            loc = page.get_by_role("button", name=re.compile(pat, re.I))
            if loc.count() > 0 and loc.first.is_visible():
                text = (loc.first.inner_text(timeout=timeout_ms) or "")
                if not negative_words.search(text):
                    loc.first.click(timeout=timeout_ms)
                    page.wait_for_timeout(300)
                    return True
        except Exception:
            pass
        # Fallback: any element containing text
        try:
            loc = page.get_by_text(re.compile(pat, re.I))
            if loc.count() > 0 and loc.first.is_visible():
                text = (loc.first.inner_text(timeout=timeout_ms) or "")
                if not negative_words.search(text):
                    try:
                        loc.first.click(timeout=timeout_ms)
                    except Exception:
                        loc.first.locator("xpath=ancestor-or-self::*[@role='button' or self::button or self::a or @onclick or @tabindex]").first.click(timeout=timeout_ms)
                    page.wait_for_timeout(300)
                    return True
        except Exception:
            pass
 
    # 2) By CSS selectors (page)
    for sel in css_buttons:
        try:
            page.locator(sel).first.click(timeout=timeout_ms)
            page.wait_for_timeout(300)
            return True
        except Exception:
            pass
 
    # 3) Try inside iframes (CMPs often sit in an iframe)
    for frame in page.frames:
        for pat in name_patterns:
            try:
                loc = frame.get_by_role("button", name=re.compile(pat, re.I))
                if loc.count() > 0 and loc.first.is_visible():
                    text = (loc.first.inner_text(timeout=timeout_ms) or "")
                    if not negative_words.search(text):
                        loc.first.click(timeout=timeout_ms)
                        page.wait_for_timeout(300)
                        return True
            except Exception:
                pass
            try:
                loc = frame.get_by_text(re.compile(pat, re.I))
                if loc.count() > 0 and loc.first.is_visible():
                    text = (loc.first.inner_text(timeout=timeout_ms) or "")
                    if not negative_words.search(text):
                        loc.first.click(timeout=timeout_ms)
                        page.wait_for_timeout(300)
                        return True
            except Exception:
                pass
        for sel in css_buttons:
            try:
                frame.locator(sel).first.click(timeout=timeout_ms)
                page.wait_for_timeout(300)
                return True
            except Exception:
                pass
 
    return False
 
def _hide_banner_with_css(page):
    """
    Inject CSS to hide known banner containers as a last resort.
    """
    hide_selectors = [
        "#onetrust-banner-sdk", "#onetrust-consent-sdk", ".ot-sdk-container",
        "#CybotCookiebotDialog", "#CybotCookiebotDialogBody",
        "#qc-cmp2-container", ".qc-cmp2-container",
        "#truste-consent-content", "#truste-consent-banner",
        "#didomi-host", ".didomi-popup", ".didomi-consent-popup",
        "#usercentrics-root", "[data-testid='usercentrics-root']",
        "[id^='sp_message_container_']","[id^='sp_message_iframe_']",
        ".cookie-banner", "#cookie-banner", "#cookie-consent", ".cc-window",
        ".cky-consent-container", ".cookie-consent", ".cookie-consent-container"
    ]
    css = ", ".join(hide_selectors) + " { display: none !important; visibility: hidden !important; opacity: 0 !important; }"
    try:
        page.add_style_tag(content=css)
        # Some banners lock scroll; re-enable
        page.evaluate("document.documentElement.style.overflow='auto'; document.body.style.overflow='auto';")
    except Exception:
        pass
 
def get_screenshot_md(
    url: str,
    # artifacts_dir: str = "artifacts",
    # *,
    viewport: Tuple[int, int] = (1920, 1080),
    full_page: bool = True,
    wait_for_ms: int = 60000,
    timeout_ms: int = 500_000,
    only_main_content: bool = True,
    remove_base64_images: bool = True,
    progress_callback=None,
) -> Tuple[str, str]:
    """
    Open `url` with your installed Microsoft Edge, dismiss/hide cookie banners,
    then save:
      - artifacts/page.md
      - artifacts/screenshot.png
    Returns (markdown_path, screenshot_path).
    """
    # out = Path(artifacts_dir)
    # out.mkdir(parents=True, exist_ok=True)
    # md_path = out / "page_test.md"
    # shot_path = out / "screenshot_test.png"
 
    with sync_playwright() as p:
        # Launch Playwright's Chromium browser (installed via playwright install)
        if progress_callback:
            progress_callback("🚀 Launching Browser", "Starting browser automation...")
        try:
            browser = p.chromium.launch(headless=True)
        except Exception as e:
            raise RuntimeError(f"Failed to launch Chromium browser: {e}")
        # page = browser.new_page(viewport={"width": viewport[0], "height": viewport[1]})


        # Create browser context with English language
        context = browser.new_context(
            viewport={"width": viewport[0], "height": viewport[1]},
            locale="en-US"
        )
        page = context.new_page()
        
        # Set Accept-Language header for English
        page.set_extra_http_headers({
            'Accept-Language': 'en-US,en;q=0.9'
        })

        if progress_callback:
            progress_callback("🌐 Loading Website", "Navigating to the target URL...")
        try:
            page.goto(url, wait_until="networkidle", timeout=timeout_ms)
        except PWTimeout:
            browser.close()
            raise RuntimeError("Navigation timeout. The site may be slow or blocking headless browsers.")

        # Give late assets a moment (mirrors your curl waitFor)
        if progress_callback:
            progress_callback("⏳ Waiting for Content", "Allowing page to fully load...")
        page.wait_for_timeout(wait_for_ms)

        # Try to accept cookies; if not, hide banner containers
        if progress_callback:
            progress_callback("🍪 Handling Cookies", "Dismissing cookie banners and popups...")
        clicked = _try_click_common_cookie_buttons(page, timeout_ms=1500)
        if not clicked:
            _hide_banner_with_css(page)
            # tiny pause to reflow
            page.wait_for_timeout(2000)

        # Now take the screenshot (banner should be gone)
        if progress_callback:
            progress_callback("📸 Taking Screenshot", "Capturing full page screenshot...")
        screenshot = page.screenshot(full_page=full_page) #path=str(shot_path), full_page=full_page)

        # Get rendered HTML for Markdown conversion
        if progress_callback:
            progress_callback("📄 Extracting Content", "Converting HTML to markdown...")
        html = page.content()
        browser.close()
 
    # HTML → Markdown
    source_html = html
    if only_main_content:
        try:
            doc = Document(source_html)
            content_html = doc.summary(html_partial=True)
        except Exception:
            content_html = source_html
    else:
        content_html = source_html
 
    soup = BeautifulSoup(content_html, "lxml")
    for t in soup(["script", "style", "noscript"]):
        t.extract()
 
    if remove_base64_images:
        for img in soup.find_all("img", src=True):
            if img["src"].startswith("data:image/"):
                img.decompose()
 
    markdown = md(str(soup), heading_style="ATX")
    #md_path.write_text(markdown, encoding="utf-8")

    if progress_callback:
        progress_callback("✅ Content Ready", "Screenshot and markdown extraction complete!")

    return screenshot,markdown
 
# Example:
# out = Path("artifacts")
# out.mkdir(parents=True, exist_ok=True)
# md_path = out / "page_test.md"
# shot_path = out / "screenshot_test.png"

# shot_file, md_file = get_screenshot_md("https://www.sky.com")
# md_path.write_text(md_file, encoding="utf-8")

# print(md_file)
# img = Image.open(io.BytesIO(shot_file))
# img.save(shot_path)

