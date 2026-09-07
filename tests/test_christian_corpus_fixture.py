import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


EXPECTED_TRADITIONS = {
    "ecumenical",
    "catholic",
    "eastern_orthodox",
    "oriental_orthodox",
    "lutheran",
    "reformed",
    "anglican",
    "methodist",
    "baptist",
    "pentecostal",
    "evangelical",
    "anabaptist",
    "adventist",
    "salvation_army",
    "friends",
    "moravian",
    "holiness",
    "restorationist",
    "korean_presbyterian",
    "korean_methodist",
    "korean_baptist",
    "korean_holiness",
    "korean_pentecostal",
    "korean_anglican",
    "korean_orthodox",
    "korean_lutheran",
    "korean_salvation_army",
    "korean_ecumenical",
}

EXPECTED_COUNTS = {
    "sources": 76,
    "passages": 80,
    "precedents": 80,
    "precedents_fts": 80,
}


def load_christian_fixture(con: sqlite3.Connection) -> None:
    fixture_sql = (ROOT / "corpus" / "christian" / "fixture.sql").read_text(
        encoding="utf-8"
    )
    registry_sql = (
        ROOT / "corpus" / "christian" / "denomination_registry.sql"
    ).read_text(encoding="utf-8")
    con.executescript(fixture_sql)
    con.executescript(registry_sql)


def test_christian_fixture_loads_expanded_denominational_scope(tmp_path):
    db_path = tmp_path / "christian.sqlite3"

    con = sqlite3.connect(db_path)
    try:
        load_christian_fixture(con)
        traditions = {
            row[0]
            for row in con.execute(
                "select distinct tradition from sources where religion = 'christian'"
            )
        }
        assert EXPECTED_TRADITIONS <= traditions

        ids = [row[0] for row in con.execute("select source_id from sources")]
        assert ids
        assert all(item.startswith("christian.") for item in ids)
        assert not any(item.startswith("catholic.") for item in ids)

        for table, expected in EXPECTED_COUNTS.items():
            assert con.execute(f"select count(*) from {table}").fetchone()[0] == expected

        source_count = con.execute("select count(*) from sources").fetchone()[0]
        catholic_count = con.execute(
            "select count(*) from sources where tradition = 'catholic'"
        ).fetchone()[0]
        assert source_count == EXPECTED_COUNTS["sources"]
        assert source_count - catholic_count >= 70
        assert con.execute(
            "select count(*) from sources where source_url <> ''"
        ).fetchone()[0] == source_count
        assert con.execute(
            "select count(*) from sources where source_kind in ('denomination_index', 'denomination_profile')"
        ).fetchone()[0] >= 60
        assert con.execute(
            "select count(*) from sources where source_id like 'christian.korea.%'"
        ).fetchone()[0] >= 20
        assert con.execute(
            "select count(*) from sources where tradition in ('eastern_orthodox', 'oriental_orthodox', 'korean_orthodox')"
        ).fetchone()[0] >= 20

        matches = con.execute(
            "select canonical_id from precedents_fts where precedents_fts match 'justification'"
        ).fetchall()
        assert matches
        assert con.execute(
            "select count(*) from precedents_fts where precedents_fts match 'Orthodox'"
        ).fetchone()[0]
        assert con.execute(
            "select count(*) from precedents_fts where precedents_fts match '한국'"
        ).fetchone()[0]
    finally:
        con.close()


def test_committed_christian_fixture_db_is_loaded_from_expanded_scope():
    db_path = ROOT / "corpus" / "christian" / "christian.sqlite3"
    assert db_path.exists()

    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        traditions = {
            row[0]
            for row in con.execute(
                "select distinct tradition from sources where religion = 'christian'"
            )
        }
        assert EXPECTED_TRADITIONS <= traditions
        for table, expected in EXPECTED_COUNTS.items():
            assert con.execute(f"select count(*) from {table}").fetchone()[0] == expected
        assert con.execute(
            "select count(*) from sources where source_id like 'christian.korea.%'"
        ).fetchone()[0] >= 20
    finally:
        con.close()


def test_legacy_catholic_collectors_now_emit_christian_catholic_scope():
    collector_dir = ROOT / "collectors" / "catholic"
    texts = "\n".join(path.read_text(encoding="utf-8") for path in collector_dir.glob("*.py"))

    assert 'ROOT / "corpus" / "christian"' in texts
    assert '"religion": "catholic"' not in texts
    assert '"religion":"catholic"' not in texts
    assert '"catholic.' not in texts
    assert '"christian.catholic.' in texts
