"""
Instagram Reels Upload - Using GitHub raw URL + Instagram Graph API
Uploads video to a temporary git branch, gets raw GitHub URL, then creates/publishes Instagram Reel.
"""

import os
import sys
import requests
import time
import uuid
import subprocess
from pathlib import Path

if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')


def upload_video_to_github(file_path):
    """
    Upload video to a temporary git branch and return the raw GitHub URL.
    Uses GITHUB_TOKEN from environment (set in workflow).
    """
    github_token = os.getenv('GITHUB_TOKEN')
    if not github_token:
        raise Exception("GITHUB_TOKEN not set in environment")

    owner_repo = os.getenv('GITHUB_REPOSITORY', 'thriveruswave/lwtnkst-2')
    run_id = os.getenv('GITHUB_RUN_ID', str(int(time.time())))
    branch_name = f"ig-video-{run_id}-{uuid.uuid4().hex[:4]}"
    video_filename = f"ig_{uuid.uuid4().hex[:8]}.mp4"

    print(f"[instagram] Using GitHub RAW URL method")
    print(f"[instagram] Repo: {owner_repo}, Branch: {branch_name}")

    # Copy video to repo root
    subprocess.run(['cp', str(file_path), video_filename], check=True, capture_output=True)
    print(f"[instagram] Copied video to {video_filename}")

    # Set up git remote with token auth
    remote_url = f"https://x-access-token:{github_token}@github.com/{owner_repo}.git"
    subprocess.run(['git', 'remote', 'set-url', 'origin', remote_url], check=True, capture_output=True)

    # Create temp branch, add video, commit, push
    subprocess.run(['git', 'checkout', '-b', branch_name], check=True, capture_output=True)
    subprocess.run(['git', 'add', '-f', video_filename], check=True, capture_output=True)
    subprocess.run(['git', 'commit', '-m', f'temp ig video {run_id}'], check=True, capture_output=True)
    push_result = subprocess.run(
        ['git', 'push', 'origin', branch_name],
        capture_output=True, text=True, timeout=60
    )
    if push_result.returncode != 0:
        raise Exception(f"Git push failed: {push_result.stderr[:200]}")

    # Build raw download URL
    raw_url = f"https://raw.githubusercontent.com/{owner_repo}/{branch_name}/{video_filename}"
    print(f"[instagram] GitHub raw URL: {raw_url}")

    return raw_url, branch_name, video_filename


def cleanup_github_temp(branch_name, video_filename):
    """Delete the temp branch and local video file."""
    try:
        # Checkout main first
        subprocess.run(['git', 'checkout', 'main'], capture_output=True, timeout=30)
        # Delete remote branch
        subprocess.run(['git', 'push', 'origin', '--delete', branch_name], capture_output=True, timeout=30)
        print(f"[instagram] Cleaned up branch: {branch_name}")
    except Exception as e:
        print(f"[instagram] Cleanup warning (branch): {e}")

    try:
        if os.path.exists(video_filename):
            os.remove(video_filename)
            print(f"[instagram] Cleaned up file: {video_filename}")
    except Exception as e:
        print(f"[instagram] Cleanup warning (file): {e}")


def upload_video_to_hosting(file_path):
    """Fallback: upload to third-party hosting. Tries multiple services."""
    last_error = None

    # uguu.se (worked previously)
    try:
        print("[instagram] Fallback: Trying uguu.se...")
        with open(file_path, 'rb') as f:
            r = requests.post('https://uguu.se/upload', files={'files[]': f}, timeout=180)
        if r.status_code == 200:
            data = r.json()
            if data.get('files') and len(data['files']) > 0:
                url = data['files'][0].get('url', '')
                if url:
                    print(f"[instagram] uguu.se success: {url}")
                    return url
    except Exception as e:
        print(f"[instagram] uguu.se failed: {e}")
        last_error = e

    # 0x0.st
    try:
        print("[instagram] Fallback: Trying 0x0.st...")
        result = subprocess.run(
            ['curl', '-s', '-F', f'file=@{file_path}', 'https://0x0.st'],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode == 0:
            url = result.stdout.strip()
            if url.startswith('https://'):
                print(f"[instagram] 0x0.st success: {url}")
                return url
    except Exception as e:
        print(f"[instagram] 0x0.st failed: {e}")
        last_error = e

    raise Exception(f"All fallback hosting services failed. Last error: {last_error}")


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

    branch_name = None
    video_filename = None

    try:
        print("[instagram] Step 1: Uploading video to GitHub for raw URL...")
        video_url, branch_name, video_filename = upload_video_to_github(video_path)
        print(f"[instagram] Public video URL: {video_url}")

        print("[instagram] Step 2: Creating REELS container via Instagram Graph API...")
        api_version = "v22.0"
        container_url = f"https://graph.facebook.com/{api_version}/{user_id}/media"
        container_params = {
            'media_type': 'REELS',
            'video_url': video_url,
            'caption': caption_limited,
            'share_to_feed': False,
            'thumb_offset': '5000',
            'access_token': access_token
        }

        container_response = requests.post(container_url, params=container_params, timeout=60)
        print(f"[instagram] Container response: {container_response.status_code}")

        if container_response.status_code != 200:
            error_msg = container_response.json().get('error', {}).get('message', 'Unknown error')
            print(f"[instagram] Container creation with Facebook endpoint failed: {error_msg}")

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

        print("[instagram] SUCCESS! Video published to Instagram Reels tab!")
        print(f"[instagram] Media ID: {media_id}")
        print("=" * 60)

        return {
            'id': media_id,
            'platform': 'instagram',
            'status': 'success'
        }

    except Exception as e:
        print(f"[instagram] ERROR: {e}")

        # If GitHub method failed, try third-party fallback
        if "GITHUB_TOKEN" in str(e) or "GitHub" in str(e) or "git" in str(e):
            print("[instagram] GitHub method failed, trying third-party fallback...")
            try:
                video_url = upload_video_to_hosting(video_path)
                print(f"[instagram] Fallback URL: {video_url}")
                # Retry with fallback URL
                container_params['video_url'] = video_url
                container_response = requests.post(container_url, params=container_params, timeout=60)
                if container_response.status_code == 200:
                    container_id = container_response.json().get('id')
                    time.sleep(60)
                    publish_response = requests.post(
                        f"https://graph.facebook.com/v22.0/{user_id}/media_publish",
                        params={"creation_id": container_id, "access_token": access_token},
                        timeout=60
                    )
                    if publish_response.status_code == 200:
                        media_id = publish_response.json().get("id")
                        print(f"[instagram] Fallback SUCCESS! Media ID: {media_id}")
                        return {'id': media_id, 'platform': 'instagram', 'status': 'success'}
            except Exception as fallback_e:
                print(f"[instagram] Fallback also failed: {fallback_e}")

        print("=" * 60)
        return {
            'platform': 'instagram',
            'status': 'failed',
            'error': str(e)
        }

    finally:
        if branch_name and video_filename:
            cleanup_github_temp(branch_name, video_filename)


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
