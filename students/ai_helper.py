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
        
        # Switching back to 1.5 Flash which has higher free tier limits
        model_name = 'models/gemini-1.5-flash'
        model = genai.GenerativeModel(model_name)
        
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
        # Fallback to gemini-1.5-flash-8b which has even higher quotas
        if "429" in str(e) or "quota" in str(e).lower():
            try:
                model = genai.GenerativeModel('models/gemini-1.5-flash-8b')
                response = model.generate_content(full_prompt)
                return response.text
            except Exception as e2:
                return f"AI Limit Reached: Aapki daily free limit khatam ho gayi hai. Please naya API key use karein ya kal try karein. (Error: {str(e2)})"
        return f"I'm sorry, I'm having trouble connecting right now. (Error: {str(e)})"
