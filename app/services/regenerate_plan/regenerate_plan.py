import os
import json
import openai
from dotenv import load_dotenv
from .regenerate_plan_schema import regenerate_plan_response, regenerate_plan_request

load_dotenv()

class RegeneratePlan:
    def __init__(self):
        self.client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    def regenerate_plan(self, input_data: regenerate_plan_request) -> regenerate_plan_response:     
        prompt = self.create_prompt(input_data)
        response = self.get_openai_response(prompt, str(input_data.dict()))
        print(response)
        try:
            response_json = json.loads(response)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse OpenAI response as JSON: {e}")
        return regenerate_plan_response(**response_json)
    
    def create_prompt(self, input_data: regenerate_plan_request) -> str:
        return f"""You are an expert travel planner specializing in modifying and improving travel itineraries based on user feedback. A traveler wants to change a specific part of their itinerary.

    You will receive:
    - The current activity to be replaced or modified
    - The full day's itinerary to help avoid overlaps
    - Additional user preferences and context

    CURRENT ITINERARY TO MODIFY:
    {input_data.current_itinerary}

    USER REQUESTED CHANGE:
    {input_data.user_change}

    FULL DAY PLAN:
    {input_data.day_plan}

    USER INFO:
    {input_data.user_info}

    INSTRUCTIONS:
    1. Replace or modify ONLY the itinerary item marked as "current_itinerary".
    2. Use information from "user_info" and "day_plan" to ensure replacements are relevant, conflict-free, and tailored to user needs.
    3. Use the destination city: {input_data.user_info.get("destination", "Unknown")}
    4. Ensure suggestions match the original time slot: {input_data.current_itinerary.get("time", "Unknown")}.
    5. Make sure activities are suitable for {input_data.user_info.get("total_adults", "N/A")} adults and {input_data.user_info.get("total_children", "N/A")} children.
    6. Use real-time data sources or recent local knowledge for suggestions.
    7. DO NOT include any extra text, formatting, markdown, or explanation.

    OUTPUT FORMAT:
    Respond ONLY with raw JSON in the following structure:

    {{
    "success": true,
    "data": {{
        "updated_activity": {{
        "id": "[same as original]",
        "time": "[same as original or adjusted if needed]",
        "title": "[New activity title]",
        "description": "[Description of the activity]",
        "place": "[Location or venue name]",
        "keyword": "[e.g., entertainment, park, museum]"
        }},
        "alternative_options": [
        {{
            "option": 1,
            "time": "[same as original or adjusted if needed]",
            "title": "[Alternative activity title]",
            "description": "[Description of the alternative activity]",
            "place": "[Alternative location or venue]",
            "keyword": "[category keyword]"
        }},
        {{
            "option": 2,
            "time": "[same as original or adjusted if needed]",
            "title": "[Alternative activity title]",
            "description": "[Description of the alternative activity]",
            "place": "[Alternative location or venue]",
            "keyword": "[category keyword]"
        }},
        {{
            "option": 3,
            "time": "[same as original or adjusted if needed]",
            "title": "[Alternative activity title]",
            "description": "[Description of the alternative activity]",
            "place": "[Alternative location or venue]",
            "keyword": "[category keyword]"
        }}
        ]
    }},
    "message": "Alternative activities generated successfully"
    }}

    AGAIN: Your output must be **valid JSON only**. No extra comments, no markdown, and no natural language explanation.
"""



    
    def get_openai_response(self, prompt: str, data: str) -> str:
        completion = self.client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "system", "content": prompt}, {"role": "user", "content": data}],
            temperature=0.7            
        )
        raw_content = completion.choices[0].message.content.strip()
        print(raw_content)
        return raw_content