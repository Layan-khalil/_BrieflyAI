import os
import json
import re
import sys
import traceback
import httpx

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"

# Arabic Unicode range
ARABIC_RE = re.compile(r'[؀-ۿ]')


def contains_arabic(text: str) -> bool:
    return bool(ARABIC_RE.search(text))


def extract_json(text: str) -> dict | None:
    """Extract a JSON object from text aggressively."""
    if not text:
        return None

    cleaned = re.sub(r'```json\s*', '', text)
    cleaned = re.sub(r'```\s*', '', cleaned)

    json_match = re.search(r'\{[\s\S]*\}', cleaned)
    if not json_match:
        return None

    json_str = json_match.group(0)
    json_str = re.sub(r',\s*}', '}', json_str)
    json_str = re.sub(r',\s*]', ']', json_str)

    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        return None


def ensure_fields(result: dict) -> dict:
    if 'summary' not in result or not isinstance(result.get('summary'), str):
        result['summary'] = ''
    if 'key_insights' not in result or not isinstance(result.get('key_insights'), list):
        result['key_insights'] = []
    if 'bullet_notes' not in result or not isinstance(result.get('bullet_notes'), list):
        result['bullet_notes'] = []
    if 'timestamps' not in result or not isinstance(result.get('timestamps'), list):
        result['timestamps'] = []
    return result


def call_gemini(prompt: str) -> str:
    """Call Gemini directly via REST API. No SDK dependency."""
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "thinkingConfig": {"thinkingBudget": 0}
        }
    }

    with httpx.Client(timeout=120) as client:
        resp = client.post(
            f"{GEMINI_URL}?key={GEMINI_API_KEY}",
            json=payload,
            headers={"Content-Type": "application/json"}
        )

    if resp.status_code != 200:
        print(f"[Gemini] HTTP {resp.status_code}: {resp.text[:500]}", file=sys.stderr)
        raise Exception(f"Gemini API returned {resp.status_code}")

    data = resp.json()
    candidates = data.get("candidates", [])
    if not candidates:
        raise Exception("No candidates in Gemini response")

    parts = candidates[0].get("content", {}).get("parts", [])
    text_parts = [p for p in parts if not p.get("thought", False)]
    text = text_parts[0].get("text", "") if text_parts else ""
    print(f"[Gemini] Response ({len(text)} chars): {text[:500]}", file=sys.stderr)
    return text


def get_prompt(language: str, title: str, transcript: str, duration: int = 0) -> str:
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
        return f"""Respond only in Arabic. All content must be in Arabic. This is mandatory.

قم بتحليل وتلخيص محتوى هذا الفيديو بالكامل.

عنوان الفيديو: {title}

النص (مع الطوابع الزمنية): {transcript_preview}{dur}

**تعليمات مهمة جداً:**
- أخرج JSON فقط، بدون أي نص إضافي
- اكتب كل المحتوى باللغة العربية فقط
- لا تستخدم علامات ```json أو ```
- **استخدم الطوابع الزمنية الحقيقية من النص**
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
        return f"""Respond only in English. All content must be in English. This is mandatory.

Analyze and summarize this ENTIRE video content from start to finish.

Video Title: {title}

Transcript (with timestamps): {transcript_preview}{duration_hint}

**Important Instructions:**
- Output ONLY valid JSON, no additional text
- Write everything in English only
- Do NOT use ```json or ``` markers
- **Use the REAL timestamps from the transcript**
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


def get_audio_prompt(language: str, title: str, duration: int = 0) -> str:
    if language == 'ar':
        dur = ""
        if duration > 0:
            mins = duration // 60
            secs = duration % 60
            dur = f"\nمدة الفيديو: {mins}:{secs:02d}"
        return f"""Respond only in Arabic. All content must be in Arabic.

استمع إلى هذا الفيديو بالكامل ثم حلله بشكل منظم.

عنوان الفيديو: {title}{dur}

**تعليمات مهمة جداً:**
- أخرج JSON فقط، بدون أي نص إضافي
- اكتب كل المحتوى باللغة العربية فقط
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
        return f"""Respond only in English. All content must be in English.

Listen to this entire video and provide a structured analysis.

Video Title: {title}

**Important Instructions:**
- Output ONLY valid JSON, no additional text
- Write everything in English only
- **Distribute timestamps evenly across the FULL video**
- **Generate 5-8 timestamps**

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


def analyze_from_youtube_url(video_url: str, title: str, language: str = 'en', duration: int = 0) -> dict:
    """Analyze a YouTube video directly via Gemini's native YouTube URL support.
    Raises GeminiYouTubeError if Gemini cannot access the video, so callers can fall back."""
    prompt = get_audio_prompt(language, title, duration)
    payload = {
        "contents": [{
            "parts": [
                {"text": prompt},
                {"fileData": {"mimeType": "video/mp4", "fileUri": video_url}}
            ]
        }],
        "generationConfig": {"thinkingConfig": {"thinkingBudget": 0}}
    }

    with httpx.Client(timeout=180) as client:
        resp = client.post(
            f"{GEMINI_URL}?key={GEMINI_API_KEY}",
            json=payload,
            headers={"Content-Type": "application/json"}
        )

    if resp.status_code != 200:
        raise Exception(f"Gemini YouTube URL failed: {resp.status_code}: {resp.text[:300]}")

    candidates = resp.json().get("candidates", [])
    if not candidates:
        raise Exception("No candidates in Gemini response")

    parts = candidates[0].get("content", {}).get("parts", [])
    text_parts = [p for p in parts if not p.get("thought", False)]
    text = text_parts[0].get("text", "") if text_parts else ""
    print(f"[Gemini YouTube] Response ({len(text)} chars): {text[:300]}", file=sys.stderr)

    result = extract_json(text)
    if result is None:
        # Gemini responded but couldn't access the video — signal the caller to fall back
        raise Exception(f"Gemini could not access YouTube URL: {text[:200]}")

    return ensure_fields(result)


def analyze_sync(transcript: str, title: str, language: str = 'en', duration: int = 0) -> dict:
    try:
        prompt = get_prompt(language, title, transcript, duration)
        text = call_gemini(prompt)
        result = extract_json(text)

        if result is None:
            print(f"[Gemini] JSON parse failed, retrying...", file=sys.stderr)
            retry_hint = "\n\nIMPORTANT: You MUST return ONLY valid JSON. No other text."
            text = call_gemini(prompt + retry_hint)
            result = extract_json(text)

        if result is None:
            print(f"[Gemini] JSON parse failed after retry", file=sys.stderr)
            if language == 'ar':
                return {"summary": "تعذر تحليل رد الذكاء الاصطناعي. يرجى المحاولة مرة أخرى.", "key_insights": [], "bullet_notes": [], "timestamps": []}
            else:
                return {"summary": "Failed to parse AI response. Please try again.", "key_insights": [], "bullet_notes": [], "timestamps": []}

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
                    result = {"summary": "تعذر تحليل المحتوى.", "key_insights": [], "bullet_notes": [], "timestamps": []}

        return ensure_fields(result)

    except Exception as e:
        print(f"[Gemini] Error: {type(e).__name__}: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        if language == 'ar':
            return {"summary": "حدث خطأ في تحليل المحتوى.", "key_insights": [], "bullet_notes": [], "timestamps": []}
        else:
            return {"summary": "Error analyzing content. Please try again.", "key_insights": [], "bullet_notes": [], "timestamps": []}


def analyze_from_audio(audio_path: str, title: str, language: str = 'en', duration: int = 0) -> dict:
    """Upload audio to Gemini Files API, wait for it to be ready, then analyze."""
    import mimetypes, time

    def _error(msg_en, msg_ar):
        return {"summary": msg_ar if language == 'ar' else msg_en,
                "key_insights": [], "bullet_notes": [], "timestamps": []}

    try:
        file_size = os.path.getsize(audio_path)
        mime_type = mimetypes.guess_type(audio_path)[0] or "audio/mp4"
        display_name = os.path.basename(audio_path)
        print(f"[Gemini Audio] Uploading {display_name} ({file_size} bytes)", file=sys.stderr)

        # ── Step 1: Initiate resumable upload ──────────────────────────────
        init_url = f"https://generativelanguage.googleapis.com/upload/v1beta/files?key={GEMINI_API_KEY}"
        init_headers = {
            "X-Goog-Upload-Protocol": "resumable",
            "X-Goog-Upload-Command": "start",
            "X-Goog-Upload-Header-Content-Length": str(file_size),
            "X-Goog-Upload-Header-Content-Type": mime_type,
            "Content-Type": "application/json",
        }
        with httpx.Client(timeout=30) as client:
            r1 = client.post(init_url, headers=init_headers,
                             content=json.dumps({"file": {"display_name": display_name}}))

        if r1.status_code != 200:
            raise Exception(f"Upload initiation failed: {r1.status_code}: {r1.text[:200]}")

        # The resumable upload URL comes from the response header
        resumable_url = r1.headers.get("X-Goog-Upload-URL", "")
        if not resumable_url:
            raise Exception("No X-Goog-Upload-URL in initiation response")

        # ── Step 2: Upload the audio bytes ─────────────────────────────────
        with open(audio_path, "rb") as f:
            audio_bytes = f.read()

        upload_headers = {
            "Content-Length": str(len(audio_bytes)),
            "X-Goog-Upload-Command": "upload, finalize",
            "X-Goog-Upload-Offset": "0",
        }
        with httpx.Client(timeout=300) as client:
            r2 = client.post(resumable_url, headers=upload_headers, content=audio_bytes)

        if r2.status_code not in (200, 201):
            raise Exception(f"Upload failed: {r2.status_code}: {r2.text[:200]}")

        file_data = r2.json().get("file", {})
        file_name_id = file_data.get("name", "")   # e.g. "files/abc123"
        file_uri    = file_data.get("uri", "")      # full https:// URI
        print(f"[Gemini Audio] Uploaded: {file_name_id}", file=sys.stderr)

        if not file_uri:
            raise Exception(f"No file URI in upload response: {r2.json()}")

        # ── Step 3: Poll until ACTIVE (large files need processing time) ───
        state_url = f"https://generativelanguage.googleapis.com/v1beta/{file_name_id}?key={GEMINI_API_KEY}"
        for attempt in range(12):
            time.sleep(3)
            with httpx.Client(timeout=15) as client:
                rs = client.get(state_url)
            if rs.status_code == 200:
                state = rs.json().get("state", "")
                print(f"[Gemini Audio] File state: {state}", file=sys.stderr)
                if state == "ACTIVE":
                    break
                if state == "FAILED":
                    raise Exception("Gemini file processing failed")
        else:
            raise Exception("File did not become ACTIVE in time")

        # ── Step 4: Generate content ────────────────────────────────────────
        prompt = get_audio_prompt(language, title, duration)
        payload = {
            "contents": [{
                "parts": [
                    {"text": prompt},
                    {"fileData": {"mimeType": mime_type, "fileUri": file_uri}}
                ]
            }],
            "generationConfig": {"thinkingConfig": {"thinkingBudget": 0}}
        }

        with httpx.Client(timeout=180) as client:
            r3 = client.post(
                f"{GEMINI_URL}?key={GEMINI_API_KEY}",
                json=payload,
                headers={"Content-Type": "application/json"}
            )

        if r3.status_code != 200:
            raise Exception(f"Content generation failed: {r3.status_code}: {r3.text[:300]}")

        candidates = r3.json().get("candidates", [])
        if not candidates:
            raise Exception("No candidates in Gemini response")

        parts = candidates[0].get("content", {}).get("parts", [])
        text_parts = [p for p in parts if not p.get("thought", False)]
        text = text_parts[0].get("text", "") if text_parts else ""
        print(f"[Gemini Audio] Response ({len(text)} chars): {text[:500]}", file=sys.stderr)

        result = extract_json(text)
        if result is None:
            return _error("Error analyzing audio. Please try again.", "حدث خطأ في تحليل الصوت.")

        return ensure_fields(result)

    except Exception as e:
        print(f"[Gemini Audio] Error: {type(e).__name__}: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        if language == 'ar':
            return {"summary": "حدث خطأ في تحليل الصوت.", "key_insights": [], "bullet_notes": [], "timestamps": []}
        else:
            return {"summary": "Error analyzing audio.", "key_insights": [], "bullet_notes": [], "timestamps": []}
