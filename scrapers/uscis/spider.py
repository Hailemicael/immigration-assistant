import scrapy
from bs4 import BeautifulSoup
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class USCISSpider(scrapy.Spider):
    name = "uscis_spider"
    start_urls = [
        "https://www.uscis.gov/forms",
        "https://www.uscis.gov/green-card",
        "https://www.uscis.gov/citizenship",
    ]
    
    custom_settings = {
        'USER_AGENT': 'Mozilla/5.0 (compatible; ImmigrationAssistBot/1.0)',
        'ROBOTSTXT_OBEY': True,
        'DOWNLOAD_DELAY': 1.5,  # Be respectful to the servers
    }
    
    def parse(self, response):
        logger.info(f"Parsing page: {response.url}")
        
        # Extract content from the current page
        content = self.extract_content(response)
        
        # Store the extracted content if it exists
        if content:
            yield {
                'url': response.url,
                'title': content['title'],
                'text': content['text'],
                'metadata': content['metadata'],
                'timestamp': content['timestamp']
            }
        
        # Follow links to other relevant pages (limiting depth for testing)
        if self.current_depth < 2:  # Limit depth for initial testing
            for link in response.css('a::attr(href)').getall():
                if self.is_relevant_link(link):
                    yield response.follow(link, self.parse)
    
    def extract_content(self, response):
        # Parse with BeautifulSoup
        soup = BeautifulSoup(response.body, 'html.parser')
        
        # Extract title
        title = soup.title.string.strip() if soup.title else ""
        
        # Extract main content - adjust selectors based on USCIS website structure
        main_content = soup.select_one('main, .main-content, .page-content, article')
        
        if not main_content:
            return None
        
        # Remove navigation, footers, etc.
        for element in main_content.select('nav, footer, .navigation, .menu'):
            element.extract()
        
        # Extract text
        text = main_content.get_text(separator='\n', strip=True)
        
        # Extract metadata (form numbers, processing times, etc.)
        metadata = self.extract_metadata(soup)
        
        return {
            'title': title,
            'text': text,
            'metadata': metadata,
            'timestamp': datetime.now().isoformat()
        }
    
    def extract_metadata(self, soup):
        metadata = {}
        
        # Extract form numbers (adjust selectors based on USCIS site structure)
        form_elements = soup.select('.form-number, .document-number, h1, h2')
        for element in form_elements:
            text = element.get_text(strip=True)
            if "Form " in text and "-" in text:
                metadata['form_number'] = text
                break
        
        # Extract filing fees if available
        fee_text = soup.find(string=lambda text: "fee" in text.lower() and "$" in text)
        if fee_text:
            metadata['filing_fee'] = fee_text
        
        return metadata
    
    def is_relevant_link(self, link):
        # Only follow internal USCIS links
        if not link.startswith('http'):
            return True
            
        relevant_patterns = [
            'uscis.gov/forms', 
            'uscis.gov/green-card',
            'uscis.gov/citizenship',
        ]
        
        return any(pattern in link for pattern in relevant_patterns)