import os
import asyncio
import aiohttp
import json
import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from docx import Document
from dotenv import load_dotenv
import urllib.parse
import logging
from app.services.single_book_suggestion.single_book_suggestion import AISuggestion
from app.services.single_book_suggestion.single_book_suggestion_schema import (
    single_book_suggestion_request,
    single_book_suggestion_response
)

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class BookData:
    def __init__(self, book_number: str, title: str, author: str, quiz_content: str):
        self.book_number = book_number
        self.title = title
        self.author = author
        self.quiz_content = quiz_content

class MultipleBookProcessor:
    def __init__(self):
        self.auth_token = os.getenv("AUTH_TOKEN")
        self.api_base_url = os.getenv("API_BASE_URL", "https://ashlynprasad-backend.vercel.app/api/v1")
        self.multiple_books_file = Path("Multiple books.docx")
        self.ai_suggestion = AISuggestion()
        
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
    
    def parse_multiple_books(self, content: str) -> List[BookData]:
        """Parse the multiple books document and extract individual book data."""
        books = []
        
        # Split content by book pattern - improved to handle special characters
        # Pattern: Book XXX Title [Author]
        book_pattern = r'(Book\s+\d+\s+[^\[\n]+\s+\[[^\]]+\])'
        
        # Split content into sections
        sections = re.split(book_pattern, content)
        
        # Process sections (every odd index is a book header, every even index is content)
        for i in range(1, len(sections), 2):
            if i + 1 < len(sections):
                book_header = sections[i].strip()
                book_content = sections[i + 1].strip()
                
                # Extract book information from header - improved regex for special characters
                header_match = re.match(r'Book\s+(\d+)\s+([^\[]+?)\s+\[([^\]]+)\]', book_header)
                if header_match:
                    book_number = header_match.group(1)
                    title = header_match.group(2).strip()
                    author = header_match.group(3).strip().replace('"', '')
                    
                    # Clean up title - handle apostrophes and other special characters
                    title = title.replace("'", "'")
                    title = re.sub(r'\s+', ' ', title)
                    
                    # Include the header with the quiz content
                    full_quiz_content = f"{book_header}\n{book_content}"
                    
                    books.append(BookData(book_number, title, author, full_quiz_content))
                    logger.info(f"Parsed book: {book_number} - {title} by {author}")
        
        return books
    
    async def get_book_by_title(self, session: aiohttp.ClientSession, title: str) -> Optional[Dict]:
        """Get book information by title from the API."""
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
            
            logger.info(f"Searching for book with title: '{search_title}'")
            logger.info(f"Encoded URL: {url}")
            
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("success") and data.get("result"):
                        books = data["result"]
                        # Filter out pagination info and return first book
                        book_list = [item for item in books if isinstance(item, dict) and 'nid' in item]
                        if book_list:
                            logger.info(f"Found book: {book_list[0].get('title')} (ID: {book_list[0].get('nid')})")
                            return book_list[0]
                elif response.status == 404:
                    logger.warning(f"Book not found: '{title}'")
                else:
                    error_text = await response.text()
                    logger.warning(f"API request failed for title '{title}': {response.status} - {error_text}")
            
            # If first attempt fails, try with simplified title (remove special characters)
            simplified_title = re.sub(r'[^\w\s]', '', search_title).strip()
            if simplified_title != search_title:
                logger.info(f"Retrying with simplified title: '{simplified_title}'")
                encoded_simplified = urllib.parse.quote(simplified_title, safe='')
                url_simplified = f"{self.api_base_url}/books/by-title?title={encoded_simplified}"
                
                async with session.get(url_simplified, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("success") and data.get("result"):
                            books = data["result"]
                            book_list = [item for item in books if isinstance(item, dict) and 'nid' in item]
                            if book_list:
                                logger.info(f"Found book with simplified title: {book_list[0].get('title')} (ID: {book_list[0].get('nid')})")
                                return book_list[0]
            
            return None
        except Exception as e:
            logger.error(f"Error fetching book info for '{title}': {e}")
            return None
    
    async def create_quiz(self, session: aiohttp.ClientSession, quiz_data: Dict) -> bool:
        """Create quiz via API."""
        try:
            url = f"{self.api_base_url}/quizz/create"
            headers = {
                "Authorization": self.auth_token,
                "Content-Type": "application/json"
            }
            
            async with session.post(url, headers=headers, json=quiz_data) as response:
                if response.status in [200, 201]:
                    result = await response.json()
                    logger.info(f"Quiz created successfully for book: {quiz_data.get('bookName')}")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"Quiz creation failed for book {quiz_data.get('bookName')}: {response.status} - {error_text}")
                    return False
        except Exception as e:
            logger.error(f"Error creating quiz for book {quiz_data.get('bookName')}: {e}")
            return False
    
    async def process_single_book(self, session: aiohttp.ClientSession, book_data: BookData) -> bool:
        """Process a single book."""
        try:
            logger.info(f"Processing book: Book {book_data.book_number} - {book_data.title}")
            
            # Get book information from API
            book_info = await self.get_book_by_title(session, book_data.title)
            if not book_info:
                logger.warning(f"Could not find book info for: {book_data.title}")
                return False
            
            book_id = book_info.get('nid')
            book_name = book_info.get('title', book_data.title)
            
            logger.info(f"Found book: {book_name} (ID: {book_id})")
            
            # Create request for AI suggestion
            suggestion_request = single_book_suggestion_request(
                extracted_quiz=book_data.quiz_content,
                bookId=book_id,
                bookName=book_name
            )
            
            # Get AI suggestion
            ai_response = await self.ai_suggestion.get_suggestion(suggestion_request)
            
            # Convert to dictionary for API
            quiz_data = {
                "bookId": ai_response.bookId,
                "bookName": ai_response.bookName,
                "questions": ai_response.questions
            }
            
            # Create quiz via API
            success = await self.create_quiz(session, quiz_data)
            if success:
                logger.info(f"Successfully processed book: {book_name}")
            else:
                logger.error(f"Failed to create quiz for book: {book_name}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error processing book {book_data.title}: {e}")
            return False
    
    async def process_books_in_batches(self, books: List[BookData], batch_size: int = 3) -> Dict[str, int]:
        """Process books in batches to avoid rate limiting."""
        results = {"successful": 0, "failed": 0}
        
        # Create aiohttp session
        connector = aiohttp.TCPConnector(limit=10, limit_per_host=5)
        timeout = aiohttp.ClientTimeout(total=300)
        
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            # Process books in batches
            for i in range(0, len(books), batch_size):
                batch = books[i:i + batch_size]
                logger.info(f"Processing batch {i//batch_size + 1} with {len(batch)} books")
                
                # Process batch concurrently
                tasks = [self.process_single_book(session, book) for book in batch]
                batch_results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Count results
                for result in batch_results:
                    if isinstance(result, Exception):
                        logger.error(f"Exception in batch processing: {result}")
                        results["failed"] += 1
                    elif result:
                        results["successful"] += 1
                    else:
                        results["failed"] += 1
                
                # Add delay between batches to avoid rate limiting
                if i + batch_size < len(books):
                    logger.info("Waiting 2 seconds between batches...")
                    await asyncio.sleep(2)
        
        return results
    
    async def process_all_books(self):
        """Process all books from the Multiple books.docx file."""
        try:
            if not self.multiple_books_file.exists():
                logger.error(f"Multiple books file not found: {self.multiple_books_file}")
                return
            
            # Extract text from the document
            content = self.extract_text_from_docx(self.multiple_books_file)
            if not content:
                logger.error("No content extracted from the multiple books file")
                return
            
            # Parse individual books from the content
            books = self.parse_multiple_books(content)
            logger.info(f"Found {len(books)} books to process")
            
            if not books:
                logger.warning("No books found in the document")
                return
            
            # Process books in batches
            results = await self.process_books_in_batches(books, batch_size=3)
            
            # Save results to file
            self.save_results_to_file(books, results)
            
            logger.info(f"Processing complete! Successful: {results['successful']}, Failed: {results['failed']}")
            
        except Exception as e:
            logger.error(f"Error in process_all_books: {e}")
    
    def save_results_to_file(self, books: List[BookData], results: Dict[str, int]):
        """Save processing results to a text file."""
        try:
            from datetime import datetime
            
            # Ensure Results directory exists
            results_dir = Path("Results")
            results_dir.mkdir(exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = results_dir / f"multiple_book_results_{timestamp}.txt"
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write("="*80 + "\n")
                f.write("📚 MULTIPLE BOOK PROCESSING RESULTS\n")
                f.write("="*80 + "\n")
                f.write(f"Processing Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Total books processed: {len(books)}\n")
                f.write(f"Successfully processed: {results['successful']}\n")
                f.write(f"Failed to process: {results['failed']}\n")
                f.write(f"Success rate: {results['successful']/len(books)*100:.1f}%\n")
                f.write("\n")
                
                f.write("BOOK DETAILS:\n")
                f.write("-"*80 + "\n")
                for book in books:
                    f.write(f"Book {book.book_number}: {book.title}\n")
                    f.write(f"  Author: {book.author}\n")
                    f.write(f"  Status: Processing attempted\n")
                    f.write("\n")
                
                f.write("\nFILE LOCATION: " + str(filename) + "\n")
                f.write("Generated by multiple_book.py\n")
            
            logger.info(f"Results saved to: {filename}")
            
        except Exception as e:
            logger.error(f"Error saving results to file: {e}")

async def main():
    """Main function to run the multiple book processor."""
    try:
        processor = MultipleBookProcessor()
        await processor.process_all_books()
    except Exception as e:
        logger.error(f"Error in main: {e}")

if __name__ == "__main__":
    asyncio.run(main())