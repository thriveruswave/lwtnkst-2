import os, sys, glob
from upload.upload_instagram import upload_to_instagram
from upload.upload_facebook import upload_to_facebook

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

    caption = "Daily automated video release #viral #reels"
    
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
