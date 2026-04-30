"""
Advanced web scraping utilities for sports company leads.
Multi-page email extraction with validation and duplicate prevention.
"""

import re
import time
import logging
import requests
import dns.resolver
import random
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from typing import List, Dict, Set, Optional, Tuple
from django.core.validators import URLValidator
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)

# User agent handling with fallback
DEFAULT_USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15',
]

try:
    from fake_useragent import UserAgent
    ua = UserAgent(fallback=random.choice(DEFAULT_USER_AGENTS))
except Exception:
    # Fallback if fake_useragent fails or isn't installed
    class FakeUserAgent:
        def __init__(self):
            self.agents = DEFAULT_USER_AGENTS
        @property
        def random(self):
            return random.choice(self.agents)
    ua = FakeUserAgent()

# Email validation handling with fallback
try:
    from email_validator import validate_email as _validate_email_lib, EmailNotValidError
    EMAIL_VALIDATOR_AVAILABLE = True
except ImportError:
    EMAIL_VALIDATOR_AVAILABLE = False
    EmailNotValidError = Exception


class ScrapingError(Exception):
    """Custom exception for scraping errors"""
    pass


class EmailExtractor:
    """
    Advanced email extraction with multi-page crawling and validation.
    """
    
    # Common email patterns to filter out
    INVALID_PATTERNS = [
        r'\.png$', r'\.jpg$', r'\.gif$', r'\.css$', r'\.js$',
        r'^noreply@', r'^no-reply@', r'^donotreply@', r'^admin@',
        r'^webmaster@', r'^info@.*\.(com|net|org)$',
        r'example\.com', r'test\.com', r'domain\.com',
        r'screenshot', r'image', r'photo', r'logo',
    ]
    
    # Priority pages to check for contact info
    CONTACT_PATHS = [
        '/contact', '/contact-us', '/about', '/about-us',
        '/team', '/staff', '/people', '/support', '/help',
        '/careers', '/jobs', '/partners', '/partnerships',
    ]
    
    def __init__(self, max_pages: int = 5, delay: float = 1.0, timeout: int = 10):
        self.max_pages = max_pages
        self.delay = delay
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
        })
        self.scraped_urls: Set[str] = set()
        self.all_emails: Set[str] = set()
        
    def _get_headers(self) -> Dict[str, str]:
        """Generate random headers for each request"""
        return {
            'User-Agent': ua.random,
            'Referer': 'https://www.google.com/',
        }
    
    def _is_valid_url(self, url: str) -> bool:
        """Validate URL format"""
        try:
            validator = URLValidator()
            validator(url)
            return True
        except ValidationError:
            return False
    
    def _is_valid_email(self, email: str) -> Tuple[bool, Optional[str]]:
        """
        Validate email format and check deliverability.
        Returns (is_valid, normalized_email).
        """
        # Check against invalid patterns first
        for pattern in self.INVALID_PATTERNS:
            if re.search(pattern, email, re.IGNORECASE):
                return False, None
        
        # Basic regex validation
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            return False, None
        
        # Use email_validator library if available
        if EMAIL_VALIDATOR_AVAILABLE:
            try:
                validation = _validate_email_lib(email, check_deliverability=False)
                normalized = validation.normalized
                return True, normalized
            except EmailNotValidError:
                return False, None
            except Exception as e:
                logger.debug(f"Email validation error for {email}: {e}")
                return False, None
        else:
            # Fallback: basic validation only
            normalized = email.lower().strip()
            # Check domain has at least one dot and valid characters
            domain = normalized.split('@')[1]
            if '.' not in domain or domain.startswith('.') or domain.endswith('.'):
                return False, None
            return True, normalized
    
    def _extract_emails_from_text(self, text: str) -> Set[str]:
        """Extract emails from text using regex patterns"""
        # Comprehensive email regex pattern
        email_pattern = re.compile(
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            re.IGNORECASE
        )
        
        # Also look for obfuscated emails
        # Pattern 1: email [at] domain [dot] com
        obfuscated_pattern1 = re.compile(
            r'([A-Za-z0-9._%+-]+)\s*\[?\s*at\s*\]?\s*([A-Za-z0-9.-]+)\s*\[?\s*dot\s*\]?\s*([A-Za-z]{2,})',
            re.IGNORECASE
        )
        
        # Pattern 2: email (at) domain (dot) com
        obfuscated_pattern2 = re.compile(
            r'([A-Za-z0-9._%+-]+)\s*\(?\s*at\s*\)?\s*([A-Za-z0-9.-]+)\s*\(?\s*dot\s*\)?\s*([A-Za-z]{2,})',
            re.IGNORECASE
        )
        
        # Pattern 3: email@domain[.]com with encoded characters
        encoded_pattern = re.compile(
            r'([A-Za-z0-9._%+-]+@)([A-Za-z0-9.-]+)\s*\[?\.\]?\s*([A-Za-z]{2,})',
            re.IGNORECASE
        )
        
        emails = set()
        
        # Standard emails
        for match in email_pattern.findall(text):
            emails.add(match.lower().strip())
        
        # Obfuscated emails - pattern 1
        for match in obfuscated_pattern1.findall(text):
            email = f"{match[0]}@{match[1]}.{match[2]}".lower()
            emails.add(email)
        
        # Obfuscated emails - pattern 2
        for match in obfuscated_pattern2.findall(text):
            email = f"{match[0]}@{match[1]}.{match[2]}".lower()
            emails.add(email)
        
        # Encoded emails
        for match in encoded_pattern.findall(text):
            email = f"{match[0]}{match[1]}.{match[2]}".lower()
            emails.add(email)
        
        return emails
    
    def _extract_emails_from_html(self, soup: BeautifulSoup) -> Set[str]:
        """Extract emails from BeautifulSoup parsed HTML"""
        emails = set()
        
        # Extract from mailto: links
        for link in soup.find_all('a', href=True):
            href = link['href']
            if href.startswith('mailto:'):
                email = href[7:].split('?')[0].lower().strip()
                if email and '@' in email:
                    emails.add(email)
        
        # Extract from all text content
        text = soup.get_text(separator=' ', strip=True)
        emails.update(self._extract_emails_from_text(text))
        
        # Look for emails in specific attributes
        for tag in soup.find_all(['a', 'span', 'div', 'p', 'li']):
            for attr in ['data-email', 'data-contact', 'data-mail']:
                if tag.get(attr):
                    potential = tag.get(attr).lower().strip()
                    if '@' in potential and '.' in potential:
                        emails.add(potential)
        
        return emails
    
    def _get_contact_urls(self, base_url: str, soup: BeautifulSoup) -> List[str]:
        """Generate potential contact page URLs from a page"""
        contact_urls = []
        parsed_base = urlparse(base_url)
        base_domain = f"{parsed_base.scheme}://{parsed_base.netloc}"
        
        for path in self.CONTACT_PATHS:
            full_url = urljoin(base_domain, path)
            if full_url not in self.scraped_urls:
                contact_urls.append(full_url)
        
        # Also look for contact links on the page
        for link in soup.find_all('a', href=True):
            href = link['href'].lower()
            text = link.get_text(strip=True).lower()
            
            # Check if link text or href suggests contact info
            contact_keywords = ['contact', 'about', 'team', 'careers', 'support']
            if any(keyword in href or keyword in text for keyword in contact_keywords):
                full_url = urljoin(base_url, link['href'])
                # Only follow links on same domain
                if urlparse(full_url).netloc == parsed_base.netloc:
                    if full_url not in self.scraped_urls and full_url not in contact_urls:
                        contact_urls.append(full_url)
        
        return contact_urls[:self.max_pages - 1]  # Limit additional pages

    def _extract_phones_from_html(self, soup: BeautifulSoup) -> Set[str]:
        """Extract phone numbers from BeautifulSoup parsed HTML"""
        phones = set()
        
        # Pattern for international phone numbers
        phone_patterns = [
            # International format: +1 (555) 123-4567, +44 20 7946 0958
            r'\+\d{1,4}[\s\-\.]?\(?\d{1,4}\)?[\s\-\.]?\d{1,4}[\s\-\.]?\d{1,4}[\s\-\.]?\d{1,4}',
            # US format: (555) 123-4567, 555-123-4567
            r'\(?\d{3}\)?[\s\-\.]?\d{3}[\s\-\.]?\d{4}',
            # European format with country code
            r'\+\d{2}[\s\-\.]?\d{3}[\s\-\.]?\d{3}[\s\-\.]?\d{3,4}',
        ]
        
        # Extract from tel: links
        for link in soup.find_all('a', href=True):
            href = link['href']
            if href.startswith('tel:'):
                phone = href[4:].split('?')[0].strip()
                # Clean up the phone number
                phone = re.sub(r'[^\d\+\-\(\)\s]', '', phone)
                if len(phone) >= 7:
                    phones.add(phone)
        
        # Extract from text content
        text = soup.get_text(separator=' ', strip=True)
        
        for pattern in phone_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                # Clean up the phone number
                cleaned = re.sub(r'[^\d\+\-\(\)\s]', '', match).strip()
                if len(cleaned) >= 7 and len(cleaned) <= 25:
                    phones.add(cleaned)
        
        # Look for phone numbers in specific attributes
        for tag in soup.find_all(['a', 'span', 'div', 'p', 'li']):
            for attr in ['data-phone', 'data-tel', 'data-contact-phone']:
                if tag.get(attr):
                    potential = tag.get(attr).strip()
                    cleaned = re.sub(r'[^\d\+\-\(\)\s]', '', potential)
                    if len(cleaned) >= 7:
                        phones.add(cleaned)
        
        return phones

    def _extract_social_media_from_html(self, soup: BeautifulSoup, base_url: str) -> Dict[str, str]:
        """Extract social media links from BeautifulSoup parsed HTML"""
        social_links = {
            'linkedin': '',
            'facebook': '',
            'instagram': '',
            'twitter': '',
            'youtube': '',
        }
        
        parsed_base = urlparse(base_url)
        
        # Social media domains to look for
        social_patterns = {
            'linkedin': r'linkedin\.com',
            'facebook': r'facebook\.com|fb\.com',
            'instagram': r'instagram\.com|instagr\.am',
            'twitter': r'twitter\.com|x\.com',
            'youtube': r'youtube\.com|youtu\.be',
        }
        
        for link in soup.find_all('a', href=True):
            href = link['href']
            
            # Handle relative URLs
            if href.startswith('/'):
                href = urljoin(base_url, href)
            
            # Check each social platform
            for platform, pattern in social_patterns.items():
                if re.search(pattern, href, re.IGNORECASE):
                    # Clean up the URL
                    if not social_links[platform]:  # Only take first found
                        social_links[platform] = href
                    break
        
        return social_links

    def _extract_country_city_from_html(self, soup: BeautifulSoup) -> Dict[str, str]:
        """Extract country and city information from HTML"""
        location_info = {
            'country': '',
            'city': '',
        }
        
        # Common patterns for address/location
        address_keywords = ['address', 'location', 'headquarters', 'office', 'contact']
        
        # Look for address elements
        for tag in soup.find_all(['div', 'p', 'span', 'address']):
            text = tag.get_text(strip=True).lower()
            
            # Check if it contains address keywords
            if any(keyword in text for keyword in address_keywords):
                # Try to extract country from common patterns
                country_patterns = [
                    r'(?:USA|United States|UK|United Kingdom|Germany|France|Italy|Spain|',
                    r'Canada|Australia|Japan|China|India|Pakistan|Brazil|Mexico|',
                    r'Netherlands|Belgium|Switzerland|Austria|Sweden|Norway|Denmark)',
                ]
                
                full_pattern = '|'.join(country_patterns)
                match = re.search(full_pattern, text, re.IGNORECASE)
                if match:
                    location_info['country'] = match.group(0)
                
                # Try to find city (often before country or after "in")
                city_match = re.search(r'(?:in|at)\s+([A-Z][a-zA-Z\s]+?)(?:,|\s+(?:USA|UK|Germany))', text)
                if city_match:
                    location_info['city'] = city_match.group(1).strip()
        
        # Look for schema.org address data
        for tag in soup.find_all(attrs={"itemtype": re.compile(r'schema\.org/PostalAddress|schema\.org/Place')}):
            country_tag = tag.find(attrs={"itemprop": "addressCountry"})
            if country_tag:
                location_info['country'] = country_tag.get_text(strip=True)
            
            city_tag = tag.find(attrs={"itemprop": "addressLocality"})
            if city_tag:
                location_info['city'] = city_tag.get_text(strip=True)
        
        return location_info
    
    def _fetch_page(self, url: str) -> Optional[BeautifulSoup]:
        """Fetch and parse a single page"""
        if not self._is_valid_url(url):
            logger.warning(f"Invalid URL: {url}")
            return None
        
        try:
            logger.info(f"Fetching: {url}")
            response = self.session.get(
                url,
                headers=self._get_headers(),
                timeout=self.timeout,
                allow_redirects=True
            )
            response.raise_for_status()
            
            # Check if content is HTML
            content_type = response.headers.get('content-type', '').lower()
            if 'text/html' not in content_type:
                logger.debug(f"Non-HTML content at {url}: {content_type}")
                return None
            
            soup = BeautifulSoup(response.content, 'lxml')
            self.scraped_urls.add(url)
            
            # Politeness delay
            time.sleep(self.delay)
            
            return soup
            
        except requests.exceptions.RequestException as e:
            logger.warning(f"Request failed for {url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return None
    
    def extract_from_website(self, website_url: str) -> Dict:
        """
        Main method to extract emails, phones, and social media from a website.
        Crawls homepage + contact pages.
        
        Returns dict with:
        - emails: List of valid unique emails
        - phones: List of phone numbers found
        - social_media: Dict with social media links (linkedin, facebook, instagram, etc.)
        - country: Country extracted from address
        - city: City extracted from address
        - scraped_pages: List of URLs crawled
        - errors: List of any errors encountered
        """
        results = {
            'emails': [],
            'phones': [],
            'social_media': {'linkedin': '', 'facebook': '', 'instagram': '', 'twitter': '', 'youtube': ''},
            'country': '',
            'city': '',
            'scraped_pages': [],
            'errors': [],
            'domain': None,
        }
        
        # Normalize URL
        if not website_url.startswith(('http://', 'https://')):
            website_url = f"https://{website_url}"
        
        parsed = urlparse(website_url)
        results['domain'] = parsed.netloc
        
        # Initialize collectors
        all_phones = set()
        all_social = {'linkedin': '', 'facebook': '', 'instagram': '', 'twitter': '', 'youtube': ''}
        all_emails = set()
        
        # Fetch homepage
        homepage_soup = self._fetch_page(website_url)
        if not homepage_soup:
            results['errors'].append(f"Failed to fetch homepage: {website_url}")
            return results
        
        # Extract from homepage
        homepage_emails = self._extract_emails_from_html(homepage_soup)
        all_emails.update(homepage_emails)
        
        homepage_phones = self._extract_phones_from_html(homepage_soup)
        all_phones.update(homepage_phones)
        
        homepage_social = self._extract_social_media_from_html(homepage_soup, website_url)
        for key, value in homepage_social.items():
            if value and not all_social[key]:
                all_social[key] = value
        
        homepage_location = self._extract_country_city_from_html(homepage_soup)
        if homepage_location['country']:
            results['country'] = homepage_location['country']
        if homepage_location['city']:
            results['city'] = homepage_location['city']
        
        results['scraped_pages'].append(website_url)
        
        # Find and crawl contact pages
        contact_urls = self._get_contact_urls(website_url, homepage_soup)
        
        for url in contact_urls:
            soup = self._fetch_page(url)
            if soup:
                # Extract emails
                page_emails = self._extract_emails_from_html(soup)
                all_emails.update(page_emails)
                
                # Extract phones
                page_phones = self._extract_phones_from_html(soup)
                all_phones.update(page_phones)
                
                # Extract social media
                page_social = self._extract_social_media_from_html(soup, url)
                for key, value in page_social.items():
                    if value and not all_social[key]:
                        all_social[key] = value
                
                # Extract location info
                page_location = self._extract_country_city_from_html(soup)
                if page_location['country'] and not results['country']:
                    results['country'] = page_location['country']
                if page_location['city'] and not results['city']:
                    results['city'] = page_location['city']
                
                results['scraped_pages'].append(url)
        
        # Validate all collected emails
        valid_emails = []
        for email in all_emails:
            is_valid, normalized = self._is_valid_email(email)
            if is_valid and normalized:
                valid_emails.append(normalized)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_emails = []
        for email in valid_emails:
            if email not in seen:
                seen.add(email)
                unique_emails.append(email)
        
        results['emails'] = unique_emails
        results['phones'] = list(all_phones)
        results['social_media'] = all_social
        
        logger.info(f"Extracted {len(unique_emails)} emails, {len(all_phones)} phones from {results['domain']}")
        
        return results


class CompanySearcher:
    """
    Search for sports companies using search engines.
    """
    
    def __init__(self, delay: float = 2.0):
        self.delay = delay
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        })
    
    def search_duckduckgo(self, query: str, max_results: int = 10) -> List[Dict]:
        """
        Search DuckDuckGo for companies.
        Note: This is a basic implementation. For production, consider using
        SerpAPI, Google Custom Search API, or other reliable search services.
        """
        results = []
        
        try:
            # DuckDuckGo HTML interface
            url = "https://html.duckduckgo.com/html/"
            params = {'q': query}
            
            headers = {
                'User-Agent': ua.random,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            }
            
            response = self.session.get(url, params=params, headers=headers, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'lxml')
            
            # Parse search results
            for result in soup.find_all('div', class_='result'):
                try:
                    # Extract title and link
                    title_elem = result.find('a', class_='result__a')
                    if not title_elem:
                        continue
                    
                    title = title_elem.get_text(strip=True)
                    link = title_elem.get('href', '')
                    
                    # DuckDuckGo redirects through their domain
                    if link.startswith('/'):
                        # Extract actual URL from DuckDuckGo redirect
                        match = re.search(r'uddg=([^&]+)', link)
                        if match:
                            import urllib.parse
                            link = urllib.parse.unquote(match.group(1))
                    
                    # Skip certain domains
                    skip_domains = [
                        'wikipedia.org', 'facebook.com', 'twitter.com',
                        'instagram.com', 'linkedin.com', 'youtube.com',
                        'pinterest.com', 'amazon.com', 'ebay.com',
                    ]
                    
                    parsed = urlparse(link)
                    if any(domain in parsed.netloc for domain in skip_domains):
                        continue
                    
                    # Extract snippet
                    snippet_elem = result.find('a', class_='result__snippet')
                    snippet = snippet_elem.get_text(strip=True) if snippet_elem else ''
                    
                    results.append({
                        'name': title,
                        'website': link,
                        'snippet': snippet,
                        'source': 'duckduckgo',
                    })
                    
                    if len(results) >= max_results:
                        break
                        
                except Exception as e:
                    logger.debug(f"Error parsing result: {e}")
                    continue
            
            time.sleep(self.delay)
            
        except Exception as e:
            logger.error(f"Search error: {e}")
        
        return results
    
    def search_sports_companies(self, sport_type: str = "sports", 
                                location: str = None,
                                max_results: int = 20) -> List[Dict]:
        """
        Search for sports companies with customizable parameters.
        """
        if location:
            query = f"{sport_type} sports company manufacturer supplier {location}"
        else:
            query = f"{sport_type} sports company manufacturer supplier wholesale"
        
        return self.search_duckduckgo(query, max_results)


def extract_emails_from_website(website_url: str, 
                                 max_pages: int = 5,
                                 delay: float = 1.0) -> Dict:
    """
    Convenience function to extract emails from a website.
    
    Args:
        website_url: URL to scrape
        max_pages: Maximum pages to crawl (homepage + contact pages)
        delay: Delay between requests in seconds
    
    Returns:
        Dict with emails, scraped_pages, errors, domain
    """
    extractor = EmailExtractor(max_pages=max_pages, delay=delay)
    return extractor.extract_from_website(website_url)


def validate_and_normalize_email(email: str) -> Tuple[bool, Optional[str]]:
    """
    Standalone email validation function.

    Args:
        email: Email address to validate

    Returns:
        Tuple of (is_valid, normalized_email)
    """
    extractor = EmailExtractor()
    return extractor._is_valid_email(email)
