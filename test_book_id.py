import os
import asyncio
import aiohttp
import urllib.parse
from pathlib import Path
from docx import Document
from dotenv import load_dotenv
import re
import logging

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class BookTitleTester:
    def __init__(self):
        self.auth_token = os.getenv("AUTH_TOKEN")
        self.api_base_url = os.getenv("API_BASE_URL", "https://ashlynprasad-backend.vercel.app/api/v1")
        self.multiple_books_file = Path("Multiple books.docx")
        
        if not self.auth_token:
            raise ValueError("AUTH_TOKEN not found in environment variables")
    
    def extract_text_from_docx(self, file_path: Path) -> str:
        """Extract text content from a DOCX file."""
        try:
            document = Document(file_path)
            paragraphs = [para.text.strip() for para in document.paragraphs if para.text.strip()]
            return "\n".join(paragraphs)
        except Exception as e:
            logger.error(f"Error extracting text from {file_path}: {e}")
            return ""
    
    def parse_book_titles(self, content: str) -> list:
        """Parse the multiple books document and extract book titles."""
        titles = []
        
        # Split content by book pattern
        book_pattern = r'(Book\s+\d+\s+[^\[\n]+\s+\[[^\]]+\])'
        sections = re.split(book_pattern, content)
        
        # Process sections to extract titles
        for i in range(1, len(sections), 2):
            book_header = sections[i].strip()
            header_match = re.match(r'Book\s+(\d+)\s+([^\[]+?)\s+\[([^\]]+)\]', book_header)
            if header_match:
                book_number = header_match.group(1)
                title = header_match.group(2).strip()
                author = header_match.group(3).strip().replace('"', '')
                
                # Clean up title - handle apostrophes and other special characters
                title = title.replace("'", "'")
                title = re.sub(r'\s+', ' ', title)
                
                titles.append({
                    'book_number': book_number,
                    'title': title,
                    'author': author
                })
        
        return titles
    
    async def test_book_lookup(self, session: aiohttp.ClientSession, book_info: dict) -> dict:
        """Test book lookup for a single book."""
        title = book_info['title']
        book_number = book_info['book_number']
        author = book_info['author']
        
        result = {
            'book_number': book_number,
            'title': title,
            'author': author,
            'found': False,
            'book_id': None,
            'api_title': None,
            'error': None
        }
        
        try:
            # Handle "Let's" titles by removing "Let's" prefix
            search_title = title
            if title.startswith("Let's "):
                search_title = title[6:]  # Remove "Let's " (6 characters)
                logger.info(f"Modified title from '{title}' to '{search_title}' (removed Let's prefix)")
            
            # First attempt with processed title
            encoded_title = urllib.parse.quote(search_title, safe='')
            url = f"{self.api_base_url}/books/by-title?title={encoded_title}"
            headers = {
                "Authorization": self.auth_token,
                "Content-Type": "application/json"
            }
            
            logger.info(f"Testing Book {book_number}: '{title}' -> searching for: '{search_title}'")
            
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("success") and data.get("result"):
                        books = data["result"]
                        book_list = [item for item in books if isinstance(item, dict) and 'nid' in item]
                        if book_list:
                            result['found'] = True
                            result['book_id'] = book_list[0].get('nid')
                            result['api_title'] = book_list[0].get('title')
                            logger.info(f"✅ Found: {result['api_title']} (ID: {result['book_id']})")
                            return result
                elif response.status == 404:
                    logger.warning(f"❌ Book not found (404): '{title}'")
                else:
                    error_text = await response.text()
                    logger.warning(f"❌ API error {response.status}: {error_text}")
                    result['error'] = f"HTTP {response.status}"
            
            # If first attempt fails, try with simplified title (remove special characters)
            simplified_title = re.sub(r'[^\w\s]', '', search_title).strip()
            if simplified_title != search_title:
                logger.info(f"🔄 Retrying with simplified title: '{simplified_title}'")
                encoded_simplified = urllib.parse.quote(simplified_title, safe='')
                url_simplified = f"{self.api_base_url}/books/by-title?title={encoded_simplified}"
                
                async with session.get(url_simplified, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("success") and data.get("result"):
                            books = data["result"]
                            book_list = [item for item in books if isinstance(item, dict) and 'nid' in item]
                            if book_list:
                                result['found'] = True
                                result['book_id'] = book_list[0].get('nid')
                                result['api_title'] = book_list[0].get('title')
                                logger.info(f"✅ Found with simplified title: {result['api_title']} (ID: {result['book_id']})")
                                return result
            
            logger.error(f"❌ Failed to find book: '{title}'")
            result['error'] = "Not found"
            
        except Exception as e:
            logger.error(f"❌ Exception testing book '{title}': {e}")
            result['error'] = str(e)
        
        return result
    
    async def test_all_books(self):
        """Test book lookup for all books in the document."""
        try:
            if not self.multiple_books_file.exists():
                logger.error(f"Multiple books file not found: {self.multiple_books_file}")
                return
            
            # Extract and parse book titles
            content = self.extract_text_from_docx(self.multiple_books_file)
            if not content:
                logger.error("No content extracted from the multiple books file")
                return
            
            book_titles = self.parse_book_titles(content)
            logger.info(f"Found {len(book_titles)} books to test")
            
            if not book_titles:
                logger.warning("No books found in the document")
                return
            
            # Test each book
            results = []
            connector = aiohttp.TCPConnector(limit=10, limit_per_host=5)
            timeout = aiohttp.ClientTimeout(total=60)
            
            async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
                for book_info in book_titles:
                    result = await self.test_book_lookup(session, book_info)
                    results.append(result)
                    
                    # Add small delay to avoid rate limiting
                    await asyncio.sleep(0.5)
            
            # Summary and save to file
            successful = [r for r in results if r['found']]
            failed = [r for r in results if not r['found']]
            
            # Save results to file
            self.save_results_to_file(book_titles, successful, failed)
            
        except Exception as e:
            logger.error(f"Error in test_all_books: {e}")
    
    def save_results_to_file(self, all_books: list, successful: list, failed: list):
        """Save test results to a text file."""
        try:
            from datetime import datetime
            
            # Ensure Results directory exists
            results_dir = Path("Results")
            results_dir.mkdir(exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = results_dir / f"book_id_test_results_{timestamp}.txt"
            
            total_books = len(all_books)
            success_count = len(successful)
            fail_count = len(failed)
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write("="*80 + "\n")
                f.write("📊 BOOK ID LOOKUP TEST RESULTS\n")
                f.write("="*80 + "\n")
                f.write(f"Test Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Total books tested: {total_books}\n")
                f.write(f"✅ Successfully found: {success_count}\n")
                f.write(f"❌ Failed to find: {fail_count}\n")
                f.write(f"Success rate: {success_count/total_books*100:.1f}%\n")
                f.write("\n")
                
                if successful:
                    f.write("✅ SUCCESSFULLY FOUND BOOKS:\n")
                    f.write("-" * 50 + "\n")
                    for book in successful:
                        f.write(f"Book {book['book_number']}: {book['title']}\n")
                        f.write(f"  → API Title: {book['api_title']}\n")
                        f.write(f"  → Book ID: {book['book_id']}\n")
                        f.write(f"  → Author: {book['author']}\n")
                        f.write("\n")
                
                if failed:
                    f.write("❌ FAILED TO FIND BOOKS:\n")
                    f.write("-" * 50 + "\n")
                    for book in failed:
                        f.write(f"Book {book['book_number']}: {book['title']}\n")
                        f.write(f"  → Author: {book['author']}\n")
                        f.write(f"  → Error: {book['error']}\n")
                        f.write("\n")
                
                f.write("="*80 + "\n")
                f.write(f"Report saved to: {filename}\n")
                f.write("Generated by test_book_id.py\n")
            
            logger.info(f"📄 Test results saved to: {filename}")
            print(f"📄 Test results saved to: {filename}")
            print(f"📊 Summary: {success_count}/{total_books} books found ({success_count/total_books*100:.1f}% success rate)")
            
        except Exception as e:
            logger.error(f"Error saving results to file: {e}")

async def main():
    """Main function to run the book ID test."""
    try:
        tester = BookTitleTester()
        await tester.test_all_books()
    except Exception as e:
        logger.error(f"Error in main: {e}")

if __name__ == "__main__":
    asyncio.run(main())