from youtube_transcript_api import YouTubeTranscriptApi
import re

def format_time(seconds):
    m, s = divmod(int(seconds), 60)
    return f"[{m:02d}:{s:02d}]"

def get_transcript(url):
    video_id = extract_video_id(url)
    try:
        ytt = YouTubeTranscriptApi()
        tlist = ytt.fetch(video_id, languages=['en', 'ar'])
        return {
            'text': ' '.join([f"{format_time(t.start)} {t.text}" for t in tlist]),
            'source': 'subtitles'
        }
    except:
        try:
            ytt = YouTubeTranscriptApi()
            fetched = ytt.list(video_id)
            transcript = next(iter(fetched))
            tlist = transcript.fetch()
            return {
                'text': ' '.join([f"{format_time(t.start)} {t.text}" for t in tlist]),
                'source': 'subtitles'
            }
        except Exception as e:
            raise Exception(f'Could not get transcript: {e}')

def extract_video_id(url):
    match = re.search(r'(?:v=|youtu\.be/)([a-zA-Z0-9_-]{11})', url)
    return match.group(1) if match else 'video'