import os
import re
import json
import datetime
import subprocess
import random
from pathlib import Path
from urllib.parse import quote
import requests
import time
from dotenv import load_dotenv
from PIL import Image

# Load environment variables
load_dotenv()

# ---------------- CONFIG ----------------

# Pollinations AI API Configuration
POLLINATIONS_API_KEY = os.getenv("POLLINATIONS_API_KEY", "")

NUM_IMAGES = 15  # 15 unique scenes for better coverage
IMAGE_WIDTH = 1080
IMAGE_HEIGHT = 1920
IMAGE_MODEL = "zimage"

# Upscale settings for HD YouTube videos
FINAL_WIDTH = 1080
FINAL_HEIGHT = 1920

STORY_MAX_WORDS = 130

TOPICS_FILE = "topics.txt"

IMAGES_DIR = Path("images")
OUTPUT_DIR = Path("output")
AUDIO_DIR = Path("audio")

MUSIC_FILE = AUDIO_DIR / "music.mp3"

NARRATION_FILE = OUTPUT_DIR / "narration.mp3"
STORY_FILE = OUTPUT_DIR / "story.txt"
SCENES_FILE = OUTPUT_DIR / "scenes.txt"
SUBS_FILE = OUTPUT_DIR / "subtitles.ass"
ANIMATED_VIDEO = OUTPUT_DIR / "animated.mp4"
VIDEO_WITH_SUBS = OUTPUT_DIR / "video_with_subs.mp4"
FINAL_VIDEO = OUTPUT_DIR / "final_video.mp4"

WHISPER_MODEL_NAME = "small"

# ----------------------------------------

def ensure_dirs():
    IMAGES_DIR.mkdir(exist_ok=True)
    OUTPUT_DIR.mkdir(exist_ok=True)
    AUDIO_DIR.mkdir(exist_ok=True)
    # Clean old images
    for f in IMAGES_DIR.glob("*.jpg"):
        f.unlink()

def choose_topic_for_today():
    """Select and consume a topic. Auto-generates new unique topics when running low."""
    # Auto-replenish topics if low
    try:
        check_and_update_topics()
    except Exception as e:
        print(f"[topics] Warning: Could not auto-generate topics: {e}")

    topics_file = Path(TOPICS_FILE)
    used_topics_file = Path("used_topics.txt")
    
    # Read available topics
    try:
        with open(topics_file, "r", encoding="utf-8") as f:
            topics = [line.strip() for line in f if line.strip()]
        print(f"[topics] 📚 Loaded topics: {len(topics)}")
    except Exception as e:
        print(f"[topics] ❌ Error reading {TOPICS_FILE}: {e}")
        return "[ANCIENT] Roman Law Twelve Tables"
    
    # If running low on topics (< 50), generate more
    if len(topics) < 50 and len(topics) >= 20:
        print(f"[topics] ⚠️ Only {len(topics)} topics left. Pre-emptively generating more...")
        try:
            check_and_update_topics()
            with open(topics_file, "r", encoding="utf-8") as f:
                topics = [line.strip() for line in f if line.strip()]
        except Exception as e:
            print(f"[topics] ⚠️ Could not refill: {e}")
    
    if not topics:
        print("[topics] ❌ No topics available! Using fallback.")
        return "[ANCIENT] Roman Law Twelve Tables"
    
    # Always pick the first topic (guarantees uniqueness per run)
    selected_topic = topics[0]
    remaining_topics = topics[1:]
    
    print(f"[topics] 🎯 Selected: '{selected_topic}'")
    print(f"[topics] 📊 Remaining: {len(remaining_topics)}")
    
    # Mark topic as used with verification
    try:
        with open(used_topics_file, "a", encoding="utf-8") as f:
            f.write(f"{selected_topic}\n")
            f.flush()
        print(f"[topics] ✅ Logged to used_topics.txt")
    except Exception as e:
        print(f"[topics] ⚠️ Could not log to used_topics.txt: {e}")
    
    # Remove used topic from topics.txt with verification
    write_success = False
    for attempt in range(3):
        try:
            with open(topics_file, "w", encoding="utf-8") as f:
                f.write("\n".join(remaining_topics) + "\n")
                f.flush()
            
            # Verify the write
            with open(topics_file, "r", encoding="utf-8") as f:
                verification = [line.strip() for line in f if line.strip()]
            
            if len(verification) != len(remaining_topics):
                print(f"[topics] ⚠️ Verification failed (attempt {attempt+1}/3)")
                continue
            
            write_success = True
            print(f"[topics] ✅ Topic removed and verified")
            break
        except Exception as e:
            print(f"[topics] ⚠️ Write error (attempt {attempt+1}/3): {e}")
    
    if not write_success:
        print(f"[topics] ❌ Failed to save topics.txt!")
    
    return selected_topic

def generate_story_with_pollinations(topic: str) -> str:
    """Generate a short English law explanation using Paid API (POST chat completions)."""
    clean_topic = topic.replace("[ANCIENT] ", "").replace("[MEDIEVAL] ", "").replace("[MODERN] ", "")
    # Truncate absurdly long topics (like JSON reasoning blobs)
    if len(clean_topic) > 300:
        clean_topic = clean_topic[:300]

    if topic.startswith("[ANCIENT]"):
        system = (
            "You are a legal historian specializing in ancient laws. "
            "Write a fascinating explanation in 30 seconds (80-130 words) in English. "
            "Explain the ancient law clearly with historical context and interesting facts. "
            "Use engaging storytelling and vivid descriptions. No headings or titles."
        )
    else:
        system = (
            "You are a legal expert specializing in modern laws worldwide. "
            "Write a clear explanation in 30 seconds (80-130 words) in English. "
            "Explain the modern law with current context and practical implications. "
            "Use accessible language and real-world examples. No headings or titles."
        )

    payload = {
        "model": "openai",
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": f"Topic: {clean_topic}. Explain this law with historical context."}
        ],
        "temperature": 1.0,
        "max_tokens": 300
    }

    headers = {
        "Authorization": f"Bearer {POLLINATIONS_API_KEY}",
        "Content-Type": "application/json"
    }

    print(f"[story] Generating English law content for: {clean_topic[:80]}...")

    max_retries = 3
    for attempt in range(max_retries):
        try:
            r = requests.post(
                "https://gen.pollinations.ai/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=60
            )
            r.raise_for_status()
            data = r.json()
            text = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()

            if not text:
                raise ValueError("API returned empty text")

            words = text.split()
            if len(words) > STORY_MAX_WORDS:
                text = " ".join(words[:STORY_MAX_WORDS])

            with open(STORY_FILE, "w", encoding="utf-8") as f:
                f.write(text)

            print(f"[story] Law content generated ({len(text.split())} words)")
            return text

        except Exception as e:
            print(f"[story] Attempt {attempt+1}/{max_retries} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(5)
            else:
                raise

def generate_scene_descriptions(story: str) -> list:
    """Enrich each story sentence with visual legal context so images match the content."""
    print(f"[scenes] Extracting {NUM_IMAGES} visual scene descriptions...")

    sentences = re.split(r'[.!?]+\s*', story.strip())
    sentences = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 10]

    visual_enhancers = [
        "detailed close-up view showing",
        "wide dramatic scene illustrating",
        "historical reenactment depicting",
        "cinematic shot capturing the moment of",
        "bird's eye view of the scene where",
        "intimate close-up of the key figure involved in",
        "grand wide shot of the historical event where",
        "dramatic angle showing the tension of",
        "detailed illustration of the practice of",
        "atmospheric scene set during",
        "portrait-style view of the central figure behind",
        "action shot showing the execution of",
        "solemn wide view of the ceremony of",
        "candid historical moment capturing",
        "dramatic reenactment showing the consequences of",
    ]

    unique_scenes = []
    for i in range(NUM_IMAGES):
        base = sentences[i % len(sentences)]
        enhancer = visual_enhancers[i % len(visual_enhancers)]
        unique_scenes.append(f"{enhancer} {base}")

    with open(SCENES_FILE, "w", encoding="utf-8") as f:
        for i, scene in enumerate(unique_scenes):
            f.write(f"{i+1}. {scene}\n")

    print(f"[scenes] Created {len(unique_scenes)} visual scenes")
    return unique_scenes

def download_image_from_drive(idx: int) -> Path:
    """Pick a random image from Google Drive folder (weighted by least-used)."""
    import json, random
    from pathlib import Path
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload

    service_key = os.environ.get("GOOGLE_SERVICE_ACCOUNT_KEY")
    folder_id = os.environ.get("GOOGLE_DRIVE_FOLDER_ID")

    if not service_key:
        raise ValueError("GOOGLE_SERVICE_ACCOUNT_KEY environment variable required")
    if not folder_id:
        raise ValueError("GOOGLE_DRIVE_FOLDER_ID environment variable required")

    cred = service_account.Credentials.from_service_account_info(
        json.loads(service_key),
        scopes=["https://www.googleapis.com/auth/drive.readonly"]
    )
    service = build("drive", "v3", credentials=cred)

    results = service.files().list(
        q=f"'{folder_id}' in parents and (mimeType='image/png' or mimeType='image/jpeg' or mimeType='image/jpg' or mimeType='image/webp')",
        fields="files(id, name)",
        pageSize=1000
    ).execute()
    files = results.get("files", [])

    if not files:
        raise ValueError("No images found in Google Drive folder")

    used_log = Path("used_images.json")
    if used_log.exists():
        with open(used_log) as f:
            usage = json.load(f)
    else:
        usage = {}

    weights = []
    for f in files:
        count = usage.get(f["id"], 0)
        weights.append(max(1, 10 - count))

    chosen = random.choices(files, weights=weights, k=1)[0]
    print(f"[image] Downloading {chosen['name']} from Drive...")

    output_path = Path(f"images/scene_{idx:02d}.jpg")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    request = service.files().get_media(fileId=chosen["id"])
    fh = open(output_path, "wb")
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()
    fh.close()

    usage[chosen["id"]] = usage.get(chosen["id"], 0) + 1
    with open(used_log, "w") as f:
        json.dump(usage, f)

    print(f"[image] Downloaded: {chosen['name']}")
    return output_path

def generate_image(scene: str, idx: int) -> Path:
    """Download image from Google Drive instead of AI generation."""
    return download_image_from_drive(idx)

def generate_images(scenes: list):
    """Generate unique images for each scene SEQUENTIALLY (avoids rate limits)"""
    print(f"[image] Generating {NUM_IMAGES} images sequentially (avoiding rate limits)...")
    return [generate_image(scene, i) for i, scene in enumerate(scenes)]

def generate_tts(story: str):
    """Generate narration using edge-tts (free Microsoft TTS)."""
    import asyncio
    try:
        import edge_tts
    except ImportError:
        subprocess.run(["pip", "install", "edge-tts"], check=True)
        import edge_tts
    
    print("[tts] Generating English narration with edge-tts...")
    
    VOICE = "en-US-GuyNeural"  # English male voice (or use "en-US-JennyNeural" for female)
    
    async def generate():
        communicate = edge_tts.Communicate(story, VOICE)
        await communicate.save(str(NARRATION_FILE))
    
    asyncio.run(generate())
    print(f"[tts] Narration saved to {NARRATION_FILE}")

def generate_word_subtitles():
    """Generate WORD-BY-WORD subtitles using Vosk (lightweight!)."""
    print("[subs] Generating word-level English subtitles with Vosk...")
    
    import json
    import wave
    from vosk import Model, KaldiRecognizer
    import os
    
    # Download Vosk model if not exists
    model_path = "vosk-model-small-en-us-0.15"
    if not os.path.exists(model_path):
        print("[subs] Downloading Vosk English model (~40 MB)...")
        import urllib.request
        import zipfile
        
        url = "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip"
        zip_path = "vosk-model.zip"
        
        urllib.request.urlretrieve(url, zip_path)
        
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(".")
        
        os.remove(zip_path)
        print("[subs] Model downloaded!")
    
    # Convert MP3 to WAV for Vosk
    wav_file = "output/narration.wav"
    os.system(f'ffmpeg -y -i {NARRATION_FILE} -ar 16000 -ac 1 {wav_file}')
    
    # Load Vosk model
    model = Model(model_path)
    
    # Open WAV file
    wf = wave.open(wav_file, "rb")
    rec = KaldiRecognizer(model, wf.getframerate())
    rec.SetWords(True)  # Enable word-level timestamps
    
    # Process audio
    words = []
    while True:
        data = wf.readframes(4000)
        if len(data) == 0:
            break
        if rec.AcceptWaveform(data):
            result = json.loads(rec.Result())
            if 'result' in result:
                for word_info in result['result']:
                    words.append({
                        'word': word_info['word'].upper(),
                        'start': word_info['start'],
                        'end': word_info['end']
                    })
    
    # Final result
    final_result = json.loads(rec.FinalResult())
    if 'result' in final_result:
        for word_info in final_result['result']:
            words.append({
                'word': word_info['word'].upper(),
                'start': word_info['start'],
                'end': word_info['end']
            })
    
    # Create ASS subtitle file
    ass_content = """[Script Info]
Title: Law Story
ScriptType: v4.00+

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial Black,16,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,2,1,5,10,10,50,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    
    for word in words:
        start = word['start']
        end = word['end']
        text = word['word']
        
        start_time = f"{int(start//3600)}:{int((start%3600)//60):02d}:{start%60:.2f}"
        end_time = f"{int(end//3600)}:{int((end%3600)//60):02d}:{end%60:.2f}"
        
        ass_content += f"Dialogue: 0,{start_time},{end_time},Default,,0,0,0,,{text}\n"
    
    # Save ASS file
    with open(SUBS_FILE, "w", encoding="utf-8") as f:
        f.write(ass_content)
    
    print(f"[subs] WORD-BY-WORD subtitles saved ({len(words)} words)")

def get_audio_duration(audio_file):
    """Get duration of audio file using ffprobe."""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(audio_file)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return float(result.stdout.strip())

def create_animated_slideshow(image_paths):
    """Create animated slideshow with Ken Burns zoom effect."""
    print("[video] Creating animated slideshow with Ken Burns effect...")
    
    # Get audio duration to match video length
    duration = get_audio_duration(NARRATION_FILE)
    per_image = duration / len(image_paths)
    
    # Create individual animated clips with zoom effect
    clips = []
    for i, img_path in enumerate(image_paths):
        clip_file = OUTPUT_DIR / f"clip_{i:02d}.mp4"
        clips.append(clip_file)
        
        # Calculate frames (30 fps)
        frames = max(int(per_image * 30), 60)
        
        # Alternate between zoom in and zoom out for variety
        if i % 2 == 0:
            # Zoom in effect
            zoom_start = 1.0
            zoom_end = 1.3
        else:
            # Zoom out effect  
            zoom_start = 1.3
            zoom_end = 1.0
        
        # Simple zoom with scale filter (more reliable on Windows)
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1",
            "-i", str(img_path),
            "-vf", (
                f"scale=8000:-1,"
                f"zoompan=z='if(lte(on,1),{zoom_start},{zoom_start}+(({zoom_end}-{zoom_start})/{frames})*on)':"
                f"d={frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={FINAL_WIDTH}x{FINAL_HEIGHT}:fps=30"
            ),
            "-t", str(per_image),
            "-c:v", "libx264",
            "-preset", "slow",  # Better quality
            "-crf", "18",  # High quality (lower = better, 18-23 is good)
            "-pix_fmt", "yuv420p",
            str(clip_file)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"[video] Zoom failed for clip {i+1}, using fallback...")
            # Fallback: simple static with slight movement
            cmd_fallback = [
                "ffmpeg", "-y",
                "-loop", "1",
                "-i", str(img_path),
                "-vf", f"scale={FINAL_WIDTH}:{FINAL_HEIGHT}:force_original_aspect_ratio=increase,crop={FINAL_WIDTH}:{FINAL_HEIGHT},fps=30",
                "-t", str(per_image),
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                str(clip_file)
            ]
            subprocess.run(cmd_fallback, check=True, capture_output=True)
        
        print(f"[video] Animated clip {i+1}/{len(image_paths)}")
    
    # Create concat list
    concat_file = OUTPUT_DIR / "concat.txt"
    with open(concat_file, "w") as f:
        for clip in clips:
            f.write(f"file '{clip.resolve()}'\n")
    
    # Concatenate all clips
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(concat_file),
        "-c", "copy",
        str(ANIMATED_VIDEO)
    ]
    subprocess.run(cmd, check=True)
    print(f"[video] Animated slideshow saved to {ANIMATED_VIDEO}")
    
    # Cleanup individual clips
    for clip in clips:
        if clip.exists():
            clip.unlink()

def add_subtitles():
    """Overlay ASS subtitles on video."""
    print("[video] Adding UPPERCASE subtitles...")
    
    # Windows path needs special handling for FFmpeg filter
    subs_path = str(SUBS_FILE.resolve()).replace("\\", "/").replace(":", "\\:")
    
    cmd = [
        "ffmpeg", "-y",
        "-i", str(ANIMATED_VIDEO),
        "-vf", f"ass='{subs_path}'",
        "-c:v", "libx264",
        "-preset", "slow",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        str(VIDEO_WITH_SUBS)
    ]
    subprocess.run(cmd, check=True)
    print(f"[video] Video with subtitles saved to {VIDEO_WITH_SUBS}")

def merge_audio():
    """Merge video with narration and background music."""
    print("[merge] Merging audio with background music...")
    
    if MUSIC_FILE.exists():
        # Merge narration + background music (music at lower volume)
        cmd = [
            "ffmpeg", "-y",
            "-i", str(VIDEO_WITH_SUBS),
            "-i", str(NARRATION_FILE),
            "-i", str(MUSIC_FILE),
            "-filter_complex", "[2:a]volume=0.25[bg];[1:a][bg]amix=inputs=2:duration=first[a]",
            "-map", "0:v",
            "-map", "[a]",
            "-shortest",
            "-c:v", "copy",
            str(FINAL_VIDEO)
        ]
    else:
        print("[merge] No music.mp3 found, using narration only")
        cmd = [
            "ffmpeg", "-y",
            "-i", str(VIDEO_WITH_SUBS),
            "-i", str(NARRATION_FILE),
            "-map", "0:v",
            "-map", "1:a",
            "-shortest",
            "-c:v", "copy",
            str(FINAL_VIDEO)
        ]
    
    subprocess.run(cmd, check=True)
    print(f"[merge] Final video saved to {FINAL_VIDEO}")

def main():
    ensure_dirs()

    topic = choose_topic_for_today()
    print("=" * 60)
    print(f"=== Topic: {topic}")
    print("=" * 60)
    
    # Save topic for YouTube title generation
    topic_file = OUTPUT_DIR / "topic.txt"
    topic_file.write_text(topic, encoding='utf-8')
    
    if topic.startswith("[ANCIENT]"):
        topic_era = "ANCIENT"
    else:
        topic_era = "MODERN"
    
    # Store era as function attribute for image generation
    generate_image.topic_era = topic_era
    print(f"[main] Era: {topic_era}")

    # 1. Generate story with Pollinations AI
    story = generate_story_with_pollinations(topic)
    
    # 2. Generate unique scene descriptions from the story
    scenes = generate_scene_descriptions(story)
    
    # 3. Generate unique images for each scene
    images = generate_images(scenes)

    # 4. Generate narration with TTS
    generate_tts(story)
    
    # 5. Generate word-level UPPERCASE subtitles with Whisper
    generate_word_subtitles()
    
    # 6. Create animated slideshow with Ken Burns effect
    create_animated_slideshow(images)
    
    # 7. Add subtitles overlay
    add_subtitles()
    
    # 8. Merge audio (narration + background music)
    merge_audio()

    print("=" * 60)
    print(f"✅ DONE. Video ready: {FINAL_VIDEO}")
    print("=" * 60)

if __name__ == "__main__":
    main()
