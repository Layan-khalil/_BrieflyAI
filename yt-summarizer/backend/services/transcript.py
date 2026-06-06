from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
from youtube_transcript_api._errors import VideoUnavailable
import os
import re
import sys
import subprocess
import tempfile
import shutil
import glob

def format_time(seconds):
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"[{h}:{m:02d}:{s:02d}]"
    return f"[{m:02d}:{s:02d}]"

def get_transcript(url):
    video_id = extract_video_id(url)

    # Strategy 1: YouTube Transcript API
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)

        # 1a: Find manually created transcript in preferred languages
        try:
            transcript = transcript_list.find_transcript(['en', 'ar'])
            segments = transcript.fetch()
            text = ' '.join([f"{format_time(s['start'])} {s['text']}" for s in segments])
            return {'text': text, 'source': 'subtitles'}
        except (NoTranscriptFound, StopIteration):
            pass

        # 1b: Find ANY available transcript
        try:
            transcript = next(iter(transcript_list))
            segments = transcript.fetch()
            text = ' '.join([f"{format_time(s['start'])} {s['text']}" for s in segments])
            return {'text': text, 'source': 'subtitles'}
        except StopIteration:
            pass

    except (TranscriptsDisabled, VideoUnavailable):
        pass
    except Exception as e:
        print(f"Transcript list error: {type(e).__name__}: {e}", file=sys.stderr)

    # Strategy 2: yt-dlp subtitle download (works where YouTube API is blocked)
    try:
        return _download_subtitles_ytdlp(video_id)
    except Exception as e:
        print(f"yt-dlp subtitle error: {type(e).__name__}: {e}", file=sys.stderr)

    # Strategy 3: Fall back to audio transcription
    return _transcribe_audio(video_id)


def _download_subtitles_ytdlp(video_id):
    """Download auto-generated subtitles using yt-dlp (bypasses YouTube Transcript API)."""
    tmpdir = tempfile.mkdtemp()
    try:
        result = subprocess.run(
            [sys.executable, "-m", "yt_dlp", "--skip-download",
             "--write-auto-sub", "--sub-langs", "en,ar",
             "--sub-format", "vtt",
             "-o", os.path.join(tmpdir, "%(id)s"),
             f"https://www.youtube.com/watch?v={video_id}"],
            capture_output=True, text=True, timeout=120
        )

        if result.returncode != 0:
            print(f"yt-dlp subtitle download stderr: {result.stderr[:500]}", file=sys.stderr)

        # Find the .vtt subtitle file
        vtt_files = glob.glob(os.path.join(tmpdir, "*.vtt"))
        if not vtt_files:
            shutil.rmtree(tmpdir, ignore_errors=True)
            raise Exception("no vtt files found")

        vtt_path = vtt_files[0]
        segments = _parse_vtt(vtt_path)
        text = ' '.join([f"{format_time(s['start'])} {s['text']}" for s in segments])
        shutil.rmtree(tmpdir, ignore_errors=True)
        return {'text': text, 'source': 'subtitles'}
    except:
        shutil.rmtree(tmpdir, ignore_errors=True)
        raise


def _parse_vtt(vtt_path):
    """Parse a .vtt subtitle file into a list of {start, text} segments."""
    import re
    segments = []
    with open(vtt_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    ts_pattern = re.compile(r'(\d+):(\d+):(\d+)\.\d+')
    current_time = None
    current_text = []

    for line in lines:
        line = line.strip()
        match = ts_pattern.search(line)
        if match:
            if current_time is not None and current_text:
                segments.append({
                    'start': current_time,
                    'text': ' '.join(current_text)
                })
            h, m, s = int(match.group(1)), int(match.group(2)), int(match.group(3))
            current_time = h * 3600 + m * 60 + s
            current_text = []
        elif line and not line.startswith('WEBVTT') and not line.startswith('NOTE') and not line.startswith('Kind:') and not line.startswith('Language:'):
            current_text.append(line.replace('&gt;', '>').replace('&lt;', '<').replace('&amp;', '&'))

    if current_time is not None and current_text:
        segments.append({
            'start': current_time,
            'text': ' '.join(current_text)
        })

    return segments


def _transcribe_audio(video_id):
    """Download audio only — direct Gemini analysis happens in main.py."""
    tmpdir = tempfile.mkdtemp()
    try:
        audio_path = os.path.join(tmpdir, "audio")

        result = subprocess.run(
            [sys.executable, "-m", "yt_dlp", "-f", "worstaudio",
             "-x", "--audio-format", "mp3", "--audio-quality", "10",
             "-o", audio_path + ".%(ext)s",
             f"https://www.youtube.com/watch?v={video_id}"],
            capture_output=True, text=True, timeout=3600
        )

        if result.returncode != 0:
            print(f"yt-dlp audio download failed: {result.stderr[:500]}", file=sys.stderr)
            shutil.rmtree(tmpdir, ignore_errors=True)
            return {'source': 'none', 'text': ''}

        files = glob.glob(os.path.join(tmpdir, "*"))
        if not files:
            shutil.rmtree(tmpdir, ignore_errors=True)
            return {'source': 'none', 'text': ''}

        # Return the audio path — main.py will pass it directly to Gemini for analysis
        return {'source': 'gemini_audio', 'text': '', 'audio_path': files[0], '_tmpdir': tmpdir}

    except Exception as e:
        print(f"Audio download error: {type(e).__name__}: {e}", file=sys.stderr)
        shutil.rmtree(tmpdir, ignore_errors=True)
        return {'source': 'none', 'text': ''}


def extract_video_id(url):
    match = re.search(r'(?:v=|youtu\.be/)([a-zA-Z0-9_-]{11})', url)
    return match.group(1) if match else 'video'