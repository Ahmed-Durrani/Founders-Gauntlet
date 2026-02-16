# game_logic.py
import os
import json
import time
from google import genai
from personas import get_system_prompt

def initialize_ai():
    """Checks for API key."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("❌ DEBUG: GEMINI_API_KEY is missing.")
        return None
    return True

def get_ai_response(user_input, current_level, chat_history):
    # The new SDK automatically picks up the GEMINI_API_KEY environment variable
    # We initialize the new Client object here:
    client = genai.Client()
    
    for attempt in range(3):
        try:
            system_instruction = get_system_prompt(current_level)
            
            history_text = "\n".join([f"{msg['role'].upper()}: {msg['content']}" for msg in chat_history])
            
            full_prompt = f"""
            {system_instruction}

            CURRENT CHAT HISTORY:
            {history_text}

            USER'S NEW INPUT:
            {user_input}
            
            IMPORTANT: You must output ONLY valid JSON.
            """

            # --- NEW SDK SYNTAX ---
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=full_prompt
            )
            
            raw_text = response.text

            # --- DEBUG PRINT ---
            print(f"\n--- AI RESPONSE (Attempt {attempt+1}) ---")
            print(raw_text)
            print("-----------------------\n")
            # -------------------

            cleaned_text = raw_text.strip()
            if cleaned_text.startswith("```"):
                first_newline = cleaned_text.find("\n")
                if first_newline != -1:
                    cleaned_text = cleaned_text[first_newline:].strip()
                if cleaned_text.endswith("```"):
                    cleaned_text = cleaned_text[:-3].strip()
            
            game_data = json.loads(cleaned_text)
            
            if "reply" not in game_data or "damage" not in game_data:
                raise ValueError("Missing keys in JSON response")
                
            return game_data

        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "Quota" in error_str:
                print(f"⚠️ Quota hit. Waiting 5 seconds... (Attempt {attempt+1}/3)")
                time.sleep(5) 
                continue 
            
            print(f"❌ CRITICAL ERROR: {e}")
            return {
                "reply": f"*(System Error: {str(e)})*",
                "damage": 0,
                "level_passed": False
            }

    return {
        "reply": "*( The investor is ignoring you. The simulation is overloaded. Try again in 1 minute. )*",
        "damage": 0,
        "level_passed": False
    }