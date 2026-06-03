# test_gemini.py
import asyncio
import google.genai as genai
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def test():
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    
    prompt = """CRITICAL: You MUST respond in ARABIC language ONLY.
    
    Say "Hello, how are you?" in ARABIC only, no English."""
    
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt
    )
    
    print("Response:", response.text)

if __name__ == "__main__":
    asyncio.run(test())