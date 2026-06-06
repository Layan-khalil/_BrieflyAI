import re
import sys
import httpx

def format_time(seconds):
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"[{h}:{m:02d}:{s:02d}]"
    return f"[{m:02d}:{s:02d}]"


def get_transcript(url):
    video_id = extract_video_id(url)

    # Strategy 1: youtubetranscript.com API (simple REST API, rarely blocked)
    transcript = _fetch_transcript_api(video_id)
    if transcript:
        return transcript

    # Strategy 2: Invidious instances (proxy YouTube data)
    transcript = _fetch_invidious(video_id)
    if transcript:
        return transcript

    # Strategy 3: yt-dlp subtitle download
    try:
        return _download_subtitles_ytdlp(video_id)
    except Exception as e:
        print(f"yt-dlp subtitle error: {type(e).__name__}: {e}", file=sys.stderr)

    # Strategy 4: yt-dlp audio + Gemini
    return _transcribe_audio(video_id)


def _fetch_transcript_api(video_id):
    """Use youtubetranscript.com API - a free third-party service that mirrors YouTube transcripts."""
    urls = [
        f"https://youtubetranscript.com/?v={video_id}",
        f"https://youtubetranscript.com/?v={video_id}&format=json",
    ]
    for url in urls:
        try:
            with httpx.Client(timeout=15, follow_redirects=True) as client:
                resp = client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list) and len(data) > 0:
                    text = ' '.join([f"{format_time(s['seconds'])} {s['text']}" for s in data])
                    return {'text': text, 'source': 'subtitles'}
        except Exception as e:
            print(f"Transcript API error ({url[:40]}): {e}", file=sys.stderr)
    return None


def _fetch_invidious(video_id):
    """Try Invidious proxy instances."""
    instances = [
        f"https://inv.nadeko.net/api/v1/captions/{video_id}",
        f"https://yewtu.be/api/v1/captions/{video_id}",
    ]
    for instance in instances:
        try:
            with httpx.Client(timeout=15) as client:
                resp = client.get(instance, headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code == 200:
                data = resp.json()
                # Find first English or Arabic caption
                for caption in data if isinstance(data, list) else []:
                    lang = caption.get('languageCode', '')
                    if lang in ('en', 'ar', 'en-US', 'en-GB'):
                        url = caption.get('url') or caption.get('captionUrl', '')
                        if url:
                            with httpx.Client(timeout=15) as client:
                                cr = client.get(url, headers={"User-Agent": "Mozilla/5.0"})
                            if cr.status_code == 200:
                                # Parse VTT from invidious
                                segments = _parse_vtt_text(cr.text)
                                text = ' '.join([f"{format_time(s['start'])} {s['text']}" for s in segments])
                                return {'text': text, 'source': 'subtitles'}
        except Exception as e:
            print(f"Invidious error: {e}", file=sys.stderr)
    return None


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


def _download_subtitles_ytdlp(video_id):
    """Download auto-generated subtitles using yt-dlp with Android client."""
    import subprocess, tempfile, os, shutil, glob
    tmpdir = tempfile.mkdtemp()
    try:
        result = subprocess.run(
            [sys.executable, "-m", "yt_dlp", "--skip-download",
             "--write-auto-sub", "--sub-langs", "en,ar",
             "--sub-format", "vtt",
             "--extractor-args", "youtube:player_client=android",
             "-o", os.path.join(tmpdir, "%(id)s"),
             f"https://www.youtube.com/watch?v={video_id}"],
            capture_output=True, text=True, timeout=120
        )

        if result.returncode != 0:
            print(f"yt-dlp subtitle stderr: {result.stderr[:300]}", file=sys.stderr)

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


def _transcribe_audio(video_id):
    """Download audio via yt-dlp then Gemini handles analysis."""
    import subprocess, tempfile, os, shutil, glob
    tmpdir = tempfile.mkdtemp()
    try:
        audio_path = os.path.join(tmpdir, "audio")
        result = subprocess.run(
            [sys.executable, "-m", "yt_dlp", "-f", "worstaudio",
             "-x", "--audio-format", "mp3", "--audio-quality", "10",
             "--extractor-args", "youtube:player_client=android",
             "-o", audio_path + ".%(ext)s",
             f"https://www.youtube.com/watch?v={video_id}"],
            capture_output=True, text=True, timeout=3600
        )

        if result.returncode != 0:
            print(f"yt-dlp audio error: {result.stderr[:300]}", file=sys.stderr)
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


def extract_video_id(url):
    match = re.search(r'(?:v=|youtu\.be/)([a-zA-Z0-9_-]{11})', url)
    return match.group(1) if match else 'video'
