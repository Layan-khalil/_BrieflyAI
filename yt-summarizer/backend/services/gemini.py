import google.genai as genai
from google.genai import types
import os
import json
import re
import sys
import asyncio

# Initialize Gemini client
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# Arabic Unicode range
ARABIC_RE = re.compile(r'[؀-ۿ]')


def contains_arabic(text: str) -> bool:
    return bool(ARABIC_RE.search(text))


def clean_json_response(text: str, language: str = 'en') -> dict:
    if not text:
        print(f"Gemini returned empty response", file=sys.stderr)
        return {"summary": "No response from AI", "key_insights": [], "bullet_notes": [], "timestamps": []}

    original = text
    # Strip markdown code blocks
    text = re.sub(r'```json\s*', '', text)
    text = re.sub(r'```\s*', '', text)

    # Find the first JSON object
    json_match = re.search(r'\{[\s\S]*\}', text)
    if json_match:
        text = json_match.group(0)

    # Normalize line endings inside strings (Gemini sometimes adds literal newlines in string values)
    text = re.sub(r'(?<="[^"]*)\n(?=[^"]*")', ' ', text)

    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        # Try again with more aggressive cleaning
        try:
            text = re.sub(r',\s*}', '}', text)  # Remove trailing commas
            result = json.loads(text)
        except json.JSONDecodeError:
            print(f"Gemini JSON parse failed. Raw response (first 1000 chars): {original[:1000]}", file=sys.stderr)
            return {"summary": "Could not parse response. Please try again.", "key_insights": [], "bullet_notes": [], "timestamps": []}

    if language == 'ar':
        text_fields = [result.get('summary', '')]
        text_fields.extend(result.get('key_insights', []))
        text_fields.extend(result.get('bullet_notes', []))
        text_fields.extend(t.get('topic', '') for t in result.get('timestamps', []))
        non_arabic = [t for t in text_fields if t and not contains_arabic(t)]
        if len(non_arabic) > len(text_fields) // 2:
            return {"_arabic_failed": True}

    return result


def get_prompt(language: str, title: str, transcript: str, duration: int = 0) -> str:
    # Cap at 80K — plenty for any video, keeps responses fast
    transcript_preview = transcript[:80000]

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
- **استخدم الطوابع الزمنية الحقيقية من النص — لا تخترع أوقاتاً عشوائية**
- **وزّع الطوابع الزمنية بالتساوي على الفيديو بالكامل من البداية إلى النهاية**
- **يجب أن يكون هناك 5-8 طوابع زمنية تغطي الفيديو كاملاً**
- **اجعل وصف كل طابع زمني محدداً ومفصلاً — صف موضوع الجزء بدقة**

مثال صحيح للطوابع الزمنية:
{{"time": "0:00", "topic": "مقدمة: شرح المشكلة الأساسية التي يعالجها الفيديو"}}
{{"time": "3:15", "topic": "الخطوة الأولى: كيفية تثبيت الأدوات المطلوبة على نظام التشغيل"}}
{{"time": "7:30", "topic": "تطبيق عملي: كتابة الكود وتجربته على بيانات حقيقية"}}

استخدم هذا التنسيق:
{{
  "summary": "ملخص الفيديو في 2-3 جمل بالعربية",
  "key_insights": ["رؤية أولى محددة", "رؤية ثانية محددة", "رؤية ثالثة محددة", "رؤية رابعة محددة", "رؤية خامسة محددة"],
  "bullet_notes": ["ملاحظة أولى محددة", "ملاحظة ثانية محددة", "ملاحظة ثالثة محددة", "ملاحظة رابعة محددة", "ملاحظة خامسة محددة"],
  "timestamps": [
    {{"time": "0:00", "topic": "وصف محدد ومفصل لما يُقال في هذا الجزء"}},
    {{"time": "5:30", "topic": "وصف محدد ومفصل للجزء التالي"}}
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
- **Use the REAL timestamps from the transcript — do NOT invent random times**
- **Distribute timestamps evenly across the FULL video, from beginning to end**
- **Generate 5-8 timestamps that cover the entire video duration**
- **Make each timestamp topic SPECIFIC and detailed — describe what's actually said at that point, not a generic section title**

Correct timestamp example:
{{"time": "0:00", "topic": "Introduction: the speaker explains the core problem this video solves"}}
{{"time": "3:15", "topic": "Step 1: installing the required tools and setting up the environment"}}
{{"time": "7:30", "topic": "Hands-on demo: writing the actual code and testing with real data"}}

Use this exact format:
{{
  "summary": "2-3 sentence summary of the video in English",
  "key_insights": ["specific insight 1", "specific insight 2", "specific insight 3", "specific insight 4", "specific insight 5"],
  "bullet_notes": ["specific note 1", "specific note 2", "specific note 3", "specific note 4", "specific note 5"],
  "timestamps": [
    {{"time": "0:00", "topic": "Specific detailed description of what's covered here"}},
    {{"time": "5:30", "topic": "Specific detailed description of the next section"}}
  ]
}}"""


def get_audio_prompt(language: str, title: str, duration: int = 0) -> str:
    """Prompt for direct audio-to-structured-analysis — no separate transcript step."""
    duration_hint = ""
    if duration > 0:
        mins = duration // 60
        secs = duration % 60
        duration_hint = f"\nVideo duration: {mins}:{secs:02d}"

    if language == 'ar':
        dur = ""
        if duration > 0:
            mins = duration // 60
            secs = duration % 60
            dur = f"\nمدة الفيديو: {mins}:{secs:02d}"
        return f"""استمع إلى هذا الفيديو بالكامل ثم حلله بشكل منظم.

عنوان الفيديو: {title}{dur}

**تعليمات مهمة جداً:**
- أخرج JSON فقط، بدون أي نص إضافي
- اكتب كل المحتوى باللغة العربية فقط
- لا تستخدم علامات ```json أو ```
- **وزّع الطوابع الزمنية بالتساوي على الفيديو بالكامل**
- **يجب أن يكون هناك 5-8 طوابع زمنية**
- **اجعل وصف كل طابع زمني محدداً ومفصلاً**

استخدم هذا التنسيق:
{{
  "summary": "ملخص الفيديو في 2-3 جمل بالعربية",
  "key_insights": ["رؤية أولى محددة", "رؤية ثانية محددة", "رؤية ثالثة محددة", "رؤية رابعة محددة", "رؤية خامسة محددة"],
  "bullet_notes": ["ملاحظة أولى محددة", "ملاحظة ثانية محددة", "ملاحظة ثالثة محددة", "ملاحظة رابعة محددة", "ملاحظة خامسة محددة"],
  "timestamps": [
    {{"time": "0:00", "topic": "وصف محدد ومفصل لما يُقال في هذا الجزء"}},
    {{"time": "5:30", "topic": "وصف محدد ومفصل للجزء التالي"}}
  ]
}}"""
    else:
        return f"""Listen to this entire video and provide a structured analysis.

Video Title: {title}{duration_hint}

**Important Instructions:**
- Output ONLY JSON, no additional text
- Write everything in English only
- Do NOT use ```json or ``` markers
- **Distribute timestamps evenly across the FULL video**
- **Generate 5-8 timestamps**
- **Make each timestamp topic SPECIFIC and detailed**

Use this exact format:
{{
  "summary": "2-3 sentence summary of the video in English",
  "key_insights": ["specific insight 1", "specific insight 2", "specific insight 3", "specific insight 4", "specific insight 5"],
  "bullet_notes": ["specific note 1", "specific note 2", "specific note 3", "specific note 4", "specific note 5"],
  "timestamps": [
    {{"time": "0:00", "topic": "Specific detailed description of what's covered here"}},
    {{"time": "5:30", "topic": "Specific detailed description of the next section"}}
  ]
}}"""


def analyze_from_audio(audio_path: str, title: str, language: str = 'en', duration: int = 0) -> dict:
    """Upload audio to Gemini and get structured analysis in one API call — no separate transcript step.

    This is faster for no-subtitle videos: 1 API call instead of transcribe + analyze.
    """
    try:
        uploaded = client.files.upload(file=audio_path)
        prompt = get_audio_prompt(language, title, duration)

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[prompt, uploaded]
        )

        text = response.text.strip()
        if not text:
            return {"_error": True}

        result = clean_json_response(text, language)

        # If Arabic validation failed, retry once
        if result.get("_arabic_failed") or (
            language == 'ar' and not contains_arabic(result.get('summary', ''))
        ):
            retry_prompt = prompt + "\n\n**ملاحظة: يجب أن تكون كل الكلمات بالعربية. أي رد بالإنجليزية غير مقبول.**"
            retry_uploaded = client.files.upload(file=audio_path)
            retry_response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[retry_prompt, retry_uploaded]
            )
            result = clean_json_response(retry_response.text, language)

        result.pop("_arabic_failed", None)
        result.pop("_error", None)
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
        print(f"Gemini audio analysis error: {type(e).__name__}: {e}")
        if language == 'ar':
            return {
                "summary": "حدث خطأ في تحليل الصوت. يرجى المحاولة مرة أخرى.",
                "key_insights": ["يرجى المحاولة مرة أخرى"],
                "bullet_notes": ["يرجى المحاولة مرة أخرى"],
                "timestamps": []
            }
        else:
            return {
                "summary": "Error analyzing audio. Please try again.",
                "key_insights": ["Please try again"],
                "bullet_notes": ["Please try again"],
                "timestamps": []
            }


async def _call_gemini(prompt: str, system_inst: str, timeout: int = 60) -> str:
    """Make an async Gemini API call with timeout. Falls back to sync on failure."""
    try:
        response = await asyncio.wait_for(
            client.aio.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_inst
                )
            ),
            timeout=timeout
        )
        return response.text
    except asyncio.TimeoutError:
        print("Gemini API call timed out", file=sys.stderr)
        raise
    except AttributeError as e:
        print(f"Async client not available ({e}), falling back to sync", file=sys.stderr)
        # Fall back to sync API if async isn't supported in this version
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_inst
            )
        )
        return response.text


async def analyze_sync(transcript: str, title: str, language: str = 'en', duration: int = 0) -> dict:
    """Get analysis from Gemini using async calls with timeout."""

    try:
        prompt = get_prompt(language, title, transcript, duration)

        system_inst = (
            "Respond only in Arabic. All content must be in Arabic."
            if language == 'ar'
            else "Respond only in English."
        )

        text = await _call_gemini(prompt, system_inst)
        result = clean_json_response(text, language)

        # If Arabic validation failed, retry once with stronger hint
        if result.get("_arabic_failed") or (
            language == 'ar' and not contains_arabic(result.get('summary', ''))
        ):
            retry_prompt = prompt + "\n\n**ملاحظة: يجب أن تكون كل الكلمات بالعربية. أي رد بالإنجليزية غير مقبول.**"
            retry_text = await _call_gemini(retry_prompt, system_inst)
            result = clean_json_response(retry_text, language)

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
