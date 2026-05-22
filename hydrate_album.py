import sys
import os
import json
import re
import urllib.request
import urllib.parse
import time
import difflib

def normalize_name(name):
    """Normalize string for filename matching: lowercase, replace non-alphanumeric with hyphens."""
    name = name.lower()
    name = re.sub(r'[^a-z0-9]+', '-', name)
    return name.strip('-')

def main():
    if len(sys.argv) < 3:
        print("Usage: python hydrate_album.py <album_json_path> <songs_dir>")
        sys.exit(1)
        
    album_path = sys.argv[1]
    songs_dir = sys.argv[2]
    
    with open(album_path, 'r', encoding='utf-8') as f:
        album_data = json.load(f)
        
    if 'tracks' in album_data:
        print(f"[{os.path.basename(album_path)}] Album already hydrated. Skipping.")
        return
        
    album_title = album_data.get('title', '')
    artist_name = album_data.get('artist', '')
    
    if not album_title or not artist_name:
        print(f"[{os.path.basename(album_path)}] Missing title or artist. Skipping.")
        return
        
    print(f"[{os.path.basename(album_path)}] Fetching MusicBrainz data for '{album_title}' by '{artist_name}'...")
    
    # 1. Search MusicBrainz for the release
    query = f'release:"{album_title}" AND artist:"{artist_name}"'
    url = f"https://musicbrainz.org/ws/2/release/?query={urllib.parse.quote(query)}&fmt=json"
    
    import requests
    
    def fetch_with_retry(url, retries=3):
        headers = {
            # MusicBrainz requires this exact format: AppName/Version ( contact-email )
            'User-Agent': 'TylerBillboardHydrator/1.0 ( tyler@example.com )', 
            'Accept': 'application/json'
        }
        for attempt in range(retries):
            try:
                # Removed verify=False so it uses secure, standard verification
                response = requests.get(url, headers=headers, timeout=10)
                response.raise_for_status()
                return response.json()
            except Exception as e:
                if attempt == retries - 1:
                    raise e
                time.sleep(2)
        return None
    
    try:
        data = fetch_with_retry(url)
    except Exception as e:
        print(f"[{os.path.basename(album_path)}] Error fetching from MusicBrainz: {e}")
        return
        
    if not data or not data.get('releases'):
        print(f"[{os.path.basename(album_path)}] No release found on MusicBrainz. Marking as empty.")
        # Mark as hydrated with empty tracks so we don't retry forever
        album_data['tracks'] = []
        with open(album_path, 'w', encoding='utf-8') as f:
            json.dump(album_data, f, ensure_ascii=False)
        return
        
    release_id = data['releases'][0]['id']
    
    # 2. Fetch tracks for the found release
    time.sleep(2) # Mandatory sleep to respect MusicBrainz rate limits
    tracks_url = f"https://musicbrainz.org/ws/2/release/{release_id}?inc=recordings&fmt=json"
    
    try:
        release_data = fetch_with_retry(tracks_url)
    except Exception as e:
        print(f"[{os.path.basename(album_path)}] Error fetching tracks: {e}")
        return
        
    mb_tracks = []
    for media in release_data.get('media', []):
        for track in media.get('tracks', []):
            if 'recording' in track and 'title' in track['recording']:
                mb_tracks.append(track['recording']['title'])
                
    if not mb_tracks:
        print(f"[{os.path.basename(album_path)}] Release has no tracks. Marking as empty.")
        album_data['tracks'] = []
        with open(album_path, 'w', encoding='utf-8') as f:
            json.dump(album_data, f, ensure_ascii=False)
        return
        
    # 3. Match against local songs directory
    all_songs = os.listdir(songs_dir)
    norm_artist = normalize_name(artist_name)
    
    # Filter songs that belong to this artist (filename ends with -artistname.json)
    artist_suffix = f"-{norm_artist}.json"
    artist_songs = [s for s in all_songs if s.endswith(artist_suffix)]
    
    final_tracks = []
    
    for track_title in mb_tracks:
        norm_title = normalize_name(track_title)
        expected_file = f"{norm_title}-{norm_artist}.json"
        
        matched_id = None
        
        # Exact match
        if expected_file in artist_songs:
            matched_id = expected_file.replace('.json', '')
        else:
            # Fuzzy match
            # Strip suffix from available artist songs to compare just the title part
            title_map = {s.replace(artist_suffix, ''): s for s in artist_songs}
            
            matches = difflib.get_close_matches(norm_title, title_map.keys(), n=1, cutoff=0.6)
            if matches:
                matched_file = title_map[matches[0]]
                matched_id = matched_file.replace('.json', '')
                
        final_tracks.append({"title": track_title, "id": matched_id})
            
    # Deduplicate while preserving order (some albums list same track twice)
    seen_titles = set()
    deduped_tracks = []
    for t in final_tracks:
        if t['title'] not in seen_titles:
            seen_titles.add(t['title'])
            deduped_tracks.append(t)
            
    # Sort: charting songs (with id) at the top, maintaining original relative order
    charting_tracks = [t for t in deduped_tracks if t['id'] is not None]
    uncharting_tracks = [t for t in deduped_tracks if t['id'] is None]
    
    ordered_tracks = charting_tracks + uncharting_tracks
    
    album_data['tracks'] = ordered_tracks
    
    with open(album_path, 'w', encoding='utf-8') as f:
        json.dump(album_data, f, ensure_ascii=False, indent=2)
        
    print(f"[{os.path.basename(album_path)}] Hydrated {len(charting_tracks)} matching Billboard tracks out of {len(mb_tracks)} total album tracks.")

if __name__ == "__main__":
    main()
