import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()

def get_ai_response(prompt, user_context=""):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return "AI is currently unavailable (API key missing). Please add GEMINI_API_KEY in your .env file."
        
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    full_prompt = f"""
    You are an AI assistant for the University Management System (UMS) of Government Polytechnic Tekari. 
    Help students, teachers, and admins with their academic or technical queries.
    Keep the tone professional and helpful.
    
    User context: {user_context}
    
    User question: {prompt}
    """
    
    try:
        response = model.generate_content(full_prompt)
        return response.text
    except Exception as e:
        return f"I'm sorry, I'm having trouble connecting right now. (Error: {str(e)})"
