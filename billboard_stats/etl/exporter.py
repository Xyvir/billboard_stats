"""Static data exporter — dumps SQLite data into JSON files for the frontend."""

import json
import logging
import os
from pathlib import Path
from billboard_stats.db.connection import get_conn, put_conn

logger = logging.getLogger(__name__)

# Output directory for static JSON data
PUBLIC_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "public" / "data"

def export_all():
    """Run all export tasks."""
    PUBLIC_DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    conn = get_conn()
    try:
        logger.info("Exporting chart weeks...")
        _export_chart_weeks(conn)
        
        logger.info("Exporting search index...")
        _export_search_index(conn)
        
        logger.info("Exporting artists...")
        _export_entities(conn, "artists", "artist_stats", "artist_id")
        
        logger.info("Exporting songs...")
        _export_entities(conn, "songs", "song_stats", "song_id")
        
        logger.info("Exporting albums...")
        _export_entities(conn, "albums", "album_stats", "album_id")
        
        logger.info("Exporting latest charts...")
        _export_latest_charts(conn)
        
        logger.info("Export complete.")
    finally:
        put_conn(conn)

def _export_chart_weeks(conn):
    """Export a summary of all available chart weeks."""
    cur = conn.cursor()
    cur.execute("SELECT chart_date, chart_type FROM chart_weeks ORDER BY chart_date DESC;")
    weeks = [dict(row) for row in cur.fetchall()]
    
    with open(PUBLIC_DATA_DIR / "chart-weeks.json", "w") as f:
        json.dump(weeks, f)

def _export_search_index(conn):
    """Export a minimal index for client-side search."""
    cur = conn.cursor()
    
    # Artists
    cur.execute("""
        SELECT a.id, a.name, s.total_hot100_songs, s.total_b200_albums, s.hot100_number_ones, s.b200_number_ones
        FROM artists a
        JOIN artist_stats s ON a.id = s.artist_id
        WHERE s.total_hot100_songs > 0 OR s.total_b200_albums > 0;
    """)
    artists = [dict(row) for row in cur.fetchall()]
    
    # Songs (Top 10000 by weeks for index size management)
    cur.execute("""
        SELECT s.id, s.title, s.artist_credit, st.peak_position, st.total_weeks
        FROM songs s
        JOIN song_stats st ON s.id = st.song_id
        ORDER BY st.total_weeks DESC
        LIMIT 10000;
    """)
    songs = [dict(row) for row in cur.fetchall()]
    
    # Albums (Top 5000 by weeks)
    cur.execute("""
        SELECT a.id, a.title, a.artist_credit, st.peak_position, st.total_weeks
        FROM albums a
        JOIN album_stats st ON a.id = st.album_id
        ORDER BY st.total_weeks DESC
        LIMIT 5000;
    """)
    albums = [dict(row) for row in cur.fetchall()]
    
    index = {
        "artists": artists,
        "songs": songs,
        "albums": albums
    }
    
    with open(PUBLIC_DATA_DIR / "search-index.json", "w") as f:
        json.dump(index, f)

def _export_entities(conn, table, stats_table, fk_col):
    """Export individual JSON files for each entity."""
    entity_dir = PUBLIC_DATA_DIR / table
    entity_dir.mkdir(parents=True, exist_ok=True)
    
    cur = conn.cursor()
    cur.execute(f"SELECT t.*, s.* FROM {table} t JOIN {stats_table} s ON t.id = s.{fk_col};")
    
    for row in cur.fetchall():
        data = dict(row)
        # Add chart run data
        if table == "songs":
            cur2 = conn.cursor()
            cur2.execute("""
                SELECT cw.chart_date, e.rank
                FROM hot100_entries e
                JOIN chart_weeks cw ON e.chart_week_id = cw.id
                WHERE e.song_id = ?
                ORDER BY cw.chart_date ASC;
            """, (data['id'],))
            data['chart_run'] = [dict(r) for r in cur2.fetchall()]
        elif table == "albums":
            cur2 = conn.cursor()
            cur2.execute("""
                SELECT cw.chart_date, e.rank
                FROM b200_entries e
                JOIN chart_weeks cw ON e.chart_week_id = cw.id
                WHERE e.album_id = ?
                ORDER BY cw.chart_date ASC;
            """, (data['id'],))
            data['chart_run'] = [dict(r) for r in cur2.fetchall()]
        elif table == "artists":
            # List of songs and albums for the artist
            cur2 = conn.cursor()
            cur2.execute("""
                SELECT s.id, s.title, st.peak_position, st.total_weeks
                FROM songs s
                JOIN song_artists sa ON s.id = sa.song_id
                JOIN song_stats st ON s.id = st.song_id
                WHERE sa.artist_id = ?
                ORDER BY st.total_weeks DESC;
            """, (data['id'],))
            data['songs'] = [dict(r) for r in cur2.fetchall()]
            
            cur2.execute("""
                SELECT a.id, a.title, st.peak_position, st.total_weeks
                FROM albums a
                JOIN album_artists aa ON a.id = aa.album_id
                JOIN album_stats st ON a.id = st.album_id
                WHERE aa.artist_id = ?
                ORDER BY st.total_weeks DESC;
            """, (data['id'],))
            data['albums'] = [dict(r) for r in cur2.fetchall()]

        with open(entity_dir / f"{data['id']}.json", "w") as f:
            json.dump(data, f)

def _export_latest_charts(conn):
    """Export the most recent charts for the homepage."""
    charts_dir = PUBLIC_DATA_DIR / "charts"
    charts_dir.mkdir(parents=True, exist_ok=True)
    
    cur = conn.cursor()
    for chart_type in ['hot-100', 'billboard-200']:
        cur.execute("""
            SELECT id, chart_date FROM chart_weeks 
            WHERE chart_type = ? 
            ORDER BY chart_date DESC LIMIT 1;
        """, (chart_type,))
        latest = cur.fetchone()
        if not latest:
            continue
            
        chart_week_id = latest['id']
        if chart_type == 'hot-100':
            cur.execute("""
                SELECT e.rank, s.title, s.artist_credit, e.peak_pos, e.last_pos, e.weeks_on_chart, e.is_new, s.id as song_id
                FROM hot100_entries e
                JOIN songs s ON e.song_id = s.id
                WHERE e.chart_week_id = ?
                ORDER BY e.rank ASC;
            """, (chart_week_id,))
        else:
            cur.execute("""
                SELECT e.rank, a.title, a.artist_credit, e.peak_pos, e.last_pos, e.weeks_on_chart, e.is_new, a.id as album_id
                FROM b200_entries e
                JOIN albums a ON e.album_id = a.id
                WHERE e.chart_week_id = ?
                ORDER BY e.rank ASC;
            """, (chart_week_id,))
            
        entries = [dict(row) for row in cur.fetchall()]
        with open(charts_dir / f"{chart_type}-latest.json", "w") as f:
            json.dump({"date": latest['chart_date'], "entries": entries}, f)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    export_all()
