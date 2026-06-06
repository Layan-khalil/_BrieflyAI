import google.genai as genai
from google.genai import types
import os
import json
import re
import sys
import traceback

# Initialize Gemini client
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# Arabic Unicode range
ARABIC_RE = re.compile(r'[؀-ۿ]')


def contains_arabic(text: str) -> bool:
    return bool(ARABIC_RE.search(text))


def extract_json(text: str) -> dict | None:
    """Aggressively try to extract a JSON object from text. Returns None on failure."""
    if not text:
        return None

    # Strip markdown code blocks
    cleaned = re.sub(r'```json\s*', '', text)
    cleaned = re.sub(r'```\s*', '', cleaned)

    # Find first JSON object
    json_match = re.search(r'\{[\s\S]*\}', cleaned)
    if not json_match:
        return None

    json_str = json_match.group(0)
    # Aggressive cleaning
    json_str = re.sub(r',\s*}', '}', json_str)
    json_str = re.sub(r',\s*]', ']', json_str)
    json_str = re.sub(r'(?<="[^"]*)\n(?=[^"]*")', ' ', json_str)

    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        return None


def ensure_fields(result: dict) -> dict:
    """Ensure required fields exist with defaults."""
    if 'summary' not in result or not isinstance(result.get('summary'), str):
        result['summary'] = ''
    if 'key_insights' not in result or not isinstance(result.get('key_insights'), list):
        result['key_insights'] = []
    if 'bullet_notes' not in result or not isinstance(result.get('bullet_notes'), list):
        result['bullet_notes'] = []
    if 'timestamps' not in result or not isinstance(result.get('timestamps'), list):
        result['timestamps'] = []
    return result


def get_prompt(language: str, title: str, transcript: str, duration: int = 0) -> str:
    # Cap at 80K
    transcript_preview = transcript[:80000]

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
        prompt = f"""Respond only in Arabic. All content must be in Arabic. This is mandatory.

قم بتحليل وتلخيص محتوى هذا الفيديو بالكامل.

عنوان الفيديو: {title}

النص (مع الطوابع الزمنية): {transcript_preview}{dur}

**تعليمات مهمة جداً:**
- أخرج JSON فقط، بدون أي نص إضافي
- اكتب كل المحتوى باللغة العربية فقط
- لا تستخدم علامات ```json أو ```
- **استخدم الطوابع الزمنية الحقيقية من النص — لا تخترع أوقاتاً عشوائية**
- **وزّع الطوابع الزمنية بالتساوي على الفيديو بالكامل**
- **يجب أن يكون هناك 5-8 طوابع زمنية**

استخدم هذا التنسيق فقط:
{{
  "summary": "ملخص الفيديو في 2-3 جمل بالعربية",
  "key_insights": ["رؤية أولى", "رؤية ثانية", "رؤية ثالثة", "رؤية رابعة", "رؤية خامسة"],
  "bullet_notes": ["ملاحظة أولى", "ملاحظة ثانية", "ملاحظة ثالثة", "ملاحظة رابعة", "ملاحظة خامسة"],
  "timestamps": [
    {{"time": "0:00", "topic": "وصف الجزء الأول"}},
    {{"time": "5:30", "topic": "وصف الجزء التالي"}}
  ]
}}"""
    else:
        prompt = f"""Respond only in English. All content must be in English. This is mandatory.

Analyze and summarize this ENTIRE video content from start to finish.

Video Title: {title}

Transcript (with timestamps): {transcript_preview}{duration_hint}

**Important Instructions:**
- Output ONLY valid JSON, no additional text
- Write everything in English only
- Do NOT use ```json or ``` markers
- **Use the REAL timestamps from the transcript — do NOT invent random times**
- **Distribute timestamps evenly across the FULL video**
- **Generate 5-8 timestamps**

Use this exact format only:
{{
  "summary": "2-3 sentence summary of the video in English",
  "key_insights": ["insight 1", "insight 2", "insight 3", "insight 4", "insight 5"],
  "bullet_notes": ["note 1", "note 2", "note 3", "note 4", "note 5"],
  "timestamps": [
    {{"time": "0:00", "topic": "Description of first section"}},
    {{"time": "5:30", "topic": "Description of next section"}}
  ]
}}"""

    return prompt


def call_gemini(prompt: str) -> str:
    """Call Gemini with sync API. No config/system_instruction — everything is in the prompt."""
    print(f"[Gemini] Sending request...", file=sys.stderr)
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )
    text = response.text
    print(f"[Gemini] Response ({len(text)} chars): {text[:500]}", file=sys.stderr)
    return text


def analyze_sync(transcript: str, title: str, language: str = 'en', duration: int = 0) -> dict:
    """Get analysis from Gemini."""
    try:
        prompt = get_prompt(language, title, transcript, duration)
        text = call_gemini(prompt)
        result = extract_json(text)

        # Retry if JSON extraction failed or Arabic validation failed
        if result is None:
            print(f"[Gemini] JSON parse failed, retrying...", file=sys.stderr)
            retry_hint = "\n\nIMPORTANT: You MUST return ONLY valid JSON. No other text."
            text = call_gemini(prompt + retry_hint)
            result = extract_json(text)

        if result is None:
            print(f"[Gemini] JSON parse failed after retry", file=sys.stderr)
            if language == 'ar':
                return {
                    "summary": "حدث خطأ في تحليل رد الذكاء الاصطناعي. يرجى المحاولة مرة أخرى.",
                    "key_insights": [], "bullet_notes": [], "timestamps": []
                }
            else:
                return {
                    "summary": "Failed to parse AI response. Please try again.",
                    "key_insights": [], "bullet_notes": [], "timestamps": []
                }

        # Arabic validation
        if language == 'ar':
            text_fields = [result.get('summary', '')]
            text_fields.extend(result.get('key_insights', []))
            text_fields.extend(result.get('bullet_notes', []))
            text_fields.extend(t.get('topic', '') for t in result.get('timestamps', []))
            non_arabic = [t for t in text_fields if t and not contains_arabic(t)]
            if len(non_arabic) > len(text_fields) // 2:
                print(f"[Gemini] Arabic validation failed, retrying...", file=sys.stderr)
                retry_hint = "\n\n**ملاحظة مهمة جداً: يجب أن تكون كل الكلمات بالعربية. أي رد بالإنجليزية غير مقبول.**"
                text = call_gemini(prompt + retry_hint)
                result = extract_json(text)
                if result is None:
                    result = {"summary": "تعذر تحليل المحتوى. يرجى المحاولة مرة أخرى.", "key_insights": [], "bullet_notes": [], "timestamps": []}

        return ensure_fields(result)

    except Exception as e:
        print(f"[Gemini] Error: {type(e).__name__}: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        if language == 'ar':
            return {"summary": "حدث خطأ في تحليل المحتوى. يرجى المحاولة مرة أخرى.", "key_insights": [], "bullet_notes": [], "timestamps": []}
        else:
            return {"summary": "Error analyzing content. Please try again.", "key_insights": [], "bullet_notes": [], "timestamps": []}


def analyze_from_audio(audio_path: str, title: str, language: str = 'en', duration: int = 0) -> dict:
    """Upload audio to Gemini and get structured analysis in one API call."""
    try:
        uploaded = client.files.upload(file=audio_path)

        if language == 'ar':
            prompt = f"""Respond only in Arabic. All content must be in Arabic. This is mandatory.

استمع إلى هذا الفيديو بالكامل ثم حلله بشكل منظم.

عنوان الفيديو: {title}

**تعليمات مهمة جداً:**
- أخرج JSON فقط، بدون أي نص إضافي
- اكتب كل المحتوى باللغة العربية فقط
- لا تستخدم علامات ```json أو ```
- **وزّع الطوابع الزمنية بالتساوي على الفيديو بالكامل**
- **يجب أن يكون هناك 5-8 طوابع زمنية**

استخدم هذا التنسيق:
{{
  "summary": "ملخص الفيديو في 2-3 جمل بالعربية",
  "key_insights": ["رؤية أولى", "رؤية ثانية", "رؤية ثالثة", "رؤية رابعة", "رؤية خامسة"],
  "bullet_notes": ["ملاحظة أولى", "ملاحظة ثانية", "ملاحظة ثالثة", "ملاحظة رابعة", "ملاحظة خامسة"],
  "timestamps": [
    {{"time": "0:00", "topic": "وصف الجزء الأول"}},
    {{"time": "5:30", "topic": "وصف الجزء التالي"}}
  ]
}}"""
        else:
            prompt = f"""Respond only in English. All content must be in English. This is mandatory.

Listen to this entire video and provide a structured analysis.

Video Title: {title}

**Important Instructions:**
- Output ONLY valid JSON, no additional text
- Write everything in English only
- Do NOT use ```json or ``` markers
- **Distribute timestamps evenly across the FULL video**
- **Generate 5-8 timestamps**
- **Make each timestamp topic specific**

Use this exact format:
{{
  "summary": "2-3 sentence summary of the video in English",
  "key_insights": ["insight 1", "insight 2", "insight 3", "insight 4", "insight 5"],
  "bullet_notes": ["note 1", "note 2", "note 3", "note 4", "note 5"],
  "timestamps": [
    {{"time": "0:00", "topic": "Description of first section"}},
    {{"time": "5:30", "topic": "Description of next section"}}
  ]
}}"""

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[prompt, uploaded]
        )

        text = response.text
        print(f"[Gemini Audio] Response ({len(text)} chars): {text[:500]}", file=sys.stderr)

        result = extract_json(text)
        if result is None:
            if language == 'ar':
                return {"summary": "حدث خطأ في تحليل الصوت. يرجى المحاولة مرة أخرى.", "key_insights": [], "bullet_notes": [], "timestamps": []}
            else:
                return {"summary": "Error analyzing audio. Please try again.", "key_insights": [], "bullet_notes": [], "timestamps": []}

        return ensure_fields(result)

    except Exception as e:
        print(f"[Gemini Audio] Error: {type(e).__name__}: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        if language == 'ar':
            return {"summary": "حدث خطأ في تحليل الصوت. يرجى المحاولة مرة أخرى.", "key_insights": [], "bullet_notes": [], "timestamps": []}
        else:
            return {"summary": "Error analyzing audio. Please try again.", "key_insights": [], "bullet_notes": [], "timestamps": []}
