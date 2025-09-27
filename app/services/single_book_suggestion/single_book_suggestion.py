import os
import json
import openai
from uuid import uuid4
import asyncio
from dotenv import load_dotenv
import concurrent.futures
from .single_book_suggestion_schema import single_book_suggestion_response, single_book_suggestion_request
import datetime
from openai import AsyncOpenAI

load_dotenv()

class AISuggestion:
    def __init__(self):
        self.client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    async def get_suggestion(self, input_data: single_book_suggestion_request) -> single_book_suggestion_response:
            prompt = self.create_prompt(input_data)
            response_text = await self.get_openai_response(prompt, input_data)
            response_json = json.loads(response_text)
            return single_book_suggestion_response(**response_json)            
    
    def create_prompt(self, input_data: single_book_suggestion_request) ->str:
        return f"""Your task is arranging the quiz you get from the text into a proper json format.

                   The quiz content is for book ID: {input_data.bookId} (integer) and book name: "{input_data.bookName}"

                   Example output:
                   {{   "bookId": {input_data.bookId},
                        "bookName": "{input_data.bookName}",
                        "questions": [
                            {{
                            "questionNo": 1,
                            "content": "What is 2 + 2?",
                            "options": ["1", "2", "3", "4"],
                            "correctAnswers": ["4"]
                            }},
                            {{
                            "questionNo": 2,
                            "content": "Which are prime numbers?",
                            "options": ["2", "3", "4", "6"],
                            "correctAnswers": ["2", "3"]
                            }}
                        ]
                        }}
                        
                   Please process the following quiz text and format it according to the example above:
                   {input_data.extracted_quiz}
                """


    async def get_openai_response(self, prompt: str, data: dict) -> single_book_suggestion_response:
        data_json = data.json()

        completion = await self.client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": data_json}
            ]
        )

        return completion.choices[0].message.content.strip()


