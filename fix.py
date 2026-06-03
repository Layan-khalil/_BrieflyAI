import codecs
code = """from youtube_transcript_api import YouTubeTranscriptApi
import re

def get_transcript(url):
    video_id = extract_video_id(url)
    try:
        ytt = YouTubeTranscriptApi()
        tlist = ytt.fetch(video_id, languages=['en', 'ar'])
        return {'text': ' '.join([t.text for t in tlist]), 'source': 'subtitles'}
    except:
        try:
            ytt = YouTubeTranscriptApi()
            fetched = ytt.list(video_id)
            transcript = next(iter(fetched))
            tlist = transcript.fetch()
            return {'text': ' '.join([t.text for t in tlist]), 'source': 'subtitles'}
        except Exception as e:
            raise Exception(f'Could not get transcript: {e}')

def extract_video_id(url):
    match = re.search(r'(?:v=|youtu\\.be/)([a-zA-Z0-9_-]{11})', url)
    return match.group(1) if match else 'video'
"""
path = r'C:\Users\HPCO\Documents\windsurf\BrieflyAI\yt-summarizer\backend\services\transcript.py'
with codecs.open(path, 'w', 'utf-8') as f:
    f.write(code)
print('Done')