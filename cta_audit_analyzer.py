"""
CTA Audit Analyzer
Real website analysis for call-to-action elements
"""

import asyncio
import os
import re
import base64
import io
import json
import requests
from urllib.parse import urljoin, urlparse
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

# Optional streamlit import
try:
    import streamlit as st
    STREAMLIT_AVAILABLE = True
except ImportError:
    STREAMLIT_AVAILABLE = False
    # Create a mock st object for when streamlit is not available
    class MockStreamlit:
        def warning(self, msg): print(f"WARNING: {msg}")
    st = MockStreamlit()

# Playwright imports
try:
    from playwright.async_api import async_playwright
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    st.warning("Playwright not available. Install with: pip install playwright && playwright install")

@dataclass
class CTAElement:
    """Represents a call-to-action element found on a webpage"""
    element_type: str  # button, link, form, input, dropdown, custom
    text: str
    href: Optional[str] = None
    position: Dict[str, int] = None  # x, y coordinates
    size: Dict[str, int] = None  # width, height
    color: str = None
    background_color: str = None
    font_size: int = None
    is_visible: bool = True
    contrast_ratio: float = None
    urgency_words: List[str] = None
    action_words: List[str] = None
    screenshot: str = None  # Base64 encoded screenshot of the element
    element_id: str = None  # Unique identifier for the element
    css_selector: str = None  # CSS selector to identify the element
    bounding_box: Dict[str, int] = None  # Complete bounding box info
    
    # Enhanced metadata
    html_id: Optional[str] = None  # HTML id attribute
    html_name: Optional[str] = None  # HTML name attribute
    html_class: Optional[str] = None  # HTML class attribute
    html_attributes: Dict[str, str] = None  # All HTML attributes
    parent_element: Optional[str] = None  # Parent element info
    is_hidden: bool = False  # Whether element is hidden
    is_dropdown: bool = False  # Whether element is in dropdown
    is_js_generated: bool = False  # Whether element is JS-generated
    onclick_handler: Optional[str] = None  # onclick attribute
    data_attributes: Dict[str, str] = None  # data-* attributes
    aria_label: Optional[str] = None  # aria-label attribute
    role: Optional[str] = None  # ARIA role
    tabindex: Optional[str] = None  # tabindex attribute
    z_index: Optional[int] = None  # CSS z-index
    computed_styles: Dict[str, str] = None  # Computed CSS styles
    
    # Link validation fields
    link_status: Optional[int] = None  # HTTP status code
    link_is_valid: Optional[bool] = None  # Whether link is valid
    link_error_message: Optional[str] = None  # Error message if link is invalid
    link_redirect_url: Optional[str] = None  # Final redirect URL
    link_response_time: Optional[float] = None  # Response time in seconds
    link_check_timestamp: Optional[str] = None  # When the link was checked

class CTAAuditAnalyzer:
    """Main class for performing CTA audits on websites using Playwright"""
    
    def __init__(self, gemini_api_key: str = None):
        self.urgency_words = [
            'now', 'today', 'immediately', 'urgent', 'limited time', 'expires',
            'hurry', 'act fast', 'don\'t wait', 'last chance', 'exclusive',
            'free', 'instant', 'quick', 'fast', 'easy', 'simple'
        ]
        
        self.action_words = [
            'buy', 'purchase', 'order', 'get', 'download', 'sign up', 'register',
            'subscribe', 'join', 'start', 'begin', 'learn more', 'discover',
            'explore', 'try', 'test', 'demo', 'contact', 'call', 'email',
            'click', 'submit', 'send', 'apply', 'book', 'reserve', 'claim'
        ]
        
        self.cta_selectors = [
            # Standard HTML elements
            'button', 'input[type="submit"]', 'input[type="button"]', 'input[type="reset"]',
            'a[href]', 'area[href]', 'select', 'option',
            
            # CTA-specific classes and IDs
            '.btn', '.button', '.cta', '.call-to-action', '.signup', '.register', 
            '.buy-now', '.download', '.contact-us', '.subscribe', '.join', '.get-started',
            '.learn-more', '.read-more', '.shop-now', '.order-now', '.book-now',
            '.try-now', '.demo', '.trial', '.free-trial', '.start-free', '.get-free',
            
            # Common CTA patterns
            '[class*="btn"]', '[class*="button"]', '[class*="cta"]', '[class*="action"]',
            '[id*="btn"]', '[id*="button"]', '[id*="cta"]', '[id*="action"]',
            '[class*="signup"]', '[class*="register"]', '[class*="buy"]', '[class*="purchase"]',
            '[class*="download"]', '[class*="contact"]', '[class*="subscribe"]',
            
            # Dropdown and menu items
            'li a', 'li button', '.dropdown-item', '.menu-item', '.nav-item',
            '.dropdown-menu a', '.dropdown-menu button', '.menu a', '.menu button',
            
            # Form elements
            'form button', 'form input[type="submit"]', 'form input[type="button"]',
            'fieldset button', 'fieldset input[type="submit"]',
            
            # Custom elements and components
            '[role="button"]', '[role="link"]', '[role="menuitem"]',
            '[tabindex]', '[onclick]', '[data-action]', '[data-toggle]',
            
            # Hidden elements that might be CTAs
            '[style*="display: none"]', '[style*="visibility: hidden"]',
            '[hidden]', '.hidden', '.sr-only', '.visually-hidden',
            
            # JavaScript-generated elements
            '[data-js]', '[data-react]', '[data-vue]', '[data-angular]',
            '.js-button', '.js-link', '.js-cta', '.js-action',
            
            # Accessibility elements
            '[aria-label]', '[aria-labelledby]', '[aria-describedby]',
            '[aria-expanded]', '[aria-haspopup]', '[aria-controls]'
        ]
        
        self.element_counter = 0  # For generating unique element IDs
        self.screenshot_threshold = 50  # Only capture screenshots for first N CTAs
        self.gemini_api_key = gemini_api_key

    def analyze_website(self, url: str, analysis_type: str = "Comprehensive CTA Audit") -> Dict[str, Any]:
        """Perform comprehensive CTA audit on a website using Playwright"""
        
        if not PLAYWRIGHT_AVAILABLE:
            error_msg = "Playwright not available. Please install with: pip install playwright && playwright install"
            return {"error": error_msg}
        
        try:
            # Validate URL
            if not self._is_valid_url(url):
                error_msg = "Invalid URL format"
                return {"error": error_msg}
            
            
            # Use Playwright to analyze the website
            with sync_playwright() as p:
                # Auto-detect headless mode: use headless=True for cloud servers (no display)
                # Auto-detect: headless=True for cloud servers, False for local with display
                is_cloud = False
                try:
                    # Check for common cloud/server indicators
                    if os.getenv("DISPLAY") is None:  # No X display
                        is_cloud = True
                    elif os.getenv("CI") is not None:  # CI/CD environment
                        is_cloud = True
                    elif os.getenv("CLOUD") is not None:  # Cloud environment flag
                        is_cloud = True
                    elif os.path.exists("/.dockerenv"):  # Docker container
                        is_cloud = True
                    elif os.path.exists("/proc/1/cgroup"):  # Docker check
                        try:
                            with open("/proc/1/cgroup", "r") as f:
                                if "docker" in f.read():
                                    is_cloud = True
                        except:
                            pass
                except:
                    # If detection fails, default to headless for safety
                    is_cloud = True
                
                headless = is_cloud
                
                # Optimized stealth args - only essential ones for bot evasion
                launch_args = [
                    '--disable-blink-features=AutomationControlled',  # Essential for bot evasion
                    '--disable-dev-shm-usage',  # Prevents shared memory issues
                    '--no-sandbox',  # Required for some environments
                    '--disable-setuid-sandbox',  # Required for some environments
                ]
                
                # For headless mode (cloud servers), add additional args
                if headless:
                    launch_args.extend([
                        '--headless=new',  # Use new headless mode (better)
                        '--disable-gpu',  # GPU not available in headless
                    ])
                
                try:
                    browser = p.chromium.launch(
                        headless=headless,
                        args=launch_args
                    )
                except Exception as e:
                    error_msg = f"Failed to launch Chromium browser: {e}"
                    print(f"   ❌ ERROR: {error_msg}")
                    return {"error": error_msg}
                
                # Extract domain from URL to determine appropriate timezone/geolocation
                parsed_url = urlparse(url)
                domain = parsed_url.netloc.lower()
                
                # Smart timezone/geolocation based on domain
                if '.co.uk' in domain or '.uk' in domain:
                    timezone_id = "Europe/London"
                    geolocation = {"latitude": 51.5074, "longitude": -0.1278}  # London
                elif '.com.au' in domain or '.au' in domain:
                    timezone_id = "Australia/Sydney"
                    geolocation = {"latitude": -33.8688, "longitude": 151.2093}  # Sydney
                elif '.ca' in domain:
                    timezone_id = "America/Toronto"
                    geolocation = {"latitude": 43.6532, "longitude": -79.3832}  # Toronto
                elif '.de' in domain:
                    timezone_id = "Europe/Berlin"
                    geolocation = {"latitude": 52.5200, "longitude": 13.4050}  # Berlin
                elif '.fr' in domain:
                    timezone_id = "Europe/Paris"
                    geolocation = {"latitude": 48.8566, "longitude": 2.3522}  # Paris
                else:
                    # Default to US (most common)
                    timezone_id = "America/New_York"
                    geolocation = {"latitude": 40.7128, "longitude": -74.0060}  # New York
                
                
                # Create browser context with realistic user agent and settings
                context = browser.new_context(
                    viewport={"width": 1920, "height": 1080},
                    locale="en-US",
                    timezone_id=timezone_id,
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    permissions=["geolocation"],
                    geolocation=geolocation,
                    color_scheme="light",
                )
                page = context.new_page()
                
                # Essential stealth script to avoid bot detection (simplified)
                page.add_init_script("""
                    // Remove webdriver property
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                    
                    // Override the plugins property to mimic real browser
                    Object.defineProperty(navigator, 'plugins', {
                        get: () => [1, 2, 3, 4, 5]
                    });
                    
                    // Override the languages property
                    Object.defineProperty(navigator, 'languages', {
                        get: () => ['en-US', 'en']
                    });
                    
                    // Override the chrome property
                    window.chrome = {
                        runtime: {},
                        loadTimes: function() {},
                        csi: function() {},
                        app: {}
                    };
                    
                    // Override permissions
                    const originalQuery = window.navigator.permissions.query;
                    window.navigator.permissions.query = (parameters) => (
                        parameters.name === 'notifications' ?
                            Promise.resolve({ state: Notification.permission }) :
                            originalQuery(parameters)
                    );
                    
                    // Mock missing properties in headless mode
                    Object.defineProperty(navigator, 'platform', {
                        get: () => 'Win32'
                    });
                    
                    Object.defineProperty(navigator, 'hardwareConcurrency', {
                        get: () => 8
                    });
                    
                    Object.defineProperty(navigator, 'deviceMemory', {
                        get: () => 8
                    });
                    
                    // Override getBattery if it exists
                    if (navigator.getBattery) {
                        navigator.getBattery = () => Promise.resolve({
                            charging: true,
                            chargingTime: 0,
                            dischargingTime: Infinity,
                            level: 1
                        });
                    }
                """)
                
                # Set essential headers (simplified - only what's needed)
                page.set_extra_http_headers({
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                })
                
                # Navigate to the page with better waiting strategy and longer timeouts
                try:
                    # Use "domcontentloaded" first, then wait for networkidle separately
                    # Increased timeout from 30s to 60s
                    page.goto(url, wait_until='domcontentloaded', timeout=60000, referer="https://www.google.com/")
                    
                    # Wait for network to be idle (all resources loaded)
                    try:
                        page.wait_for_load_state("networkidle", timeout=60000)  # Increased from 30s to 60s
                    except:
                        print("   ⚠️  Network idle timeout (continuing anyway)")
                        # Try with domcontentloaded as fallback
                        try:
                            page.wait_for_load_state("domcontentloaded", timeout=15000)
                            page.wait_for_timeout(3000)  # Give extra time for JS
                        except:
                            pass
                    
                    # Wait for load event
                    try:
                        page.wait_for_load_state("load", timeout=30000)  # Increased from 10s to 30s
                    except:
                        print("   ⚠️  Load event timeout (continuing anyway)")
                except Exception as e:
                    # Try fallback navigation strategy
                    try:
                        print("   ⚠️  Primary navigation failed, trying fallback...")
                        page.goto(url, wait_until='load', timeout=90000, referer="https://www.google.com/")
                        page.wait_for_timeout(5000)  # Give extra time for JS execution
                    except Exception as fallback_error:
                        browser.close()
                        error_msg = f"Navigation failed after multiple attempts. The website may be too slow or unreachable. Last error: {str(fallback_error)}"
                        print(f"   ❌ ERROR: {error_msg}")
                        return {"error": error_msg}
                
                
                
                # Handle cookies before scrolling
                try:
                    try:
                        from get_markdown_screenshot import _try_click_common_cookie_buttons, _hide_banner_with_css
                        clicked = _try_click_common_cookie_buttons(page, timeout_ms=1500)
                        if clicked:
                            print("   ✅ Cookie banner accepted")
                        else:
                            _hide_banner_with_css(page)
                            page.wait_for_timeout(1000)
                            print("   ✅ Cookie banner hidden")
                    except ImportError:
                        # Fallback: try basic cookie button clicking
                        print("   ⚠️  Cookie handling module not available, using basic method...")
                        try:
                            accept_buttons = page.locator("button:has-text('Accept'), button:has-text('Agree'), button:has-text('OK')")
                            if accept_buttons.count() > 0:
                                accept_buttons.first.click(timeout=1500)
                                print("   ✅ Cookie banner accepted (basic method)")
                        except:
                            pass
                except Exception as e:
                    print(f"   ⚠️  Cookie handling failed: {e} (continuing anyway)")
                
                # Scroll page to trigger lazy loading and dynamic content
                try:
                    page_height = page.evaluate("document.body.scrollHeight")
                    
                    # Scroll in increments to trigger lazy loading
                    scroll_steps = [0.25, 0.5, 0.75, 1.0, 0.0]  # 25%, 50%, 75%, bottom, top
                    
                    for i, scroll_position in enumerate(scroll_steps, 1):
                        scroll_y = int(page_height * scroll_position)
                        page.evaluate(f"window.scrollTo(0, {scroll_y})")
                        page.wait_for_timeout(800)  # Wait for content to load
                        try:
                            page.wait_for_load_state("networkidle", timeout=5000)  # Increased from 3s to 5s
                        except:
                            pass
                    
                    # Final scroll to top
                    page.evaluate("window.scrollTo(0, 0)")
                    page.wait_for_timeout(1000)
                    
                    # Wait for images to load
                    page.evaluate("""
                        () => Promise.all(
                            Array.from(document.images)
                                .filter(img => !img.complete)
                                .map(img => new Promise((resolve) => {
                                    img.onload = resolve;
                                    img.onerror = resolve;
                                    setTimeout(resolve, 5000);
                                }))
                        )
                    """)
                    
                    # Final network idle wait
                    try:
                        page.wait_for_load_state("networkidle", timeout=10000)  # Increased from 5s to 10s
                    except:
                        # Fallback to domcontentloaded if networkidle fails
                        try:
                            page.wait_for_load_state("domcontentloaded", timeout=5000)
                            page.wait_for_timeout(2000)
                        except:
                            pass
                except Exception as e:
                    print(f"   ⚠️  Scrolling error: {e} (continuing anyway)")
                
                # Find all CTA elements
                cta_elements = self._find_cta_elements_with_playwright(page, url)
                
                # Validate CTA links (this will update the cta_elements with link validation data)
                cta_elements = self._validate_cta_links(cta_elements)
                valid_links = sum(1 for cta in cta_elements if cta.link_is_valid is True)
                broken_links = sum(1 for cta in cta_elements if cta.link_is_valid is False)
                
                # Analyze each CTA element
                analyzed_ctas = self._analyze_cta_elements(cta_elements)
                
                # Generate AI-powered recommendations if API key is available
                ai_recommendations = []
                if self.gemini_api_key:
                    ai_recommendations = self._generate_ai_recommendations(cta_elements, url)
                
                # Generate visual heatmap data
                heatmap_data = self._generate_visual_heatmap_data(cta_elements, analyzed_ctas)
                
                # Generate audit results
                audit_results = self._generate_audit_results(url, analyzed_ctas, analysis_type, ai_recommendations, heatmap_data)
                
                browser.close()

                return audit_results
                
        except Exception as e:
            error_msg = f"Analysis failed: {str(e)}"
            return {"error": error_msg}

    def _is_valid_url(self, url: str) -> bool:
        """Validate URL format"""
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except:
            return False

    def _capture_element_screenshot(self, page, element, element_id: str) -> str:
        """Capture a screenshot of a specific CTA element"""
        try:
            # Get the bounding box of the element
            box = element.bounding_box()
            if not box:
                return None
            
            # Add some padding around the element for better visibility
            padding = 10
            x = max(0, int(box['x'] - padding))
            y = max(0, int(box['y'] - padding))
            width = int(box['width'] + (padding * 2))
            height = int(box['height'] + (padding * 2))
            
            # Take a screenshot of the specific area
            screenshot_bytes = page.screenshot(
                clip={'x': x, 'y': y, 'width': width, 'height': height}
            )
            
            # Convert to base64 for storage
            screenshot_b64 = base64.b64encode(screenshot_bytes).decode('utf-8')
            return screenshot_b64
            
        except Exception as e:
            print(f"Error capturing screenshot for element {element_id}: {str(e)}")
            return None

    def _determine_element_type(self, element_data: Dict[str, Any]) -> str:
        """Determine the element type based on element data"""
        tag_name = element_data['tagName']
        
        if tag_name in ['button', 'input']:
            return 'button'
        elif tag_name == 'a':
            return 'link'
        elif tag_name in ['select', 'option']:
            return 'dropdown'
        elif tag_name == 'form':
            return 'form'
        elif tag_name == 'area':
            return 'area'
        elif element_data['role']:
            return element_data['role']
        else:
            return 'custom'
    
    def _is_js_generated(self, element_data: Dict[str, Any]) -> bool:
        """Check if element is likely JavaScript-generated"""
        return (
            element_data['onclick'] or
            any(key in element_data['dataAttributes'] for key in ['data-js', 'data-react', 'data-vue', 'data-angular']) or
            any(cls in element_data['className'] for cls in ['js-', 'react-', 'vue-', 'angular-']) or
            element_data['tagName'] in ['div', 'span'] and element_data['role'] in ['button', 'link']
        )
    
    def _generate_selector_from_data(self, element_data: Dict[str, Any]) -> str:
        """Generate CSS selector from element data"""
        try:
            # Try ID first
            if element_data['id']:
                return f"#{element_data['id']}"
            
            # Try classes
            if element_data['className']:
                classes = element_data['className'].strip().split()
                if classes:
                    return f".{'.'.join(classes[:2])}"
            
            # Try role
            if element_data['role']:
                return f"[role='{element_data['role']}']"
            
            # Try data attributes
            if element_data['dataAttributes']:
                for key, value in element_data['dataAttributes'].items():
                    if key in ['data-testid', 'data-cy', 'data-qa']:
                        return f"[{key}='{value}']"
            
            # Fall back to tag name
            return element_data['tagName']
            
        except:
            return "unknown"

    def _generate_element_selector(self, element) -> str:
        """Generate a CSS selector for the element (legacy method)"""
        try:
            # Try to get a unique identifier
            element_id = element.get_attribute('id')
            if element_id:
                return f"#{element_id}"
            
            # Try class names
            class_names = element.get_attribute('class')
            if class_names:
                classes = class_names.strip().split()
                if classes:
                    return f".{'.'.join(classes[:2])}"  # Use first two classes
            
            # Fall back to tag name with position
            tag_name = element.evaluate('el => el.tagName.toLowerCase()')
            parent = element.evaluate('el => el.parentElement')
            if parent:
                siblings = parent.evaluate('el => Array.from(el.children)')
                index = siblings.index(element) if element in siblings else 0
                return f"{tag_name}:nth-child({index + 1})"
            
            return tag_name
            
        except:
            return "unknown"

    def _generate_ai_recommendations(self, cta_elements: List[CTAElement], url: str) -> List[str]:
        """Generate AI-powered recommendations using Gemini API"""
        if not self.gemini_api_key:
            return []
        
        try:
            # Prepare CTA data for AI analysis
            cta_data = []
            for cta in cta_elements:
                cta_data.append({
                    'text': cta.text,
                    'type': cta.element_type,
                    'position': cta.position,
                    'size': cta.size,
                    'href': cta.href
                })
            
            # Create prompt for AI analysis
            prompt = f"""
            Analyze these Call-to-Action (CTA) elements from the website {url} and provide 5 specific, actionable recommendations to improve conversion rates:
            
            CTA Elements Found:
            {json.dumps(cta_data, indent=2)}
            
            Please provide recommendations that are:
            1. Specific and actionable
            2. Based on conversion optimization best practices
            3. Tailored to the specific CTAs found
            4. Include specific suggestions for text, positioning, or styling improvements
            
            Format as a numbered list of recommendations.
            """
            
            # Call Gemini API
            headers = {
                'Content-Type': 'application/json',
            }
            
            data = {
                "contents": [{
                    "parts": [{"text": prompt}]
                }],
                "generationConfig": {
                    "temperature": 0.7,
                    "topK": 40,
                    "topP": 0.95,
                    "maxOutputTokens": 1024,
                }
            }
            
            response = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={self.gemini_api_key}",
                headers=headers,
                json=data,
                timeout=60  # Increased from 30s to 60s for slower API responses
            )
            
            if response.status_code == 200:
                result = response.json()
                if 'candidates' in result and len(result['candidates']) > 0:
                    ai_text = result['candidates'][0]['content']['parts'][0]['text']
                    # Parse the AI response into individual recommendations
                    recommendations = []
                    lines = ai_text.split('\n')
                    for line in lines:
                        line = line.strip()
                        if line and (line[0].isdigit() or line.startswith('•') or line.startswith('-') or line.startswith('*')):
                            # Clean up the recommendation text
                            clean_line = re.sub(r'^\d+\.\s*', '', line)  # Remove numbers
                            clean_line = re.sub(r'^[•\-*]\s*', '', clean_line)  # Remove bullets
                            if clean_line:
                                recommendations.append(clean_line)
                    return recommendations[:5]  # Return top 5 recommendations
            
        except requests.exceptions.Timeout:
            print(f"      ⚠️  AI recommendations timeout (request took >30s)")
        except requests.exceptions.RequestException as e:
            print(f"      ⚠️  AI recommendations request failed: {str(e)}")
        except Exception as e:
            print(f"      ⚠️  Error generating AI recommendations: {str(e)}")
        
        return []

    def _generate_visual_heatmap_data(self, cta_elements: List[CTAElement], analyzed_ctas: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Generate data for visual heatmap of CTA elements with issue information"""
        heatmap_data = {
            'cta_positions': [],
            'cta_scores': [],
            'cta_texts': [],
            'cta_types': [],
            'cta_issues': [],
            'cta_severity': [],
            'cta_element_ids': []
        }
        
        # Create a mapping of element_id to issues for quick lookup
        issues_by_element = {}
        if analyzed_ctas:
            for cta_analysis in analyzed_ctas:
                element_id = cta_analysis['element'].element_id
                issues = cta_analysis.get('issues', [])
                issues_by_element[element_id] = issues
        
        for cta in cta_elements:
            if cta.position and cta.size:
                # Calculate center point for heatmap
                center_x = cta.position['x'] + (cta.size['width'] / 2)
                center_y = cta.position['y'] + (cta.size['height'] / 2)
                
                # Get issues for this CTA
                cta_issues = issues_by_element.get(cta.element_id, [])
                issue_types = [issue.get('type', '') for issue in cta_issues]
                severities = [issue.get('severity', '') for issue in cta_issues]
                
                # Determine overall severity (highest priority)
                overall_severity = 'None'
                if 'High' in severities:
                    overall_severity = 'High'
                elif 'Medium' in severities:
                    overall_severity = 'Medium'
                elif 'Low' in severities:
                    overall_severity = 'Low'
                
                heatmap_data['cta_positions'].append([center_x, center_y])
                heatmap_data['cta_scores'].append(80)  # Default score for visualization
                heatmap_data['cta_texts'].append(cta.text[:30] + "..." if len(cta.text) > 30 else cta.text)
                heatmap_data['cta_types'].append(cta.element_type)
                heatmap_data['cta_issues'].append(', '.join(issue_types) if issue_types else 'None')
                heatmap_data['cta_severity'].append(overall_severity)
                heatmap_data['cta_element_ids'].append(cta.element_id)
        
        return heatmap_data

    def _find_cta_elements_with_playwright(self, page, base_url: str) -> List[CTAElement]:
        """Find ALL potential CTA elements using comprehensive Playwright analysis"""
        cta_elements = []
        
        try:
            # Wait for page to fully load and execute JavaScript
            try:
                page.wait_for_load_state('networkidle', timeout=30000)
            except:
                # If networkidle times out, try domcontentloaded
                try:
                    page.wait_for_load_state('domcontentloaded', timeout=15000)
                    page.wait_for_timeout(2000)  # Give extra time for JS
                except:
                    # Last resort: just wait for load
                    page.wait_for_load_state('load', timeout=10000)
                    page.wait_for_timeout(3000)
            
            # Execute JavaScript to find all possible CTA elements
            all_elements = page.evaluate("""
                () => {
                    const elements = [];
                    const allElements = document.querySelectorAll('*');
                    
                    allElements.forEach((el, index) => {
                        const tagName = el.tagName.toLowerCase();
                        const text = (el.innerText || el.textContent || el.value || '').trim();
                        const className = el.className || '';
                        const id = el.id || '';
                        const href = el.href || '';
                        const onclick = el.onclick ? el.onclick.toString() : '';
                        const role = el.getAttribute('role') || '';
                        const ariaLabel = el.getAttribute('aria-label') || '';
                        const tabIndex = el.getAttribute('tabindex') || '';
                        const dataAttributes = {};
                        
                        // Collect all data-* attributes
                        Array.from(el.attributes).forEach(attr => {
                            if (attr.name.startsWith('data-')) {
                                dataAttributes[attr.name] = attr.value;
                            }
                        });
                        
                        // Check if element is a potential CTA
                        const isPotentialCTA = (
                            // Standard interactive elements
                            ['button', 'a', 'input', 'select', 'option', 'area'].includes(tagName) ||
                            // Elements with CTA-like classes
                            /btn|button|cta|action|signup|register|buy|purchase|download|contact|subscribe|join|get-started|learn-more|read-more|shop-now|order-now|book-now|try-now|demo|trial|free-trial|start-free|get-free/i.test(className) ||
                            // Elements with CTA-like IDs
                            /btn|button|cta|action|signup|register|buy|purchase|download|contact|subscribe|join|get-started|learn-more|read-more|shop-now|order-now|book-now|try-now|demo|trial|free-trial|start-free|get-free/i.test(id) ||
                            // Elements with action words in text
                            /buy|purchase|order|get|download|sign up|register|subscribe|join|start|begin|learn more|discover|explore|try|test|demo|contact|call|email|click|submit|send|apply|book|reserve|claim|now|today|immediately|urgent|limited time|expires|hurry|act fast|don't wait|last chance|exclusive|free|instant|quick|fast|easy|simple/i.test(text) ||
                            // Elements with CTA-like hrefs
                            /signup|register|buy|purchase|download|contact|subscribe|join|get-started|learn-more|read-more|shop-now|order-now|book-now|try-now|demo|trial|free-trial|start-free|get-free/i.test(href) ||
                            // Elements with onclick handlers
                            onclick.length > 0 ||
                            // Elements with specific roles
                            ['button', 'link', 'menuitem'].includes(role) ||
                            // Elements with tabindex (interactive)
                            tabIndex !== '' ||
                            // Elements with aria-label containing action words
                            /buy|purchase|order|get|download|sign up|register|subscribe|join|start|begin|learn more|discover|explore|try|test|demo|contact|call|email|click|submit|send|apply|book|reserve|claim/i.test(ariaLabel) ||
                            // Elements with data attributes indicating CTAs
                            Object.keys(dataAttributes).some(key => /action|toggle|target|cta|button/i.test(key))
                        );
                        
                        if (isPotentialCTA) {
                            const rect = el.getBoundingClientRect();
                            const computedStyle = window.getComputedStyle(el);
                            
                            elements.push({
                                index: index,
                                tagName: tagName,
                                text: text,
                                className: className,
                                id: id,
                                href: href,
                                onclick: onclick,
                                role: role,
                                ariaLabel: ariaLabel,
                                tabIndex: tabIndex,
                                dataAttributes: dataAttributes,
                                rect: {
                                    x: rect.x,
                                    y: rect.y,
                                    width: rect.width,
                                    height: rect.height,
                                    top: rect.top,
                                    left: rect.left,
                                    bottom: rect.bottom,
                                    right: rect.right
                                },
                                isVisible: rect.width > 0 && rect.height > 0 && computedStyle.display !== 'none' && computedStyle.visibility !== 'hidden',
                                isHidden: computedStyle.display === 'none' || computedStyle.visibility === 'hidden' || el.hidden,
                                zIndex: computedStyle.zIndex !== 'auto' ? parseInt(computedStyle.zIndex) : null,
                                parentElement: el.parentElement ? el.parentElement.tagName.toLowerCase() : null,
                                isInDropdown: el.closest('.dropdown, .dropdown-menu, .menu, .nav-menu, [role="menu"], [role="menubar"]') !== null,
                                computedStyles: {
                                    display: computedStyle.display,
                                    visibility: computedStyle.visibility,
                                    position: computedStyle.position,
                                    backgroundColor: computedStyle.backgroundColor,
                                    color: computedStyle.color,
                                    fontSize: computedStyle.fontSize,
                                    fontWeight: computedStyle.fontWeight,
                                    textAlign: computedStyle.textAlign,
                                    cursor: computedStyle.cursor
                                }
                            });
                        }
                    });
                    
                    return elements;
                }
            """)            
            # Process each found element
            for element_data in all_elements:
                try:
                    self.element_counter += 1
                    element_id = f"cta_{self.element_counter}"                    
                    # Determine element type
                    element_type = self._determine_element_type(element_data)
                    
                    # Extract text content
                    text = element_data['text'] or element_data['ariaLabel'] or ''
                    
                    # Get href or action - filter out JavaScript code
                    href = element_data['href'] or None
                    onclick = element_data['onclick'] or None
                    
                    # Only use onclick if href is not available and onclick looks like a URL
                    if not href and onclick:
                        # Check if onclick contains a URL pattern (not just JS code)
                        if re.search(r'https?://|window\.location|location\.href', onclick):
                            # Extract URL from onclick if possible
                            url_match = re.search(r'(https?://[^\s\'"]+)', onclick)
                            if url_match:
                                href = url_match.group(1)
                        # Otherwise, don't use onclick as href (it's JS code, not a URL)
                    
                    # Clean and validate href
                    if href:
                        # Remove JavaScript function calls and invalid patterns
                        href = href.strip()
                        
                        # Skip if it's clearly JavaScript code
                        if not self._is_valid_url_pattern(href):
                            # Invalid URL pattern (likely JS code), set to None
                            href = None
                        elif not href.startswith(('http', 'javascript:', 'mailto:', 'tel:', '#')):
                            # Convert relative URLs to absolute
                            if href.startswith('/'):
                                # Keep as relative, will be handled in validation
                                pass
                            else:
                                href = urljoin(base_url, href)
                    
                    # Create position and size data
                    rect = element_data['rect']
                    position = {'x': int(rect['x']), 'y': int(rect['y'])}
                    size = {'width': int(rect['width']), 'height': int(rect['height'])}
                    bounding_box = {
                        'x': int(rect['left']),
                        'y': int(rect['top']),
                        'width': int(rect['width']),
                        'height': int(rect['height'])
                    }
                    
                    # Capture screenshot only for first N CTAs to reduce data size
                    screenshot = None
                    if element_data['isVisible'] and self.element_counter <= self.screenshot_threshold:
                        try:
                            # Use Playwright to find and screenshot the element
                            selector = self._generate_selector_from_data(element_data)
                            element = page.query_selector(selector)
                            if element:
                                screenshot = self._capture_element_screenshot(page, element, element_id)
                        except:
                            pass
                        
                        # Generate CSS selector
                    css_selector = self._generate_selector_from_data(element_data)
                    
                    # Extract HTML attributes
                    html_attributes = {
                        'class': element_data['className'],
                        'id': element_data['id'],
                        'onclick': element_data['onclick'],
                        'role': element_data['role'],
                        'aria-label': element_data['ariaLabel'],
                        'tabindex': element_data['tabIndex']
                    }
                    
                    # Create enhanced CTA element (trimmed for performance)
                    # Only store essential computed styles, not all
                    essential_styles = {}
                    if element_data.get('computedStyles'):
                        # Only keep essential style properties
                        essential_props = ['color', 'backgroundColor', 'fontSize', 'fontWeight', 'display', 'visibility']
                        for prop in essential_props:
                            if prop in element_data['computedStyles']:
                                essential_styles[prop] = element_data['computedStyles'][prop]
                    
                    # Trim HTML attributes - only keep essential ones
                    essential_attrs = {
                        'class': element_data['className'],
                        'id': element_data['id'],
                        'role': element_data['role'],
                        'aria-label': element_data['ariaLabel']
                    }
                    
                    cta = CTAElement(
                        element_type=element_type,
                        text=text,
                        href=href,
                        position=position,
                        size=size,
                        screenshot=screenshot,  # Only for first N CTAs
                        element_id=element_id,
                        css_selector=css_selector,
                        bounding_box=bounding_box,
                        
                        # Enhanced metadata (trimmed)
                        html_id=element_data['id'] or None,
                        html_class=element_data['className'] or None,
                        html_attributes=essential_attrs,  # Reduced attributes
                        is_hidden=element_data['isHidden'],
                        is_dropdown=element_data['isInDropdown'],
                        is_js_generated=self._is_js_generated(element_data),
                        onclick_handler=element_data['onclick'] or None,
                        aria_label=element_data['ariaLabel'] or None,
                        role=element_data['role'] or None,
                        computed_styles=essential_styles if essential_styles else None,  # Only essential styles
                        is_visible=element_data['isVisible']
                    )
                    
                    cta_elements.append(cta)
                    
                except Exception as e:
                    continue 
                    
        except Exception as e:
            error_msg = f"Error finding CTA elements: {str(e)}"
            if STREAMLIT_AVAILABLE:
                st.warning(error_msg)
        
        return cta_elements

    def _analyze_cta_elements(self, cta_elements: List[CTAElement]) -> List[Dict[str, Any]]:
        """Analyze CTA elements for various quality metrics using industry best practices"""
        analyzed = []
        
        for cta in cta_elements:
            analysis = {
                'element': cta,
                'text_analysis': self._analyze_text(cta.text),
                'visibility_score': self._calculate_visibility_score(cta),
                'urgency_score': self._calculate_urgency_score(cta.text),
                'action_clarity': self._calculate_action_clarity(cta.text),
                'accessibility_score': self._calculate_accessibility_score(cta),
                'mobile_responsiveness_score': self._calculate_mobile_responsiveness_score(cta),
                'color_contrast_score': self._calculate_color_contrast_score(cta),
                'conversion_optimization_score': self._calculate_conversion_optimization_score(cta),
                'link_validity_score': self._calculate_link_validity_score(cta),
                'issues': [],
                'recommendations': []
            }
            
            # Calculate overall score with weighted metrics
            analysis['overall_score'] = self._calculate_weighted_overall_score(analysis)
            
            # Identify issues
            self._identify_issues(analysis)
            
            # Generate recommendations
            self._generate_recommendations(analysis)
            
            analyzed.append(analysis)
        
        return analyzed

    def _calculate_weighted_overall_score(self, analysis: Dict[str, Any]) -> int:
        """Calculate weighted overall score based on industry importance"""
        # Weighted scoring based on conversion impact
        weights = {
            'conversion_optimization_score': 0.22,  # Most important for business
            'action_clarity': 0.18,  # Critical for user understanding
            'urgency_score': 0.13,   # Important for conversion
            'visibility_score': 0.13, # Important for user attention
            'accessibility_score': 0.13, # Important for compliance and usability
            'link_validity_score': 0.13, # Critical for functionality
            'mobile_responsiveness_score': 0.08, # Important for mobile users
        }
        
        weighted_score = 0
        for metric, weight in weights.items():
            if metric in analysis:
                weighted_score += analysis[metric] * weight
        
        return int(weighted_score)

    def _analyze_text(self, text: str) -> Dict[str, Any]:
        """Analyze CTA text for quality indicators"""
        text_lower = text.lower()
        
        return {
            'length': len(text),
            'has_action_word': any(word in text_lower for word in self.action_words),
            'has_urgency_word': any(word in text_lower for word in self.urgency_words),
            'is_generic': text_lower in ['click here', 'read more', 'learn more', 'more info'],
            'has_benefit': any(word in text_lower for word in ['free', 'save', 'get', 'win', 'earn']),
            'is_negative': any(word in text_lower for word in ['don\'t', 'avoid', 'stop', 'no'])
        }

    def _calculate_visibility_score(self, cta: CTAElement) -> int:
        """Calculate visibility score (0-100) based on industry best practices"""
        score = 0  # Start from 0 for more precise scoring
        
        # Position scoring (above the fold is crucial)
        if cta.position and cta.position['y'] < 600:  # Above the fold
            score += 25
        elif cta.position and cta.position['y'] < 1200:  # Near the fold
            score += 15
        else:
            score += 5  # Below the fold
        
        # Size scoring (industry standards: minimum 44x44px for touch targets)
        if cta.size:
            min_size = 44
            if cta.size['width'] >= min_size and cta.size['height'] >= min_size:
                score += 20
            elif cta.size['width'] >= 32 and cta.size['height'] >= 32:
                score += 10
            else:
                score -= 10  # Too small for good usability
        
        # Text length factor (optimal range: 2-5 words)
        word_count = len(cta.text.split()) if cta.text else 0
        if 2 <= word_count <= 5:
            score += 20
        elif word_count == 1:
            score += 15
        elif 6 <= word_count <= 8:
            score += 10
        else:
            score -= 5
        
        # Element type factor (buttons are most effective)
        if cta.element_type == 'button':
            score += 20
        elif cta.element_type == 'form':
            score += 15
        elif cta.element_type == 'link':
            score += 10
        else:
            score += 5
        
        # Z-index and layering (higher z-index = more prominent)
        if cta.z_index and cta.z_index > 0:
            score += 10
        
        # Visibility status
        if cta.is_visible and not cta.is_hidden:
            score += 15
        else:
            score -= 20
        
        return min(100, max(0, score))

    def _calculate_urgency_score(self, text: str) -> int:
        """Calculate urgency score based on industry best practices"""
        text_lower = text.lower()
        score = 0
        
        # High-impact urgency words (scarcity, time-sensitive)
        high_urgency_words = ['now', 'today', 'immediately', 'urgent', 'limited time', 'expires', 
                             'hurry', 'act fast', 'don\'t wait', 'last chance', 'exclusive', 
                             'only', 'few left', 'while supplies last', 'today only']
        high_urgency_count = sum(1 for word in high_urgency_words if word in text_lower)
        score += high_urgency_count * 20
        
        # Medium-impact urgency words
        medium_urgency_words = ['free', 'instant', 'quick', 'fast', 'easy', 'simple', 'get started']
        medium_urgency_count = sum(1 for word in medium_urgency_words if word in text_lower)
        score += medium_urgency_count * 12
        
        # Action words (conversion-focused)
        action_count = sum(1 for word in self.action_words if word in text_lower)
        score += action_count * 8
        
        # Bonus for multiple urgency indicators
        total_urgency_indicators = high_urgency_count + medium_urgency_count + action_count
        if total_urgency_indicators >= 3:
            score += 15  # Bonus for multiple indicators
        elif total_urgency_indicators >= 2:
            score += 8
        
        # Penalty for negative or passive language
        negative_words = ['maybe', 'perhaps', 'consider', 'think about', 'might want to']
        if any(word in text_lower for word in negative_words):
            score -= 15
        
        return min(100, max(0, score))

    def _calculate_action_clarity(self, text: str) -> int:
        """Calculate action clarity based on conversion optimization best practices"""
        text_lower = text.lower()
        
        if not text_lower:
            return 0
        
        score = 0
        
        # Primary action words (high conversion impact)
        primary_actions = ['buy', 'purchase', 'order', 'get', 'download', 'sign up', 'register', 
                          'subscribe', 'join', 'start', 'begin', 'try', 'test', 'demo', 'contact']
        primary_count = sum(1 for word in primary_actions if word in text_lower)
        score += primary_count * 25
        
        # Secondary action words
        secondary_actions = ['learn more', 'discover', 'explore', 'read more', 'view', 'see', 'find out']
        secondary_count = sum(1 for word in secondary_actions if word in text_lower)
        score += secondary_count * 15
        
        # Generic text penalties (industry best practice: avoid generic CTAs)
        generic_penalties = {
            'click here': -40,
            'read more': -30,
            'learn more': -25,
            'more info': -20,
            'here': -35,
            'this': -30
        }
        
        for generic_text, penalty in generic_penalties.items():
            if generic_text in text_lower:
                score += penalty
                break  # Only apply the highest penalty
        
        # Benefit/value proposition bonus
        benefit_words = ['free', 'save', 'get', 'win', 'earn', 'discount', 'off', 'deal', 'offer']
        benefit_count = sum(1 for word in benefit_words if word in text_lower)
        score += benefit_count * 12
        
        # Specificity bonus (specific actions are clearer)
        specific_indicators = ['now', 'today', 'instantly', 'in 30 seconds', 'step by step']
        if any(indicator in text_lower for indicator in specific_indicators):
            score += 15
        
        # Length optimization (2-5 words is optimal)
        word_count = len(text.split())
        if 2 <= word_count <= 5:
            score += 10
        elif word_count == 1:
            score += 5
        elif word_count > 8:
            score -= 10  # Too wordy reduces clarity
        
        # Question format penalty (CTAs should be commands, not questions)
        if text_lower.endswith('?'):
            score -= 20
        
        return min(100, max(0, score))

    def _calculate_accessibility_score(self, cta: CTAElement) -> int:
        """Calculate accessibility score based on WCAG 2.1 AA standards"""
        score = 0
        
        # Text content requirements (WCAG 2.1 AA)
        if not cta.text or cta.text.strip() == "":
            if cta.aria_label:
                score += 20  # Has accessible alternative text
            else:
                score -= 40  # No accessible text at all
        else:
            score += 25  # Has visible text
        
        # Text length optimization (3-50 characters is ideal)
        text_length = len(cta.text) if cta.text else 0
        if 3 <= text_length <= 50:
            score += 20
        elif text_length < 3:
            score -= 15
        elif text_length > 50:
            score -= 10
        
        # ARIA attributes (WCAG compliance)
        if cta.aria_label:
            score += 15
        if cta.role in ['button', 'link', 'menuitem']:
            score += 15
        if cta.tabindex and cta.tabindex != '-1':
            score += 10
        
        # Keyboard accessibility
        if cta.element_type in ['button', 'a'] or (cta.tabindex and cta.tabindex != '-1'):
            score += 20
        elif cta.onclick_handler and not cta.tabindex:
            score -= 20  # Interactive but not keyboard accessible
        
        # Size requirements (WCAG: minimum 44x44px for touch targets)
        if cta.size:
            min_size = 44
            if cta.size['width'] >= min_size and cta.size['height'] >= min_size:
                score += 20
            elif cta.size['width'] >= 32 and cta.size['height'] >= 32:
                score += 10
            else:
                score -= 15  # Too small for accessibility
        
        # Visibility requirements
        if cta.is_visible and not cta.is_hidden:
            score += 15
        else:
            score -= 25  # Hidden elements are not accessible
        
        # Focus indicators (basic check)
        if cta.element_type in ['button', 'a', 'input']:
            score += 10  # Native elements have built-in focus indicators
        
        # Screen reader compatibility
        if cta.element_type == 'link' and not cta.text and not cta.aria_label:
            score -= 30  # Links without accessible text
        
        return min(100, max(0, score))

    def _calculate_mobile_responsiveness_score(self, cta: CTAElement) -> int:
        """Calculate mobile responsiveness score based on industry standards"""
        score = 0
        
        # Size requirements for mobile (minimum 44x44px touch target)
        if cta.size:
            min_touch_size = 44
            if cta.size['width'] >= min_touch_size and cta.size['height'] >= min_touch_size:
                score += 30
            elif cta.size['width'] >= 32 and cta.size['height'] >= 32:
                score += 20
            else:
                score -= 20  # Too small for mobile
        
        # Text length optimization for mobile (shorter is better)
        if cta.text:
            word_count = len(cta.text.split())
            if word_count <= 3:
                score += 25
            elif word_count <= 5:
                score += 20
            elif word_count <= 8:
                score += 10
            else:
                score -= 10  # Too long for mobile screens
        
        # Element type suitability for mobile
        if cta.element_type == 'button':
            score += 25  # Buttons are most mobile-friendly
        elif cta.element_type == 'link':
            score += 15
        elif cta.element_type == 'form':
            score += 10
        
        # Touch-friendly attributes
        if cta.tabindex and cta.tabindex != '-1':
            score += 15  # Keyboard accessible
        
        # Avoid dropdowns on mobile (unless necessary)
        if cta.is_dropdown:
            score -= 10  # Dropdowns can be problematic on mobile
        
        return min(100, max(0, score))

    def _calculate_color_contrast_score(self, cta: CTAElement) -> int:
        """Calculate color contrast score (simplified version)"""
        score = 50  # Base score
        
        # This is a simplified version - in a real implementation, 
        # you would need to extract actual color values and calculate contrast ratios
        # For now, we'll use heuristics based on common patterns
        
        # Check if element has computed styles
        if cta.computed_styles:
            bg_color = cta.computed_styles.get('backgroundColor', '')
            text_color = cta.computed_styles.get('color', '')
            
            # Basic checks for high contrast indicators
            if 'rgb(255, 255, 255)' in text_color and 'rgb(0, 0, 0)' in bg_color:
                score += 30  # High contrast
            elif 'rgb(0, 0, 0)' in text_color and 'rgb(255, 255, 255)' in bg_color:
                score += 30  # High contrast
            elif 'rgb(255, 255, 255)' in text_color or 'rgb(0, 0, 0)' in text_color:
                score += 15  # At least one high contrast color
            else:
                score -= 10  # May have low contrast
        
        # Check for common high-contrast color combinations
        if cta.html_class:
            class_lower = cta.html_class.lower()
            if any(color in class_lower for color in ['white', 'black', 'primary', 'secondary']):
                score += 10
        
        return min(100, max(0, score))

    def _calculate_conversion_optimization_score(self, cta: CTAElement) -> int:
        """Calculate conversion optimization score based on industry best practices"""
        score = 0
        
        # Text optimization
        if cta.text:
            text_lower = cta.text.lower()
            
            # High-converting action words
            high_convert_words = ['buy', 'purchase', 'order', 'get', 'download', 'sign up', 'register']
            if any(word in text_lower for word in high_convert_words):
                score += 25
            
            # Urgency indicators
            urgency_words = ['now', 'today', 'free', 'limited', 'exclusive']
            if any(word in text_lower for word in urgency_words):
                score += 20
            
            # Benefit/value words
            benefit_words = ['save', 'win', 'earn', 'discount', 'off', 'deal']
            if any(word in text_lower for word in benefit_words):
                score += 15
            
            # Avoid generic text
            generic_words = ['click here', 'read more', 'learn more', 'more info']
            if any(word in text_lower for word in generic_words):
                score -= 30
        
        # Element type optimization
        if cta.element_type == 'button':
            score += 20  # Buttons convert better than links
        elif cta.element_type == 'form':
            score += 15
        
        # Position optimization (above the fold)
        if cta.position and cta.position['y'] < 600:
            score += 25
        elif cta.position and cta.position['y'] < 1200:
            score += 15
        
        # Size optimization (prominent but not overwhelming)
        if cta.size:
            if 100 <= cta.size['width'] <= 300 and 40 <= cta.size['height'] <= 60:
                score += 20  # Optimal size range
            elif cta.size['width'] >= 80 and cta.size['height'] >= 35:
                score += 15  # Good size
            else:
                score -= 10  # Too small or too large
        
        return min(100, max(0, score))

    def _calculate_link_validity_score(self, cta: CTAElement) -> int:
        """Calculate link validity score based on link accessibility and functionality"""
        score = 0
        
        # If no href, this is not a link-based CTA
        if not cta.href:
            if cta.element_type == 'link':
                score = 0  # Links should have href
            else:
                score = 50  # Non-link elements are neutral
            return score
        
        # Check if link validation was performed
        if cta.link_is_valid is None:
            score = 50  # Unknown status
            return score
        
        # Link is valid
        if cta.link_is_valid:
            score = 100
            
            # Bonus for fast response times
            if cta.link_response_time and cta.link_response_time < 1.0:
                score = min(100, score + 10)  # Bonus for fast response
            elif cta.link_response_time and cta.link_response_time > 5.0:
                score = max(0, score - 20)  # Penalty for slow response
        else:
            # Link is invalid - score based on error type
            if cta.link_error_message:
                if "404" in cta.link_error_message:
                    score = 0  # Page not found
                elif "403" in cta.link_error_message:
                    score = 10  # Access forbidden
                elif "500" in cta.link_error_message:
                    score = 20  # Server error
                elif "timeout" in cta.link_error_message.lower():
                    score = 15  # Timeout
                elif "connection" in cta.link_error_message.lower():
                    score = 5   # Connection error
                elif "ssl" in cta.link_error_message.lower():
                    score = 25  # SSL error
                elif "skipped" in cta.link_error_message.lower():
                    score = 50  # Skipped (javascript, mailto, etc.)
                else:
                    score = 30  # Other errors
            else:
                score = 0  # Unknown error
        
        return min(100, max(0, score))

    def _identify_issues(self, analysis: Dict[str, Any]) -> None:
        """Identify specific issues with the CTA"""
        cta = analysis['element']
        text_analysis = analysis['text_analysis']
        
        # Create detailed CTA info for context
        cta_info = {
            'text': cta.text,
            'type': cta.element_type,
            'element_id': cta.element_id,
            'css_selector': cta.css_selector,
            'position': f"x:{cta.position['x']}, y:{cta.position['y']}" if cta.position else "Unknown",
            'size': f"{cta.size['width']}x{cta.size['height']}" if cta.size else "Unknown",
            'href': cta.href[:50] + "..." if cta.href and len(cta.href) > 50 else cta.href,
            'has_screenshot': cta.screenshot is not None,
            'html_id': cta.html_id,
            'html_name': cta.html_name,
            'html_class': cta.html_class,
            'is_hidden': cta.is_hidden,
            'is_dropdown': cta.is_dropdown,
            'is_js_generated': cta.is_js_generated,
            'onclick_handler': cta.onclick_handler,
            'aria_label': cta.aria_label,
            'role': cta.role,
            'tabindex': cta.tabindex,
            'z_index': cta.z_index,
            'parent_element': cta.parent_element
        }
        
        # Generic text issues
        if text_analysis['is_generic']:
            analysis['issues'].append({
                'type': 'Generic Text',
                'severity': 'High',
                'element': f'"{cta.text}" ({cta.element_type})',
                'element_id': cta.element_id,
                'css_selector': cta.css_selector,
                'location': f"Position: {cta_info['position']}",
                'description': f'CTA text "{cta.text}" is too generic and doesn\'t indicate specific action',
                'recommendation': 'Use specific, action-oriented text that clearly indicates what will happen (e.g., "Get Started", "Download Now", "Sign Up Free")',
                'cta_details': cta_info
            })
        
        # Missing action words
        if not text_analysis['has_action_word'] and len(cta.text) > 5:
            analysis['issues'].append({
                'type': 'Unclear Action',
                'severity': 'Medium',
                'element': f'"{cta.text}" ({cta.element_type})',
                'element_id': cta.element_id,
                'css_selector': cta.css_selector,
                'location': f"Position: {cta_info['position']}",
                'description': f'CTA text "{cta.text}" doesn\'t clearly indicate the action users should take',
                'recommendation': 'Include action words like "Get", "Download", "Sign Up", "Learn More", "Try Now"',
                'cta_details': cta_info
            })
        
        # Very short text
        if len(cta.text) < 3:
            analysis['issues'].append({
                'type': 'Insufficient Text',
                'severity': 'High',
                'element': f'"{cta.text}" ({cta.element_type})',
                'element_id': cta.element_id,
                'css_selector': cta.css_selector,
                'location': f"Position: {cta_info['position']}",
                'description': f'CTA text "{cta.text}" is too short to be descriptive or accessible',
                'recommendation': 'Add descriptive text that explains the action (minimum 3-5 characters)',
                'cta_details': cta_info
            })
        
        # Very long text
        if len(cta.text) > 50:
            analysis['issues'].append({
                'type': 'Text Too Long',
                'severity': 'Medium',
                'element': f'"{cta.text[:30]}..." ({cta.element_type})',
                'element_id': cta.element_id,
                'css_selector': cta.css_selector,
                'location': f"Position: {cta_info['position']}",
                'description': f'CTA text is too long ({len(cta.text)} chars) and may reduce effectiveness',
                'recommendation': 'Keep CTA text concise and focused (ideally under 30 characters)',
                'cta_details': cta_info
            })
        
        # Empty text
        if not cta.text or cta.text.strip() == "":
            analysis['issues'].append({
                'type': 'Empty Text',
                'severity': 'Medium',
                'element': f'Empty {cta.element_type}',
                'element_id': cta.element_id,
                'css_selector': cta.css_selector,
                'location': f"Position: {cta_info['position']}",
                'description': f'{cta.element_type.title()} has no text content',
                'recommendation': 'Add descriptive text to make the CTA accessible and clear',
                'cta_details': cta_info
            })
        
        # Missing href for links
        if cta.element_type == 'link' and not cta.href:
            analysis['issues'].append({
                'type': 'Missing Link',
                'severity': 'High',
                'element': f'"{cta.text}" (link)',
                'element_id': cta.element_id,
                'css_selector': cta.css_selector,
                'location': f"Position: {cta_info['position']}",
                'description': f'Link "{cta.text}" has no destination URL',
                'recommendation': 'Add a proper href attribute to make the link functional',
                'cta_details': cta_info
            })
        
        # Hidden CTA elements
        if cta.is_hidden:
            analysis['issues'].append({
                'type': 'Hidden CTA',
                'severity': 'Medium',
                'element': f'"{cta.text}" ({cta.element_type})',
                'element_id': cta.element_id,
                'css_selector': cta.css_selector,
                'location': f"Position: {cta_info['position']}",
                'description': f'CTA "{cta.text}" is hidden and may not be accessible to users',
                'recommendation': 'Make the CTA visible or ensure it becomes visible through user interaction',
                'cta_details': cta_info
            })
        
        # Missing accessibility attributes
        if not cta.aria_label and not cta.text and cta.element_type in ['button', 'link']:
            analysis['issues'].append({
                'type': 'Missing Accessibility Label',
                'severity': 'High',
                'element': f'"{cta.text}" ({cta.element_type})',
                'element_id': cta.element_id,
                'css_selector': cta.css_selector,
                'location': f"Position: {cta_info['position']}",
                'description': f'{cta.element_type.title()} has no accessible text or aria-label',
                'recommendation': 'Add descriptive text or aria-label for screen readers',
                'cta_details': cta_info
            })
        
        # JavaScript-generated elements without proper attributes
        if cta.is_js_generated and not cta.role and not cta.aria_label:
            analysis['issues'].append({
                'type': 'JS-Generated Element Missing Accessibility',
                'severity': 'Medium',
                'element': f'"{cta.text}" ({cta.element_type})',
                'element_id': cta.element_id,
                'css_selector': cta.css_selector,
                'location': f"Position: {cta_info['position']}",
                'description': f'JavaScript-generated {cta.element_type} lacks proper accessibility attributes',
                'recommendation': 'Add role, aria-label, or other accessibility attributes',
                'cta_details': cta_info
            })
        
        # Dropdown CTAs without proper structure
        if cta.is_dropdown and not cta.role:
            analysis['issues'].append({
                'type': 'Dropdown CTA Missing Role',
                'severity': 'Medium',
                'element': f'"{cta.text}" ({cta.element_type})',
                'element_id': cta.element_id,
                'css_selector': cta.css_selector,
                'location': f"Position: {cta_info['position']}",
                'description': f'Dropdown {cta.element_type} lacks proper ARIA role',
                'recommendation': 'Add appropriate role attribute (e.g., menuitem, button)',
                'cta_details': cta_info
            })
        
        # Elements with onclick but no keyboard accessibility
        if cta.onclick_handler and not cta.tabindex and cta.element_type not in ['button', 'a', 'input']:
            analysis['issues'].append({
                'type': 'Missing Keyboard Accessibility',
                'severity': 'Medium',
                'element': f'"{cta.text}" ({cta.element_type})',
                'element_id': cta.element_id,
                'css_selector': cta.css_selector,
                'location': f"Position: {cta_info['position']}",
                'description': f'Element with onclick handler is not keyboard accessible',
                'recommendation': 'Add tabindex or use proper interactive element (button, a)',
                'cta_details': cta_info
            })
        
        # Missing ID for tracking
        if not cta.html_id and cta.element_type in ['button', 'link']:
            analysis['issues'].append({
                'type': 'Missing Element ID',
                'severity': 'Low',
                'element': f'"{cta.text}" ({cta.element_type})',
                'element_id': cta.element_id,
                'css_selector': cta.css_selector,
                'location': f"Position: {cta_info['position']}",
                'description': f'{cta.element_type.title()} lacks an ID attribute for tracking and testing',
                'recommendation': 'Add a unique ID attribute for better tracking and testing',
                'cta_details': cta_info
            })
        
        # Link validity issues
        if cta.href and cta.element_type in ['link', 'button']:
            if cta.link_is_valid is False:
                severity = 'High'
                if cta.link_error_message:
                    if '404' in cta.link_error_message:
                        issue_type = 'Broken Link (404)'
                        description = f'Link "{cta.href}" returns a 404 error - page not found'
                        recommendation = 'Fix the broken link by updating the URL or removing the CTA if the page no longer exists'
                    # elif '403' in cta.link_error_message:
                    #     issue_type = 'Access Forbidden (403)'
                    #     description = f'Link "{cta.href}" returns a 403 error - access forbidden'
                    #     recommendation = 'Check permissions and ensure the link is accessible to users'
                    elif '500' in cta.link_error_message:
                        issue_type = 'Server Error (500)'
                        description = f'Link "{cta.href}" returns a 500 error - server error'
                        recommendation = 'Contact the server administrator to fix the server-side issue'
                    elif 'timeout' in cta.link_error_message.lower():
                        issue_type = 'Link Timeout'
                        description = f'Link "{cta.href}" times out when accessed'
                        recommendation = 'Check server performance or consider using a CDN to improve response times'
                    elif 'connection' in cta.link_error_message.lower():
                        issue_type = 'Connection Error'
                        description = f'Link "{cta.href}" cannot be reached due to connection issues'
                        recommendation = 'Verify the URL is correct and the server is online'
                    elif 'ssl' in cta.link_error_message.lower():
                        issue_type = 'SSL Certificate Error'
                        description = f'Link "{cta.href}" has SSL certificate issues'
                        recommendation = 'Fix SSL certificate configuration or use HTTP if appropriate'
                    else:
                        issue_type = 'Link Error'
                        description = f'Link "{cta.href}" has an error: {cta.link_error_message}'
                        recommendation = 'Investigate and fix the link issue'
                else:
                    issue_type = 'Invalid Link'
                    description = f'Link "{cta.href}" is not valid'
                    recommendation = 'Check the link URL and ensure it points to a valid destination'
                
                analysis['issues'].append({
                    'type': issue_type,
                    'severity': severity,
                    'element': f'"{cta.text}" ({cta.element_type})',
                    'element_id': cta.element_id,
                    'css_selector': cta.css_selector,
                    'location': f"Position: {cta_info['position']}",
                    'description': description,
                    'recommendation': recommendation,
                    'cta_details': cta_info
                })
            
            elif cta.link_is_valid is True and cta.link_response_time and cta.link_response_time > 3.0:
                analysis['issues'].append({
                    'type': 'Slow Link Response',
                    'severity': 'Medium',
                    'element': f'"{cta.text}" ({cta.element_type})',
                    'element_id': cta.element_id,
                    'css_selector': cta.css_selector,
                    'location': f"Position: {cta_info['position']}",
                    'description': f'Link "{cta.href}" is slow to respond ({cta.link_response_time:.2f}s)',
                    'recommendation': 'Optimize server performance or consider using a CDN to improve response times',
                    'cta_details': cta_info
                })
            
            elif cta.link_redirect_url and cta.link_redirect_url != cta.href:
                analysis['issues'].append({
                    'type': 'Redirect Link',
                    'severity': 'Low',
                    'element': f'"{cta.text}" ({cta.element_type})',
                    'element_id': cta.element_id,
                    'css_selector': cta.css_selector,
                    'location': f"Position: {cta_info['position']}",
                    'description': f'Link "{cta.href}" redirects to "{cta.link_redirect_url}"',
                    'recommendation': 'Consider updating the link to point directly to the final destination to improve performance',
                    'cta_details': cta_info
                })

    def _generate_recommendations(self, analysis: Dict[str, Any]) -> None:
        """Generate recommendations for improving the CTA"""
        cta = analysis['element']
        text_analysis = analysis['text_analysis']
        
        # Text improvements
        if not text_analysis['has_action_word']:
            analysis['recommendations'].append('Add action-oriented words to make the CTA more compelling')
        
        if not text_analysis['has_urgency_word']:
            analysis['recommendations'].append('Consider adding urgency words to create a sense of immediacy')
        
        if not text_analysis['has_benefit']:
            analysis['recommendations'].append('Include benefit words to highlight value proposition')
        
        # General recommendations
        if analysis['visibility_score'] < 70:
            analysis['recommendations'].append('Improve CTA visibility with better positioning or styling')
        
        if analysis['action_clarity'] < 60:
            analysis['recommendations'].append('Make the action more clear and specific')
        
        # Link validity recommendations
        if analysis['link_validity_score'] < 50:
            analysis['recommendations'].append('Fix broken or invalid links to ensure CTAs are functional')
        
        if cta.href and cta.link_response_time and cta.link_response_time > 2.0:
            analysis['recommendations'].append('Optimize link performance to improve user experience')

    def _generate_audit_results(self, url: str, analyzed_ctas: List[Dict[str, Any]], analysis_type: str, ai_recommendations: List[str] = None, heatmap_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Generate final audit results"""
        if not analyzed_ctas:
            return {
                "url": url,
                "analysis_type": analysis_type,
                "total_ctas": 0,
                "primary_ctas": 0,
                "secondary_ctas": 0,
                "form_ctas": 0,
                "link_ctas": 0,
                "cta_issues": [],
                "cta_strengths": [],
                "recommendations": [],
                "score": 0,
                "error": "No CTA elements found on the website"
            }
        
        # Categorize CTAs
        primary_ctas = [cta for cta in analyzed_ctas if cta['urgency_score'] > 60 and cta['action_clarity'] > 70]
        secondary_ctas = [cta for cta in analyzed_ctas if cta not in primary_ctas and cta['element'].element_type == 'link']
        form_ctas = [cta for cta in analyzed_ctas if cta['element'].element_type == 'form']
        link_ctas = [cta for cta in analyzed_ctas if cta['element'].element_type == 'link']
        
        # Count CTAs by element type for better categorization
        cta_counts_by_type = {}
        for cta_analysis in analyzed_ctas:
            element_type = cta_analysis['element'].element_type
            cta_counts_by_type[element_type] = cta_counts_by_type.get(element_type, 0) + 1
        
        # Calculate "Other" category (CTAs not in button, link, form)
        standard_types = {'button', 'link', 'form', 'dropdown'}
        other_count = sum(count for cta_type, count in cta_counts_by_type.items() if cta_type not in standard_types)
        
        # Collect all issues
        all_issues = []
        for cta_analysis in analyzed_ctas:
            all_issues.extend(cta_analysis['issues'])
        
        # Collect all recommendations
        all_recommendations = []
        for cta_analysis in analyzed_ctas:
            all_recommendations.extend(cta_analysis['recommendations'])
        
        # Remove duplicates
        unique_recommendations = list(set(all_recommendations))
        
        # Add AI recommendations if available
        if ai_recommendations:
            unique_recommendations.extend(ai_recommendations)
            unique_recommendations = list(set(unique_recommendations))  # Remove duplicates again
        
        # Calculate overall score using weighted metrics
        if analyzed_ctas:
            # Use the new weighted overall score
            overall_score = int(sum(cta['overall_score'] for cta in analyzed_ctas) / len(analyzed_ctas))
            
            # Calculate individual metric averages for reporting
            avg_visibility = sum(cta['visibility_score'] for cta in analyzed_ctas) / len(analyzed_ctas)
            avg_urgency = sum(cta['urgency_score'] for cta in analyzed_ctas) / len(analyzed_ctas)
            avg_clarity = sum(cta['action_clarity'] for cta in analyzed_ctas) / len(analyzed_ctas)
            avg_accessibility = sum(cta['accessibility_score'] for cta in analyzed_ctas) / len(analyzed_ctas)
            avg_mobile = sum(cta['mobile_responsiveness_score'] for cta in analyzed_ctas) / len(analyzed_ctas)
            avg_conversion = sum(cta['conversion_optimization_score'] for cta in analyzed_ctas) / len(analyzed_ctas)
            avg_contrast = sum(cta['color_contrast_score'] for cta in analyzed_ctas) / len(analyzed_ctas)
            avg_link_validity = sum(cta['link_validity_score'] for cta in analyzed_ctas) / len(analyzed_ctas)
        else:
            overall_score = 0
            avg_visibility = avg_urgency = avg_clarity = avg_accessibility = 0
            avg_mobile = avg_conversion = avg_contrast = avg_link_validity = 0
        
        # Generate strengths
        strengths = []
        if len(primary_ctas) > 0:
            strengths.append(f"Found {len(primary_ctas)} strong primary CTAs")
        if any(cta['text_analysis']['has_urgency_word'] for cta in analyzed_ctas):
            strengths.append("Good use of urgency words in CTAs")
        if any(cta['text_analysis']['has_action_word'] for cta in analyzed_ctas):
            strengths.append("Clear action-oriented language")
        if len(analyzed_ctas) > 5:
            strengths.append("Good variety of CTA options")
        
        if not strengths:
            strengths.append("Website has CTA elements present")
        
        result = {
            "url": url,
            "analysis_type": analysis_type,
            "total_ctas": len(analyzed_ctas),
            "primary_ctas": len(primary_ctas),
            "secondary_ctas": len(secondary_ctas),
            "form_ctas": len(form_ctas),
            "link_ctas": len(link_ctas),
            "cta_issues": all_issues,  # Include all issues
            "cta_strengths": strengths,
            "recommendations": unique_recommendations,  # Include all recommendations
            "score": overall_score,
            "detailed_analysis": analyzed_ctas,  # Include detailed analysis for debugging
            "total_issues": len(all_issues),
            "total_recommendations": len(unique_recommendations),
            # CTA counts by type (for UI display)
            "cta_counts_by_type": cta_counts_by_type,
            "other_ctas": other_count,
            # Enhanced scoring metrics
            "scoring_breakdown": {
                "overall_score": overall_score,
                "visibility_score": int(avg_visibility),
                "urgency_score": int(avg_urgency),
                "action_clarity_score": int(avg_clarity),
                "accessibility_score": int(avg_accessibility),
                "mobile_responsiveness_score": int(avg_mobile),
                "conversion_optimization_score": int(avg_conversion),
                "color_contrast_score": int(avg_contrast),
                "link_validity_score": int(avg_link_validity)
            }
        }
        
        # Add AI recommendations and heatmap data if available
        if ai_recommendations:
            result["ai_recommendations"] = ai_recommendations
        if heatmap_data:
            result["heatmap_data"] = heatmap_data
        
        return result

    def _is_valid_url_pattern(self, url: str) -> bool:
        """Check if URL is a valid URL pattern (not JavaScript code or invalid patterns)"""
        if not url or not isinstance(url, str):
            return False
        
        # Skip JavaScript protocol links
        if url.startswith(('javascript:', 'mailto:', 'tel:', '#')):
            return False
        
        # Skip URLs that contain JavaScript function definitions
        js_patterns = [
            r'function\s+\w+\s*\(',  # function name()
            r'function\s*\(',  # function()
            r'=>\s*{',  # arrow functions
            r'\(\)\s*=>',  # () =>
            r'rg\(\)\s*{}',  # rg() {}
            r'\w+\s*\(\)\s*{}',  # any function() {}
            r'void\s*\(',  # void(
            r'return\s+',  # return statements
            r'var\s+\w+',  # var declarations
            r'let\s+\w+',  # let declarations
            r'const\s+\w+',  # const declarations
        ]
        
        for pattern in js_patterns:
            if re.search(pattern, url, re.IGNORECASE):
                return False
        
        # Skip URLs that look like JavaScript code (contain common JS keywords)
        js_keywords = ['function', 'return', 'var ', 'let ', 'const ', '=>', 'void', 'undefined', 'null']
        url_lower = url.lower()
        if any(keyword in url_lower and not url_lower.startswith('http') for keyword in js_keywords):
            # Check if it's actually a URL with these words in the path vs JS code
            if not (url.startswith('http') or url.startswith('/') or url.startswith('./')):
                return False
        
        # Skip URLs that are clearly not URLs (contain spaces, newlines, etc. in suspicious ways)
        if re.search(r'[{}();]\s*function|function\s*[{}();]', url):
            return False
        
        # Check for valid URL structure
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            # If it has a scheme, it should be http/https
            if parsed.scheme and parsed.scheme not in ['http', 'https', 'ftp', 'file']:
                return False
        except:
            pass
        
        return True
    
    def _check_link_validity(self, url: str, timeout: int = 10) -> Dict[str, Any]:
        """Check if a link is valid and accessible"""
        import time
        from datetime import datetime
        
        result = {
            'link_status': None,
            'link_is_valid': False,
            'link_error_message': None,
            'link_redirect_url': None,
            'link_response_time': None,
            'link_check_timestamp': datetime.now().isoformat()
        }
        
        try:
            # Skip checking if no URL or if it's a javascript: or mailto: link
            if not url or url.startswith(('javascript:', 'mailto:', 'tel:', '#')):
                result['link_error_message'] = f"Skipped: {url.split(':')[0] if ':' in url else 'invalid'} link"
                result['link_is_valid'] = None  # Not invalid, just not checkable
                return result
            
            # Check if URL pattern is valid (not JavaScript code)
            if not self._is_valid_url_pattern(url):
                result['link_error_message'] = "Skipped: Invalid URL pattern (likely JavaScript code)"
                result['link_is_valid'] = None  # Not invalid, just not checkable
                return result
            
            # Handle relative URLs - we'll try to validate them if they're simple paths
            if url.startswith('/'):
                # For relative URLs, we can't validate without base URL
                # But we'll mark them as potentially valid if they look like paths
                if re.match(r'^/[a-zA-Z0-9/._-]+$', url):
                    result['link_error_message'] = "Skipped: Relative URL (needs base URL for validation)"
                    result['link_is_valid'] = None  # Unknown status
                    return result
                else:
                    result['link_error_message'] = "Skipped: Invalid relative URL pattern"
                    result['link_is_valid'] = None
                    return result
            
            start_time = time.time()
            
            # Make the request with proper headers
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }
            
            response = requests.get(
                url, 
                headers=headers, 
                timeout=timeout, 
                allow_redirects=True,
                verify=True
            )
            
            end_time = time.time()
            response_time = end_time - start_time
            
            result['link_status'] = response.status_code
            result['link_response_time'] = response_time
            result['link_redirect_url'] = response.url if response.url != url else None
            
            # Determine if link is valid based on status code
            if 200 <= response.status_code < 400:
                result['link_is_valid'] = True
            elif response.status_code == 404:
                result['link_error_message'] = "Page not found (404)"
            elif response.status_code == 403:
                result['link_error_message'] = "Access forbidden (403)"
            elif response.status_code == 500:
                result['link_error_message'] = "Server error (500)"
            elif response.status_code >= 400:
                result['link_error_message'] = f"Client error ({response.status_code})"
            else:
                result['link_error_message'] = f"Unexpected status code ({response.status_code})"
                
        except requests.exceptions.Timeout:
            result['link_error_message'] = f"Request timeout (>{timeout}s)"
        except requests.exceptions.ConnectionError:
            result['link_error_message'] = "Connection error - unable to reach server"
        except requests.exceptions.SSLError:
            result['link_error_message'] = "SSL certificate error"
        except requests.exceptions.TooManyRedirects:
            result['link_error_message'] = "Too many redirects"
        except requests.exceptions.InvalidURL:
            result['link_error_message'] = "Invalid URL format"
        except Exception as e:
            result['link_error_message'] = f"Unexpected error: {str(e)}"
        
        return result

    def _validate_cta_links(self, cta_elements: List[CTAElement]) -> List[CTAElement]:
        """Validate all CTA links and update their link validation fields"""
        import concurrent.futures
        import threading
        
        # Count links that need validation
        links_to_check = [cta for cta in cta_elements if cta.href and cta.element_type in ['link', 'button']]
        total_links = len(links_to_check)
        
        if total_links == 0:
            print("      ℹ️  No links to validate")
            return cta_elements
        
        print(f"      🔗 Validating {total_links} links (using 5 concurrent workers)...")
        
        def check_single_link(cta: CTAElement) -> CTAElement:
            """Check a single CTA link"""
            if cta.href and cta.element_type in ['link', 'button']:
                link_result = self._check_link_validity(cta.href)
                
                # Update CTA element with link validation results
                cta.link_status = link_result['link_status']
                cta.link_is_valid = link_result['link_is_valid']
                cta.link_error_message = link_result['link_error_message']
                cta.link_redirect_url = link_result['link_redirect_url']
                cta.link_response_time = link_result['link_response_time']
                cta.link_check_timestamp = link_result['link_check_timestamp']
            
            return cta
        
        # Use ThreadPoolExecutor for concurrent link checking
        validated_ctas = []
        checked_count = 0
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            # Submit all link checking tasks
            future_to_cta = {executor.submit(check_single_link, cta): cta for cta in cta_elements}
            
            # Collect results as they complete
            for future in concurrent.futures.as_completed(future_to_cta):
                try:
                    validated_cta = future.result()
                    validated_ctas.append(validated_cta)
                    checked_count += 1
                    if checked_count % 5 == 0 or checked_count == total_links:
                        print(f"         Validated {checked_count}/{total_links} links...")
                except Exception as e:
                    # If validation fails, keep the original CTA
                    original_cta = future_to_cta[future]
                    original_cta.link_error_message = f"Validation failed: {str(e)}"
                    validated_ctas.append(original_cta)
                    checked_count += 1
        
        return validated_ctas

def perform_cta_audit(url: str, analysis_type: str = "Comprehensive CTA Audit", gemini_api_key: str = None) -> Dict[str, Any]:
    """Main function to perform CTA audit on a website"""
    analyzer = CTAAuditAnalyzer(gemini_api_key=gemini_api_key)
    return analyzer.analyze_website(url, analysis_type)

def generate_visual_report(audit_results: Dict[str, Any]) -> str:
    """Generate a visual HTML report with CTA screenshots and detailed analysis"""
    if "error" in audit_results:
        return f"<h2>Error</h2><p>{audit_results['error']}</p>"
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>CTA Audit Report - {audit_results.get('url', 'Unknown')}</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            .cta-item {{ border: 1px solid #ddd; margin: 10px 0; padding: 15px; border-radius: 5px; }}
            .cta-screenshot {{ max-width: 300px; border: 1px solid #ccc; margin: 10px 0; }}
            .issue {{ background-color: #ffe6e6; padding: 10px; margin: 5px 0; border-left: 4px solid #ff4444; }}
            .recommendation {{ background-color: #e6f3ff; padding: 10px; margin: 5px 0; border-left: 4px solid #4444ff; }}
            .cta-info {{ background-color: #f9f9f9; padding: 10px; margin: 5px 0; }}
            .score {{ font-size: 24px; font-weight: bold; color: #333; }}
            .high-severity {{ border-left-color: #ff0000; }}
            .medium-severity {{ border-left-color: #ff8800; }}
            .low-severity {{ border-left-color: #ffaa00; }}
        </style>
    </head>
    <body>
        <h1>CTA Audit Report</h1>
        <div class="cta-info">
            <h2>Summary</h2>
            <p><strong>URL:</strong> {audit_results.get('url', 'Unknown')}</p>
            <p><strong>Analysis Type:</strong> {audit_results.get('analysis_type', 'Unknown')}</p>
            <p><strong>Total CTAs Found:</strong> {audit_results.get('total_ctas', 0)}</p>
            <p><strong>Primary CTAs:</strong> {audit_results.get('primary_ctas', 0)}</p>
            <p><strong>Secondary CTAs:</strong> {audit_results.get('secondary_ctas', 0)}</p>
            <p><strong>Form CTAs:</strong> {audit_results.get('form_ctas', 0)}</p>
            <p><strong>Link CTAs:</strong> {audit_results.get('link_ctas', 0)}</p>
            <p><strong>Overall Score:</strong> <span class="score">{audit_results.get('score', 0)}/100</span></p>
        </div>
    """
    
    # Add detailed CTA analysis
    if 'detailed_analysis' in audit_results:
        html += "<h2>Detailed CTA Analysis</h2>"
        for i, cta_analysis in enumerate(audit_results['detailed_analysis'], 1):
            cta = cta_analysis['element']
            html += f"""
            <div class="cta-item">
                <h3>CTA #{i} - {cta.element_type.title()}</h3>
                <div class="cta-info">
                    <p><strong>Text:</strong> "{cta.text}"</p>
                    <p><strong>Element ID:</strong> {cta.element_id}</p>
                    <p><strong>CSS Selector:</strong> {cta.css_selector}</p>
                    <p><strong>Position:</strong> x:{cta.position['x']}, y:{cta.position['y']}</p>
                    <p><strong>Size:</strong> {cta.size['width']}x{cta.size['height']}</p>
                    <p><strong>Href:</strong> {cta.href or 'N/A'}</p>
                    <p><strong>Visibility Score:</strong> {cta_analysis['visibility_score']}/100</p>
                    <p><strong>Urgency Score:</strong> {cta_analysis['urgency_score']}/100</p>
                    <p><strong>Action Clarity:</strong> {cta_analysis['action_clarity']}/100</p>
                    <p><strong>Accessibility Score:</strong> {cta_analysis['accessibility_score']}/100</p>
                    
                    <h4>Enhanced Metadata:</h4>
                    <p><strong>HTML ID:</strong> {cta.html_id or 'N/A'}</p>
                    <p><strong>HTML Name:</strong> {cta.html_name or 'N/A'}</p>
                    <p><strong>HTML Class:</strong> {cta.html_class or 'N/A'}</p>
                    <p><strong>ARIA Label:</strong> {cta.aria_label or 'N/A'}</p>
                    <p><strong>Role:</strong> {cta.role or 'N/A'}</p>
                    <p><strong>Tab Index:</strong> {cta.tabindex or 'N/A'}</p>
                    <p><strong>Parent Element:</strong> {cta.parent_element or 'N/A'}</p>
                    <p><strong>Z-Index:</strong> {cta.z_index or 'N/A'}</p>
                    <p><strong>Is Hidden:</strong> {'Yes' if cta.is_hidden else 'No'}</p>
                    <p><strong>Is Dropdown:</strong> {'Yes' if cta.is_dropdown else 'No'}</p>
                    <p><strong>Is JS Generated:</strong> {'Yes' if cta.is_js_generated else 'No'}</p>
                    <p><strong>OnClick Handler:</strong> {'Yes' if cta.onclick_handler else 'No'}</p>
                    
                    {f'<p><strong>OnClick Code:</strong> <code>{cta.onclick_handler[:100]}{"..." if len(cta.onclick_handler) > 100 else ""}</code></p>' if cta.onclick_handler else ''}
                    
                    {f'<h4>Data Attributes:</h4><ul>{"".join([f"<li><strong>{k}:</strong> {v}</li>" for k, v in cta.data_attributes.items()])}</ul>' if cta.data_attributes else ''}
                    
                    {f'<h4>Computed Styles:</h4><ul>{"".join([f"<li><strong>{k}:</strong> {v}</li>" for k, v in cta.computed_styles.items()])}</ul>' if cta.computed_styles else ''}
            """
            
            # Add screenshot if available
            if cta.screenshot:
                html += f'<img src="data:image/png;base64,{cta.screenshot}" class="cta-screenshot" alt="CTA Screenshot" />'
            
            html += "</div>"
            
            # Add issues
            if cta_analysis['issues']:
                html += "<h4>Issues Found:</h4>"
                for issue in cta_analysis['issues']:
                    severity_class = f"{issue['severity'].lower()}-severity"
                    html += f"""
                    <div class="issue {severity_class}">
                        <strong>{issue['type']} ({issue['severity']})</strong><br>
                        {issue['description']}<br>
                        <em>Recommendation: {issue['recommendation']}</em>
                    </div>
                    """
            
            # Add recommendations
            if cta_analysis['recommendations']:
                html += "<h4>Recommendations:</h4>"
                for rec in cta_analysis['recommendations']:
                    html += f'<div class="recommendation">{rec}</div>'
            
            html += "</div>"
    
    # Add overall issues and recommendations
    if audit_results.get('cta_issues'):
        html += "<h2>All Issues Summary</h2>"
        for issue in audit_results['cta_issues']:
            severity_class = f"{issue['severity'].lower()}-severity"
            html += f"""
            <div class="issue {severity_class}">
                <strong>{issue['type']} ({issue['severity']})</strong><br>
                <strong>Element:</strong> {issue['element']}<br>
                <strong>Location:</strong> {issue['location']}<br>
                {issue['description']}<br>
                <em>Recommendation: {issue['recommendation']}</em>
            </div>
            """
    
    if audit_results.get('recommendations'):
        html += "<h2>All Recommendations</h2>"
        for rec in audit_results['recommendations']:
            html += f'<div class="recommendation">{rec}</div>'
    
    html += """
    </body>
    </html>
    """
    
    return html
