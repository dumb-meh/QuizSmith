from pydantic import BaseModel
from typing import List, Union, Dict,Any  

class single_book_suggestion_request (BaseModel):
    extracted_quiz:str
    bookId: int
    bookName: str
class single_book_suggestion_response(BaseModel):
    bookId: int
    bookName: str
    questions: List[Dict[str, Any]] 