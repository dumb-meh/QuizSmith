import asyncio
import os
from dotenv import load_dotenv
from single_book import BookProcessor

async def test_auth_token():
    """Test if AUTH_TOKEN is properly loaded"""
    load_dotenv()
    auth_token = os.getenv("AUTH_TOKEN")
    
    if not auth_token or auth_token == "your_auth_token_here":
        print("❌ AUTH_TOKEN not configured. Please update .env file with your actual auth token")
        return False
    
    print("✅ AUTH_TOKEN is configured")
    return True

async def test_book_files():
    """Test if book files exist"""
    processor = BookProcessor()
    
    if not processor.books_folder.exists():
        print("❌ Book folder not found")
        return False
    
    docx_files = list(processor.books_folder.glob("*.docx"))
    print(f"✅ Found {len(docx_files)} book files:")
    for file in docx_files:
        title = processor.extract_title_from_filename(file.name)
        print(f"  - {file.name} → Title: '{title}'")
    
    return len(docx_files) > 0

if __name__ == "__main__":
    print("Testing setup...")
    
    async def run_tests():
        auth_ok = await test_auth_token()
        files_ok = await test_book_files()
        
        if auth_ok and files_ok:
            print("\n✅ Setup looks good! You can now run: python single_book.py")
        else:
            print("\n❌ Please fix the issues above before running the main script")
    
    asyncio.run(run_tests())