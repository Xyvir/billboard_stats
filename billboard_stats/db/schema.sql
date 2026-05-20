-- Billboard Music Statistics Platform — Database Schema (SQLite version)

-- ============================================================
-- Core Tables
-- ============================================================

-- Individual artists (normalized, deduplicated)
CREATE TABLE IF NOT EXISTS artists (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    image_url   TEXT
);

-- Unique songs (identified by title + raw credit)
CREATE TABLE IF NOT EXISTS songs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    title           TEXT NOT NULL,
    artist_credit   TEXT NOT NULL,
    image_url       TEXT,
    UNIQUE(title, artist_credit)
);

-- Unique albums
CREATE TABLE IF NOT EXISTS albums (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    title           TEXT NOT NULL,
    artist_credit   TEXT NOT NULL,
    image_url       TEXT,
    UNIQUE(title, artist_credit)
);

-- Many-to-many: songs <-> normalized artists
CREATE TABLE IF NOT EXISTS song_artists (
    song_id     INTEGER REFERENCES songs(id),
    artist_id   INTEGER REFERENCES artists(id),
    role        TEXT NOT NULL DEFAULT 'primary',
    PRIMARY KEY (song_id, artist_id)
);

-- Many-to-many: albums <-> normalized artists
CREATE TABLE IF NOT EXISTS album_artists (
    album_id    INTEGER REFERENCES albums(id),
    artist_id   INTEGER REFERENCES artists(id),
    role        TEXT NOT NULL DEFAULT 'primary',
    PRIMARY KEY (album_id, artist_id)
);

-- Each weekly chart publication
CREATE TABLE IF NOT EXISTS chart_weeks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    chart_date  TEXT NOT NULL,
    chart_type  TEXT NOT NULL CHECK (chart_type IN ('hot-100', 'billboard-200')),
    UNIQUE(chart_date, chart_type)
);

-- Weekly Hot 100 position entries
CREATE TABLE IF NOT EXISTS hot100_entries (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    chart_week_id   INTEGER NOT NULL REFERENCES chart_weeks(id),
    song_id         INTEGER NOT NULL REFERENCES songs(id),
    rank            INTEGER NOT NULL,
    peak_pos        INTEGER,
    last_pos        INTEGER,
    weeks_on_chart  INTEGER,
    is_new          BOOLEAN NOT NULL DEFAULT 0,
    UNIQUE(chart_week_id, rank)
);

-- Weekly Billboard 200 position entries
CREATE TABLE IF NOT EXISTS b200_entries (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    chart_week_id   INTEGER NOT NULL REFERENCES chart_weeks(id),
    album_id        INTEGER NOT NULL REFERENCES albums(id),
    rank            INTEGER NOT NULL,
    peak_pos        INTEGER,
    last_pos        INTEGER,
    weeks_on_chart  INTEGER,
    is_new          BOOLEAN NOT NULL DEFAULT 0,
    UNIQUE(chart_week_id, rank)
);

-- ============================================================
-- Pre-computed Stats Tables
-- ============================================================

-- Aggregated stats per song
CREATE TABLE IF NOT EXISTS song_stats (
    song_id             INTEGER PRIMARY KEY REFERENCES songs(id),
    total_weeks         INTEGER NOT NULL DEFAULT 0,
    peak_position       INTEGER,
    weeks_at_peak       INTEGER NOT NULL DEFAULT 0,
    weeks_at_number_one INTEGER NOT NULL DEFAULT 0,
    debut_date          TEXT,
    last_date           TEXT,
    debut_position      INTEGER
);

-- Aggregated stats per album
CREATE TABLE IF NOT EXISTS album_stats (
    album_id            INTEGER PRIMARY KEY REFERENCES albums(id),
    total_weeks         INTEGER NOT NULL DEFAULT 0,
    peak_position       INTEGER,
    weeks_at_peak       INTEGER NOT NULL DEFAULT 0,
    weeks_at_number_one INTEGER NOT NULL DEFAULT 0,
    debut_date          TEXT,
    last_date           TEXT,
    debut_position      INTEGER
);

-- Aggregated career stats per artist (cross-chart)
CREATE TABLE IF NOT EXISTS artist_stats (
    artist_id               INTEGER PRIMARY KEY REFERENCES artists(id),
    total_hot100_songs      INTEGER NOT NULL DEFAULT 0,
    total_b200_albums       INTEGER NOT NULL DEFAULT 0,
    total_hot100_weeks      INTEGER NOT NULL DEFAULT 0,
    total_b200_weeks        INTEGER NOT NULL DEFAULT 0,
    hot100_number_ones      INTEGER NOT NULL DEFAULT 0,
    b200_number_ones        INTEGER NOT NULL DEFAULT 0,
    best_hot100_peak        INTEGER,
    best_b200_peak          INTEGER,
    first_chart_date        TEXT,
    latest_chart_date       TEXT,
    max_simultaneous_hot100 INTEGER NOT NULL DEFAULT 0
);

-- ============================================================
-- Indexes
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_hot100_song_id ON hot100_entries(song_id);
CREATE INDEX IF NOT EXISTS idx_hot100_chart_week ON hot100_entries(chart_week_id);
CREATE INDEX IF NOT EXISTS idx_b200_album_id ON b200_entries(album_id);
CREATE INDEX IF NOT EXISTS idx_b200_chart_week ON b200_entries(chart_week_id);
CREATE INDEX IF NOT EXISTS idx_chart_weeks_date ON chart_weeks(chart_date);
CREATE INDEX IF NOT EXISTS idx_chart_weeks_type_date ON chart_weeks(chart_type, chart_date);
CREATE INDEX IF NOT EXISTS idx_song_artists_artist ON song_artists(artist_id);
CREATE INDEX IF NOT EXISTS idx_album_artists_artist ON album_artists(artist_id);
