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
        
        # Determine the model to use
        model_name = 'gemini-1.5-flash'
        try:
            model = genai.GenerativeModel(model_name)
        except Exception:
            model = genai.GenerativeModel('gemini-pro')
        
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
        # If it was a model error, try one last time with gemini-pro directly
        if "404" in str(e) or "not found" in str(e).lower():
            try:
                model = genai.GenerativeModel('gemini-pro')
                response = model.generate_content(full_prompt)
                return response.text
            except Exception as e2:
                return f"AI connection error: {str(e2)}"
        return f"I'm sorry, I'm having trouble connecting right now. (Error: {str(e)})"
