from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import json
import os

load_dotenv()

from services.transcript import get_transcript, _transcribe_audio_ytdlp
from services.youtube import get_video_metadata
from services.gemini import analyze_sync, analyze_from_audio, analyze_from_youtube_url
from models import SummarizeRequest
import shutil

app = FastAPI()

# CORS: allow localhost for dev + FRONTEND_URL + any Vercel preview domain
origins = ["http://localhost:3000", "http://localhost:3001"]
if os.getenv("FRONTEND_URL"):
    origins.append(os.getenv("FRONTEND_URL"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
@app.post("/api/summarize")
def summarize(req: SummarizeRequest):
    try:
        # Get language from request
        language = req.language if hasattr(req, 'language') else 'en'
        
        # Fetch metadata
        metadata = get_video_metadata(req.url)
        
        # Fetch transcript
        transcript_data = get_transcript(req.url)

        # Check if transcript is available
        if transcript_data['source'] == 'none':
            if language == 'ar':
                no_sub = {
                    "summary": "هذا الفيديو لا يحتوي على ترجمة نصية. يرجى تجربة فيديو آخر.",
                    "key_insights": ["لا توجد ترجمة نصية متاحة للتحليل"],
                    "bullet_notes": ["جرب فيديو يحتوي على ترجمة نصية"],
                    "timestamps": []
                }
            else:
                no_sub = {
                    "summary": "This video doesn't have subtitles available. Please try another video.",
                    "key_insights": ["No subtitles available for analysis"],
                    "bullet_notes": ["Try a video with captions/subtitles"],
                    "timestamps": []
                }
            return {
                "metadata": metadata,
                "transcript_source": "none",
                "analysis": no_sub
            }

        # No subtitles: try Gemini's native YouTube URL support first
        if transcript_data['source'] == 'gemini_youtube':
            try:
                analysis = analyze_from_youtube_url(
                    transcript_data['url'],
                    metadata["title"],
                    language,
                    metadata.get("duration", 0)
                )
                return {
                    "metadata": metadata,
                    "transcript_source": "gemini",
                    "analysis": analysis
                }
            except Exception as yt_err:
                # Gemini couldn't access this URL — fall back to downloading audio
                import sys
                print(f"[Main] YouTube URL failed ({yt_err}), falling back to audio download", file=sys.stderr)
                audio_data = _transcribe_audio_ytdlp(transcript_data['url'].split('v=')[-1])
                if audio_data['source'] == 'gemini_audio':
                    analysis = analyze_from_audio(
                        audio_data['audio_path'],
                        metadata["title"],
                        language,
                        metadata.get("duration", 0)
                    )
                    shutil.rmtree(audio_data.get('_tmpdir', ''), ignore_errors=True)
                    return {
                        "metadata": metadata,
                        "transcript_source": "gemini",
                        "analysis": analysis
                    }
                # Audio download also failed — nothing we can do
                if language == 'ar':
                    return {"metadata": metadata, "transcript_source": "none", "analysis": {
                        "summary": "تعذر الوصول إلى محتوى هذا الفيديو. يرجى تجربة فيديو آخر.",
                        "key_insights": [], "bullet_notes": [], "timestamps": []
                    }}
                return {"metadata": metadata, "transcript_source": "none", "analysis": {
                    "summary": "Could not access this video's content. Please try another video.",
                    "key_insights": [], "bullet_notes": [], "timestamps": []
                }}

        # No subtitles: analyze audio directly with Gemini (one API call instead of transcribe+summarize)
        if transcript_data['source'] == 'gemini_audio':
            analysis = analyze_from_audio(
                transcript_data['audio_path'],
                metadata["title"],
                language,
                metadata.get("duration", 0)
            )
            shutil.rmtree(transcript_data.get('_tmpdir', ''), ignore_errors=True)
            return {
                "metadata": metadata,
                "transcript_source": "gemini",
                "analysis": analysis
            }

        # Subtitles available: analyze transcript with Gemini
        analysis = analyze_sync(
            transcript_data["text"],
            metadata["title"],
            language,
            metadata.get("duration", 0)
        )
        
        # Return combined response
        return {
            "metadata": metadata,
            "transcript_source": transcript_data["source"],
            "analysis": analysis
        }
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback; traceback.print_exc()
        language = req.language if hasattr(req, 'language') else 'en'
        if language == 'ar':
            return {
                "metadata": {"title": "", "duration": 0, "channel": "", "thumbnail": ""},
                "transcript_source": "error",
                "analysis": {
                    "summary": "حدث خطأ غير متوقع. يرجى المحاولة مرة أخرى.",
                    "key_insights": ["يرجى المحاولة مرة أخرى"],
                    "bullet_notes": ["يرجى المحاولة مرة أخرى"],
                    "timestamps": []
                }
            }
        else:
            return {
                "metadata": {"title": "", "duration": 0, "channel": "", "thumbnail": ""},
                "transcript_source": "error",
                "analysis": {
                    "summary": "An unexpected error occurred. Please try again.",
                    "key_insights": ["Please try again"],
                    "bullet_notes": ["Please try again"],
                    "timestamps": []
                }
            }

@app.get("/health")
def health():
    return {"status": "ok"}
