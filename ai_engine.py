# ai_engine.py

"""
AI communication and prompt management using Ollama with timeout safety.
"""

import ollama
import config
from validator import extract_sql

def mindsql_start(messages):
    """
    Sends the prompt to Ollama with a token limit and temperature adjustment
    to prevent the model from stalling or over-refusing.
    """
    try:
        # options help prevent the model from hanging in infinite loops
        response = ollama.chat(
            model=config.MODEL_NAME, 
            messages=messages,
            options={
                'temperature': 0.3,   # Slight creativity helps break 'refusal' loops
                'num_predict': 150,   # Stops the AI from writing a novel
                'top_p': 0.9          # Allows for more logical word choices
            }
        )

        ai_text = response['message']['content']
        
        print("\n[AI RESPONSE DEBUG]")
        print("AI output preview:", ai_text[:200])

        # --- Catch Clarifications ---
        if ai_text.strip().startswith("CLARIFICATION_NEEDED:"):
            return ai_text.strip()

        # Extract clean SQL
        sql_code = extract_sql(ai_text) or ai_text.strip()
        return sql_code

    except Exception as e:
        return f"CLARIFICATION_NEEDED: AI connection timeout or error: {str(e)}"

def chat_with_model(messages):
    """
    Full text mode for Database Expert/Chat mode.
    """
    return ollama.chat(
        model=config.MODEL_NAME, 
        messages=messages,
        options={'temperature': 0.4} # Higher temp for better conversation
    )