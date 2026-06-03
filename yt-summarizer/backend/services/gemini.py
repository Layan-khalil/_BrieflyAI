import google.genai as genai
from google.genai import types
import os
import json
import re

# Initialize Gemini client
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# Arabic Unicode range
ARABIC_RE = re.compile(r'[؀-ۿ]')

def contains_arabic(text: str) -> bool:
    """Check if text contains Arabic characters"""
    return bool(ARABIC_RE.search(text))

def clean_json_response(text: str, language: str = 'en') -> dict:
    """Extract and parse JSON from response"""
    if not text:
        return {
            "summary": "No response from AI",
            "key_insights": [],
            "bullet_notes": [],
            "timestamps": []
        }

    # Remove markdown code blocks
    text = re.sub(r'```json\s*', '', text)
    text = re.sub(r'```\s*', '', text)

    # Find JSON object
    json_match = re.search(r'\{[\s\S]*\}', text)
    if json_match:
        text = json_match.group(0)

    # Parse JSON
    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        return {
            "summary": "Could not parse response. Please try again.",
            "key_insights": [],
            "bullet_notes": [],
            "timestamps": []
        }

    # Validate language compliance for Arabic requests
    if language == 'ar':
        text_fields = [result.get('summary', '')]
        text_fields.extend(result.get('key_insights', []))
        text_fields.extend(result.get('bullet_notes', []))
        text_fields.extend(t.get('topic', '') for t in result.get('timestamps', []))

        non_arabic = [t for t in text_fields if t and not contains_arabic(t)]
        if len(non_arabic) > len(text_fields) // 2:
            # Signal to caller that Arabic validation failed
            return {"_arabic_failed": True}

    return result

def get_prompt(language: str, title: str, transcript: str, duration: int = 0) -> str:
    """Get prompt in specified language"""

    # Increase limit for long videos — Gemini 2.5 handles 1M tokens
    transcript_preview = transcript[:150000]

    duration_hint = ""
    if duration > 0:
        mins = duration // 60
        secs = duration % 60
        duration_hint = f"\nVideo duration: {mins}:{secs:02d} — the last timestamp MUST be near this time."

    if language == 'ar':
        dur = ""
        if duration > 0:
            mins = duration // 60
            secs = duration % 60
            dur = f"\nمدة الفيديو: {mins}:{secs:02d} — يجب أن يكون آخر طابع زمني قريباً من هذا الوقت."
        return f"""قم بتحليل وتلخيص محتوى هذا الفيديو بالكامل.

عنوان الفيديو: {title}

النص (مع الطوابع الزمنية): {transcript_preview}{dur}

**تعليمات مهمة جداً:**
- أخرج JSON فقط، بدون أي نص إضافي
- اكتب كل المحتوى باللغة العربية فقط — هذا إلزامي
- لا تستخدم علامات ```json أو ```
- كل النص يجب أن يكون بالعربية: الملخص، الرؤى، الملاحظات، والمواضيع في الطوابع الزمنية
- لا تكتب أي شيء بالإنجليزية إطلاقاً
- **استخدم الطوابع الزمنية الحقيقية من النص [MM:SS] — لا تخترع أوقاتاً عشوائية**
- **وزّع الطوابع الزمنية بالتساوي على الفيديو بالكامل من البداية إلى النهاية**
- **يجب أن يكون هناك 8-12 طابعاً زمنياً تغطي الفيديو كاملاً**

استخدم هذا التنسيق بالضبط:
{{
  "summary": "ملخص الفيديو في 2-3 جمل بالعربية",
  "key_insights": ["رؤية أولى", "رؤية ثانية", "رؤية ثالثة", "رؤية رابعة", "رؤية خامسة"],
  "bullet_notes": ["ملاحظة أولى", "ملاحظة ثانية", "ملاحظة ثالثة", "ملاحظة رابعة", "ملاحظة خامسة"],
  "timestamps": [
    {{"time": "0:00", "topic": "الموضوع الأول"}},
    {{"time": "5:30", "topic": "الموضوع الثاني"}}
  ]
}}"""
    else:
        return f"""Analyze and summarize this ENTIRE video content from start to finish.

Video Title: {title}

Transcript (with timestamps): {transcript_preview}{duration_hint}

**Important Instructions:**
- Output ONLY JSON, no additional text
- Write everything in English only — this is mandatory
- Do NOT use ```json or ``` markers
- All text must be in English: summary, insights, notes, and topics in timestamps
- **Use the REAL timestamps from the transcript [MM:SS] — do NOT invent random times**
- **Distribute timestamps evenly across the FULL video, from the very beginning to the end**
- **Generate 8-12 timestamps that cover the entire video duration**

Use this exact format:
{{
  "summary": "2-3 sentence summary of the video in English",
  "key_insights": ["insight 1", "insight 2", "insight 3", "insight 4", "insight 5"],
  "bullet_notes": ["note 1", "note 2", "note 3", "note 4", "note 5"],
  "timestamps": [
    {{"time": "0:00", "topic": "First topic"}},
    {{"time": "5:30", "topic": "Second topic"}}
  ]
}}"""

async def analyze_sync(transcript: str, title: str, language: str = 'en', duration: int = 0) -> dict:
    """Get analysis from Gemini"""

    try:
        prompt = get_prompt(language, title, transcript, duration)

        system_inst = (
            "Respond only in Arabic. All content must be in Arabic."
            if language == 'ar'
            else "Respond only in English."
        )

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_inst
            )
        )

        result = clean_json_response(response.text, language)

        # If Arabic validation failed, retry once with stronger hint
        if result.get("_arabic_failed") or (
            language == 'ar' and not contains_arabic(result.get('summary', ''))
        ):
            retry_prompt = prompt + "\n\n**ملاحظة: يجب أن تكون كل الكلمات بالعربية. أي رد بالإنجليزية غير مقبول.**"
            retry_response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=retry_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_inst
                )
            )
            result = clean_json_response(retry_response.text, language)

        # Ensure required fields exist
        result.pop("_arabic_failed", None)
        if 'summary' not in result:
            result['summary'] = "No summary available"
        if 'key_insights' not in result:
            result['key_insights'] = []
        if 'bullet_notes' not in result:
            result['bullet_notes'] = []
        if 'timestamps' not in result:
            result['timestamps'] = []

        return result

    except Exception as e:
        print(f"Gemini API error: {e}")
        if language == 'ar':
            return {
                "summary": "حدث خطأ في تحليل المحتوى. يرجى المحاولة مرة أخرى.",
                "key_insights": ["يرجى المحاولة مرة أخرى"],
                "bullet_notes": ["يرجى المحاولة مرة أخرى"],
                "timestamps": []
            }
        else:
            return {
                "summary": "Error analyzing content. Please try again.",
                "key_insights": ["Please try again"],
                "bullet_notes": ["Please try again"],
                "timestamps": []
            }