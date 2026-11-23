"""Schema 14 (DESIGN.md §46.9): `runs` learns the mode 'video' and the Video tab's three tables arrive (`videos`, `video_segments`, `video_speeds`).

What these protect: a database made by the 1.26 studio (schema 13) is upgraded after a copy is kept, loses no run, no picture, no track and nothing else hanging off a run
(the rebuild of `runs` is done with foreign keys off, and a mistake there would cascade everything away), ends up exactly the tables a new database has (the same columns, types
and order, and the same definition of `runs`), a second start changes nothing and makes no second copy, a database this build made is refused by 1.26 as every schema is, and the
new tables hold their own rules (a clip belongs to a run and goes with it; a segment is queued, running, done, failed or canceled; a speed is kept once for each quality and size).

A schema 13 database is made by taking a current one and putting it back: the three tables dropped, the CHECK on `runs.mode` without 'video', and the version set to 13. That is what
1.26 had, and it is what the upgrade is built to find.
"""

from __future__ import annotations

import re
import sqlite3

import pytest
from test_bin import columns
from test_builder_schema import NOW, stored_version, table_names
from test_db import run_row

import studio.db as db_module
from studio.db import SCHEMA_VERSION, Database, DatabaseError
from studio.video.schema import VIDEO_SCHEMA

VIDEO_TABLES = {"videos", "video_segments", "video_speeds"}


def as_schema_13(path) -> None:
    """Put a current database back to what 1.26 left: no video tables, `runs` rebuilt with the CHECK that does not know 'video', version 13. The rebuild takes the table's own
    definition out of SQLite and edits it, so the result is the table as it was except for what schema 14 added."""
    conn = sqlite3.connect(path)
    try:
        for table in VIDEO_TABLES:
            conn.execute(f"DROP TABLE IF EXISTS {table}")
        definition = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='runs'").fetchone()[0]
        # (a table that was itself renamed into place is stored with its name in quotes: both spellings are found)
        old = re.sub(r'CREATE TABLE "?runs"? \(', "CREATE TABLE runs_13 (", definition.replace(",'video'", ""), count=1)
        assert "video" not in old and "runs_13" in old and old != definition, old  # the edit really took
        names = [r[1] for r in conn.execute("PRAGMA table_info(runs)")]
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute(old)
        conn.execute(f"INSERT INTO runs_13 ({', '.join(names)}) SELECT {', '.join(names)} FROM runs")
        conn.execute("DROP TABLE runs")
        conn.execute("ALTER TABLE runs_13 RENAME TO runs")
        conn.execute("CREATE INDEX idx_runs_status ON runs(status, seq)")
        conn.execute("UPDATE meta SET value='13' WHERE key='schema_version'")
        conn.commit()
    finally:
        conn.close()


def runs_sql(path) -> str:
    """The definition of `runs` as SQLite stores it, with the quotes a RENAME puts round the name taken away, so that a rebuilt table and a new one can be compared."""
    conn = sqlite3.connect(path)
    try:
        sql = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='runs'").fetchone()[0]
    finally:
        conn.close()
    return re.sub(r'\s+', " ", sql.replace('"runs"', "runs"))


def indexes_of(path, table: str = "runs") -> set[str]:
    conn = sqlite3.connect(path)
    try:
        return {r[1] for r in conn.execute(f"PRAGMA index_list({table})")}
    finally:
        conn.close()


def insert_run(db: Database, n: int, mode: str) -> str:
    assert db.insert_run_if_capacity({**run_row(n), "mode": mode}, cap=100)
    return run_row(n)["id"]


# ---------------------------------------------------------------- a new database
def test_a_new_database_has_the_video_tables_and_accepts_the_mode(tmp_path):
    path = tmp_path / "studio.sqlite"
    db = Database(path)
    try:
        assert SCHEMA_VERSION >= 14 and stored_version(path) == str(SCHEMA_VERSION) and VIDEO_TABLES <= table_names(path)
        assert [c[0] for c in columns(path, "videos")] == [
            "id", "run_id", "seed", "width", "height", "fps", "frames", "seconds", "has_audio", "audio_channels", "audio_rate", "bytes", "path", "poster_path", "thumb_path", "created_at", "note"]
        assert [c[0] for c in columns(path, "video_segments")] == ["run_id", "idx", "status", "seed", "frames", "seconds", "prompt", "start_image", "path", "started_at", "finished_at", "error"]
        assert [c[0] for c in columns(path, "video_speeds")] == ["variant", "width", "height", "seconds_per_second", "samples", "updated_at"]
        assert "idx_videos_run" in indexes_of(path, "videos")
        assert sqlite3.connect(path).execute("PRAGMA foreign_key_check").fetchall() == []
        run = insert_run(db, 1, "video")
        assert db.get_run(run)["mode"] == "video"
        with pytest.raises(sqlite3.IntegrityError):  # the CHECK still refuses a mode that does not exist
            insert_run(db, 2, "film")
    finally:
        db.close()


def test_every_statement_of_the_video_schema_can_be_run_twice():
    """`IF NOT EXISTS` all through: opening a database again, or one from a build that already made some of the tables, changes nothing."""
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE runs (id TEXT PRIMARY KEY)")
    conn.executescript(VIDEO_SCHEMA)
    conn.executescript(VIDEO_SCHEMA)


# ---------------------------------------------------------------- the upgrade from schema 13 (1.26)
def database_as_1_26(tmp_path):
    """A schema 13 database with a run of each of the older kinds, a project with a music run filed in it, and a picture and a track hanging off their runs: what an upgrade must not lose."""
    path, fresh = tmp_path / "studio.sqlite", tmp_path / "fresh.sqlite"
    Database(fresh).close()
    db = Database(path)
    project = "c" * 32
    assert db.create_project(project, "Logo", NOW) == "created"
    for n, mode in ((1, "generate"), (2, "music"), (3, "vector"), (4, "edit"), (5, "speech")):
        insert_run(db, n, mode)
    assert db.file_run(run_row(2)["id"], project) == "filed"
    with db.tx() as c:
        c.execute("INSERT INTO images (id, run_id, kind, idx, seed, width, height, has_alpha, bytes, path, created_at) VALUES "
                  "('i1', ?, 'output', 0, 1, 8, 8, 0, 10, 'images/a.png', ?)", (run_row(1)["id"], NOW))
        c.execute("INSERT INTO tracks (id, run_id, idx, seed, seconds, sample_rate, channels, bytes, path, created_at) VALUES "
                  "('t1', ?, 0, 1, 1.0, 44100, 2, 10, 'audio/a.wav', ?)", (run_row(2)["id"], NOW))
        c.execute("INSERT INTO speech_parts (run_id, idx, title, chars) VALUES (?, 0, 'One', 10)", (run_row(5)["id"],))
    before = [dict(r) for r in db.read_all("SELECT * FROM runs ORDER BY seq")]
    db.close()
    as_schema_13(path)
    return path, fresh, before


def test_a_1_26_database_is_upgraded_after_a_copy_and_keeps_everything(tmp_path):
    path, fresh, before = database_as_1_26(tmp_path)
    assert stored_version(path) == "13" and not (VIDEO_TABLES & table_names(path))
    with pytest.raises(sqlite3.IntegrityError):  # the old table really does refuse the new mode: the rebuild below is not a no-op
        with sqlite3.connect(path) as conn:
            run = {**run_row(9), "mode": "video"}
            conn.execute(f"INSERT INTO runs ({', '.join(run)}) VALUES ({', '.join('?' for _ in run)})", tuple(run.values()))

    migrated = Database(path)
    try:
        assert stored_version(path) == str(SCHEMA_VERSION) and VIDEO_TABLES <= table_names(path)
        assert columns(path, "runs") == columns(fresh, "runs")  # the same columns, types and order as a new database: the rebuild gave what CREATE gives
        assert runs_sql(path) == runs_sql(fresh)  # and the same definition, CHECK included
        after = [dict(r) for r in migrated.read_all("SELECT * FROM runs ORDER BY seq")]
        assert after == before  # every run, every column it had, in the order it had them
        assert {"idx_runs_status", "idx_runs_deleted", "idx_runs_project", "idx_runs_prompt"} <= indexes_of(path)  # the rebuild dropped them; they are back
        assert indexes_of(path) == indexes_of(fresh)
        assert [p["name"] for p in migrated.list_projects()] == ["Logo"] and migrated.list_projects()[0]["counts"]["music"] == 1
        assert sqlite3.connect(path).execute("PRAGMA foreign_key_check").fetchall() == []
        # what hung off a run is still there (a rebuild with foreign keys on would have cascaded it away)
        assert [migrated.read_one(f"SELECT COUNT(*) AS n FROM {t}")["n"] for t in ("images", "tracks", "speech_parts")] == [1, 1, 1]
        # and a clip can be made: the mode is accepted and its rows hang off the run
        run = insert_run(migrated, 9, "video")
        with migrated.tx() as c:
            c.execute("INSERT INTO video_segments (run_id, idx, status, seed, frames, seconds, prompt) VALUES (?, 0, 'queued', 1, 25, 1.0, 'a fox')", (run,))
        assert migrated.get_run(run)["mode"] == "video"
    finally:
        migrated.close()
    copy = tmp_path / f"studio.sqlite.before-schema-{SCHEMA_VERSION}"  # named for the version the upgrade went TO
    assert copy.exists() and stored_version(copy) == "13" and not (VIDEO_TABLES & table_names(copy))  # the database as 1.26 left it: a way back
    assert [r[0] for r in sqlite3.connect(copy).execute("SELECT id FROM runs ORDER BY seq")] == [run_row(n)["id"] for n in (1, 2, 3, 4, 5)]


def test_a_database_from_further_back_goes_all_the_way_in_one_start(tmp_path):
    """A schema 9 database (1.19) is rebuilt once, to the current definition, and ends up able to hold every mode including the newest: the rebuild at 14 does what 3, 7 and 10 did."""
    from test_speech_schema import as_schema_9

    path = tmp_path / "studio.sqlite"
    Database(path).close()
    as_schema_9(path)  # takes 'speech' and the two columns of schema 10 out of `runs` (and the speech tables away)
    as_schema_13(path)  # then 'video' and the video tables, on top of that
    conn = sqlite3.connect(path)
    conn.execute("UPDATE meta SET value='9' WHERE key='schema_version'")
    conn.commit()
    conn.close()
    assert stored_version(path) == "9"
    for mode in ("speech", "video"):  # the old table refuses both newer modes, so what follows is a real rebuild
        with pytest.raises(sqlite3.IntegrityError):
            with sqlite3.connect(path) as conn:
                run = {k: v for k, v in {**run_row(9), "mode": mode}.items() if k in {r[1] for r in conn.execute("PRAGMA table_info(runs)")}}
                conn.execute(f"INSERT INTO runs ({', '.join(run)}) VALUES ({', '.join('?' for _ in run)})", tuple(run.values()))
    migrated = Database(path)
    try:
        assert stored_version(path) == str(SCHEMA_VERSION)
        for n, mode in enumerate(("generate", "edit", "music", "vector", "speech", "video"), start=1):
            insert_run(migrated, n, mode)
        assert sqlite3.connect(path).execute("PRAGMA foreign_key_check").fetchall() == []
    finally:
        migrated.close()


def test_an_existing_copy_is_never_replaced_by_a_later_attempt(tmp_path):
    path = tmp_path / "studio.sqlite"
    Database(path).close()
    as_schema_13(path)
    keep = tmp_path / f"studio.sqlite.before-schema-{SCHEMA_VERSION}"
    keep.write_bytes(b"the oldest copy")
    Database(path).close()
    assert keep.read_bytes() == b"the oldest copy"


def test_a_second_start_changes_nothing_and_makes_no_second_copy(tmp_path):
    path, _, _ = database_as_1_26(tmp_path)
    Database(path).close()
    copy = tmp_path / f"studio.sqlite.before-schema-{SCHEMA_VERSION}"
    first = copy.read_bytes()
    shape = sqlite3.connect(path).execute("SELECT group_concat(sql) FROM sqlite_master ORDER BY name").fetchone()
    Database(path).close()
    assert copy.read_bytes() == first
    assert sqlite3.connect(path).execute("SELECT group_concat(sql) FROM sqlite_master ORDER BY name").fetchone() == shape


def test_a_database_made_by_this_build_is_refused_by_1_26(tmp_path, monkeypatch):
    """An older studio that opens this database would reject its clips' runs (its CHECK does not know the mode), so it refuses, as every schema has."""
    path = tmp_path / "studio.sqlite"
    Database(path).close()
    monkeypatch.setattr(db_module, "SCHEMA_VERSION", 13)
    with pytest.raises(DatabaseError, match="newer version of the studio"):
        Database(path)


def test_a_new_database_that_was_never_at_schema_13_is_not_given_a_copy(tmp_path):
    Database(tmp_path / "studio.sqlite").close()
    assert not list(tmp_path.glob("*.before-schema-*"))


# ---------------------------------------------------------------- the tables hold the rules themselves
@pytest.fixture
def db(tmp_path):
    database = Database(tmp_path / "studio.sqlite")
    yield database
    database.close()


VIDEO = ("INSERT INTO videos (id, run_id, seed, width, height, fps, frames, seconds, has_audio, bytes, path, poster_path, created_at) "
         "VALUES (?, ?, 1, 256, 128, 24.0, 25, 1.04, 1, 100, 'video/x/clip.mp4', 'video/x/poster.jpg', ?)")
SEGMENT = "INSERT INTO video_segments (run_id, idx, status, seed, frames, seconds, prompt) VALUES (?, ?, ?, 1, 25, 1.04, 'a fox')"


def insert(db: Database, sql: str, args: tuple = ()) -> None:
    with db.tx() as c:
        c.execute(sql, args)


def test_a_clip_belongs_to_a_run_that_is_there_and_goes_with_it(db):
    run, other = insert_run(db, 1, "video"), insert_run(db, 2, "video")
    for r, vid in ((run, "v1"), (other, "v2")):
        insert(db, VIDEO, (vid, r, NOW))
        insert(db, SEGMENT, (r, 0, "done"))
    with pytest.raises(sqlite3.IntegrityError):  # a clip cannot hang off a run that is not there
        insert(db, VIDEO, ("v3", "f" * 32, NOW))
    with db.tx() as c:
        db._delete_rows(c, [run])  # what Delete forever does for a run
    for table in ("videos", "video_segments"):
        assert db.read_one(f"SELECT COUNT(*) AS n, MIN(run_id) AS only FROM {table}")["only"] == other, table  # the other clip keeps its rows
    assert db.read_one("SELECT COUNT(*) AS n FROM videos")["n"] == 1


def test_a_segment_is_queued_running_done_failed_or_canceled_and_nothing_else_and_numbered_once(db):
    run = insert_run(db, 1, "video")
    for n, status in enumerate(("queued", "running", "done", "failed", "canceled")):
        insert(db, SEGMENT, (run, n, status))
    with pytest.raises(sqlite3.IntegrityError):
        insert(db, SEGMENT, (run, 5, "paused"))
    with pytest.raises(sqlite3.IntegrityError):  # each piece number once for a clip
        insert(db, SEGMENT, (run, 0, "queued"))


def test_a_speed_is_kept_once_for_each_quality_and_size(db):
    insert(db, "INSERT INTO video_speeds (variant, width, height, seconds_per_second, samples, updated_at) VALUES ('distilled', 1280, 704, 20.0, 1, ?)", (NOW,))
    insert(db, "INSERT INTO video_speeds (variant, width, height, seconds_per_second, samples, updated_at) VALUES ('distilled', 1024, 576, 12.0, 1, ?)", (NOW,))
    with pytest.raises(sqlite3.IntegrityError):
        insert(db, "INSERT INTO video_speeds (variant, width, height, seconds_per_second, samples, updated_at) VALUES ('distilled', 1280, 704, 21.0, 2, ?)", (NOW,))
