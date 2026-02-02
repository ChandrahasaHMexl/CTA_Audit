import requests
import json
import re
from typing import List, Dict, Any, Optional, Set, Tuple
from dataclasses import dataclass
import pandas as pd
from datetime import datetime
from urllib.parse import urljoin, urlparse
import time
import logging
from bs4 import BeautifulSoup
import cloudscraper

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class SkyProduct:
    """Data class to represent any Sky product/deal."""
    id: str
    name: str
    category: str
    sub_category: str
    page_type: str
    source_url: str
    price: str
    price_display: str
    original_price: str
    discount_info: str
    primary_label: str
    offer_tag: str
    description: str
    features: List[str]
    included_items: List[str]
    cta_text: str
    cta_link: str
    media_url: str
    contract_info: str
    availability: str
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'id': self.id,
            'name': self.name,
            'category': self.category,
            'sub_category': self.sub_category,
            'page_type': self.page_type,
            'source_url': self.source_url,
            'price': self.price,
            'price_display': self.price_display,
            'original_price': self.original_price,
            'discount_info': self.discount_info,
            'primary_label': self.primary_label,
            'offer_tag': self.offer_tag,
            'description': self.description,
            'features': self.features,
            'included_items': self.included_items,
            'cta_text': self.cta_text,
            'cta_link': self.cta_link,
            'media_url': self.media_url,
            'contract_info': self.contract_info,
            'availability': self.availability,
            'metadata': self.metadata,
        }

class UniversalSkyExtractor:
    """Universal extractor for any Sky UK website page."""
    
    def __init__(self, base_delay: float = 1.0, max_retries: int = 3):
        self.session = cloudscraper.create_scraper()
        self.base_delay = base_delay
        self.max_retries = max_retries
        self.products: List[SkyProduct] = []
        
        # Configure session
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-GB,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        
        # Product detection patterns
        self.product_patterns = {
            'deals': ['deal', 'offer', 'package', 'bundle'],
            'tv': ['television', 'tv', 'stream', 'glass', 'entertainment'],
            'broadband': ['broadband', 'fibre', 'wifi', 'internet'],
            'mobile': ['mobile', 'phone', 'sim', 'data'],
            'sports': ['sport', 'football', 'premier league', 'f1'],
            'cinema': ['cinema', 'movie', 'film'],
            'products': ['product', 'service', 'subscription']
        }
    
    def extract_from_url(self, url: str) -> List[SkyProduct]:
        """Extract products from any Sky URL."""
        logger.info(f"🚀 Starting extraction from: {url}")
        
        # Fetch the page
        html_content = self._fetch_page(url)
        if not html_content:
            logger.error("❌ Failed to fetch page content")
            return []
        
        # Detect page type
        page_type = self._detect_page_type(url, html_content)
        logger.info(f"📄 Detected page type: {page_type}")
        
        # Extract JSON data
        json_data = self._extract_json_data(html_content)
        if not json_data:
            logger.warning("⚠️  No JSON data found, trying alternative extraction")
            return self._extract_from_html(html_content, url, page_type)
        
        # Analyze JSON structure
        self._analyze_json_structure(json_data, url)
        
        # Extract products from JSON
        self.products = self._extract_products_from_json(json_data, url, page_type)
        
        logger.info(f"✅ Extracted {len(self.products)} products from {url}")
        return self.products
    
    def _fetch_page(self, url: str) -> Optional[str]:
        """Fetch page content with retries and error handling."""
        for attempt in range(self.max_retries):
            try:
                logger.info(f"📡 Fetching page (attempt {attempt + 1}/{self.max_retries})")
                
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
                
                logger.info(f"✅ Successfully fetched page ({len(response.content)} bytes)")
                return response.text
                
            except requests.exceptions.RequestException as e:
                logger.warning(f"⚠️  Attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retries - 1:
                    wait_time = self.base_delay * (2 ** attempt)
                    logger.info(f"⏱️  Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"❌ All attempts failed for {url}")
        
        return None
    
    def _detect_page_type(self, url: str, html_content: str) -> str:
        """Detect the type of Sky page based on URL and content."""
        url_lower = url.lower()
        content_lower = html_content.lower()
        
        # URL-based detection
        if '/deals' in url_lower:
            return 'deals'
        elif '/tv' in url_lower or '/stream' in url_lower or '/glass' in url_lower:
            return 'tv'
        elif '/broadband' in url_lower or '/wifi' in url_lower:
            return 'broadband'
        elif '/mobile' in url_lower or '/phone' in url_lower:
            return 'mobile'
        elif '/sports' in url_lower:
            return 'sports'
        elif '/cinema' in url_lower or '/movies' in url_lower:
            return 'cinema'
        
        # Content-based detection
        for page_type, keywords in self.product_patterns.items():
            keyword_count = sum(1 for keyword in keywords if keyword in content_lower)
            if keyword_count >= 2:  # At least 2 keywords match
                return page_type
        
        return 'general'
    
    def _extract_json_data(self, html_content: str) -> Optional[Dict[str, Any]]:
        """Extract JSON data from HTML content."""
        json_data_sources = []
        
        # Method 1: __NEXT_DATA__ script tag (Next.js applications)
        next_data_pattern = r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>'
        next_data_match = re.search(next_data_pattern, html_content, re.DOTALL)
        
        if next_data_match:
            try:
                next_data = json.loads(next_data_match.group(1))
                json_data_sources.append(('next_data', next_data))
                logger.info("✅ Found __NEXT_DATA__ JSON")
            except json.JSONDecodeError as e:
                logger.warning(f"⚠️  Failed to parse __NEXT_DATA__: {e}")
        
        # Method 2: Other script tags with JSON
        script_pattern = r'<script[^>]*type=["\']application/json["\'][^>]*>(.*?)</script>'
        script_matches = re.findall(script_pattern, html_content, re.DOTALL | re.IGNORECASE)
        
        for i, script_content in enumerate(script_matches):
            try:
                script_json = json.loads(script_content)
                json_data_sources.append((f'script_{i}', script_json))
                logger.info(f"✅ Found JSON in script tag {i}")
            except json.JSONDecodeError:
                continue
        
        # Method 3: Inline JavaScript objects
        js_object_patterns = [
            r'window\.__INITIAL_STATE__\s*=\s*({.*?});',
            r'window\.__APP_DATA__\s*=\s*({.*?});',
            r'window\.__PAGE_DATA__\s*=\s*({.*?});',
            r'var\s+initialData\s*=\s*({.*?});',
            r'const\s+pageData\s*=\s*({.*?});'
        ]
        
        for pattern_name, pattern in enumerate(js_object_patterns):
            matches = re.findall(pattern, html_content, re.DOTALL)
            for match in matches:
                try:
                    js_object = json.loads(match)
                    json_data_sources.append((f'js_object_{pattern_name}', js_object))
                    logger.info(f"✅ Found JavaScript object {pattern_name}")
                except json.JSONDecodeError:
                    continue
        
        # Return the largest/most comprehensive JSON data
        if json_data_sources:
            # Sort by data size (most comprehensive first)
            json_data_sources.sort(key=lambda x: len(str(x[1])), reverse=True)
            source_name, json_data = json_data_sources[0]
            logger.info(f"📊 Using JSON data from: {source_name}")
            return json_data
        
        return None
    
    def _analyze_json_structure(self, json_data: Dict[str, Any], url: str) -> None:
        """Analyze the JSON structure to understand data organization."""
        logger.info("🔍 Analyzing JSON structure...")
        
        analysis = self._analyze_object_recursive(json_data, "root", max_depth=8)
        
        logger.info(f"📊 JSON Structure Analysis:")
        logger.info(f"   • Total objects: {analysis['total_objects']}")
        logger.info(f"   • Arrays found: {analysis['arrays_found']}")
        logger.info(f"   • Potential products: {analysis['potential_products']}")
        logger.info(f"   • Product containers: {len(analysis['product_containers'])}")
        
        if analysis['product_containers']:
            logger.info("🎯 Product containers found at:")
            for path, count, obj_type in analysis['product_containers'][:10]:  # Show top 10
                logger.info(f"   • {path}: {count} {obj_type}")
    
    def _analyze_object_recursive(self, obj: Any, path: str, max_depth: int = 6, current_depth: int = 0) -> Dict[str, Any]:
        """Recursively analyze JSON structure to find products."""
        analysis = {
            'total_objects': 0,
            'arrays_found': 0,
            'potential_products': 0,
            'product_containers': []
        }
        
        if current_depth > max_depth:
            return analysis
        
        if isinstance(obj, dict):
            analysis['total_objects'] += 1
            
            # Check if this object looks like a product
            if self._is_potential_product(obj):
                analysis['potential_products'] += 1
            
            # Check for product containers
            product_container_keys = [
                'deals', 'products', 'items', 'offers', 'packages', 'services',
                'tv', 'broadband', 'mobile', 'bundles', 'plans', 'subscriptions'
            ]
            
            for key in product_container_keys:
                if key in obj and isinstance(obj[key], list) and len(obj[key]) > 0:
                    first_item = obj[key][0]
                    if isinstance(first_item, dict) and self._is_potential_product(first_item):
                        analysis['product_containers'].append((f"{path}.{key}", len(obj[key]), 'products'))
            
            # Recursively analyze
            for key, value in obj.items():
                child_path = f"{path}.{key}" if path != "root" else key
                child_analysis = self._analyze_object_recursive(value, child_path, max_depth, current_depth + 1)
                
                # Merge results
                for k, v in child_analysis.items():
                    if k == 'product_containers':
                        analysis[k].extend(v)
                    else:
                        analysis[k] += v
        
        elif isinstance(obj, list):
            analysis['arrays_found'] += 1
            
            if len(obj) > 0 and isinstance(obj[0], dict):
                if self._is_potential_product(obj[0]):
                    analysis['product_containers'].append((path, len(obj), 'direct_products'))
                
                # Analyze first few items
                for i, item in enumerate(obj[:3]):
                    item_path = f"{path}[{i}]"
                    child_analysis = self._analyze_object_recursive(item, item_path, max_depth, current_depth + 1)
                    
                    for k, v in child_analysis.items():
                        if k == 'product_containers':
                            analysis[k].extend(v)
                        else:
                            analysis[k] += v
        
        return analysis
    
    def _is_potential_product(self, obj: Dict[str, Any]) -> bool:
        """Check if an object looks like a product/deal."""
        if not isinstance(obj, dict):
            return False
        
        # Primary indicators (strong signals)
        primary_indicators = [
            'heading', 'title', 'name', 'price', 'cost', 'pricing',
            'cta', 'offer', 'deal', 'package', 'product'
        ]
        
        # Secondary indicators (supporting signals)
        secondary_indicators = [
            'description', 'features', 'category', 'media', 'image',
            'link', 'href', 'url', 'id', 'key'
        ]
        
        # Tertiary indicators (weak but relevant signals)
        tertiary_indicators = [
            'disclaimer', 'terms', 'availability', 'contract',
            'monthly', 'subscription', 'service'
        ]
        
        # Count matches
        primary_matches = sum(1 for key in obj.keys() 
                            if any(indicator in key.lower() for indicator in primary_indicators))
        
        secondary_matches = sum(1 for key in obj.keys() 
                              if any(indicator in key.lower() for indicator in secondary_indicators))
        
        tertiary_matches = sum(1 for key in obj.keys() 
                             if any(indicator in key.lower() for indicator in tertiary_indicators))
        
        # Scoring system
        score = (primary_matches * 3) + (secondary_matches * 2) + (tertiary_matches * 1)
        
        # Also check for specific Sky product patterns
        sky_patterns = ['sky', 'stream', 'glass', 'broadband', 'mobile', 'sports', 'cinema']
        sky_matches = sum(1 for key, value in obj.items() 
                         if isinstance(value, str) and 
                         any(pattern in value.lower() for pattern in sky_patterns))
        
        return score >= 5 or (primary_matches >= 2) or (sky_matches >= 2)
    
    def _extract_products_from_json(self, json_data: Dict[str, Any], url: str, page_type: str) -> List[SkyProduct]:
        """Extract products from JSON data using multiple strategies."""
        logger.info("🎯 Extracting products from JSON data...")
        
        products = []
        
        # Strategy 1: Standard Next.js structure
        products.extend(self._extract_from_nextjs_structure(json_data, url, page_type))
        
        # Strategy 2: Recursive deep search
        products.extend(self._extract_products_recursive(json_data, url, page_type, "root"))
        
        # Strategy 3: Component-based extraction
        products.extend(self._extract_from_components(json_data, url, page_type))
        
        # Strategy 4: Pattern-based extraction
        products.extend(self._extract_by_patterns(json_data, url, page_type))
        
        # Remove duplicates
        unique_products = self._remove_duplicate_products(products)
        
        logger.info(f"📦 Extracted {len(unique_products)} unique products")
        return unique_products
    
    def _extract_from_nextjs_structure(self, json_data: Dict[str, Any], url: str, page_type: str) -> List[SkyProduct]:
        """Extract from standard Next.js page structure."""
        products = []
        
        try:
            # Navigate through common Next.js paths
            paths_to_try = [
                ['props', 'pageProps', 'data', 'content'],
                ['props', 'pageProps', 'content'],
                ['props', 'pageProps', 'data'],
                ['props', 'pageProps'],
                ['pageProps', 'data', 'content'],
                ['pageProps', 'content'],
                ['pageProps', 'data'],
                ['data', 'content'],
                ['content']
            ]
            
            for path in paths_to_try:
                current_obj = json_data
                
                # Navigate through the path
                for key in path:
                    if isinstance(current_obj, dict) and key in current_obj:
                        current_obj = current_obj[key]
                    else:
                        break
                else:
                    # Successfully navigated the full path
                    if isinstance(current_obj, list):
                        logger.info(f"✅ Found content array at {' -> '.join(path)}")
                        products.extend(self._extract_from_content_array(current_obj, url, page_type))
                    elif isinstance(current_obj, dict):
                        logger.info(f"✅ Found content object at {' -> '.join(path)}")
                        products.extend(self._extract_products_recursive(current_obj, url, page_type, ' -> '.join(path)))
        
        except Exception as e:
            logger.warning(f"⚠️  Error in Next.js extraction: {e}")
        
        return products
    
    def _extract_from_content_array(self, content_array: List[Any], url: str, page_type: str) -> List[SkyProduct]:
        """Extract products from a content array."""
        products = []
        
        for item in content_array:
            if isinstance(item, dict):
                # Check for direct deals/products in the item
                product_keys = ['deals', 'products', 'items', 'offers', 'packages']
                
                for key in product_keys:
                    if key in item and isinstance(item[key], list):
                        for product_obj in item[key]:
                            if isinstance(product_obj, dict):
                                product = self._create_product_from_object(product_obj, url, page_type)
                                if product:
                                    products.append(product)
                
                # Check if the item itself is a product
                if self._is_potential_product(item):
                    product = self._create_product_from_object(item, url, page_type)
                    if product:
                        products.append(product)
        
        return products
    
    def _extract_products_recursive(self, obj: Any, url: str, page_type: str, path: str, max_depth: int = 8, current_depth: int = 0) -> List[SkyProduct]:
        """Recursively extract products from any JSON structure."""
        products = []
        
        if current_depth > max_depth:
            return products
        
        if isinstance(obj, dict):
            # Check if this object is a product
            if self._is_potential_product(obj):
                product = self._create_product_from_object(obj, url, page_type, path)
                if product:
                    products.append(product)
            
            # Recursively search in values
            for key, value in obj.items():
                new_path = f"{path}.{key}" if path != "root" else key
                products.extend(self._extract_products_recursive(value, url, page_type, new_path, max_depth, current_depth + 1))
        
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                new_path = f"{path}[{i}]"
                products.extend(self._extract_products_recursive(item, url, page_type, new_path, max_depth, current_depth + 1))
        
        return products
    
    def _extract_from_components(self, json_data: Dict[str, Any], url: str, page_type: str) -> List[SkyProduct]:
        """Extract products by looking for specific component types."""
        products = []
        
        def search_components(obj: Any, path: str = "") -> None:
            if isinstance(obj, dict):
                component_key = obj.get('componentKey', '')
                component_type = obj.get('type', '')
                
                # Look for product-related components
                product_components = [
                    'deals', 'products', 'offers', 'packages', 'cards',
                    'productGrid', 'dealCards', 'offerCards', 'productList'
                ]
                
                if component_key in product_components or component_type in product_components:
                    # Extract products from this component
                    for key in ['deals', 'products', 'items', 'offers', 'data']:
                        if key in obj and isinstance(obj[key], list):
                            for product_obj in obj[key]:
                                if isinstance(product_obj, dict):
                                    product = self._create_product_from_object(product_obj, url, page_type, f"{path}.{key}")
                                    if product:
                                        products.append(product)
                
                # Recursively search
                for key, value in obj.items():
                    search_components(value, f"{path}.{key}" if path else key)
            
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    search_components(item, f"{path}[{i}]" if path else f"[{i}]")
        
        search_components(json_data)
        return products
    
    def _extract_by_patterns(self, json_data: Dict[str, Any], url: str, page_type: str) -> List[SkyProduct]:
        """Extract products using pattern matching."""
        products = []
        
        def search_patterns(obj: Any, path: str = "") -> None:
            if isinstance(obj, dict):
                # Pattern 1: Objects with pricing and heading/title
                has_price = any(key in obj for key in ['price', 'pricing', 'cost'])
                has_title = any(key in obj for key in ['heading', 'title', 'name'])
                
                if has_price and has_title:
                    product = self._create_product_from_object(obj, url, page_type, f"{path} (price+title)")
                    if product:
                        products.append(product)
                
                # Pattern 2: Objects with CTA and description
                has_cta = any(key in obj for key in ['cta', 'button', 'link'])
                has_description = any(key in obj for key in ['description', 'bodyText', 'content'])
                
                if has_cta and has_description and self._is_potential_product(obj):
                    product = self._create_product_from_object(obj, url, page_type, f"{path} (cta+desc)")
                    if product:
                        products.append(product)
                
                # Continue searching
                for key, value in obj.items():
                    search_patterns(value, f"{path}.{key}" if path else key)
            
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    search_patterns(item, f"{path}[{i}]" if path else f"[{i}]")
        
        search_patterns(json_data)
        return products
    
    def _create_product_from_object(self, obj: Dict[str, Any], url: str, page_type: str, source_path: str = "") -> Optional[SkyProduct]:
        """Create a SkyProduct from a JSON object."""
        try:
            # Extract basic information
            name = self._extract_name(obj)
            if not name:
                return None  # Skip objects without a name
            
            product_id = obj.get('id', f"product_{hash(str(obj))}")
            
            # Extract category information
            category, sub_category = self._extract_categories(obj, page_type)
            
            # Extract pricing information
            price_info = self._extract_pricing(obj)
            
            # Extract content
            description = self._extract_description(obj)
            
            # Extract features and included items
            features = self._extract_features(obj)
            included_items = self._extract_included_items(obj)
            
            # Extract CTA information
            cta_text, cta_link = self._extract_cta(obj, url)
            
            # Extract media
            media_url = self._extract_media_url(obj)
            
            # Extract additional information
            contract_info = self._extract_contract_info(obj)
            availability = self._extract_availability_info(obj)
            
            # Extract metadata
            metadata = {
                'source_path': source_path,
                'extraction_method': 'json_analysis',
                'object_keys': list(obj.keys()),
                'object_size': len(str(obj))
            }
            
            return SkyProduct(
                id=product_id,
                name=name,
                category=category,
                sub_category=sub_category,
                page_type=page_type,
                source_url=url,
                price=price_info['price'],
                price_display=price_info['display'],
                original_price=price_info['original'],
                discount_info=price_info['discount'],
                primary_label=price_info['primary_label'],
                offer_tag=self._extract_offer_tag(obj),
                description=description,
                features=features,
                included_items=included_items,
                cta_text=cta_text,
                cta_link=cta_link,
                media_url=media_url,
                contract_info=contract_info,
                availability=availability,
                metadata=metadata
            )
        
        except Exception as e:
            logger.warning(f"⚠️  Error creating product from object: {e}")
            return None
    
    def _extract_name(self, obj: Dict[str, Any]) -> str:
        """Extract product name from object."""
        name_keys = ['heading', 'title', 'name', 'productName', 'dealName']
        
        for key in name_keys:
            if key in obj and isinstance(obj[key], str) and obj[key].strip():
                return obj[key].strip()
        
        return ""
    
    def _extract_categories(self, obj: Dict[str, Any], page_type: str) -> Tuple[str, str]:
        """Extract category information."""
        category = ""
        sub_category = ""
        
        # Check for explicit categories
        if 'categories' in obj and isinstance(obj['categories'], dict):
            categories = obj['categories']
            category = categories.get('category', '')
            sub_category = categories.get('subCategory', '')
        
        # If no explicit category, infer from page type and content
        if not category:
            category = page_type.title()
        
        # Look for category clues in the object
        if 'category' in obj:
            category = str(obj['category'])
        
        return category, sub_category
    
    def _extract_pricing(self, obj: Dict[str, Any]) -> Dict[str, str]:
        """Extract comprehensive pricing information."""
        pricing = {
            'price': '',
            'display': '',
            'original': '',
            'discount': '',
            'primary_label': ''
        }
        
        # Look for price object
        if 'price' in obj and isinstance(obj['price'], dict):
            price_obj = obj['price']
            
            price = price_obj.get('price', '')
            prefix = price_obj.get('prefix', '')
            suffix = price_obj.get('suffix', '')
            
            pricing['price'] = price
            pricing['display'] = f"{prefix} {price}{suffix}".strip()
            pricing['original'] = price_obj.get('strikethroughPrice', '')
            pricing['discount'] = price_obj.get('savingAmountText', '')
            
            # Labels
            labels = price_obj.get('labels', {})
            if isinstance(labels, dict):
                pricing['primary_label'] = labels.get('primary', '')
        
        # Look for direct price fields
        elif 'price' in obj and isinstance(obj['price'], str):
            pricing['price'] = obj['price']
            pricing['display'] = obj['price']
        
        return pricing
    
    def _extract_description(self, obj: Dict[str, Any]) -> str:
        """Extract product description."""
        desc_keys = ['description', 'bodyText', 'content', 'subHeading', 'summary']
        
        for key in desc_keys:
            if key in obj and isinstance(obj[key], str) and obj[key].strip():
                return obj[key].strip()
        
        return ""
    
    def _extract_features(self, obj: Dict[str, Any]) -> List[str]:
        """Extract product features."""
        features = []
        
        # Look in subOffers
        if 'subOffers' in obj and isinstance(obj['subOffers'], list):
            for sub_offer in obj['subOffers']:
                if isinstance(sub_offer, dict):
                    # Extract from RTBs (Reasons to Believe)
                    rtbs = sub_offer.get('rtbs', [])
                    for rtb in rtbs:
                        if isinstance(rtb, dict):
                            feature = rtb.get('heading', '') or rtb.get('bodyText', '')
                            if feature and feature not in features:
                                features.append(feature)
        
        # Look for direct features array
        if 'features' in obj and isinstance(obj['features'], list):
            features.extend([f for f in obj['features'] if f is not None and str(f).strip()])
        
        # Look in filters
        if 'filters' in obj and isinstance(obj['filters'], list):
            features.extend([f for f in obj['filters'] if f is not None and str(f).strip()])
        
        return features
    
    def _extract_included_items(self, obj: Dict[str, Any]) -> List[str]:
        """Extract included items/services."""
        included = []
        
        if 'subOffers' in obj and isinstance(obj['subOffers'], list):
            for sub_offer in obj['subOffers']:
                if isinstance(sub_offer, dict):
                    heading = sub_offer.get('heading', '')
                    if heading:
                        included.append(heading)
        
        return included
    
    def _extract_cta(self, obj: Dict[str, Any], base_url: str) -> Tuple[str, str]:
        """Extract call-to-action information."""
        cta_text = ""
        cta_link = ""
        
        if 'cta' in obj and isinstance(obj['cta'], dict):
            cta = obj['cta']
            cta_text = cta.get('text', '')
            cta_link = cta.get('href', '')
            
            # Make relative URLs absolute
            if cta_link and not cta_link.startswith('http'):
                cta_link = urljoin(base_url, cta_link)
        
        return cta_text, cta_link
    
    def _extract_media_url(self, obj: Dict[str, Any]) -> str:
        """Extract media URL."""
        if 'media' in obj and isinstance(obj['media'], dict):
            media = obj['media']
            return media.get('asset', '') or media.get('src', '') or media.get('url', '')
        
        return ""
    
    def _extract_offer_tag(self, obj: Dict[str, Any]) -> str:
        """Extract offer tag."""
        if 'offerTag' in obj and isinstance(obj['offerTag'], dict):
            return obj['offerTag'].get('text', '')
        
        return ""
    
    def _extract_contract_info(self, obj: Dict[str, Any]) -> str:
        """Extract contract information."""
        text_fields = [obj.get('disclaimer', ''), obj.get('price', {}).get('disclaimer', '')]
        full_text = ' '.join(text_fields).lower()
        
        # Look for contract patterns
        patterns = [
            r'(\d+)[-\s]*month\s*contract',
            r'(\d+)[-\s]*month\s*term',
            r'(\d+)m\s*contract'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, full_text)
            if match:
                return f"{match.group(1)}-month contract"
        
        return ""
    
    def _extract_availability_info(self, obj: Dict[str, Any]) -> str:
        """Extract availability information."""
        disclaimer = obj.get('disclaimer', '').lower()
        
        if 'new customers only' in disclaimer:
            return 'New customers only'
        elif 'existing customers' in disclaimer:
            return 'Existing customers'
        
        return 'General availability'
    
    def _remove_duplicate_products(self, products: List[SkyProduct]) -> List[SkyProduct]:
        """Remove duplicate products based on name and price."""
        seen = set()
        unique_products = []
        
        for product in products:
            key = (product.name.lower(), product.price, product.category)
            if key not in seen:
                unique_products.append(product)
                seen.add(key)
        
        logger.info(f"🧹 Removed {len(products) - len(unique_products)} duplicate products")
        return unique_products
    
    def _extract_from_html(self, html_content: str, url: str, page_type: str) -> List[SkyProduct]:
        """Fallback: Extract products from HTML when JSON is not available."""
        logger.info("🔄 Attempting HTML extraction as fallback...")
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            products = []
            
            # Look for common product containers
            selectors = [
                '[data-component*="deal"]',
                '[data-component*="product"]',
                '[class*="deal"]',
                '[class*="product"]',
                '[class*="offer"]',
                '[class*="package"]',
                '.card',
                '.tile',
                '[data-testid*="product"]',
                '[data-testid*="deal"]'
            ]
            
            for selector in selectors:
                elements = soup.select(selector)
                
                for element in elements:
                    # Try to extract basic product info from HTML
                    name = self._extract_text_from_element(element, ['h1', 'h2', 'h3', '[data-testid*="title"]'])
                    price = self._extract_text_from_element(element, ['[data-testid*="price"]', '.price', '[class*="price"]'])
                    
                    if name:
                        product = SkyProduct(
                            id=f"html_{hash(name)}",
                            name=name,
                            category=page_type.title(),
                            sub_category="",
                            page_type=page_type,
                            source_url=url,
                            price=price,
                            price_display=price,
                            original_price="",
                            discount_info="",
                            primary_label="",
                            offer_tag="",
                            description="",
                            features=[],
                            included_items=[],
                            cta_text="",
                            cta_link="",
                            media_url="",
                            contract_info="",
                            availability="",
                            metadata={'extraction_method': 'html_fallback'}
                        )
                        products.append(product)
            
            logger.info(f"📄 Extracted {len(products)} products from HTML")
            return products
            
        except Exception as e:
            logger.error(f"❌ HTML extraction failed: {e}")
            return []
    
    def _extract_text_from_element(self, element, selectors: List[str]) -> str:
        """Extract text from HTML element using selectors."""
        for selector in selectors:
            found = element.select_one(selector)
            if found and found.get_text(strip=True):
                return found.get_text(strip=True)
        return ""
    
    def display_products_summary(self) -> None:
        """Display a comprehensive summary of extracted products."""
        if not self.products:
            logger.warning("❌ No products found to display")
            return
        
        print(f"\n{'=' * 80}")
        print(f"{'UNIVERSAL SKY EXTRACTION RESULTS':^80}")
        print(f"{'=' * 80}")
        
        # Group by category
        categories = {}
        for product in self.products:
            cat = product.category or 'Other'
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(product)
        
        # Display summary statistics
        print(f"\n📊 EXTRACTION SUMMARY:")
        print(f"   • Total products found: {len(self.products)}")
        print(f"   • Categories: {len(categories)}")
        print(f"   • Page type: {self.products[0].page_type if self.products else 'Unknown'}")
        print(f"   • Source: {self.products[0].source_url if self.products else 'Unknown'}")
        
        # Display by category
        for category, cat_products in sorted(categories.items()):
            print(f"\n🏷️  {category.upper()} ({len(cat_products)} products)")
            print("─" * 60)
            
            for i, product in enumerate(cat_products, 1):
                print(f"\n{i}. 📦 {product.name}")
                
                if product.price_display:
                    print(f"   💰 {product.price_display}")
                    if product.original_price:
                        print(f"   🔸 Original: {product.original_price}")
                    if product.discount_info:
                        print(f"   💸 Save: {product.discount_info}")
                
                if product.offer_tag:
                    print(f"   🎯 {product.offer_tag}")
                
                if product.primary_label:
                    print(f"   ℹ️  {product.primary_label}")
                
                if product.contract_info:
                    print(f"   📅 {product.contract_info}")
                
                if product.cta_text:
                    print(f"   🔗 {product.cta_text}")
                
                if product.included_items:
                    items = ', '.join(product.included_items[:3])
                    if len(product.included_items) > 3:
                        items += f" (+{len(product.included_items) - 3} more)"
                    print(f"   📋 Includes: {items}")
                
                if product.features:
                    features = ', '.join(product.features[:2])
                    if len(product.features) > 2:
                        features += f" (+{len(product.features) - 2} more)"
                    print(f"   ✨ Features: {features}")
    
    def save_results(self, base_filename: str) -> None:
        """Save extraction results to multiple formats."""
        if not self.products:
            logger.warning("❌ No products to save")
            return
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save detailed JSON
        json_file = f"{base_filename}_{timestamp}.json"
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump([product.to_dict() for product in self.products], f, indent=2, ensure_ascii=False)
        logger.info(f"💾 Saved detailed JSON: {json_file}")
        
        # Save CSV
        csv_file = f"{base_filename}_{timestamp}.csv"
        df = pd.DataFrame([product.to_dict() for product in self.products])
        df.to_csv(csv_file, index=False, encoding='utf-8')
        logger.info(f"💾 Saved CSV: {csv_file}")
        
        # Save summary report
        report_file = f"{base_filename}_report_{timestamp}.txt"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(f"Universal Sky Extraction Report\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Source URL: {self.products[0].source_url if self.products else 'Unknown'}\n")
            f.write(f"{'=' * 60}\n\n")
            
            f.write(f"Total products extracted: {len(self.products)}\n")
            
            # Category breakdown
            categories = {}
            for product in self.products:
                cat = product.category or 'Other'
                categories[cat] = categories.get(cat, 0) + 1
            
            f.write(f"\nCategory breakdown:\n")
            for cat, count in sorted(categories.items()):
                f.write(f"- {cat}: {count} products\n")
            
            # Extraction methods
            methods = {}
            for product in self.products:
                method = product.metadata.get('extraction_method', 'unknown')
                methods[method] = methods.get(method, 0) + 1
            
            f.write(f"\nExtraction methods:\n")
            for method, count in methods.items():
                f.write(f"- {method}: {count} products\n")
        
        logger.info(f"📄 Saved report: {report_file}")

def main():
    """Main execution function with example usage."""
    
    # Example URLs to test
    test_urls = [
        "https://www.sky.com/deals",
        "https://www.sky.com/tv",
        "https://www.sky.com/broadband",
        "https://www.sky.com/mobile",
        "https://www.sky.com/tv/sky-glass"
    ]
    
    print("🚀 Universal Sky Extractor")
    print("=" * 50)
    
    # Get URL from user or use default
    url = input(f"Enter Sky URL to extract from (or press Enter for deals page): ").strip()
    if not url:
        url = "https://www.sky.com/deals"
    
    print(f"\n🎯 Extracting from: {url}")
    
    # Create extractor and run
    extractor = UniversalSkyExtractor()
    products = extractor.extract_from_url(url)
    
    if products:
        # Display results
        extractor.display_products_summary()
        
        # Save results
        output_base = r"c:\Users\nji562\Downloads\ExpDesign\sky_universal_extraction"
        extractor.save_results(output_base)
        
        print(f"\n🎉 Extraction completed successfully!")
        print(f"📈 Found {len(products)} products from {url}")
    
    else:
        print("\n❌ No products were extracted")
        print("   • Check if the URL is accessible")
        print("   • Verify the page contains product data")
        print("   • Try a different Sky page")

if __name__ == "__main__":
    main()