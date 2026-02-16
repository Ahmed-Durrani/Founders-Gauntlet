# game_logic.py
import os
import json
import google.generativeai as genai
from personas import get_system_prompt

# Configure Gemini
# NOTE: In a real app, use os.getenv("GEMINI_API_KEY")
# For local testing, you can hardcode it or set it in your terminal environment.
# os.environ["GEMINI_API_KEY"] = "YOUR_ACTUAL_API_KEY_HERE"

def initialize_ai():
    """Checks for API key and sets up the model."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None
    genai.configure(api_key=api_key)
    return True

def get_ai_response(user_input, current_level, chat_history):
    """
    Sends user input to Gemini and parses the JSON response.
    """
    try:
        # 1. Select the model (Flash is fast/cheap)
        model = genai.GenerativeModel('gemini-flash-latest')

        # 2. Construct the full context
        # We inject the system prompt + recent chat history to keep context
        system_instruction = get_system_prompt(current_level)
        
        # Convert simple chat history list to a string format for the prompt
        history_text = "\n".join([f"{msg['role'].upper()}: {msg['content']}" for msg in chat_history])
        
        full_prompt = f"""
        {system_instruction}

        CURRENT CHAT HISTORY:
        {history_text}

        USER'S NEW INPUT:
        {user_input}
        
        REMINDER: Output strict JSON only.
        """

        # 3. Call the API
        response = model.generate_content(full_prompt)
        raw_text = response.text

        # 4. Clean and Parse JSON
        # LLMs sometimes wrap JSON in ```json ... ``` blocks. We strip those.
        cleaned_text = raw_text.strip()
        if cleaned_text.startswith("```"):
            cleaned_text = cleaned_text.split("```")[1]
            if cleaned_text.startswith("json"):
                cleaned_text = cleaned_text[4:]
        
        game_data = json.loads(cleaned_text)
        
        # Validate keys exist
        if "reply" not in game_data or "damage" not in game_data:
            raise ValueError("Missing keys in JSON response")
            
        return game_data

    except Exception as e:
        # Fallback in case of AI error or JSON parsing failure
        print(f"Error: {e}")
        return {
            "reply": "*( The simulation glitched. The investor stares at you blankly. Try saying that again. )*",
            "damage": 0,
            "level_passed": False,
            "feedback": f"System Error: {str(e)}"
        }