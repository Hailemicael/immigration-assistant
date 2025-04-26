from scrapy.crawler import CrawlerProcess
from scrapers.uscis.spider import USCISSpider
import json
import os

def run_crawler():
    # Create data directory if it doesn't exist
    os.makedirs('data', exist_ok=True)
    
    # Configure the output
    output_file = 'data/uscis_data.jsonl'
    
    # Initialize the crawler process
    process = CrawlerProcess(settings={
        'FEEDS': {
            output_file: {
                'format': 'jsonlines',
                'encoding': 'utf8',
                'overwrite': True
            }
        },
        'LOG_LEVEL': 'INFO'
    })
    
    # Start the crawler
    process.crawl(USCISSpider)
    process.start()
    
    print(f"Crawler completed. Data saved to {output_file}")

if __name__ == "__main__":
    run_crawler()