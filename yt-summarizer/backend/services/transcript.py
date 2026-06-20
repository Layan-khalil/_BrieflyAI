import re
import sys
import os
import httpx

def format_time(seconds):
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"[{h}:{m:02d}:{s:02d}]"
    return f"[{m:02d}:{s:02d}]"


def get_transcript(url):
    video_id = extract_video_id(url)

    # Strategy 1: Supadata API — works on cloud IPs, handles no-subtitle videos via Whisper
    transcript = _fetch_supadata(video_id)
    if transcript:
        return transcript

    # Strategy 2: youtube-transcript-api
    transcript = _fetch_youtube_transcript_api(video_id)
    if transcript:
        return transcript

    # Strategy 3: youtubetranscript.com API
    transcript = _fetch_transcript_api(video_id)
    if transcript:
        return transcript

    # Strategy 4: Invidious proxy instances
    transcript = _fetch_invidious(video_id)
    if transcript:
        return transcript

    # Strategy 5: yt-dlp subtitle download
    try:
        return _download_subtitles_ytdlp(video_id)
    except Exception as e:
        print(f"yt-dlp subtitle error: {type(e).__name__}: {e}", file=sys.stderr)

    # No subtitles found — let Gemini analyze the YouTube URL directly
    return {'source': 'gemini_youtube', 'text': '', 'url': f'https://www.youtube.com/watch?v={video_id}'}


def _fetch_supadata(video_id):
    """Supadata API — bypasses cloud IP blocks, uses Whisper for no-subtitle videos."""
    import time
    api_key = os.getenv("SUPADATA_API_KEY")
    if not api_key:
        return None
    try:
        headers = {"x-api-key": api_key}
        params = {"url": f"https://www.youtube.com/watch?v={video_id}"}
        with httpx.Client(timeout=30) as client:
            resp = client.get("https://api.supadata.ai/v1/transcript", params=params, headers=headers)

        # Async job — poll until done
        if resp.status_code == 202:
            job_id = resp.json().get("jobId")
            print(f"Supadata: async job {job_id}, polling...", file=sys.stderr)
            for _ in range(24):
                time.sleep(5)
                with httpx.Client(timeout=15) as client:
                    resp = client.get(f"https://api.supadata.ai/v1/transcript/{job_id}", headers=headers)
                if resp.status_code == 200:
                    break
            else:
                print("Supadata: job timed out", file=sys.stderr)
                return None

        if resp.status_code in (402, 429):
            print(f"Supadata: monthly limit reached", file=sys.stderr)
            return {'source': 'limit_exceeded'}

        if resp.status_code != 200:
            print(f"Supadata error: {resp.status_code}: {resp.text[:200]}", file=sys.stderr)
            return None

        content = resp.json().get("content", [])
        if not content:
            print("Supadata: empty content", file=sys.stderr)
            return None

        text = ' '.join([f"{format_time(int(s['offset']) // 1000)} {s['text']}" for s in content])
        print(f"Supadata: got {len(content)} segments", file=sys.stderr)
        return {'text': text, 'source': 'subtitles'}

    except Exception as e:
        print(f"Supadata error: {type(e).__name__}: {e}", file=sys.stderr)
        return None


def _fetch_youtube_transcript_api(video_id):
    """Use youtube-transcript-api library — hits YouTube's own timedtext endpoint."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        api = YouTubeTranscriptApi()

        # Try preferred languages first
        for langs in [['en', 'en-US', 'en-GB'], ['ar']]:
            try:
                segments = list(api.fetch(video_id, languages=langs))
                if segments:
                    text = ' '.join([f"{format_time(s.start)} {s.text}" for s in segments])
                    print(f"youtube-transcript-api: got {len(segments)} segments via fetch({langs})", file=sys.stderr)
                    return {'text': text, 'source': 'subtitles'}
            except Exception as e:
                print(f"youtube-transcript-api fetch({langs}) error: {type(e).__name__}: {e}", file=sys.stderr)
                continue

        # Any available transcript (auto-generated included)
        try:
            transcript_list = api.list(video_id)
            for t in transcript_list:
                try:
                    segments = list(t.fetch())
                    if segments:
                        text = ' '.join([f"{format_time(s.start)} {s.text}" for s in segments])
                        print(f"youtube-transcript-api: got {len(segments)} segments via list+fetch({t.language_code})", file=sys.stderr)
                        return {'text': text, 'source': 'subtitles'}
                except Exception as e:
                    print(f"youtube-transcript-api list fetch error ({t.language_code}): {type(e).__name__}: {e}", file=sys.stderr)
        except Exception as e:
            print(f"youtube-transcript-api list error: {type(e).__name__}: {e}", file=sys.stderr)

    except Exception as e:
        print(f"youtube-transcript-api import error: {type(e).__name__}: {e}", file=sys.stderr)
    return None


def _fetch_transcript_api(video_id):
    """Use youtubetranscript.com API."""
    try:
        url = f"https://youtubetranscript.com/?v={video_id}&format=json"
        with httpx.Client(timeout=15, follow_redirects=True) as client:
            resp = client.get(url, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list) and len(data) > 0:
                text = ' '.join([f"{format_time(s['seconds'])} {s['text']}" for s in data])
                return {'text': text, 'source': 'subtitles'}
    except Exception as e:
        print(f"youtubetranscript error: {e}", file=sys.stderr)
    return None


def _fetch_invidious(video_id):
    """Try Invidious proxy instances for captions."""
    instances = [
        f"https://inv.nadeko.net/api/v1/captions/{video_id}",
        f"https://yewtu.be/api/v1/captions/{video_id}",
    ]
    for base_url in instances:
        try:
            with httpx.Client(timeout=15) as client:
                resp = client.get(base_url, headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code == 200:
                data = resp.json()
                for caption in data if isinstance(data, list) else []:
                    lang = caption.get('languageCode', '')
                    if lang in ('en', 'ar', 'en-US', 'en-GB', 'en-AU'):
                        url = caption.get('url', '')
                        if url:
                            with httpx.Client(timeout=15) as client:
                                cr = client.get(url, headers={"User-Agent": "Mozilla/5.0"})
                            if cr.status_code == 200:
                                segments = _parse_vtt_text(cr.text)
                                if segments:
                                    text = ' '.join([f"{format_time(s['start'])} {s['text']}" for s in segments])
                                    return {'text': text, 'source': 'subtitles'}
        except Exception as e:
            print(f"Invidious caption error: {e}", file=sys.stderr)
    return None


def _download_audio_invidious(video_id):
    """Get audio stream URL from Invidious, download it, pass to Gemini."""
    import tempfile, os, shutil
    instances = [
        "https://inv.nadeko.net",
        "https://yewtu.be",
        "https://invidious.privacyredirect.com",
        "https://inv.tux.pizza",
    ]
    for instance in instances:
        try:
            url = f"{instance}/api/v1/videos/{video_id}"
            print(f"[Invidious] Trying {instance}", file=sys.stderr)
            with httpx.Client(timeout=15) as client:
                resp = client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code != 200:
                print(f"[Invidious] {instance} returned {resp.status_code}", file=sys.stderr)
                continue

            data = resp.json()
            formats = data.get('adaptiveFormats', []) or data.get('formatStreams', [])
            audio_url = None
            for fmt in formats:
                mime = fmt.get('type', '') or fmt.get('mimeType', '')
                if mime.startswith('audio'):
                    audio_url = fmt.get('url') or fmt.get('audioUrl', '')
                    print(f"[Invidious] Found audio format: {mime}", file=sys.stderr)
                    break

            if not audio_url:
                print(f"[Invidious] No audio format found at {instance}", file=sys.stderr)
                continue

            tmpdir = tempfile.mkdtemp()
            audio_path = os.path.join(tmpdir, "audio.mp4")
            print(f"[Invidious] Downloading audio from {instance}...", file=sys.stderr)
            with httpx.Client(timeout=300, follow_redirects=True) as client:
                resp = client.get(audio_url, headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code == 200:
                with open(audio_path, 'wb') as f:
                    f.write(resp.content)
                size = os.path.getsize(audio_path)
                print(f"[Invidious] Downloaded {size} bytes", file=sys.stderr)
                if size > 1000:
                    return {'source': 'gemini_audio', 'text': '', 'audio_path': audio_path, '_tmpdir': tmpdir}
            else:
                print(f"[Invidious] Audio download returned {resp.status_code}", file=sys.stderr)
            shutil.rmtree(tmpdir, ignore_errors=True)
        except Exception as e:
            print(f"[Invidious] {instance} error: {type(e).__name__}: {e}", file=sys.stderr)
    return {'source': 'none', 'text': ''}


def _download_subtitles_ytdlp(video_id):
    """Download auto-generated subtitles using yt-dlp."""
    import subprocess, tempfile, os, shutil, glob
    tmpdir = tempfile.mkdtemp()
    try:
        cmd = [sys.executable, "-m", "yt_dlp", "--skip-download",
               "--write-auto-sub", "--sub-langs", "en,ar",
               "--sub-format", "vtt",
               "--extractor-args", "youtube:player_client=android",
               "-o", os.path.join(tmpdir, "%(id)s"),
               f"https://www.youtube.com/watch?v={video_id}"]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

        vtt_files = glob.glob(os.path.join(tmpdir, "*.vtt"))
        if not vtt_files:
            raise Exception("no vtt files found")

        vtt_path = vtt_files[0]
        segments = _parse_vtt_text(open(vtt_path, 'r', encoding='utf-8').read())
        text = ' '.join([f"{format_time(s['start'])} {s['text']}" for s in segments])
        shutil.rmtree(tmpdir, ignore_errors=True)
        return {'text': text, 'source': 'subtitles'}
    except:
        shutil.rmtree(tmpdir, ignore_errors=True)
        raise


def _transcribe_audio_ytdlp(video_id):
    """Download audio via yt-dlp with impersonation."""
    import subprocess, tempfile, os, shutil, glob
    tmpdir = tempfile.mkdtemp()
    try:
        audio_path = os.path.join(tmpdir, "audio")

        # tv_embedded bypasses SABR restrictions; others as fallback
        clients = ["tv_embedded", "android", "ios", "web"]
        result = None
        for client in clients:
            cmd = [sys.executable, "-m", "yt_dlp",
                   "-f", "139/249/worstaudio/bestaudio",  # lowest-quality audio formats
                   "--extractor-args", f"youtube:player_client={client}",
                   "--no-playlist",
                   "-o", audio_path + ".%(ext)s",
                   f"https://www.youtube.com/watch?v={video_id}"]
            print(f"[yt-dlp] Trying client={client}", file=sys.stderr)
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
            if result.returncode == 0:
                print(f"[yt-dlp] Success with client={client}", file=sys.stderr)
                break
            print(f"[yt-dlp] client={client} failed: {result.stderr[-150:]}", file=sys.stderr)

        if result is None or result.returncode != 0:
            shutil.rmtree(tmpdir, ignore_errors=True)
            return {'source': 'none', 'text': ''}

        files = glob.glob(os.path.join(tmpdir, "*"))
        if not files:
            shutil.rmtree(tmpdir, ignore_errors=True)
            return {'source': 'none', 'text': ''}

        return {'source': 'gemini_audio', 'text': '', 'audio_path': files[0], '_tmpdir': tmpdir}
    except Exception as e:
        print(f"Audio download error: {type(e).__name__}: {e}", file=sys.stderr)
        shutil.rmtree(tmpdir, ignore_errors=True)
        return {'source': 'none', 'text': ''}


def _parse_vtt_text(vtt_text):
    """Parse VTT subtitle text into segments."""
    segments = []
    lines = vtt_text.split('\n')
    ts_pattern = re.compile(r'(\d+):(\d+):(\d+)\.\d+')
    current_time = None
    current_text = []

    for line in lines:
        line = line.strip()
        match = ts_pattern.search(line)
        if match:
            if current_time is not None and current_text:
                segments.append({'start': current_time, 'text': ' '.join(current_text)})
            h, m, s = int(match.group(1)), int(match.group(2)), int(match.group(3))
            current_time = h * 3600 + m * 60 + s
            current_text = []
        elif line and not line.startswith('WEBVTT') and not line.startswith('NOTE') and not line.startswith('Kind:') and not line.startswith('Language:'):
            current_text.append(line.replace('&gt;', '>').replace('&lt;', '<').replace('&amp;', '&'))

    if current_time is not None and current_text:
        segments.append({'start': current_time, 'text': ' '.join(current_text)})
    return segments


def extract_video_id(url):
    match = re.search(r'(?:v=|youtu\.be/)([a-zA-Z0-9_-]{11})', url)
    return match.group(1) if match else 'video'
