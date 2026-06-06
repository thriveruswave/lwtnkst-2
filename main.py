import os
import re
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
    is_ancient = topic.startswith("[ANCIENT]")
    is_medieval = topic.startswith("[MEDIEVAL]")
    is_modern = topic.startswith("[MODERN]")
    clean_topic = topic.replace("[ANCIENT] ", "").replace("[MEDIEVAL] ", "").replace("[MODERN] ", "")
    # Truncate absurdly long topics (like JSON reasoning blobs)
    if len(clean_topic) > 300:
        clean_topic = clean_topic[:300]

    if is_ancient:
        system = (
            "You are a legal historian specializing in ancient laws. "
            "Write a fascinating explanation in 30 seconds (80-130 words) in English. "
            "Explain the ancient law clearly with historical context and interesting facts. "
            "Use engaging storytelling and vivid descriptions. No headings or titles."
        )
    elif is_medieval:
        system = (
            "You are a legal historian specializing in medieval laws. "
            "Write an intriguing explanation in 30 seconds (80-130 words) in English. "
            "Explain the medieval law with historical context and fascinating details. "
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

def generate_image(scene: str, idx: int) -> Path:
    """Generate VIRAL-WORTHY, contextually relevant images using scene-specific prompts."""
    
    if not POLLINATIONS_API_KEY:
        raise ValueError("POLLINATIONS_API_KEY not set! Get your API key from https://enter.pollinations.ai")
    
    # Create unique seed for each image
    seed = hash(scene + str(idx)) % 1000000
    
    # Determine era
    topic_era = getattr(generate_image, 'topic_era', 'MODERN')
    
    # VIRAL-OPTIMIZED PROMPTS: Scene-specific, attention-grabbing, contextually relevant
    # Each prompt is tailored to the ACTUAL scene content for maximum engagement
    
    if topic_era == 'ANCIENT':
        style_prompt = (
            # CRITICAL: SFW AND CLOTHING FIRST - ABSOLUTE PRIORITY
            f"SAFE FOR WORK, FULLY CLOTHED PEOPLE, "
            f"everyone wearing complete period clothing, "
            f"full robes and togas covering entire body, "
            f"modest historical dress, NO NUDITY, "
            f"professional family-friendly content, "
            # Anatomy (with clothing)
            f"professional photograph, correct human anatomy, "
            f"beautiful faces with clear eyes nose mouth, "
            f"normal hands with 5 fingers, proper proportions, "
            f"realistic clothed people, "
            # Scene content
            f"{scene}, "
            f"ancient Roman or Greek legal setting, "
            f"judges and citizens in full traditional robes, "
            f"detailed expressive faces, dignified poses, "
            # Environment
            f"magnificent ancient architecture, marble columns, "
            f"stone temples, classical buildings, "
            # Lighting
            f"golden hour lighting, warm sunlight, cinematic, "
            # Quality
            f"photorealistic, ultra detailed, sharp focus, "
            f"professional photography, 8k quality, "
            f"National Geographic documentary style"
        )
    elif topic_era == 'MEDIEVAL':
        scene_themes = [
            (f"king on ornate throne in grand castle throne room, royal court gathered, nobles in velvet robes and crowns, massive stained glass window behind throne, stone pillars, tapestries, {scene}",
             f"royal court session, king issuing decree, candlelit throne room, majestic"),
            (f"village market square on market day, merchants selling goods at wooden stalls, peasants in wool tunics and linen, cobblestones, thatched roofs, town crier, {scene}",
             f"medieval village life, bustling market, colorful produce and fabrics, sunny"),
            (f"monks in a stone monastery scriptorium, copying illuminated manuscripts by candlelight, towering bookshelves, parchment and ink, arched windows, {scene}",
             f"monastic library, quiet scholarly atmosphere, warm candle glow, peaceful"),
            (f"knights in shining armor on horseback at a jousting tournament, colorful heraldic banners, wooden stands filled with cheering nobles, blue sky, {scene}",
             f"medieval tournament, action scene, dust and excitement, bright outdoors"),
            (f"gothic cathedral interior, towering arched ceilings, rainbow light through stained glass, priest in ornate vestments at altar, praying congregation, {scene}",
             f"cathedral ceremony, sacred atmosphere, divine light through windows, awe-inspiring"),
            (f"dungeon scene, torch-lit stone prison cell, iron bars, chains on walls, jailer in leather armor, prisoner in rough tunic, mysterious shadows, {scene}",
             f"dark dungeon, secret meeting, atmospheric torchlight, tense mood"),
            (f"grand medieval banquet hall, long wooden table filled with food and drink, nobles feasting, minstrels playing harp and lute, roaring fireplace, {scene}",
             f"royal feast, lavish celebration, warm firelight, joyful merrymaking"),
            (f"castle siege, trebuchets and battering rams attacking stone walls, soldiers with shields and swords, smoke and fire, banners flying, dramatic, {scene}",
             f"battle scene, medieval warfare, chaos and action, epic scale"),
            (f"medieval courtroom in a guild hall, magistrates in fur-trimmed robes at elevated bench, merchants and craftsmen presenting cases, wooden interior, {scene}",
             f"guild court, legal proceeding, serious businessmen, formal atmosphere"),
            (f"village church interior, stone walls, wooden pews, simple altar with candles, villagers in humble clothing gathered for prayer, peaceful, {scene}",
             f"village church, quiet devotion, humble faithful, serene atmosphere"),
            (f"scribe at work in a tower study, writing on parchment with quill, maps and charts on walls, astronomical instruments, single candle, cozy, {scene}",
             f"medieval study, scholar at work, intellectual pursuit, warm solitary light"),
            (f"castle courtyard, soldiers training with swords and shields, blacksmith at forge making armor, horses in stable, busy castle life, sunny day, {scene}",
             f"castle daily life, training yard, active bustling, medieval routine"),
            (f"winter scene, snow-covered castle and village, peasants in fur cloaks warming at bonfire, frozen river, bare trees, twilight sky with stars, {scene}",
             f"medieval winter, cold atmosphere, snow and firelight, beautiful"),
            (f"stone bridge over moat leading to castle gatehouse, travelers on horseback, merchant carts, drawbridge raised, flags on towers, countryside, {scene}",
             f"castle entrance, travelers arriving, medieval landscape, scenic view"),
            (f"royal bedchamber at dawn, canopy bed with rich curtains, noblewoman in velvet gown attended by maids, sunrise through arched window, intimate, {scene}",
             f"royal chamber, morning ritual, elegant and intimate, soft morning light"),
        ]
        theme = scene_themes[idx % len(scene_themes)]
        style_prompt = (
            f"SAFE FOR WORK, FULLY CLOTHED PEOPLE, "
            f"everyone in complete modest medieval period clothing, NO NUDITY, "
            f"correct human anatomy, beautiful faces, proper proportions, realistic people, "
            f"{theme[0]}, "
            f"{theme[1]}, "
            f"highly detailed photorealistic, sharp focus, 8k, cinematic quality"
        )
    else:  # MODERN
        style_prompt = (
            # CRITICAL: SFW AND CLOTHING FIRST - ABSOLUTE PRIORITY
            f"SAFE FOR WORK, FULLY CLOTHED PEOPLE, "
            f"everyone wearing complete business attire, "
            f"full suits and professional clothing covering entire body, "
            f"modest business dress, NO NUDITY, "
            f"professional family-friendly content, "
            # Anatomy (with clothing)
            f"professional photograph, correct human anatomy, "
            f"beautiful faces with clear eyes nose mouth, "
            f"normal hands with 5 fingers, proper proportions, "
            f"realistic clothed people, "
            # Scene content
            f"{scene}, "
            f"modern professional legal setting, "
            f"diverse lawyers and judges in full business suits, "
            f"detailed expressive faces, professional poses, "
            # Environment
            f"contemporary courthouse, glass and marble, modern architecture, "
            # Lighting
            f"professional lighting, bright clean atmosphere, "
            # Quality
            f"photorealistic, ultra detailed, sharp focus, "
            f"professional photography, 8k quality, "
            f"corporate magazine style"
        )
    
    # COMPREHENSIVE negative prompt - block ALL deformities AND NSFW
    negative_prompt = (
        # CRITICAL: NSFW blocking
        "nude, nudity, naked, nsfw, exposed skin, bare chest, "
        "bare body, undressed, topless, revealing, "
        "inappropriate, adult content, sexual, "
        # Face deformities
        "deformed face, ugly face, distorted face, malformed face, "
        "disfigured face, bad eyes, crossed eyes, missing eyes, extra eyes, "
        "bad nose, missing nose, deformed mouth, bad teeth, "
        "asymmetrical face, mutated face, "
        # Body deformities
        "deformed body, bad anatomy, wrong anatomy, extra limbs, "
        "missing limbs, extra arms, extra legs, missing arms, missing legs, "
        "bad hands, deformed hands, extra fingers, missing fingers, "
        "fused fingers, mutated hands, poorly drawn hands, "
        "bad feet, deformed feet, extra toes, missing toes, "
        "malformed limbs, disfigured, mutation, mutated, "
        "extra body parts, duplicate body parts, "
        # Proportions
        "bad proportions, long neck, long body, elongated, "
        "stretched, distorted proportions, "
        # Quality issues
        "blurry, low quality, low resolution, pixelated, "
        "grainy, jpeg artifacts, compression artifacts, "
        # Style issues
        "cartoon, anime, drawing, painting, illustration, "
        "3d render, cgi, "
        # Other
        "watermark, text, signature, username, "
        "cropped, cut off, out of frame"
    )
    
    # Encode prompts
    safe_prompt = quote(style_prompt)
    safe_negative = quote(negative_prompt)
    
    # Use PAID API with Turbo model
    url = (
        f"https://gen.pollinations.ai/image/{safe_prompt}"
        f"?width={IMAGE_WIDTH}&height={IMAGE_HEIGHT}"
        f"&model={IMAGE_MODEL}"
        f"&seed={seed}"
        f"&nologo=true"
        f"&nofeed=true"
        f"&enhance=true"
        f"&negative_prompt={safe_negative}"
    )
    
    headers = {
        "Authorization": f"Bearer {POLLINATIONS_API_KEY}"
    }

    out = IMAGES_DIR / f"scene_{idx:02d}.jpg"
    out_upscaled = IMAGES_DIR / f"scene_{idx:02d}_hd.jpg"
    print(f"[image] 🎬 Generating VIRAL {topic_era.lower()} image {idx+1}/{NUM_IMAGES}...")
    print(f"[image] 📸 Scene: {scene[:70]}...")
    
    # Robust retry logic
    max_retries = 5
    retry_delays = [5, 10, 15, 30, 60]
    
    for attempt in range(max_retries):
        try:
            r = requests.get(url, headers=headers, timeout=90)
            r.raise_for_status()
            
            # Validate image
            if len(r.content) < 1000:
                raise ValueError("Image too small")
            
            # Save directly as the final image (no upscaling needed)
            out_upscaled.write_bytes(r.content)
            print(f"[image] ✅ Image {idx+1} ready! ({len(r.content)//1024}KB)")
            
            time.sleep(2)
            return out_upscaled
            
        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if e.response else "Unknown"
            if attempt < max_retries - 1:
                wait_time = retry_delays[attempt]
                print(f"[image] ⚠️ HTTP {status_code}! Retry {attempt+2}/{max_retries} in {wait_time}s...")
                time.sleep(wait_time)
            else:
                print(f"[image] ❌ Failed: HTTP {status_code}")
                raise
                
        except Exception as e:
            if attempt < max_retries - 1:
                wait_time = retry_delays[attempt]
                print(f"[image] ⚠️ Error: {str(e)[:50]}. Retry {attempt+2}/{max_retries} in {wait_time}s...")
                time.sleep(wait_time)
            else:
                print(f"[image] ❌ Failed after {max_retries} attempts: {e}")
                raise
    
    raise Exception(f"Image {idx+1} generation failed")

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
    
    # Extract era from topic for image styling
    if topic.startswith("[ANCIENT]"):
        topic_era = "ANCIENT"
    elif topic.startswith("[MEDIEVAL]"):
        topic_era = "MEDIEVAL"
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
