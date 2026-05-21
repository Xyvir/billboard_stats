"""Incremental chart update and flat-file data enrichment.

Usage:
    python -m billboard_stats.etl.updater          # run fetch + gap repair + enrichment
    python -m billboard_stats.etl.updater --repair  # gap repair only
    python -m billboard_stats.etl.updater --update  # fetch and enrich only
"""

import datetime
import logging
import os
import json
import re
import glob
from collections import defaultdict
from pathlib import Path

from billboard_stats.etl.fetcher import (
    DATA_DIR,
    download_hot100,
    download_b200,
    find_failed_downloads,
    get_latest_publishable_chart_week,
)

logger = logging.getLogger(__name__)

BATCH_LIMIT = 100


def slugify(text: str) -> str:
    """Generate safe filenames for the static SPA."""
    return re.sub(r'[^a-z0-9]+', '-', str(text).lower()).strip('-')


def _get_latest_chart_dates_fs(data_dir: str) -> dict:
    """Scan filesystem for the latest non-future Saturday per chart_type."""
    latest_dates = {"hot-100": None, "billboard-200": None}
    
    hot100_dir = os.path.join(data_dir, "hot100")
    if os.path.exists(hot100_dir):
        files = sorted([f for f in os.listdir(hot100_dir) if f.endswith(".json")])
        if files:
            latest_dates["hot-100"] = datetime.date.fromisoformat(files[-1].replace(".json", ""))

    b200_dir = os.path.join(data_dir, "b200")
    if os.path.exists(b200_dir):
        files = sorted([f for f in os.listdir(b200_dir) if f.endswith(".json")])
        if files:
            latest_dates["billboard-200"] = datetime.date.fromisoformat(files[-1].replace(".json", ""))

    return latest_dates


def build_search_index(data_dir: str):
    """Generates the global search index for the SPA."""
    logger.info("Building static search index...")
    index = {"artists": [], "songs": [], "albums": []}
    
    for category in ["artists", "songs", "albums"]:
        cat_dir = os.path.join(data_dir, category)
        if not os.path.exists(cat_dir):
            continue
            
        for fname in os.listdir(cat_dir):
            if not fname.endswith(".json"):
                continue
            with open(os.path.join(cat_dir, fname), 'r', encoding='utf-8') as f:
                data = json.load(f)
                name = data.get("name") or data.get("title")
                artist = data.get("artist", "")
                
                # Format exactly as the SPA expects
                entry = {"name": name, "ref": f"{category}/{fname}"}
                if artist:
                    entry["artist"] = artist
                
                index[category].append(entry)

    with open(os.path.join(data_dir, "search_index.json"), "w", encoding="utf-8") as out:
        json.dump(index, out)
    logger.info("Search index rebuilt.")


def run_incremental_enrichment(data_dir: str):
    """Processes weekly JSONs, adds metadata, and builds entity profiles."""
    logger.info("Jane's Flat-File Enrichment Initializing...")
    
    # Ensure profile directories exist
    for d in ["songs", "albums", "artists"]:
        os.makedirs(os.path.join(data_dir, d), exist_ok=True)

    all_files = []
    for ctype in ["hot100", "b200"]:
        dpath = os.path.join(data_dir, ctype)
        if os.path.exists(dpath):
            for f in os.listdir(dpath):
                if f.endswith(".json"):
                    all_files.append((ctype, f, os.path.join(dpath, f)))

    # Sort chronologically (oldest first). CRITICAL for calculating history.
    all_files.sort(key=lambda x: x[1])

    files_processed = 0
    for ctype, fname, filepath in all_files:
        if files_processed >= BATCH_LIMIT:
            logger.info(f"Batch limit of {BATCH_LIMIT} reached. Saving runner resources.")
            break

        with open(filepath, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                logger.error(f"Corrupted JSON: {filepath}")
                continue

        # Skip if already enriched
        if not data or "weeks_on_chart" in data[0]:
            continue 

        logger.info(f"Enriching: {filepath}")
        date_str = fname.replace(".json", "")
        upgraded_data = []

        for track in data:
            title = track.get("title", track.get("song", "Unknown"))
            artist = track.get("artist", "Unknown")
            rank = track.get("rank", track.get("position"))
            
            item_id = f"{slugify(title)}-{slugify(artist)}"
            artist_id = slugify(artist)
            type_dir = "songs" if ctype == "hot100" else "albums"
            
            item_path = os.path.join(data_dir, type_dir, f"{item_id}.json")
            artist_path = os.path.join(data_dir, "artists", f"{artist_id}.json")

            # Read historical profile to calculate current stats
            if os.path.exists(item_path):
                with open(item_path, 'r', encoding='utf-8') as pf:
                    item_profile = json.load(pf)
            else:
                item_profile = {"id": item_id, "title": title, "artist": artist, "peak": 999, "history": []}

            try:
                rank_int = int(rank)
            except (ValueError, TypeError):
                rank_int = 999 

            weeks_on_chart = len(item_profile["history"]) + 1
            peak = min(item_profile["peak"], rank_int)
            last_week = item_profile["history"][-1]["rank"] if item_profile["history"] else "-"

            # The fat payload for the weekly chart SPA view
            track_meta = {
                "rank": rank,
                "title": title,
                "artist": artist,
                "id": item_id,
                "artist_id": artist_id,
                "last_week": last_week,
                "peak_position": peak if peak != 999 else "-",
                "weeks_on_chart": weeks_on_chart
            }
            upgraded_data.append(track_meta)

            # Update the specific item profile
            item_profile["peak"] = peak
            item_profile["history"].append({"date": date_str, "rank": rank})
            with open(item_path, 'w', encoding='utf-8') as pf:
                json.dump(item_profile, pf)

            # Update the specific artist profile
            if os.path.exists(artist_path):
                with open(artist_path, 'r', encoding='utf-8') as af:
                    artist_profile = json.load(af)
            else:
                artist_profile = {"id": artist_id, "name": artist, "items": []}
                
            if item_id not in artist_profile["items"]:
                artist_profile["items"].append(item_id)
                with open(artist_path, 'w', encoding='utf-8') as af:
                    json.dump(artist_profile, af)

        # Overwrite weekly file with enriched data
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(upgraded_data, f)
            
        files_processed += 1

    if files_processed > 0:
        build_search_index(data_dir)


def update_charts(data_dir: str = None):
    """Incremental fetch of new data to the filesystem."""
    if data_dir is None:
        data_dir = DATA_DIR

    latest = _get_latest_chart_dates_fs(data_dir)
    latest_valid_week = get_latest_publishable_chart_week()

    # Hot 100
    hot100_latest = latest.get("hot-100")
    if hot100_latest:
        start = (hot100_latest + datetime.timedelta(days=1)).isoformat()
        end = latest_valid_week.isoformat()
        if hot100_latest < latest_valid_week:
            logger.info(f"Hot 100: fetching from {start} to {end}")
            download_hot100(start, end, data_dir)
        else:
            logger.info("Hot 100: already current.")

    # Billboard 200
    b200_latest = latest.get("billboard-200")
    if b200_latest:
        start = (b200_latest + datetime.timedelta(days=1)).isoformat()
        end = latest_valid_week.isoformat()
        if b200_latest < latest_valid_week:
            logger.info(f"Billboard 200: fetching from {start} to {end}")
            download_b200(data_dir=data_dir, start_date=start, end_date=end)
        else:
            logger.info("Billboard 200: already current.")

    run_incremental_enrichment(data_dir)


def repair_gaps(data_dir: str = None, since_year: int = 2025):
    """Find and re-download genuinely missing historical data."""
    if data_dir is None:
        data_dir = DATA_DIR

    latest_valid_week = get_latest_publishable_chart_week()
    repaired = {"hot-100": 0, "billboard-200": 0}

    for chart_type in ["hot-100", "billboard-200"]:
        missing = find_failed_downloads(
            chart_type,
            since_year,
            latest_valid_week.year,
            data_dir,
        )
        missing = [d for d in missing if d <= latest_valid_week.isoformat()]

        if not missing:
            logger.info(f"{chart_type}: no gaps found since {since_year}.")
            continue

        logger.info(f"{chart_type}: {len(missing)} missing dates found. Re-downloading...")

        if chart_type == "hot-100":
            download_hot100(missing[0], missing[-1], data_dir, overwrite=True)
            repaired["hot-100"] = len(missing)
        else:
            download_b200(
                data_dir=data_dir,
                overwrite=True,
                start_date=missing[0],
                end_date=missing[-1],
            )
            repaired["billboard-200"] = len(missing)

    return repaired


def run_update(data_dir: str = None, repair: bool = True, update: bool = True):
    """CLI entry point."""
    results = {}
    if repair:
        logger.info("=== Gap Repair ===")
        results["repair"] = repair_gaps(data_dir)
    if update:
        logger.info("=== Incremental Update & Enrichment ===")
        update_charts(data_dir)
        results["update"] = "Complete"
    return results


if __name__ == "__main__":
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    parser = argparse.ArgumentParser(description="Billboard chart flat-file updater")
    parser.add_argument("--repair", action="store_true", help="Run gap repair only")
    parser.add_argument("--update", action="store_true", help="Run incremental update only")
    parser.add_argument("--data-dir", default=None, help="Data directory override")
    args = parser.parse_args()

    do_repair = args.repair or (not args.repair and not args.update)
    do_update = args.update or (not args.repair and not args.update)

    results = run_update(data_dir=args.data_dir, repair=do_repair, update=do_update)
    print(f"\nResults: {results}")
