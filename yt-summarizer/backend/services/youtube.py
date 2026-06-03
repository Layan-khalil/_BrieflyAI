import re
import yt_dlp

def get_video_metadata(url: str) -> dict:
    """Extract video metadata using yt-dlp"""
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True,  # Faster extraction
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=False)
            return {
                'title': info.get('title', 'Unknown'),
                'duration': info.get('duration', 0),
                'channel': info.get('uploader', 'Unknown'),
                'thumbnail': info.get('thumbnail', '')
            }
        except Exception as e:
            raise Exception(f'Could not fetch metadata: {e}')

def extract_video_id(url: str) -> str:
    """Extract YouTube video ID from URL"""
    patterns = [
        r'(?:v=|\/)([0-9A-Za-z_-]{11})(?:[?&]|$)',
        r'youtu\.be\/([0-9A-Za-z_-]{11})'
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    raise ValueError('Invalid YouTube URL')

    