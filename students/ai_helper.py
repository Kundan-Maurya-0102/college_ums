import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()

def get_ai_response(prompt, user_context=""):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return "AI is currently unavailable (API key missing). Please add GEMINI_API_KEY in your .env file."
        
    try:
        genai.configure(api_key=api_key)
        
        # Using the latest and most stable model name with full path
        # Try 2.0 Flash first, then fallback to 1.5 Flash
        model_name = 'models/gemini-2.0-flash'
        try:
            model = genai.GenerativeModel(model_name)
        except Exception:
            model = genai.GenerativeModel('models/gemini-1.5-flash')
        
        full_prompt = f"""
        You are an AI assistant for the University Management System (UMS) of Government Polytechnic Tekari. 
        Help students, teachers, and admins with their academic or technical queries.
        Keep the tone professional and helpful.
        
        User context: {user_context}
        
        User question: {prompt}
        """
        
        response = model.generate_content(full_prompt)
        return response.text
    except Exception as e:
        # Final fallback attempt with the most basic model name
        if "404" in str(e) or "not found" in str(e).lower():
            try:
                model = genai.GenerativeModel('models/gemini-1.5-flash')
                response = model.generate_content(full_prompt)
                return response.text
            except Exception as e2:
                return f"AI connection error: Please check if your API key is correct and has billing/quota enabled. (Details: {str(e2)})"
        return f"I'm sorry, I'm having trouble connecting right now. (Error: {str(e)})"
