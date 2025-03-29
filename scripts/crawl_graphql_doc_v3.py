import requests
from bs4 import BeautifulSoup
import json
import os
import re
from urllib.parse import urljoin
import time
from collections import deque

class WarcraftLogsAPICrawler:
    def __init__(self, base_url, max_depth=5, output_dir="warcraftlogs_docs"):
        self.base_url = base_url
        self.max_depth = max_depth
        self.output_dir = output_dir
        self.visited = set()
        self.data = {}  # URL -> {raw_html, text}
        
        # Create output directory if it doesn't exist
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
    
    def get_page_content(self, url):
        """Fetch a URL and return soup and raw HTML."""
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
        """Check if URL is a valid documentation page and hasn't been visited."""
        if url in self.visited:
            return False
        
        # Check if URL is part of API documentation
        return url.startswith(self.base_url) and (url.endswith('.html') or url.endswith('.doc.html'))
    
    def extract_text(self, soup):
        """Extract useful text content from the soup."""
        if not soup:
            return ""
            
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
        """Extract valid links from the page."""
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
    
    def crawl_breadth_first(self):
        """Crawl the website using breadth-first approach up to max_depth."""
        # Queue of (url, depth) pairs
        queue = deque([(self.base_url, 1)])
        
        while queue:
            url, depth = queue.popleft()
            
            if depth > self.max_depth:
                continue
                
            if url in self.visited:
                continue
                
            print(f"Crawling: {url} (Depth: {depth})")
            self.visited.add(url)
            
            # Get the page content
            soup, raw_html = self.get_page_content(url)
            if not soup:
                continue
                
            # Extract text
            text = self.extract_text(soup)
            
            # Save the data
            self.data[url] = {
                "raw_html": raw_html,
                "text": text
            }
            
            # Extract and queue links for next depth
            links = self.extract_links(soup, url)
            for link in links:
                if link not in self.visited:
                    queue.append((link, depth + 1))
            
            # Add a small delay to be nice to the server
            time.sleep(0.5)
    
    def save_data(self):
        """Save all data to a single JSON file."""
        output_path = os.path.join(self.output_dir, 'warcraftlogs_api_docs.json')
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=4)
        
        print(f"Saved all data to {output_path}")
        print(f"Crawled {len(self.visited)} pages")

if __name__ == "__main__":
    base_url = "https://www.warcraftlogs.com/v2-api-docs/warcraft/"
    crawler = WarcraftLogsAPICrawler(base_url)
    crawler.crawl_breadth_first()
    crawler.save_data()