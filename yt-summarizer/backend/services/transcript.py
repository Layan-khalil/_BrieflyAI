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

    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)

        # Strategy 1: Find manually created transcript in preferred languages
        try:
            transcript = transcript_list.find_transcript(['en', 'ar'])
            segments = transcript.fetch()
            text = ' '.join([f"{format_time(s['start'])} {s['text']}" for s in segments])
            return {'text': text, 'source': 'subtitles'}
        except (NoTranscriptFound, StopIteration):
            pass

        # Strategy 2: Find ANY available transcript (auto-generated or manual)
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

    # All subtitle strategies failed — fall back to audio transcription
    return _transcribe_audio(video_id)


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