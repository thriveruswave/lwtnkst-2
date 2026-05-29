"""
YouTube Upload Script - Updated for 2025

Uses refresh token from GitHub Secrets to upload videos.
"""

import os
from pathlib import Path
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import datetime

def get_authenticated_service():
    """Authenticate using refresh token from environment."""
    
    # Get credentials from GitHub Secrets
    client_id = os.getenv('YT_CLIENT_ID')
    client_secret = os.getenv('YT_CLIENT_SECRET')
    refresh_token = os.getenv('YT_REFRESH_TOKEN')
    
    if not all([client_id, client_secret, refresh_token]):
        raise ValueError(
            "Missing credentials! Set these GitHub Secrets:\n"
            "  - YT_CLIENT_ID\n"
            "  - YT_CLIENT_SECRET\n"
            "  - YT_REFRESH_TOKEN"
        )
    
    # Create credentials from refresh token
    creds = Credentials(
        None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=["https://www.googleapis.com/auth/youtube"]
    )
    
    # Refresh to get access token
    creds.refresh(Request())
    
    return build('youtube', 'v3', credentials=creds)

def upload_to_youtube(video_file, title, description, tags, category_id='27'):
    """Upload video to YouTube and return result."""
    youtube = get_authenticated_service()
    
    body = {
        'snippet': {
            'title': title,
            'description': description,
            'tags': tags,
            'categoryId': category_id
        },
        'status': {
            'privacyStatus': 'public',
            'selfDeclaredMadeForKids': False,
        }
    }
    
    if '#Shorts' not in body['snippet']['description']:
        body['snippet']['description'] += '\n\n#Shorts'
    
    media = MediaFileUpload(
        str(video_file),
        chunksize=-1,
        resumable=True,
        mimetype='video/mp4'
    )
    
    print(f"[youtube] Uploading: {title}")
    request = youtube.videos().insert(
        part=','.join(body.keys()),
        body=body,
        media_body=media
    )
    
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"[youtube] Progress: {int(status.progress() * 100)}%")
    
    print(f"[youtube] ✅ Uploaded! Video ID: {response['id']}")
    print(f"[youtube] URL: https://youtube.com/shorts/{response['id']}")
    
    return response

def main():
    """Upload the generated video to YouTube."""
    video_file = Path('output/final_video.mp4')
    
    if not video_file.exists():
        print("[youtube] ❌ No video found at output/final_video.mp4")
        return
    
    # Read the story and topic for title
    story_file = Path('output/story.txt')
    topic_file = Path('output/topic.txt')
    
    # Try to get topic first (most reliable)
    if topic_file.exists():
        topic = topic_file.read_text(encoding='utf-8').strip()
        # Remove era tags for cleaner title
        topic = topic.replace('[ANCIENT] ', '').replace('[MEDIEVAL] ', '').replace('[MODERN] ', '')
        title = topic
    elif story_file.exists():
        story = story_file.read_text(encoding='utf-8').strip()
        # Extract first sentence for title
        first_sentence = story.split('.')[0] if '.' in story else story.split('!')[0]
        title = first_sentence.strip()
    else:
        title = "Fascinating Law from History"
    
    # Ensure title is not too long (YouTube limit is 100, but 70 is better for mobile)
    if len(title) > 70:
        title = title[:67] + "..."
    
    # Read story text for description
    story_text = ""
    if story_file.exists():
        story_text = story_file.read_text(encoding='utf-8').strip()
    
    # Create engaging description with full story
    if story_text:
        description = f"""{title}

{story_text}

#Shorts #Law #LegalHistory #History #Education #AncientLaw #MedievalLaw #Justice"""
    else:
        description = (
            "Discover fascinating legal history and laws from around the world! "
            "Learn about ancient codes, medieval justice, and modern legal systems.\n\n"
            "#Shorts #Law #LegalHistory #History #Education #AncientLaw #MedievalLaw #Justice"
        )
    
    tags = [
        'Law', 'Legal History', 'History', 'Education', 'Legal System',
        'Shorts', 'Justice', 'Court', 'Ancient Law', 'Medieval Law',
        'World History', 'Legal Education', 'Historical Facts'
    ]
    
    # Upload
    try:
        upload_to_youtube(
            video_file=video_file,
            title=title,
            description=description,
            tags=tags,
            category_id='27'  # Education category
        )
    except Exception as e:
        print(f"[youtube] ❌ Upload failed: {e}")
        raise

if __name__ == '__main__':
    main()
