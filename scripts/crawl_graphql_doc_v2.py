import requests
from bs4 import BeautifulSoup
import json
import os
import re
from urllib.parse import urljoin, urlparse
import time
from collections import defaultdict

class WarcraftLogsAPICrawler:
    def __init__(self, base_url, max_depth=5, output_dir="warcraftlogs_docs"):
        self.base_url = base_url
        self.max_depth = max_depth
        self.output_dir = output_dir
        self.visited = set()
        self.data = defaultdict(dict)
        
        # Create output directory if it doesn't exist
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
    
    def get_soup(self, url):
        """Fetch a URL and return a BeautifulSoup object."""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            return BeautifulSoup(response.text, 'html.parser'), response.text
        except Exception as e:
            print(f"Error fetching {url}: {e}")
            return None, None
    
    def is_valid_url(self, url):
        """Check if the URL is a valid documentation page and hasn't been visited."""
        if url in self.visited:
            return False
        
        # Check if the URL is part of the API documentation
        return url.startswith(self.base_url) and (url.endswith('.html') or url.endswith('.doc.html'))
    
    def extract_text(self, soup):
        """Extract useful text content from the soup."""
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.extract()
        
        # Get text
        text = soup.get_text(separator=' ', strip=True)
        
        # Clean up whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = '\n'.join(chunk for chunk in chunks if chunk)
        
        return text
    
    def extract_links(self, soup, current_url):
        """Extract links from the page."""
        links = []
        
        if not soup:
            return links
            
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href']
            
            # Convert relative URL to absolute
            if not href.startswith('http'):
                href = urljoin(self.base_url, href)
            
            # Check if it's a valid URL
            if self.is_valid_url(href):
                links.append(href)
                
        return links
    
    def find_all_reference_pages(self):
        """Get all reference pages from the base URL."""
        print(f"Finding all reference pages from {self.base_url}")
        soup, _ = self.get_soup(self.base_url)
        
        if not soup:
            print(f"Failed to fetch the base URL: {self.base_url}")
            return []
        
        # Get all hrefs from the page
        hrefs = [a['href'] for a in soup.find_all('a', href=True)]
        
        # Filter out external links and construct full URLs
        reference_pages = []
        for href in hrefs:
            if href.startswith('http'):
                # Only keep if it's part of our documentation
                if href.startswith(self.base_url):
                    reference_pages.append(href)
            else:
                # It's a relative URL, join with base URL
                full_url = urljoin(self.base_url, href)
                reference_pages.append(full_url)
        
        # Filter valid URLs (those ending with .html or .doc.html)
        valid_references = [url for url in reference_pages if self.is_valid_url(url)]
        
        print(f"Found {len(valid_references)} reference pages")
        return valid_references
    
    def crawl(self, url=None, depth=0):
        """Crawl the website up to max_depth."""
        if depth > self.max_depth:
            return
            
        if url in self.visited:
            return
            
        print(f"Crawling: {url} (Depth: {depth})")
        self.visited.add(url)
        
        # Get the page content
        soup, raw_html = self.get_soup(url)
        if not soup:
            return
            
        # Extract text
        text = self.extract_text(soup)
        
        # Save the data
        self.data[url] = {
            "raw_html": raw_html,
            "text": text
        }
        
        # Save to file as we go to avoid data loss on crashes
        self.save_to_file(url)
        
        # Extract and follow links
        links = self.extract_links(soup, url)
        
        for link in links:
            # Add a small delay to be nice to the server
            time.sleep(0.5)
            self.crawl(link, depth + 1)
    
    def save_to_file(self, url):
        """Save the data for a URL to a file."""
        # Create a filename from the URL
        # Strip the base URL to get just the relative path
        relative_path = url.replace(self.base_url, '')
        filename = re.sub(r'[^a-zA-Z0-9]', '_', relative_path) + '.json'
        filepath = os.path.join(self.output_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.data[url], f, ensure_ascii=False, indent=4)
    
    def save_all(self):
        """Save all data to a single JSON file."""
        all_data_path = os.path.join(self.output_dir, 'all_data.json')
        with open(all_data_path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=4)
        
        print(f"Saved all data to {all_data_path}")
        print(f"Crawled {len(self.visited)} pages")
    
    def run(self):
        """Run the crawler starting from all reference pages."""
        # First, find all reference pages from the base URL
        reference_pages = self.find_all_reference_pages()
        
        # Then crawl each reference page
        for page in reference_pages:
            self.crawl(page)
        
        # Save all the data
        self.save_all()

if __name__ == "__main__":
    base_url = "https://www.warcraftlogs.com/v2-api-docs/warcraft/"
    crawler = WarcraftLogsAPICrawler(base_url)
    crawler.run()