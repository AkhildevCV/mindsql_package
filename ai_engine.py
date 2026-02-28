# ai_engine.py
"""
AI communication and prompt management using Ollama.
Supports both strict SQL mode and conversational chat mode.
"""

import ollama
import config
from validator import extract_sql


def mindsql_start(messages: list) -> str:
    """
    Sends messages to Ollama in strict/SQL mode.
    Returns clean SQL or a CLARIFICATION_NEEDED string.
    """
    try:
        response = ollama.chat(
            model=config.MODEL_NAME,
            messages=messages,
            options={
                "temperature": 0.2,    # Low temp for deterministic SQL
                "num_predict": 250,    # Enough for complex queries
                "top_p": 0.9,
                "repeat_penalty": 1.1, # Prevent hallucination loops
            },
        )
        ai_text = response["message"]["content"]

        # Pass through guardrail responses unchanged
        if ai_text.strip().startswith(("CLARIFICATION_NEEDED:", "SCHEMA_ANSWER:")):
            return ai_text.strip()

        # Extract and return clean SQL
        return extract_sql(ai_text) or ai_text.strip()

    except ollama.ResponseError as exc:
        if "model" in str(exc).lower():
            return (
                f"CLARIFICATION_NEEDED: Model '{config.MODEL_NAME}' not found. "
                "Run the installer or: ollama create mindsql-v2 -f Modelfile"
            )
        return f"CLARIFICATION_NEEDED: Ollama error – {exc}"
    except Exception as exc:
        return f"CLARIFICATION_NEEDED: AI connection error – {exc}"


def chat_with_model(messages: list) -> dict:
    """
    Full conversational mode – returns the raw Ollama response dict.
    Used by mindsql_ans and mindsql_export.
    """
    try:
        return ollama.chat(
            model=config.MODEL_NAME,
            messages=messages,
            options={
                "temperature": 0.5,    # Slightly more creative for explanations
                "num_predict": 512,
                "repeat_penalty": 1.1,
            },
        )
    except Exception as exc:
        # Return a dict that mimics Ollama's structure so callers don't crash
        return {"message": {"content": f"CLARIFICATION_NEEDED: {exc}"}}


def stream_chat(messages: list, on_token=None):
    """
    Streaming version – calls on_token(str) for each token received.
    Returns the full assembled response string.
    """
    full = ""
    try:
        for chunk in ollama.chat(
            model=config.MODEL_NAME,
            messages=messages,
            stream=True,
            options={"temperature": 0.5, "num_predict": 512},
        ):
            token = chunk["message"]["content"]
            full += token
            if on_token:
                on_token(token)
    except Exception as exc:
        err = f"\n[Error: {exc}]"
        full += err
        if on_token:
            on_token(err)
    return full
