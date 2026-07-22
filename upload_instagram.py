"""
Instagram Reels Upload - Using free file hosting + Instagram Graph API
"""

import os
import sys
import requests
import time
from pathlib import Path

if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

HOSTING_TIMEOUT = (15, 180)


def upload_video_to_hosting(file_path):
    """Upload video to a public file hosting service. Tries multiple fallbacks."""
    last_error = None
    file_size_mb = Path(file_path).stat().st_size / (1024 * 1024)
    print(f"[instagram] Video size: {file_size_mb:.2f} MB")

    # Method 1: catbox.moe (most reliable, direct download)
    try:
        print("[instagram] Trying catbox.moe...")
        with open(file_path, 'rb') as f:
            r = requests.post(
                'https://catbox.moe/user/api.php',
                data={'reqtype': 'fileupload'},
                files={'fileToUpload': f},
                timeout=180
            )
        if r.status_code == 200:
            url = r.text.strip()
            if url.startswith('https://'):
                print(f"[instagram] catbox.moe success: {url}")
                return url
        print(f"[instagram] catbox.moe HTTP {r.status_code}: {r.text[:100]}")
    except Exception as e:
        print(f"[instagram] catbox.moe failed: {e}")
        last_error = e

    # Method 2: uguu.se (reliable direct download)
    try:
        print("[instagram] Trying uguu.se...")
        with open(file_path, 'rb') as f:
            r = requests.post(
                'https://uguu.se/upload',
                files={'files[]': f},
                timeout=180
            )
        if r.status_code == 200:
            data = r.json()
            if data.get('files') and len(data['files']) > 0:
                url = data['files'][0].get('url', '')
                if url:
                    print(f"[instagram] uguu.se success: {url}")
                    return url
        print(f"[instagram] uguu.se HTTP {r.status_code}: {r.text[:100]}")
    except Exception as e:
        print(f"[instagram] uguu.se failed: {e}")
        last_error = e

    # Method 3: 0x0.st (simple, direct download)
    try:
        print("[instagram] Trying 0x0.st via curl...")
        import subprocess
        result = subprocess.run(
            ['curl', '-s', '-F', f'file=@{file_path}', 'https://0x0.st'],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode == 0:
            url = result.stdout.strip()
            if url.startswith('https://'):
                print(f"[instagram] 0x0.st success: {url}")
                return url
        print(f"[instagram] 0x0.st failed: {result.stderr[:200]}")
    except Exception as e:
        print(f"[instagram] 0x0.st failed: {e}")
        last_error = e

    # Method 4: file.io (last resort)
    try:
        print("[instagram] Trying file.io...")
        with open(file_path, 'rb') as f:
            r = requests.post('https://file.io', files={'file': f}, timeout=120)
        if r.status_code == 200:
            data = r.json()
            if data.get('success'):
                url = data['link']
                print(f"[instagram] file.io success: {url}")
                return url
            print(f"[instagram] file.io returned: {data}")
        else:
            print(f"[instagram] file.io HTTP {r.status_code}")
    except Exception as e:
        print(f"[instagram] file.io failed: {e}")
        last_error = e

    raise Exception(f"All hosting services failed. Last error: {last_error}")


def upload_to_instagram(video_path, caption):
    print("\n" + "=" * 60)
    print("INSTAGRAM UPLOAD STARTING")
    print("=" * 60)

    access_token = os.getenv('IG_ACCESS_TOKEN') or os.getenv('INSTAGRAM_ACCESS_TOKEN')
    user_id = os.getenv('IG_USER_ID') or os.getenv('INSTAGRAM_ACCOUNT_ID')

    if not access_token:
        print("[instagram] Skipping - access token not set")
        return {'status': 'skipped', 'reason': 'Missing token', 'platform': 'instagram'}

    if not user_id:
        print("[instagram] Skipping - user ID not set")
        return {'status': 'skipped', 'reason': 'Missing user ID', 'platform': 'instagram'}

    print(f"[instagram] User ID: {user_id}")
    print(f"[instagram] Token: {access_token[:20]}...")

    video_path_obj = Path(video_path)
    if not video_path_obj.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")

    caption_limited = caption[:2200] if len(caption) > 2200 else caption
    print(f"[instagram] Caption length: {len(caption_limited)} characters")

    try:
        print("[instagram] Step 1: Uploading video to public hosting...")
        video_url = upload_video_to_hosting(video_path)
        print(f"[instagram] Public video URL: {video_url}")

        print("[instagram] Step 2: Creating REELS container via Instagram Graph API...")
        api_version = "v22.0"
        container_url = f"https://graph.facebook.com/{api_version}/{user_id}/media"
        container_params = {
            'media_type': 'REELS',
            'video_url': video_url,
            'caption': caption_limited,
            'share_to_feed': 'false',
            'thumb_offset': '5000',
            'access_token': access_token
        }

        container_response = requests.post(container_url, params=container_params, timeout=60)
        print(f"[instagram] Container response: {container_response.status_code}")

        if container_response.status_code != 200:
            error_msg = container_response.json().get('error', {}).get('message', 'Unknown error')
            print(f"[instagram] Container creation failed: {error_msg}")

            print("[instagram] Retrying with graph.instagram.com endpoint...")
            container_url = f"https://graph.instagram.com/{api_version}/{user_id}/media"
            container_response = requests.post(container_url, params=container_params, timeout=60)

            if container_response.status_code != 200:
                raise Exception(f"Container Error: {error_msg}")

        container_id = container_response.json().get('id')
        print(f"[instagram] Container created: {container_id}")

        print("[instagram] Step 3: Polling container status...")
        for attempt in range(6):
            time.sleep(30)
            status_url = f"https://graph.facebook.com/{api_version}/{container_id}"
            status_params = {
                "fields": "status_code,status",
                "access_token": access_token
            }
            status_resp = requests.get(status_url, params=status_params, timeout=30)
            if status_resp.status_code == 200:
                status_data = status_resp.json()
                code = status_data.get("status_code", status_data.get("status", "UNKNOWN"))
                print(f"[instagram] Container status (attempt {attempt+1}): {code}")
                if code in ("FINISHED", "PUBLISHED", "ready"):
                    break
                elif code in ("ERROR", "FAILED"):
                    error_msg = status_data.get("error_message", "Processing error")
                    raise Exception(f"Container processing failed: {error_msg}")
            else:
                print(f"[instagram] Status check HTTP {status_resp.status_code}: {status_resp.text[:200]}")
        else:
            print("[instagram] Container still processing, proceeding with publish anyway...")

        print("[instagram] Step 4: Publishing container...")
        publish_endpoints = [
            f"https://graph.facebook.com/{api_version}/{user_id}/media_publish",
            f"https://graph.instagram.com/{api_version}/{user_id}/media_publish"
        ]
        publish_params = {
            "creation_id": container_id,
            "access_token": access_token
        }
        publish_response = None
        for endpoint in publish_endpoints:
            print(f"[instagram] Trying publish endpoint: {endpoint}")
            publish_response = requests.post(endpoint, params=publish_params, timeout=60)
            if publish_response.status_code == 200:
                break
            print(f"[instagram] Publish failed on {endpoint}: {publish_response.status_code}")
            print(f"[instagram] Response: {publish_response.text[:300]}")

        if not publish_response or publish_response.status_code != 200:
            error_msg = "Publish failed on all endpoints"
            if publish_response:
                try:
                    error_data = publish_response.json()
                    error_msg = error_data.get("error", {}).get("message", publish_response.text[:200])
                except Exception:
                    error_msg = publish_response.text[:200] or "Unknown error"
            print(f"[instagram] Publish failed: {error_msg}")
            raise Exception(f"Instagram Publish Error: {error_msg}")

        media_id = publish_response.json().get("id")

        print("[instagram] SUCCESS! Video published to Instagram!")
        print(f"[instagram] Media ID: {media_id}")
        print("=" * 60)

        return {
            'id': media_id,
            'platform': 'instagram',
            'status': 'success'
        }

    except Exception as e:
        print(f"[instagram] ERROR: {e}")
        print("=" * 60)
        return {
            'platform': 'instagram',
            'status': 'failed',
            'error': str(e)
        }


if __name__ == '__main__':
    video_file = Path('output/final_video.mp4')
    if video_file.exists():
        try:
            result = upload_to_instagram(str(video_file), "Test upload")
            print(f"\nResult: {result}")
        except Exception as e:
            print(f"\nFailed: {e}")
    else:
        print(f"Video not found: {video_file}")
