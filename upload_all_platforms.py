"""
Multi-Platform Upload Script

Uploads videos to:
- YouTube Shorts
- Instagram Reels
- TikTok
- Facebook Reels
- Threads
- Twitter/X
- VK

Each platform requires its own API credentials.
"""

import os
import sys
from pathlib import Path
import re


def generate_metadata_from_topic(topic: str, story: str):
    """
    Generate dynamic title, description, and tags based on the topic.
    
    Args:
        topic: The topic string (e.g., "[ANCIENT] Code of Hammurabi Eye for an Eye")
        story: The generated story content
        
    Returns:
        dict with 'title', 'description', 'tags'
    """
    # Extract era and clean topic
    is_ancient = topic.startswith("[ANCIENT]")
    is_medieval = topic.startswith("[MEDIEVAL]")
    
    clean_topic = topic.replace("[ANCIENT] ", "").replace("[MEDIEVAL] ", "").replace("[MODERN] ", "")
    
    # Determine era label
    if is_ancient:
        era = "Ancient"
        era_hashtag = "#AncientLaw"
    else:
        era = "Medieval"
        era_hashtag = "#MedievalLaw"
    
    # Generate title (use first sentence of story or topic)
    title_parts = story.split('.')
    if title_parts and len(title_parts[0]) > 10:
        title = title_parts[0][:100]
    else:
        title = f"{era} Law: {clean_topic[:80]}"
    
    # Generate description
    description = f"""Fascinating {era.lower()} law explained!

Topic: {clean_topic}

{story[:200]}...

#Shorts #LegalHistory {era_hashtag} #Law #History #Education #Facts"""
    
    # Generate tags
    tags = [
        'Law', 'Legal History', f'{era} Law', 'History',
        'Education', 'Facts', 'Shorts', 'Reels'
    ]
    
    # Add topic-specific keywords
    topic_words = clean_topic.split()
    for word in topic_words:
        if len(word) > 4 and word not in tags:
            tags.append(word)
    
    return {
        'title': title,
        'description': description,
        'tags': tags[:15]  # Limit to 15 tags
    }


def main():
    """Upload video to all configured platforms."""
    video_file = Path('output/final_video.mp4')
    
    if not video_file.exists():
        print("[upload] ❌ No video found at output/final_video.mp4")
        return
    
    # Read topic from output/topic.txt (preferred) or used_topics.txt (fallback)
    topic_file = Path('output/topic.txt')
    used_topics_file = Path('used_topics.txt')
    topic = "Law History"
    
    if topic_file.exists():
        topic = topic_file.read_text(encoding='utf-8').strip()
        print(f"[upload] 📋 Topic from topic.txt: {topic}")
    elif used_topics_file.exists():
        with open(used_topics_file, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f if line.strip()]
            if lines:
                topic = lines[-1]  # Get the most recent topic
        print(f"[upload] 📋 Topic from used_topics.txt: {topic}")
    
    # Read story for metadata
    story_file = Path('output/story.txt')
    story = ""
    if story_file.exists():
        story = story_file.read_text(encoding='utf-8')
    
    # Generate dynamic metadata based on topic
    metadata = generate_metadata_from_topic(topic, story)
    title = metadata['title']
    description = metadata['description']
    tags = metadata['tags']
    
    print("\n" + "="*60)
    print("📋 UPLOAD METADATA")
    print("="*60)
    print(f"Topic: {topic}")
    print(f"Title: {title}")
    print(f"Description: {description[:100]}...")
    print(f"Tags: {', '.join(tags[:5])}...")
    print("="*60)
    
    results = {}
    
    # Define importer helper to lazily import platform modules
    def import_uploader(module_name, func_name):
        try:
            mod = __import__(module_name, fromlist=[func_name])
            return getattr(mod, func_name)
        except Exception as e:
            print(f"[{module_name}] Failed to import {func_name}: {e}")
            return None

    # Upload to YouTube
    if all([
        os.getenv('YT_CLIENT_ID'),
        os.getenv('YT_CLIENT_SECRET'),
        os.getenv('YT_REFRESH_TOKEN')
    ]):
        print("\n" + "="*60)
        print("📺 Uploading to YouTube...")
        print("="*60)
        try:
            upload_to_youtube = import_uploader('upload_to_youtube', 'upload_to_youtube')
            if upload_to_youtube:
                result = upload_to_youtube(video_file, title, description, tags)
                results['youtube'] = result
                print(f"✅ YouTube: https://youtube.com/shorts/{result['id']}")
            else:
                raise Exception("Import failed")
        except Exception as e:
            print(f"❌ YouTube failed: {e}")
            results['youtube'] = None
    else:
        print("⏭️  Skipping YouTube (credentials not set)")
    
    # Upload to Instagram
    if all([
        os.getenv('INSTAGRAM_ACCESS_TOKEN'),
        os.getenv('INSTAGRAM_ACCOUNT_ID')
    ]):
        print("\n" + "="*60)
        print("📸 Uploading to Instagram...")
        print("="*60)
        try:
            upload_to_instagram = import_uploader('upload_instagram', 'upload_to_instagram')
            if upload_to_instagram:
                result = upload_to_instagram(video_file, description)
                results['instagram'] = result
                if result.get('status') == 'success':
                    print(f"✅ Instagram: Uploaded successfully")
                else:
                    print(f"❌ Instagram: {result.get('error', 'Unknown error')}")
            else:
                raise Exception("Import failed")
        except Exception as e:
            print(f"❌ Instagram failed: {e}")
            results['instagram'] = None
    else:
        print("⏭️  Skipping Instagram (credentials not set)")
    
    # Upload to TikTok
    if os.getenv('TIKTOK_ACCESS_TOKEN'):
        print("\n" + "="*60)
        print("🎵 Uploading to TikTok...")
        print("="*60)
        try:
            upload_to_tiktok = import_uploader('upload_tiktok', 'upload_to_tiktok')
            if upload_to_tiktok:
                result = upload_to_tiktok(video_file, title, description)
                results['tiktok'] = result
                print(f"✅ TikTok: Uploaded successfully")
            else:
                raise Exception("Import failed")
        except Exception as e:
            print(f"❌ TikTok failed: {e}")
            results['tiktok'] = None
    else:
        print("⏭️  Skipping TikTok (credentials not set)")
    
    # Upload to Facebook
    if all([
        os.getenv('FB_ACCESS_TOKEN'),
        os.getenv('FB_PAGE_ID')
    ]):
        print("\n" + "="*60)
        print("📘 Uploading to Facebook...")
        print("="*60)
        try:
            upload_to_facebook = import_uploader('upload_facebook', 'upload_to_facebook')
            if upload_to_facebook:
                result = upload_to_facebook(video_file, description)
                results['facebook'] = result
                print(f"✅ Facebook: Uploaded successfully")
            else:
                raise Exception("Import failed")
        except Exception as e:
            print(f"❌ Facebook failed: {e}")
            results['facebook'] = None
    else:
        print("⏭️  Skipping Facebook (credentials not set)")
    
    # Upload to Threads
    if all([
        os.getenv('THREADS_ACCESS_TOKEN'),
        os.getenv('THREADS_USER_ID')
    ]):
        print("\n" + "="*60)
        print("🧵 Uploading to Threads...")
        print("="*60)
        try:
            upload_to_threads = import_uploader('upload_threads', 'upload_to_threads')
            if upload_to_threads:
                result = upload_to_threads(video_file, description)
                results['threads'] = result
                print(f"✅ Threads: Uploaded successfully")
            else:
                raise Exception("Import failed")
        except Exception as e:
            print(f"❌ Threads failed: {e}")
            results['threads'] = None
    else:
        print("⏭️  Skipping Threads (credentials not set)")
    
    # Upload to Twitter/X
    print("\n" + "="*60)
    print("🐦 Checking Twitter/X credentials...")
    print("="*60)
    
    twitter_api_key = os.getenv('TWITTER_API_KEY')
    twitter_api_secret = os.getenv('TWITTER_API_SECRET')
    twitter_access_token = os.getenv('TWITTER_ACCESS_TOKEN')
    twitter_access_secret = os.getenv('TWITTER_ACCESS_SECRET')
    
    # Debug: Show which credentials are set
    print(f"[twitter] API Key: {'✅ Set' if twitter_api_key else '❌ Not set'}")
    print(f"[twitter] API Secret: {'✅ Set' if twitter_api_secret else '❌ Not set'}")
    print(f"[twitter] Access Token: {'✅ Set' if twitter_access_token else '❌ Not set'}")
    print(f"[twitter] Access Secret: {'✅ Set' if twitter_access_secret else '❌ Not set'}")
    
    if all([twitter_api_key, twitter_api_secret, twitter_access_token, twitter_access_secret]):
        print(f"[twitter] ✅ All credentials present!")
        print(f"[twitter] 🚀 Starting upload...")
        try:
            upload_to_twitter = import_uploader('upload_twitter', 'upload_to_twitter')
            if upload_to_twitter:
                result = upload_to_twitter(video_file, description)
                results['twitter'] = result
                print(f"\n✅ Twitter: Upload successful!")
                print(f"   Tweet ID: {result.get('id', 'N/A')}")
                print(f"   URL: {result.get('url', 'N/A')}")
            else:
                raise Exception("Import failed")
        except Exception as e:
            print(f"\n❌ Twitter upload FAILED!")
            print(f"   Error type: {type(e).__name__}")
            print(f"   Error message: {str(e)}")
            print(f"   Full error: {repr(e)}")
            
            print(f"\n🔍 Troubleshooting:")
            print(f"   - Check if Twitter credentials are correct in GitHub Secrets")
            print(f"   - Verify Twitter app has 'Read and Write' permissions")
            print(f"   - Check if Access Token was regenerated after permission change")
            print(f"   - Verify video file exists and is valid")
            
            results['twitter'] = None
    else:
        print(f"[twitter] ⏭️  Skipping Twitter (credentials not set)")
        print(f"[twitter] Missing credentials - add to GitHub Secrets:")
        if not twitter_api_key:
            print(f"   - TWITTER_API_KEY")
        if not twitter_api_secret:
            print(f"   - TWITTER_API_SECRET")
        if not twitter_access_token:
            print(f"   - TWITTER_ACCESS_TOKEN")
        if not twitter_access_secret:
            print(f"   - TWITTER_ACCESS_SECRET")
        results['twitter'] = None
    
    # Upload to VK
    if all([
        os.getenv('VK_ACCESS_TOKEN'),
        os.getenv('VK_GROUP_ID')
    ]):
        print("\n" + "="*60)
        print("🇷🇺 Uploading to VK...")
        print("="*60)
        try:
            upload_to_vk = import_uploader('upload_vk', 'upload_to_vk')
            if upload_to_vk:
                result = upload_to_vk(video_file, description, title)
                results['vk'] = result
                print(f"✅ VK: {result.get('post_url', 'Uploaded successfully')}")
            else:
                raise Exception("Import failed")
        except Exception as e:
            print(f"❌ VK failed: {e}")
            results['vk'] = None
    else:
        print("⏭️  Skipping VK (credentials not set)")
    
    # Summary
    print("\n" + "="*60)
    print("📊 Upload Summary")
    print("="*60)
    for platform, result in results.items():
        status = "✅ Success" if result else "❌ Failed"
        print(f"{platform.capitalize()}: {status}")
    print("="*60)

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"\n[upload] ❌ Upload pipeline error: {e}")
        print("[upload] Continuing gracefully...")
