import os
import asyncio
import aiohttp
import time
from pathlib import Path
from urllib.parse import quote
from dotenv import load_dotenv
from docx import Document

from app.services.single_book_suggestion.single_book_suggestion import AISuggestion
from app.services.single_book_suggestion.single_book_suggestion_schema import (
    single_book_suggestion_request,
    single_book_suggestion_response
)

# Load environment variables
load_dotenv()

class BookProcessor:
    def __init__(self):
        self.auth_token = os.getenv("AUTH_TOKEN")
        if not self.auth_token:
            raise ValueError("AUTH_TOKEN not found in environment variables")
        
        self.ai_suggestion = AISuggestion()
        self.base_url = "https://ashlynprasad-backend.vercel.app/api/v1"
        self.books_folder = Path("Book")
        
        # Rate limiting - delay between API calls to avoid rate limiting
        self.api_delay = 1.0  # 1 second between API calls
        
    def extract_title_from_filename(self, filename: str) -> str:
        """Extract the book title from the filename (everything before ' by ')"""
        # Remove the .docx extension
        name_without_ext = filename.replace('.docx', '')
        
        # Split by ' by ' and take the first part
        if ' by ' in name_without_ext:
            title = name_without_ext.split(' by ')[0].strip()
            return title
        else:
            # If ' by ' is not found, use the whole filename without extension
            return name_without_ext.strip()
    
    def extract_text_from_docx(self, file_path: Path) -> str:
        """Extract text content from a DOCX file"""
        try:
            document = Document(file_path)
            paragraphs = [para.text.strip() for para in document.paragraphs if para.text.strip()]
            text = "\n".join(paragraphs)
            if not text.strip():
                raise ValueError(f"DOCX file {file_path} contains no extractable text.")
            return text
        except Exception as e:
            raise ValueError(f"Unable to extract text from DOCX {file_path}: {e}")
    
    async def get_book_by_title(self, session: aiohttp.ClientSession, title: str) -> dict:
        """Get book information by title from the API"""
        encoded_title = quote(title)
        url = f"{self.base_url}/books/by-title?title={encoded_title}"
        
        headers = {
            "Authorization": self.auth_token,
            "Content-Type": "application/json"
        }
        
        try:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("success") and data.get("result") and len(data["result"]) > 0:
                        # Get the first book from the results (excluding the pagination info)
                        books = [item for item in data["result"] if isinstance(item, dict) and "nid" in item]
                        if books:
                            return books[0]  # Return the first matching book
                    raise ValueError(f"No book found with title: {title}")
                else:
                    error_text = await response.text()
                    raise ValueError(f"API error {response.status}: {error_text}")
                    
        except aiohttp.ClientError as e:
            raise ValueError(f"Network error when fetching book by title '{title}': {e}")
    
    async def create_quiz(self, session: aiohttp.ClientSession, quiz_data: dict) -> dict:
        """Create quiz using the API"""
        url = f"{self.base_url}/quizz/create"
        
        headers = {
            "Authorization": self.auth_token,
            "Content-Type": "application/json"
        }
        
        try:
            async with session.post(url, headers=headers, json=quiz_data) as response:
                if response.status == 200 or response.status == 201:
                    return await response.json()
                else:
                    error_text = await response.text()
                    raise ValueError(f"Quiz creation API error {response.status}: {error_text}")
                    
        except aiohttp.ClientError as e:
            raise ValueError(f"Network error when creating quiz: {e}")
    
    async def process_single_book(self, session: aiohttp.ClientSession, file_path: Path) -> dict:
        """Process a single book file"""
        try:
            print(f"Processing: {file_path.name}")
            
            # Extract title from filename
            title = self.extract_title_from_filename(file_path.name)
            print(f"Extracted title: {title}")
            
            # Get book info by title
            book_info = await self.get_book_by_title(session, title)
            book_id = book_info["nid"]
            book_name = book_info["title"]
            print(f"Found book ID: {book_id}, Name: {book_name}")
            
            # Extract text content from the docx file
            extracted_quiz = self.extract_text_from_docx(file_path)
            print(f"Extracted {len(extracted_quiz)} characters of quiz content")
            
            # Create request for AI suggestion
            request_data = single_book_suggestion_request(
                extracted_quiz=extracted_quiz,
                bookId=book_id,
                bookName=book_name
            )
            
            # Get AI suggestion (formatted quiz)
            print("Getting AI suggestion...")
            ai_response = await self.ai_suggestion.get_suggestion(request_data)
            
            # Convert to dict for API call
            quiz_data = {
                "bookId": ai_response.bookId,
                "bookName": ai_response.bookName,
                "questions": ai_response.questions
            }
            
            # Create quiz via API
            print("Creating quiz via API...")
            quiz_result = await self.create_quiz(session, quiz_data)
            
            print(f"✅ Successfully processed: {file_path.name}")
            return {
                "file": file_path.name,
                "book_id": book_id,
                "book_name": book_name,
                "status": "success",
                "quiz_result": quiz_result
            }
            
        except Exception as e:
            error_msg = f"❌ Error processing {file_path.name}: {str(e)}"
            print(error_msg)
            return {
                "file": file_path.name,
                "status": "error",
                "error": str(e)
            }
    
    async def process_all_books(self):
        """Process all books in the Book folder"""
        if not self.books_folder.exists():
            raise ValueError(f"Book folder not found: {self.books_folder}")
        
        # Get all .docx files
        docx_files = list(self.books_folder.glob("*.docx"))
        if not docx_files:
            raise ValueError("No .docx files found in the Book folder")
        
        print(f"Found {len(docx_files)} book files to process")
        
        results = []
        
        # Create a single aiohttp session for all requests
        async with aiohttp.ClientSession() as session:
            # Process books with some delay to avoid rate limiting
            for i, file_path in enumerate(docx_files):
                if i > 0:  # Add delay between books (except for the first one)
                    print(f"Waiting {self.api_delay} seconds to avoid rate limiting...")
                    await asyncio.sleep(self.api_delay)
                
                result = await self.process_single_book(session, file_path)
                results.append(result)
        
        return results

async def main():
    """Main function to run the book processing"""
    try:
        processor = BookProcessor()
        results = await processor.process_all_books()
        
        # Print summary
        print("\n" + "="*50)
        print("PROCESSING SUMMARY")
        print("="*50)
        
        successful = [r for r in results if r["status"] == "success"]
        failed = [r for r in results if r["status"] == "error"]
        
        print(f"Total files: {len(results)}")
        print(f"Successful: {len(successful)}")
        print(f"Failed: {len(failed)}")
        
        if successful:
            print("\n✅ Successfully processed:")
            for result in successful:
                print(f"  - {result['file']} (Book ID: {result['book_id']})")
        
        if failed:
            print("\n❌ Failed to process:")
            for result in failed:
                print(f"  - {result['file']}: {result['error']}")
        
    except Exception as e:
        print(f"Fatal error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)