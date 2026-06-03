import os
import sys
import json
import asyncio
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.youtube import get_video_metadata
from services.transcript import get_transcript
from services.gemini import analyze_stream

async def main():
    url = 'https://youtu.be/dALYlOpvMXI'

    print('Testing metadata...')
    meta = get_video_metadata(url)
    print('Title:', meta['title'])

    print('Testing transcript...')
    t = get_transcript(url)
    print('Transcript source:', t['source'])
    print('Transcript length:', len(t['text']))

    print('Testing Gemini...')
    result = ''
    async for chunk in analyze_stream(t['text'], meta['title']):
        result += chunk

    clean = result.replace('```json', '').replace('```', '').strip()
    
    try:
        parsed = json.loads(clean)
        print('\n--- SUMMARY ---')
        print(parsed['summary'])
        print('\n--- KEY INSIGHTS ---')
        for i in parsed['key_insights']:
            print(' -', i)
        print('\n--- NOTES ---')
        for n in parsed['bullet_notes']:
            print(' -', n)
        print('\n--- TIMESTAMPS ---')
        for ts in parsed['timestamps']:
            print(f" [{ts['time']}] {ts['topic']}")
    except Exception as e:
        print('Parse error:', e)
        print('Raw response:', result)

asyncio.run(main())