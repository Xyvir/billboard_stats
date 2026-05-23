import os
import glob
import json
import subprocess

def main():
    albums_dir = "billboard_stats/data/albums"
    songs_dir = "billboard_stats/data/songs"

    if not os.path.exists(albums_dir) or not os.path.exists(songs_dir):
        print("Data directories not found. Skipping hydration.")
        return

    album_files = glob.glob(os.path.join(albums_dir, "*.json"))
    print(f"Found {len(album_files)} total albums. Checking for unhydrated albums...")

    processed_count = 0
    for f in album_files:
        try:
            with open(f, 'r', encoding='utf-8') as fp:
                data = json.load(fp)
                if 'tracks' in data:
                    continue # Already hydrated
        except Exception as e:
            print(f"Error reading {f}: {e}")
            continue

        print(f"Hydrating {f}...")
        try:
            subprocess.run(["python", "hydrate_album.py", f, songs_dir], check=True)
            processed_count += 1
        except subprocess.CalledProcessError as e:
            print(f"Failed to hydrate {f}")
            
    print(f"Hydration complete. Processed {processed_count} new albums.")

if __name__ == "__main__":
    main()
