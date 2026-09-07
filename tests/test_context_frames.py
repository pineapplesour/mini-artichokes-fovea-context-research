from shared_platform.context_frames import (
    EventFrame,
    LegalTaxonomy,
    StoredEventFrame,
    extract_legal_event_frames,
    frame_sim,
    ensure_event_frame_schema,
    load_event_frames,
    rank_analogous_frames,
    stored_event_frames_from_records,
    upsert_event_frames,
)


ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]


def test_legal_taxonomy_resolves_aliases_and_scores_shared_investigative_actor():
    taxonomy = LegalTaxonomy.default()

    police = taxonomy.resolve("경찰", slot="actor")
    prosecutor = taxonomy.resolve("검찰", slot="actor")
    military_key = taxonomy.resolve("열쇠", slot="object")
    kidney = taxonomy.resolve("신장", slot="object")

    assert police == "LEGAL/STATE_ACTOR/INVESTIGATIVE/POLICE"
    assert prosecutor == "LEGAL/STATE_ACTOR/INVESTIGATIVE/PROSECUTOR"
    assert taxonomy.tax_sim(police, prosecutor) >= 0.75
    assert taxonomy.tax_sim(military_key, kidney) < 0.25


def test_frame_sim_treats_sim_login_and_password_hack_as_contextually_close():
    taxonomy = LegalTaxonomy.default()
    query = EventFrame(
        actor_class=taxonomy.resolve("경찰", slot="actor"),
        action_class=taxonomy.resolve("유심 공기계 로그인", slot="action"),
        object_class=taxonomy.resolve("카카오톡", slot="object"),
        method_class=taxonomy.resolve("유심 재삽입", slot="method"),
        issue_tags=("WARRANT_SCOPE", "ELECTRONIC_EVIDENCE", "EXCLUSIONARY_RULE"),
        outcome="UNLAWFUL",
    )
    candidate = EventFrame(
        actor_class=taxonomy.resolve("검찰", slot="actor"),
        action_class=taxonomy.resolve("비밀번호 해킹", slot="action"),
        object_class=taxonomy.resolve("텔레그램", slot="object"),
        method_class=taxonomy.resolve("비밀번호 우회", slot="method"),
        issue_tags=("WARRANT_SCOPE", "ELECTRONIC_EVIDENCE", "EXCLUSIONARY_RULE"),
        outcome="UNLAWFUL",
    )

    score = frame_sim(query, candidate, taxonomy)

    assert score >= 0.55


def test_frame_sim_filters_military_key_from_kidney_height_context():
    taxonomy = LegalTaxonomy.default()
    key_management = EventFrame(
        actor_class=taxonomy.resolve("군부대", slot="actor"),
        action_class=taxonomy.resolve("열쇠 보관", slot="action"),
        object_class=taxonomy.resolve("탄약고 열쇠", slot="object"),
        method_class=taxonomy.resolve("분리 관리", slot="method"),
        issue_tags=("MILITARY_SECURITY", "KEY_MANAGEMENT"),
        outcome="CONDITIONAL",
    )
    body_height = EventFrame(
        actor_class=taxonomy.resolve("군인", slot="actor"),
        action_class=taxonomy.resolve("신체 성장", slot="action"),
        object_class=taxonomy.resolve("신장", slot="object"),
        method_class="",
        issue_tags=("MEDICAL_BODY",),
        outcome="NONE",
    )

    assert frame_sim(key_management, body_height, taxonomy) < 0.30


def test_extract_legal_event_frames_normalizes_sim_messenger_access_query():
    taxonomy = LegalTaxonomy.default()

    frames = extract_legal_event_frames("경찰이 피의자 유심 빼서 공기계에 꽂고 카톡 로그인한 증거 합법임?", taxonomy)

    assert len(frames) == 1
    frame = frames[0]
    assert frame.actor_class == "LEGAL/STATE_ACTOR/INVESTIGATIVE/POLICE"
    assert frame.action_class == "LEGAL/ACTION/ELECTRONIC_ACCESS/ACCOUNT_LOGIN/SIM_REINSERT_LOGIN"
    assert frame.object_class == "LEGAL/OBJECT/COMM/MESSENGER/KAKAOTALK"
    assert frame.method_class == "LEGAL/METHOD/TECHNICAL_ACCESS/SIM_REINSERTION"
    assert "WARRANT_SCOPE" in frame.issue_tags
    assert "ELECTRONIC_EVIDENCE" in frame.issue_tags


def test_extract_legal_event_frames_normalizes_usim_and_subscriber_module_aliases():
    taxonomy = LegalTaxonomy.default()

    frame = extract_legal_event_frames(
        "수사기관이 가입자식별모듈을 제거한 뒤 공기계로 카카오톡 계정에 접속했다.",
        taxonomy,
    )[0]

    assert frame.action_class == "LEGAL/ACTION/ELECTRONIC_ACCESS/ACCOUNT_LOGIN/SIM_REINSERT_LOGIN"
    assert frame.object_class == "LEGAL/OBJECT/COMM/MESSENGER/KAKAOTALK"
    assert frame.method_class == "LEGAL/METHOD/TECHNICAL_ACCESS/SIM_REINSERTION"
    assert "ELECTRONIC_EVIDENCE" in frame.issue_tags


def test_extract_legal_event_frames_normalizes_password_pattern_unlock_aliases():
    taxonomy = LegalTaxonomy.default()

    frame = extract_legal_event_frames(
        "수사기관이 피의자 휴대전화 패턴을 우회해 잠금해제하고 텔레그램 계정에 접속했다.",
        taxonomy,
    )[0]

    assert frame.action_class == "LEGAL/ACTION/ELECTRONIC_ACCESS/ACCOUNT_LOGIN/PASSWORD_BYPASS"
    assert frame.object_class == "LEGAL/OBJECT/COMM/MESSENGER/TELEGRAM"
    assert frame.method_class == "LEGAL/METHOD/TECHNICAL_ACCESS/PASSWORD_BYPASS"
    assert "ELECTRONIC_EVIDENCE" in frame.issue_tags


def test_extract_legal_event_frames_keeps_military_key_apart_from_body_height():
    taxonomy = LegalTaxonomy.default()

    military = extract_legal_event_frames("군대에서 키는 어캐 관리해야함?", taxonomy)[0]
    height = extract_legal_event_frames("군 복무 중 신체 키와 체격 성장에 관한 상담", taxonomy)[0]
    mixed_height = extract_legal_event_frames("군 복무 중 신체 키 성장 관리는 어떻게 하나?", taxonomy)[0]

    assert military.object_class == "LEGAL/OBJECT/SECURITY/KEY"
    assert "KEY_MANAGEMENT" in military.issue_tags
    assert height.object_class == "LEGAL/OBJECT/BODY/HEIGHT"
    assert "MEDICAL_BODY" in height.issue_tags
    assert mixed_height.object_class == "LEGAL/OBJECT/BODY/HEIGHT"
    assert "KEY_MANAGEMENT" not in mixed_height.issue_tags
    assert frame_sim(military, height, taxonomy) < 0.30


def test_rank_analogous_frames_returns_cross_case_contextual_matches_with_path_reason():
    taxonomy = LegalTaxonomy.default()
    target = StoredEventFrame(
        frame_id="f-target",
        doc_id="case-2021노1520",
        chunk_id="chunk-1",
        frame=extract_legal_event_frames(
            "검사가 유심칩을 별도의 휴대전화 공기계에 꽂고 인증번호를 받아 카카오톡 계정에 접속하였다.",
            taxonomy,
        )[0],
        text="검사가 유심칩을 공기계에 꽂아 카카오톡 계정에 접속한 판례",
    )
    negative = StoredEventFrame(
        frame_id="f-negative",
        doc_id="case-height",
        chunk_id="chunk-1",
        frame=extract_legal_event_frames("군 복무 중 신체 키와 체격 성장에 관한 상담", taxonomy)[0],
        text="신체 키 성장 사건",
    )

    matches = rank_analogous_frames(
        "경찰이 피의자 유심 빼서 카톡 로그인하는거 합법임?",
        [negative, target],
        taxonomy=taxonomy,
        threshold=0.55,
    )

    assert [match.frame.doc_id for match in matches] == ["case-2021노1520"]
    assert matches[0].edge_type == "ANALOGOUS_FRAME"
    assert "frame_sim" in matches[0].path_reason


def test_short_sim_removal_query_matches_password_bypass_context_without_body_height_noise():
    taxonomy = LegalTaxonomy.default()
    same_sim = StoredEventFrame(
        frame_id="f-sim",
        doc_id="case-prosecutor-sim",
        chunk_id="chunk-1",
        frame=extract_legal_event_frames("검찰이 피의자 유심을 뽑아 별도 보관한 전자정보 증거 사건", taxonomy)[0],
        text="검찰 유심 분리 전자정보 증거",
    )
    password_bypass = StoredEventFrame(
        frame_id="f-password",
        doc_id="case-password-bypass",
        chunk_id="chunk-1",
        frame=extract_legal_event_frames("수사기관이 피의자 비밀번호를 해킹함", taxonomy)[0],
        text="수사기관 비밀번호 해킹 전자정보 접근",
    )
    body_height = StoredEventFrame(
        frame_id="f-height",
        doc_id="case-height",
        chunk_id="chunk-1",
        frame=extract_legal_event_frames("군 복무 중 신체 키와 체격 성장에 관한 상담", taxonomy)[0],
        text="신체 키 성장 사건",
    )

    matches = rank_analogous_frames(
        "경찰이 유심을 뽑음",
        [body_height, password_bypass, same_sim],
        taxonomy=taxonomy,
        threshold=0.55,
    )

    assert [match.frame.doc_id for match in matches] == ["case-prosecutor-sim", "case-password-bypass"]
    assert matches[0].score > matches[1].score


def test_event_frame_sqlite_roundtrip_supports_analogous_ranking(tmp_path):
    import sqlite3

    taxonomy = LegalTaxonomy.default()
    db_path = tmp_path / "frames.sqlite3"
    with sqlite3.connect(db_path) as conn:
        ensure_event_frame_schema(conn)
        upsert_event_frames(
            conn,
            [
                StoredEventFrame(
                    frame_id="f1",
                    doc_id="case-2021노1520",
                    chunk_id="chunk-1",
                    frame=extract_legal_event_frames(
                        "검사가 유심칩을 공기계에 꽂아 카카오톡 계정에 접속한 전자정보 증거 사건",
                        taxonomy,
                    )[0],
                    text="유심 공기계 카카오톡 접속",
                )
            ],
        )
        loaded = load_event_frames(conn)

    assert len(loaded) == 1
    assert loaded[0].frame_id == "f1"
    assert loaded[0].frame.issue_tags == ("ELECTRONIC_EVIDENCE", "WARRANT_SCOPE")
    matches = rank_analogous_frames("경찰이 유심 빼서 카톡 로그인한 증거 합법임?", loaded, taxonomy=taxonomy)
    assert matches and matches[0].frame.doc_id == "case-2021노1520"


def test_stored_event_frames_from_records_uses_canonical_id_and_full_text():
    taxonomy = LegalTaxonomy.default()
    frames = stored_event_frames_from_records(
        [
            {
                "canonical_id": "case-2021노1520",
                "full_text": "검사가 유심칩을 공기계에 꽂아 인증번호를 받아 카카오톡 계정에 접속한 사건",
            },
            {"canonical_id": "noise", "full_text": "아무 법률 맥락 없는 문장"},
        ],
        taxonomy=taxonomy,
    )

    assert len(frames) == 1
    assert frames[0].frame_id == "case-2021노1520#frame1"
    assert frames[0].doc_id == "case-2021노1520"
    assert frames[0].chunk_id == "case-2021노1520#full_text"


def test_build_lawkey_event_frames_populates_sqlite_db(tmp_path):
    import sqlite3

    from tools.build_lawkey_event_frames import build_lawkey_event_frames

    db_path = tmp_path / "lawkey.sqlite3"
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE precedents (
              canonical_id TEXT PRIMARY KEY,
              full_text TEXT NOT NULL
            );
            INSERT INTO precedents VALUES
              ('case-2021노1520', '검사가 유심칩을 공기계에 꽂아 인증번호를 받아 카카오톡 계정에 접속한 사건'),
              ('noise', '아무 법률 맥락 없는 문장');
            """
        )

    report = build_lawkey_event_frames(db_path)

    assert report["sourceCount"] == 2
    assert report["frameCount"] == 1
    with sqlite3.connect(db_path) as conn:
        loaded = load_event_frames(conn)
    assert [frame.doc_id for frame in loaded] == ["case-2021노1520"]


def test_build_lawkey_event_frames_cli_runs_from_outside_repo(tmp_path):
    import sqlite3
    import subprocess
    import sys

    db_path = tmp_path / "lawkey.sqlite3"
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE precedents (
              canonical_id TEXT PRIMARY KEY,
              full_text TEXT NOT NULL
            );
            INSERT INTO precedents VALUES
              ('case-2021노1520', '검사가 유심칩을 공기계에 꽂아 인증번호를 받아 카카오톡 계정에 접속한 사건');
            """
        )

    script = ROOT / "tools" / "build_lawkey_event_frames.py"
    completed = subprocess.run(
        [sys.executable, str(script), "--db-path", str(db_path)],
        cwd=tmp_path,
        check=True,
        text=True,
        capture_output=True,
    )

    assert '"frameCount": 1' in completed.stdout
