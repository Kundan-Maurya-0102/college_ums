import os
import logging

from django.conf import settings
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv()

# Predefined responses for when AI is down or quota reached
DUMMY_RESPONSES = {
    "attendance": "Aap apni attendance dashboard par dekh sakte hain. Agar attendance 75% se kam hai, toh please apne subject teacher se contact karein.",
    "marks": "Internal marks aur results dashboard par upload kar diye gaye hain. Aap apne 'Marks' section mein jaakar check kar sakte hain.",
    "notice": "Sare important notices 'Notices' tab mein available hain. Latest updates ke liye wahan check karein.",
    "college": "{college} ek technical institution hai jo quality education provide karta hai.",
    "contact": "Kise bhi technical issue ke liye aap college admin office mein contact kar sakte hain.",
    "fee": "Fee details aap apne dashboard ke 'Fees' section mein dekh sakte hain. Pending dues ke liye admin office contact karein.",
    "exam": "Exam schedule dashboard par available hai. 'Exam Timetable' section check karein.",
    "leave": "Leave apply karne ke liye dashboard mein 'Leave Application' section use karein.",
    "certificate": "Certificates download karne ke liye 'Certificates' section mein jaayein.",
}

def get_fallback_response(prompt):
    prompt_lower = prompt.lower()
    college_name = getattr(settings, "COLLEGE_NAME", "") or "your college"
    for key, response in DUMMY_RESPONSES.items():
        if key in prompt_lower:
            return f"[Offline Mode] {response.format(college=college_name)}"
    return "[Offline Mode] Main abhi available nahi hoon. Please thodi der baad try karein ya apne dashboard par details check karein."

def get_ai_response(prompt, user_context=""):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return get_fallback_response(prompt)

    try:
        from google import genai

        client = genai.Client(api_key=api_key)

        college_name = getattr(settings, "COLLEGE_NAME", "") or "the college"
        full_prompt = f"""
        You are 'UMS AI Assistant', a helpful AI for the University Management System (UMS) of {college_name}.

        Your Goal:
        - Provide high-quality, accurate, and helpful answers to students, teachers, and admins.
        - If someone asks about college details, refer to {college_name}.
        - Use a friendly yet professional tone.
        - Use Markdown for formatting (bolding, lists, etc.).
        - If you don't know something specific about the user's personal records (like their exact marks), politely ask them to check their dashboard.

        User Context: {user_context}

        User Query: {prompt}

        Please provide a detailed and helpful response in a mix of Hindi and English (Hinglish).
        """

        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=full_prompt,
        )
        return response.text
    except Exception as e:
        # If API fails for any reason, use fallback instead of showing error
        logger.error(f"AI Error: {e}")
        return get_fallback_response(prompt)
