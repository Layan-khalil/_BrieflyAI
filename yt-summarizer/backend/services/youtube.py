import re
import sys
import httpx

def get_video_metadata(url: str) -> dict:
    """Extract video metadata using YouTube oEmbed (no bot blocking)."""
    try:
        video_id = extract_video_id(url)
        # oEmbed endpoint - very rarely blocked on cloud IPs
        oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
        with httpx.Client(timeout=15) as client:
            resp = client.get(oembed_url, headers={"User-Agent": "Mozilla/5.0"})

        if resp.status_code == 200:
            data = resp.json()
            title = data.get('title', 'Unknown')
            channel = data.get('author_name', 'Unknown')
            thumbnail = f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg"
            return {'title': title, 'duration': 0, 'channel': channel, 'thumbnail': thumbnail}

        # Fallback: try invidious
        invidious_urls = [
            f"https://inv.nadeko.net/api/v1/videos/{video_id}",
            f"https://yewtu.be/api/v1/videos/{video_id}",
            f"https://invidious.snopyta.org/api/v1/videos/{video_id}",
        ]
        for inv_url in invidious_urls:
            try:
                with httpx.Client(timeout=10) as client:
                    resp = client.get(inv_url, headers={"User-Agent": "Mozilla/5.0"})
                if resp.status_code == 200:
                    data = resp.json()
                    return {
                        'title': data.get('title', 'Unknown'),
                        'duration': data.get('lengthSeconds', 0),
                        'channel': data.get('author', 'Unknown'),
                        'thumbnail': data.get('thumbnailUrl', '') or f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg"
                    }
            except Exception:
                continue

    except Exception as e:
        print(f"Metadata error: {type(e).__name__}: {e}", file=sys.stderr)

    return {'title': 'YouTube Video', 'duration': 0, 'channel': 'YouTube', 'thumbnail': ''}


def extract_video_id(url: str) -> str:
    patterns = [
        r'(?:v=|\/)([0-9A-Za-z_-]{11})(?:[?&]|$)',
        r'youtu\.be\/([0-9A-Za-z_-]{11})'
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    raise ValueError('Invalid YouTube URL')
