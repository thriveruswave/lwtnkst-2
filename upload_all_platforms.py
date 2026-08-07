import os, sys, glob
from pathlib import Path
from upload_instagram import upload_to_instagram
from upload_facebook import upload_to_facebook

def get_topic():
    """Read the current topic from output/topic.txt or used_topics.txt."""
    tp = Path("output/topic.txt")
    if tp.exists():
        topic = tp.read_text(encoding="utf-8").strip()
        if topic:
            return topic.replace("[ANCIENT] ", "").replace("[MEDIEVAL] ", "").replace("[MODERN] ", "")
    if os.path.exists("used_topics.txt"):
        with open("used_topics.txt", "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
            if lines:
                last = lines[-1]
                last = last.replace("[ANCIENT] ", "").replace("[MEDIEVAL] ", "").replace("[MODERN] ", "")
                return last
    return "Ancient History"

def get_story():
    """Read the generated content from output/story.txt."""
    st = Path("output/story.txt")
    if st.exists():
        return st.read_text(encoding="utf-8").strip()
    return ""

def build_caption(topic, story):
    """Build a clean caption from the actual topic and content."""
    parts = [topic]
    if story:
        parts.append("")
        parts.append(story)
    parts.append("")
    parts.append("#History #AncientHistory #HistoryFacts")
    return "\n".join(parts)

def main():
    print("Starting Multi-Platform Video Publisher...")
    processed_dir = "Processed_Videos"
    videos = []
    if os.path.exists(processed_dir):
        videos = [os.path.join(processed_dir, f) for f in os.listdir(processed_dir) if f.endswith(".mp4")]
    if not videos:
        videos = glob.glob("output/**/*.mp4", recursive=True)
    
    if not videos:
        print("No videos found to upload.")
        return

    latest_video = max(videos, key=os.path.getmtime)
    print(f"Selected Video: {latest_video}")

    topic = get_topic()
    story = get_story()
    caption = build_caption(topic, story)
    print(f"Caption: {caption[:100]}...")
    
    print("\n1. Uploading to Instagram...")
    try:
        upload_to_instagram(latest_video, caption=caption)
    except Exception as e:
        print(f"Instagram upload error: {e}")
    
    print("\n2. Uploading to Facebook...")
    try:
        upload_to_facebook(latest_video, caption)
    except Exception as e:
        print(f"Facebook upload error: {e}")

if __name__ == "__main__":
    main()
