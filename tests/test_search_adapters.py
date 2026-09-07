import re
import sqlite3
from contextlib import nullcontext
from pathlib import Path

from shared_platform.context_frames import (
    LegalTaxonomy,
    StoredEventFrame,
    ensure_event_frame_schema,
    extract_legal_event_frames,
    upsert_event_frames,
)
from shared_platform.products import ProductProfile
from shared_platform.beta6 import (
    _search_documents_for_beta6_candidate_scan,
    build_beta6_candidate_search_plan,
    collect_candidate_rows,
)
from shared_platform.search import describe_query_expansion, search_documents, to_beta6_selected_record
from shared_platform.tcm_mcq import (
    canonicalize_tcm_answer_number,
    parse_tcm_mcq,
    tcm_mcq_option_terms,
    tcm_mcq_search_text,
)
import shared_platform.search as search_mod


def _make_precedents_db(path):
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE precedents (
          canonical_id TEXT PRIMARY KEY,
          source_dataset TEXT,
          source_path TEXT,
          title TEXT,
          case_number TEXT,
          court TEXT,
          decision_date TEXT,
          case_name TEXT,
          case_type TEXT,
          full_text TEXT NOT NULL,
          text_hash TEXT NOT NULL
        );
        CREATE VIRTUAL TABLE precedents_fts USING fts5(
          canonical_id UNINDEXED,
          full_text,
          tokenize='unicode61'
        );
        INSERT INTO precedents VALUES
          ('doc-quran-1','islam/all/scripture','quran/2/255','Quran 2:255','Quran 2:255','Qur''an','','Ayat al-Kursi','scripture_window','Allah, worship, protection, throne and knowledge.','hash1'),
          ('doc-fiqh-1','islam/hanafi/fiqh','fiqh/prayer','Prayer Times','Prayer','Hanafi fiqh','','Prayer time ruling','legal_issue_bundle','Prayer time, qibla, fasting and worship practice.','hash2');
        INSERT INTO precedents_fts(canonical_id, full_text)
          SELECT canonical_id, full_text FROM precedents;
        """
    )
    conn.commit()
    conn.close()


def _make_islam_school_db(path):
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE precedents (
          canonical_id TEXT PRIMARY KEY,
          source_dataset TEXT,
          source_path TEXT,
          title TEXT,
          case_number TEXT,
          court TEXT,
          decision_date TEXT,
          case_name TEXT,
          case_type TEXT,
          full_text TEXT NOT NULL,
          text_hash TEXT NOT NULL
        );
        CREATE VIRTUAL TABLE precedents_fts USING fts5(
          canonical_id UNINDEXED,
          full_text,
          tokenize='unicode61'
        );
        INSERT INTO precedents VALUES
          ('doc-wali-hanafi','islam/sunni/hanafi/fiqh','fiqh/hanafi/wali','Hanafi discussion of wali','Fiqh: wali','Hanafi fiqh','','nikah wali','fiqh_school_bundle','[META]
religion: islam
tradition: sunni
school: hanafi
authority_level: 82
source_kind: fiqh
authority_label: madhhab fiqh

ولي النكاح guardian nikah marriage contract consent. Hanafi school discussion mentions wali and marriage contract conditions.','hash-wali'),
          ('doc-wali-shafii','islam/sunni/shafii/fiqh','fiqh/shafii/wali','Shafi''i discussion of wali','Fiqh: wali','Shafi''i fiqh','','nikah wali','fiqh_school_bundle','[META]
religion: islam
tradition: sunni
school: shafii
authority_level: 82
source_kind: fiqh
authority_label: madhhab fiqh

الولي في النكاح guardian nikah marriage. Shafi''i school discussion treats wali as part of marriage validity conditions.','hash-shafii'),
          ('doc-prayer','islam/all//scripture','quran/prayer','Quran prayer','Quran 2:144','Qur''an','','qibla','scripture_window','[META]
religion: islam
tradition: all
school:
authority_level: 100
source_kind: scripture

qibla prayer direction المسجد الحرام قبلة صلاة','hash-prayer');
        INSERT INTO precedents_fts(canonical_id, full_text)
          SELECT canonical_id, full_text FROM precedents;
        """
    )
    conn.commit()
    conn.close()


def _make_islam_prayer_count_db(path):
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE precedents (
          canonical_id TEXT PRIMARY KEY,
          source_dataset TEXT,
          source_path TEXT,
          title TEXT,
          case_number TEXT,
          court TEXT,
          decision_date TEXT,
          case_name TEXT,
          case_type TEXT,
          full_text TEXT NOT NULL,
          text_hash TEXT NOT NULL
        );
        CREATE VIRTUAL TABLE precedents_fts USING fts5(
          canonical_id UNINDEXED,
          full_text,
          tokenize='unicode61'
        );
        INSERT INTO precedents VALUES
          ('doc-day-count','islam/all//scripture','quran/day','Day count verse','Quran day','Qur''an','','how long stayed','scripture_window','[META]
religion: islam
tradition: all
authority_level: 100
source_kind: scripture

하루 몇번 얼마나 머물렀는가 خَمْسِينَ day count stayed without prayer topic.','hash-day'),
          ('doc-prayer-times','islam/all//scripture','quran/prayer','Prayer times verse','Quran prayer','Qur''an','','daily prayer times','scripture_window','[META]
religion: islam
tradition: all
authority_level: 100
source_kind: scripture

prayer salah salat صلاة الصلوة five daily prayers fixed prayer times.','hash-prayer');
        INSERT INTO precedents_fts(canonical_id, full_text)
          SELECT canonical_id, full_text FROM precedents;
        """
    )
    conn.commit()
    conn.close()


def _make_tcm_domain_db(path):
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE precedents (
          canonical_id TEXT PRIMARY KEY,
          source_dataset TEXT,
          source_path TEXT,
          title TEXT,
          case_number TEXT,
          court TEXT,
          decision_date TEXT,
          case_name TEXT,
          case_type TEXT,
          full_text TEXT NOT NULL,
          text_hash TEXT NOT NULL
        );
        CREATE VIRTUAL TABLE precedents_fts USING fts5(
          canonical_id UNINDEXED,
          full_text,
          tokenize='unicode61'
        );
        INSERT INTO precedents VALUES
          ('doc-gamcho-classic','tcm-kmm/kmm/korean-classic/classic_canon','donguibogam/gamcho','東醫寶鑑 (Dongui Bogam, 1613)','Dongui Bogam #甘草','Dongui Bogam','','甘草 classic entry','classic_canon_unit','[META]
religion: tcm-kmm
tradition: kmm
school: korean-classic
authority_level: 100
source_kind: classic_canon
authority_label: classic canon

甘草 감초 licorice 조화제약 諸藥을 조화시키는 본초 고문헌 근거.','hash-gamcho-classic'),
          ('doc-gamcho-low','tcm-kmm/tcm/tcm-clinical/case_record','cases/gamcho','Modern case note','Case #甘草','case collection','','甘草 repeated note','case_record_unit','[META]
religion: tcm-kmm
tradition: tcm
school: tcm-clinical
authority_level: 50
source_kind: case_record
authority_label: case record

감초 감초 감초 감초 감초 repeated modern note without canon context.','hash-gamcho-low'),
          ('doc-pregnancy-contra','tcm-kmm/kmm/bencao/materia_medica','bencao/contra','本草 금기','Bencao #禁忌','materia medica','','pregnancy contraindication','materia_medica_unit','[META]
religion: tcm-kmm
tradition: kmm
school: bencao
authority_level: 84
source_kind: materia_medica
authority_label: materia medica

妊娠 pregnancy 임신 禁忌 contraindication 금기 본초 약재 안전 확인.','hash-contra'),
          ('doc-insomnia-pattern','tcm-kmm/kmm/korean-classic/classic_authoritative','classic/insomnia','불면 변증 고전','Classic #失眠','classic text','','insomnia pattern','classic_authoritative_unit','[META]
religion: tcm-kmm
tradition: kmm
school: korean-classic
authority_level: 90
source_kind: classic_authoritative
authority_label: authoritative classic

失眠 불면 不眠 심신불교 心腎不交 변증 pattern differentiation.','hash-insomnia');
        INSERT INTO precedents_fts(canonical_id, full_text)
          SELECT canonical_id, full_text FROM precedents;
        """
    )
    conn.commit()
    conn.close()


def _make_tcm_passage_graph_db(path):
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE precedents (
          canonical_id TEXT PRIMARY KEY,
          source_dataset TEXT,
          source_path TEXT,
          title TEXT,
          case_number TEXT,
          court TEXT,
          decision_date TEXT,
          case_name TEXT,
          case_type TEXT,
          full_text TEXT NOT NULL,
          text_hash TEXT NOT NULL
        );
        CREATE VIRTUAL TABLE precedents_fts USING fts5(
          canonical_id UNINDEXED,
          full_text,
          tokenize='unicode61'
        );
        CREATE TABLE sources (
          source_id TEXT PRIMARY KEY,
          religion TEXT NOT NULL,
          tradition TEXT NOT NULL DEFAULT '',
          school TEXT NOT NULL DEFAULT '',
          source_kind TEXT NOT NULL,
          authority_level INTEGER NOT NULL,
          authority_label TEXT NOT NULL,
          title TEXT NOT NULL,
          subtitle TEXT NOT NULL DEFAULT '',
          author_body TEXT NOT NULL DEFAULT '',
          edition TEXT NOT NULL DEFAULT '',
          language TEXT NOT NULL,
          script TEXT NOT NULL DEFAULT '',
          source_url TEXT NOT NULL DEFAULT '',
          license TEXT NOT NULL DEFAULT '',
          license_notes TEXT NOT NULL DEFAULT '',
          valid_from TEXT NOT NULL DEFAULT '',
          valid_to TEXT NOT NULL DEFAULT '',
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE passages (
          passage_id TEXT PRIMARY KEY,
          source_id TEXT NOT NULL,
          canonical_ref TEXT NOT NULL,
          parent_ref TEXT NOT NULL DEFAULT '',
          ref_sort INTEGER NOT NULL DEFAULT 0,
          language TEXT NOT NULL,
          script TEXT NOT NULL DEFAULT '',
          text TEXT NOT NULL,
          normalized_text TEXT NOT NULL,
          heading TEXT NOT NULL DEFAULT '',
          tags_json TEXT NOT NULL DEFAULT '[]',
          text_hash TEXT NOT NULL
        );
        INSERT INTO sources (
          source_id, religion, tradition, school, source_kind, authority_level,
          authority_label, title, author_body, language
        ) VALUES (
          'tcm.demo.classic', 'tcm-kmm', 'kmm', 'korean-classic', 'classic_canon',
          100, 'classic canon', 'Demo Classic', 'Demo', 'ko'
        );
        INSERT INTO passages VALUES
          ('tcm.demo.0001','tcm.demo.classic','Demo 1','Demo Classic',1,'ko','','인접 원문: 밤에 편안히 눕지 못하고 마음이 안정되지 않는다.','인접 원문','수면 원문','[]','hash-p1'),
          ('tcm.demo.0002','tcm.demo.classic','Demo 2','Demo Classic',2,'ko','','불면 침 치료 근거를 설명하는 검색 seed 문단.','불면 침 치료 근거','검색 seed','[]','hash-p2'),
          ('tcm.demo.0003','tcm.demo.classic','Demo 3','Demo Classic',3,'ko','','멀리 가지 않는 후속 설명.','후속 설명','후속','[]','hash-p3');
        INSERT INTO precedents VALUES
          ('doc.tcm.demo.0001','tcm-kmm/kmm/korean-classic/classic_canon','tcm.demo.classic','Demo Classic','Demo 1','Demo','','수면 원문','classic_canon_unit','[META]
religion: tcm-kmm
tradition: kmm
school: korean-classic
authority_level: 100
source_kind: classic_canon
authority_label: classic canon

인접 원문: 밤에 편안히 눕지 못하고 마음이 안정되지 않는다.','hash-p1'),
          ('doc.tcm.demo.0002','tcm-kmm/kmm/korean-classic/classic_canon','tcm.demo.classic','Demo Classic','Demo 2','Demo','','검색 seed','classic_canon_unit','[META]
religion: tcm-kmm
tradition: kmm
school: korean-classic
authority_level: 100
source_kind: classic_canon
authority_label: classic canon

불면 침 치료 근거를 설명하는 검색 seed 문단.','hash-p2'),
          ('doc.tcm.demo.0003','tcm-kmm/kmm/korean-classic/classic_canon','tcm.demo.classic','Demo Classic','Demo 3','Demo','','후속','classic_canon_unit','[META]
religion: tcm-kmm
tradition: kmm
school: korean-classic
authority_level: 100
source_kind: classic_canon
authority_label: classic canon

멀리 가지 않는 후속 설명.','hash-p3');
        INSERT INTO precedents_fts(canonical_id, full_text)
          SELECT canonical_id, full_text FROM precedents;
        """
    )
    conn.commit()
    conn.close()


def _make_documents_db(path):
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE documents (
          canonical_id TEXT PRIMARY KEY,
          source_dataset TEXT NOT NULL,
          source_path TEXT,
          source_url TEXT,
          doc_type TEXT,
          title TEXT,
          topic TEXT,
          disorder TEXT,
          author TEXT,
          journal TEXT,
          pub_date TEXT,
          language TEXT,
          question TEXT,
          answer TEXT,
          body TEXT,
          full_text TEXT NOT NULL,
          text_hash TEXT,
          license TEXT,
          extra_json TEXT
        );
        CREATE VIRTUAL TABLE documents_fts USING fts5(
          title, question, answer, body, topic, disorder,
          content='documents', content_rowid='rowid',
          tokenize='unicode61'
        );
        INSERT INTO documents VALUES
          ('doc-psych-1','who:icd11','icd/anxiety','https://example.test','guideline','Anxiety overview','anxiety','anxiety','','WHO','2024','en','','','Anxiety symptoms, panic, worry and functional impairment.','Anxiety symptoms, panic, worry and functional impairment.','hash1','WHO','{}'),
          ('doc-psych-1b','who:icd11','icd/panic-b','https://example.test','guideline','Panic criteria B','panic','panic','','WHO','2024','en','','','Panic worry CBT safety signal impairment.','Panic worry CBT safety signal impairment.','hash1b','WHO','{}'),
          ('doc-psych-1c','who:icd11','icd/panic-c','https://example.test','guideline','Panic criteria C','panic','panic','','WHO','2024','en','','','Panic worry CBT breathing fear symptoms.','Panic worry CBT breathing fear symptoms.','hash1c','WHO','{}'),
          ('doc-psych-2','pmc:psychiatry','pmc/sleep','https://example.test','paper','Sleep and mood','sleep','depression','','PMC','2024','en','','','Sleep disruption, insomnia and mood symptoms.','Sleep disruption, insomnia and mood symptoms.','hash2','OA','{}'),
          ('doc-psych-3','s2:psych','s2/panic','https://example.test','research_paper','Panic CBT review','panic cbt','panic','','S2','2024','en','','','Panic worry CBT breathing exposure and safety assessment.','Panic worry CBT breathing exposure and safety assessment.','hash4','OA','{}'),
          ('doc-psych-low','hf:psychocounsel_pref','hf/chat','https://example.test','counseling_preference','Many chat snippets','sleep anxiety','anxiety','','HF','2024','en','','','insomnia anxiety panic worry insomnia anxiety panic worry counseling preference chat.','insomnia anxiety panic worry insomnia anxiety panic worry counseling preference chat.','hash3','HF','{}');
        INSERT INTO documents_fts(rowid, title, question, answer, body, topic, disorder)
          SELECT rowid, title, question, answer, body, topic, disorder FROM documents;
        """
    )
    conn.commit()
    conn.close()


def _make_simli_role_only_documents_db(path):
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE documents (
          canonical_id TEXT PRIMARY KEY,
          source_dataset TEXT NOT NULL,
          source_path TEXT,
          source_url TEXT,
          doc_type TEXT,
          title TEXT,
          topic TEXT,
          disorder TEXT,
          author TEXT,
          journal TEXT,
          pub_date TEXT,
          language TEXT,
          question TEXT,
          answer TEXT,
          body TEXT,
          full_text TEXT NOT NULL,
          text_hash TEXT,
          license TEXT,
          extra_json TEXT
        );
        CREATE INDEX idx_documents_type ON documents(doc_type);
        CREATE INDEX idx_documents_lang ON documents(language);
        INSERT INTO documents VALUES
          ('doc-dsm-adhd','apa:dsm5','dsm/adhd','https://example.test','dsm5_chunk','DSM-5 ADHD criteria','adhd','adhd','','APA','2013','en','','','ADHD attention hyperactivity anxiety differential diagnosis.','ADHD attention hyperactivity anxiety differential diagnosis.','hash-dsm','APA','{}'),
          ('doc-dsm-mdd','apa:dsm5','dsm/mdd','https://example.test','dsm5_chunk','DSM-5 MDD criteria','depression','depression','','APA','2013','en','','','Major depressive disorder criteria.','Major depressive disorder criteria.','hash-dsm2','APA','{}'),
          ('doc-guideline-adhd','guidelines:clinical','nice/adhd','https://example.test','guideline_chunk','NICE ADHD guideline','nice_adhd_ng87','adhd','','NICE','2024','en','','','ADHD medication review anxiety risk signs and referral guidance.','ADHD medication review anxiety risk signs and referral guidance.','hash-guideline','NICE','{}'),
          ('doc-paper-noise','pmc:psychiatry','pmc/noise','https://example.test','research_paper','DSM-5 mentioned in passing','noise','noise','','PMC','2024','en','','','DSM-5 DSM-5 DSM-5 generic paper noise.','DSM-5 DSM-5 DSM-5 generic paper noise.','hash-paper','OA','{}');
        """
    )
    conn.commit()
    conn.close()


def test_simli_source_role_query_uses_filtered_role_rows_without_generic_fts(tmp_path):
    db_path = tmp_path / "psych-role.sqlite3"
    _make_simli_role_only_documents_db(db_path)

    rows = search_mod._search_documents(
        db_path,
        "ADHD anxiety DSM-5",
        limit=4,
        language="en",
        product_key="simli",
    )

    assert [row.canonical_id for row in rows] == ["doc-dsm-adhd"]
    assert {row.source_kind for row in rows} == {"dsm5_chunk"}


def test_simli_clinical_guideline_role_query_uses_guideline_rows_without_generic_fts(tmp_path):
    db_path = tmp_path / "psych-guideline-role.sqlite3"
    _make_simli_role_only_documents_db(db_path)

    rows = search_mod._search_documents(
        db_path,
        "ADHD anxiety clinical guideline",
        limit=4,
        language="en",
        product_key="simli",
    )

    assert [row.canonical_id for row in rows] == ["doc-guideline-adhd"]
    assert {row.source_kind for row in rows} == {"guideline_chunk"}


def test_simli_answer_language_does_not_filter_english_source_corpus(tmp_path):
    db_path = tmp_path / "psych.sqlite3"
    _make_documents_db(db_path)

    rows = search_mod._search_documents(
        db_path,
        "panic CBT",
        limit=3,
        language="ko",
        product_key="simli",
    )

    assert rows
    assert {row.language for row in rows} == {"en"}
    assert any(row.canonical_id == "doc-psych-3" for row in rows)


def test_precedents_adapter_returns_beta6_compatible_rows(tmp_path):
    db_path = tmp_path / "religion.sqlite3"
    _make_precedents_db(db_path)
    profile = ProductProfile(
        key="islam",
        name="Islam AI",
        db_path=db_path,
        db_shape="precedents",
        languages=("en",),
        default_language="en",
        theme="islam",
        safety_notice="notice",
    )

    rows = search_documents(profile, "qibla prayer", limit=3)

    assert rows[0].canonical_id == "doc-fiqh-1"
    selected = to_beta6_selected_record(rows[0])
    assert selected["file_id"] == "doc-fiqh-1"
    assert selected["extracted_text"].startswith("Prayer time")
    assert selected["case_number"] == "Prayer"
    assert selected["source_group"] == "structured_precedent"


def test_islam_daily_prayer_query_drops_count_words_before_ranking(tmp_path):
    db_path = tmp_path / "islam-prayer-count.sqlite3"
    _make_islam_prayer_count_db(db_path)
    profile = ProductProfile(
        key="islam",
        name="Islam AI",
        db_path=db_path,
        db_shape="precedents",
        languages=("ko", "en", "ar"),
        default_language="ko",
        theme="islam",
        safety_notice="notice",
    )

    expansion = describe_query_expansion(profile, "하루 몇번 기도해야함 꾸란 하디스 근거")
    rows = search_documents(profile, "하루 몇번 기도해야함 꾸란 하디스 근거", limit=2)

    assert "하루" not in expansion["surfaceTerms"]
    assert "몇번" not in expansion["surfaceTerms"]
    assert "خمس" not in expansion["expandedTerms"]
    assert "five" not in expansion["expandedTerms"]
    assert rows[0].canonical_id == "doc-prayer-times"
    assert rows[1].canonical_id == "doc-day-count"


def test_documents_adapter_supports_simli_schema(tmp_path):
    db_path = tmp_path / "psych.sqlite3"
    _make_documents_db(db_path)
    profile = ProductProfile(
        key="simli",
        name="Mental Health AI",
        db_path=db_path,
        db_shape="documents",
        languages=("ko", "en"),
        default_language="ko",
        theme="simli",
        safety_notice="notice",
    )

    rows = search_documents(profile, "panic worry", limit=3)

    assert rows[0].canonical_id in {"doc-psych-1", "doc-psych-1b"}
    selected = to_beta6_selected_record(rows[0])
    assert selected["file_id"] in {"doc-psych-1", "doc-psych-1b"}
    assert selected["case_name"] in {"anxiety", "panic"}
    assert "panic" in selected["extracted_text"].lower()


def test_documents_adapter_expands_common_korean_mental_health_terms(tmp_path):
    db_path = tmp_path / "psych.sqlite3"
    _make_documents_db(db_path)
    profile = ProductProfile(
        key="simli",
        name="Mental Health AI",
        db_path=db_path,
        db_shape="documents",
        languages=("ko", "en"),
        default_language="ko",
        theme="simli",
        safety_notice="notice",
    )

    rows = search_documents(profile, "수면 문제와 우울감", limit=3, language="ko")

    assert rows
    assert rows[0].canonical_id == "doc-psych-2"


def test_simli_documents_adapter_excludes_low_confidence_chat_evidence_by_default(tmp_path):
    db_path = tmp_path / "psych.sqlite3"
    _make_documents_db(db_path)
    profile = ProductProfile(
        key="simli",
        name="Mental Health AI",
        db_path=db_path,
        db_shape="documents",
        languages=("ko", "en"),
        default_language="ko",
        theme="simli",
        safety_notice="notice",
    )

    rows = search_documents(profile, "불면 불안 공황", limit=5, language="ko")

    assert rows
    assert "doc-psych-low" not in {row.canonical_id for row in rows}
    assert rows[0].source_dataset in {"who:icd11", "pmc:psychiatry"}
    assert rows[0].case_type in {"guideline", "paper"}


def test_simli_documents_adapter_keeps_authoritative_source_diversity(tmp_path):
    db_path = tmp_path / "psych.sqlite3"
    _make_documents_db(db_path)
    profile = ProductProfile(
        key="simli",
        name="Mental Health AI",
        db_path=db_path,
        db_shape="documents",
        languages=("ko", "en"),
        default_language="ko",
        theme="simli",
        safety_notice="notice",
    )

    rows = search_documents(profile, "panic worry CBT", limit=3, language="en")

    datasets = {row.source_dataset for row in rows}
    assert len(datasets) >= 2
    assert "hf:psychocounsel_pref" not in datasets


def test_simli_lawkey_sized_top_k_does_not_fetch_huge_raw_fulltext_pool(monkeypatch, tmp_path):
    db_path = tmp_path / "psych.sqlite3"
    db_path.touch()
    captured_limits = []

    monkeypatch.setattr(search_mod, "_connect_readonly", lambda _path: nullcontext(object()))
    monkeypatch.setattr(search_mod, "_search_simli_authoritative_rows_by_rowid_range", lambda *args, **kwargs: [])

    def fake_fetch(_conn, sql, params):
        if "JOIN documents d" in sql:
            captured_limits.append(params[-1])
        return []

    monkeypatch.setattr(search_mod, "_fetchall_with_deadline", fake_fetch)

    rows = search_mod._search_documents(
        db_path,
        "insomnia anxiety",
        fts='"insomnia" OR "anxiety"',
        limit=100,
        language="ko",
        product_key="simli",
    )

    assert rows == []
    assert captured_limits
    assert captured_limits[0] <= 1200


def test_simli_beta6_repeated_keyword_search_uses_tight_inner_fetch_caps(monkeypatch, tmp_path):
    db_path = tmp_path / "psych.sqlite3"
    db_path.touch()
    captured_fts_limits = []
    captured_authoritative_limits = []

    monkeypatch.setattr(search_mod, "_connect_readonly", lambda _path: nullcontext(object()))

    def fake_authoritative(_conn, _fts, *, language="", limit=0, db_key=""):
        captured_authoritative_limits.append(limit)
        return []

    def fake_fetch(_conn, sql, params):
        if "JOIN documents d" in sql:
            captured_fts_limits.append(params[-1])
        return []

    monkeypatch.setattr(search_mod, "_search_simli_authoritative_rows_by_rowid_range", fake_authoritative)
    monkeypatch.setattr(search_mod, "_fetchall_with_deadline", fake_fetch)

    rows = search_mod._search_documents(
        db_path,
        "insomnia anxiety CBT",
        fts='"insomnia" OR "anxiety" OR "CBT"',
        limit=100,
        language="ko",
        product_key="simli",
    )

    assert rows == []
    assert captured_fts_limits and captured_fts_limits[0] <= 500
    assert captured_authoritative_limits and captured_authoritative_limits[0] <= 500


def test_simli_skips_authoritative_range_when_main_fts_has_enough_default_evidence(monkeypatch, tmp_path):
    db_path = tmp_path / "psych.sqlite3"
    db_path.touch()
    authoritative_calls = []
    rows = [
        {
            "canonical_id": f"doc-{index}",
            "source_dataset": "who:icd11" if index % 2 else "pmc:psychiatry",
            "source_path": f"path-{index}",
            "source_url": "",
            "doc_type": "guideline" if index % 2 else "paper",
            "title": f"evidence {index}",
            "topic": "insomnia anxiety",
            "disorder": "anxiety",
            "pub_date": "",
            "language": "ko",
            "full_text": "insomnia anxiety CBT evidence",
        }
        for index in range(30)
    ]

    monkeypatch.setattr(search_mod, "_connect_readonly", lambda _path: nullcontext(object()))
    monkeypatch.setattr(search_mod, "_fetchall_with_deadline", lambda _conn, _sql, _params: rows)

    def fake_authoritative(*args, **kwargs):
        authoritative_calls.append(kwargs)
        return []

    monkeypatch.setattr(search_mod, "_search_simli_authoritative_rows_by_rowid_range", fake_authoritative)

    result = search_mod._search_documents(
        db_path,
        "insomnia anxiety CBT",
        fts='"insomnia" OR "anxiety" OR "CBT"',
        limit=20,
        language="ko",
        product_key="simli",
    )

    assert len(result) == 20
    assert authoritative_calls == []


def test_simli_authoritative_rowid_range_has_total_time_budget(monkeypatch):
    ranges = [(f"dataset-{index}", index * 10, (index * 10) + 9) for index in range(10)]
    calls = []
    clock = {"value": 0.0}

    def fake_monotonic():
        clock["value"] += 0.04
        return clock["value"]

    def fake_fetch(_conn, _sql, params):
        calls.append(tuple(params))
        return []

    monkeypatch.setenv("RELIGION_SIMLI_AUTHORITATIVE_RANGE_BUDGET_SECONDS", "0.05")
    monkeypatch.setattr(search_mod.time, "monotonic", fake_monotonic)
    monkeypatch.setattr(search_mod, "_simli_authoritative_rowid_ranges", lambda _conn, *, db_key: ranges)
    monkeypatch.setattr(search_mod, "_fetchall_with_deadline", fake_fetch)

    rows = search_mod._search_simli_authoritative_rows_by_rowid_range(
        object(),
        '"depression"',
        language="ko",
        limit=100,
        db_key="psych.sqlite3",
    )

    assert rows == []
    assert 0 < len(calls) < len(ranges)


def test_simli_authoritative_range_budget_default_is_tight_for_beta6_keyword_scans(monkeypatch):
    monkeypatch.delenv("RELIGION_SIMLI_AUTHORITATIVE_RANGE_BUDGET_SECONDS", raising=False)

    assert search_mod._simli_authoritative_range_budget_seconds() == 0.3


def test_simli_role_hint_rows_are_capped_below_beta6_per_keyword_limit(monkeypatch):
    monkeypatch.delenv("RELIGION_SIMLI_ROLE_HINT_LIMIT_MAX", raising=False)

    assert search_mod._simli_role_hint_result_limit(700) == 24
    assert search_mod._simli_role_hint_result_limit(20) == 20


def test_precedents_adapter_prefers_higher_authority_when_relevance_is_close(tmp_path):
    db_path = tmp_path / "authority.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE precedents (
          canonical_id TEXT PRIMARY KEY,
          source_dataset TEXT,
          source_path TEXT,
          title TEXT,
          case_number TEXT,
          court TEXT,
          decision_date TEXT,
          case_name TEXT,
          case_type TEXT,
          full_text TEXT NOT NULL,
          text_hash TEXT NOT NULL
        );
        CREATE VIRTUAL TABLE precedents_fts USING fts5(
          canonical_id UNINDEXED,
          full_text,
          tokenize='unicode61'
        );
        INSERT INTO precedents VALUES
          ('doc-low','islam/forum','low','Low authority note','Low','forum','','low','note','[META] authority_level: 10 qibla qibla qibla qibla qibla qibla qibla qibla','hash1'),
          ('doc-high','islam/all/scripture','high','High authority source','High','scripture','','high','scripture_window','[META] authority_level: 100 qibla','hash2');
        INSERT INTO precedents_fts(canonical_id, full_text)
          SELECT canonical_id, full_text FROM precedents;
        """
    )
    conn.commit()
    conn.close()
    profile = ProductProfile(
        key="islam",
        name="Islam AI",
        db_path=db_path,
        db_shape="precedents",
        languages=("en",),
        default_language="en",
        theme="islam",
        safety_notice="notice",
    )

    rows = search_documents(profile, "qibla", limit=2)

    assert rows[0].canonical_id == "doc-high"


def test_catholic_search_expands_exact_bible_reference_to_citation_row(tmp_path):
    db_path = tmp_path / "catholic.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE precedents (
          canonical_id TEXT PRIMARY KEY,
          source_dataset TEXT,
          source_path TEXT,
          title TEXT,
          case_number TEXT,
          court TEXT,
          decision_date TEXT,
          case_name TEXT,
          case_type TEXT,
          full_text TEXT NOT NULL,
          text_hash TEXT NOT NULL
        );
        CREATE VIRTUAL TABLE precedents_fts USING fts5(
          canonical_id UNINDEXED,
          full_text,
          tokenize='unicode61'
        );
        INSERT INTO precedents VALUES
          ('doc-gen-42-21','catholic/latin//scripture','vulgate/genesis','Clementine Vulgate','Gen 42:21','','','Genesis','scripture_window','[META]
authority_level: 100
source_kind: scripture
Joseph brothers recognized their sin concerning their brother Joseph.','hash1'),
          ('doc-gen-42-20','catholic/latin//scripture','vulgate/genesis','Clementine Vulgate','Gen 42:20','','','Genesis','scripture_window','[META]
authority_level: 100
source_kind: scripture
Bring your youngest brother to me.','hash-prev'),
          ('doc-gen-42-6','catholic/latin//scripture','vulgate/genesis','Clementine Vulgate','Gen 42:6','','','Genesis','scripture_window','[META]
authority_level: 100
source_kind: scripture
Joseph was governor over Egypt and his brothers bowed before him.','hash-context'),
          ('doc-vatican','catholic/all/vatican-ii/official_doctrine','vatican','Vatican text','Council 1','','','Council','official_doctrine_unit','Genesis 42 and 21 appear as unrelated numeric tokens.','hash2');
        INSERT INTO precedents_fts(canonical_id, full_text)
          SELECT canonical_id, full_text FROM precedents;
        """
    )
    conn.commit()
    conn.close()
    product = ProductProfile(
        key="catholic",
        name="Catholic Test",
        db_path=db_path,
        db_shape="precedents",
        languages=("ko", "en"),
        default_language="ko",
        theme="",
        safety_notice="test",
    )

    assert search_documents(product, "Gen 42:21", limit=3)[0].canonical_id == "doc-gen-42-21"
    assert search_documents(product, "창 42:21", limit=3)[0].canonical_id == "doc-gen-42-21"
    contextual_rows = search_documents(
        product,
        "창 42:21 아우가 누구인가?\n\n① 레위\n② 베냐민\n③ 르우벤\n④ 요셉",
        limit=3,
    )
    assert [row.canonical_id for row in contextual_rows[:2]] == ["doc-gen-42-21", "doc-gen-42-6"]


def test_catholic_search_expands_public_mcq_citation_options_with_stem_book(tmp_path):
    db_path = tmp_path / "catholic.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE precedents (
          canonical_id TEXT PRIMARY KEY,
          source_dataset TEXT,
          source_path TEXT,
          title TEXT,
          case_number TEXT,
          court TEXT,
          decision_date TEXT,
          case_name TEXT,
          case_type TEXT,
          full_text TEXT NOT NULL,
          text_hash TEXT NOT NULL
        );
        CREATE VIRTUAL TABLE precedents_fts USING fts5(
          canonical_id UNINDEXED,
          full_text,
          tokenize='unicode61'
        );
        INSERT INTO precedents VALUES
          ('doc-exod-15-21','catholic/korean//scripture','korrv/exodus','Korean Revised Version','Exod 15:21','','','Exodus','scripture_window','[META]
authority_level: 90
source_kind: scripture
미리암이 그들에게 화답하여 가로되 너희는 여호와를 찬송하라 그는 높고 영화로우심이요 말과 그 탄 자를 바다에 던지셨음이로다','hash-target'),
          ('doc-exod-14-31','catholic/korean//scripture','korrv/exodus','Korean Revised Version','Exod 14:31','','','Exodus','scripture_window','[META]
authority_level: 90
source_kind: scripture
이스라엘이 여호와께서 애굽 사람들에게 베푸신 큰 일을 보았으므로','hash-other'),
          ('doc-doctrine','catholic/all/vatican-ii/official_doctrine','vatican','Doctrine','Council 1','','','Council','official_doctrine_unit','출애굽기와 찬송이라는 말이 있지만 특정 성경 citation은 아니다.','hash-doctrine');
        INSERT INTO precedents_fts(canonical_id, full_text)
          SELECT canonical_id, full_text FROM precedents;
        """
    )
    conn.commit()
    conn.close()
    product = ProductProfile(
        key="catholic",
        name="Catholic Test",
        db_path=db_path,
        db_shape="precedents",
        languages=("ko", "en"),
        default_language="ko",
        theme="",
        safety_notice="test",
    )

    rows = search_documents(
        product,
        "다음 본문은 출애굽기 어디에 기록되어 있는가? “너희는 여호와를 찬송하라 그는 높고 영화로우심이요 말과 그 탄 자를 바다에 던지셨음이로다”\n\n① 13:1-2\n② 14:31\n③ 15:21\n④ 40:35",
        limit=5,
    )

    assert rows[0].canonical_id == "doc-exod-15-21"


def test_catholic_beta6_search_plan_keeps_later_public_citation_options():
    product = ProductProfile(
        key="catholic",
        name="Catholic Test",
        db_path=Path("unused.sqlite3"),
        db_shape="precedents",
        languages=("ko", "en"),
        default_language="ko",
        theme="",
        safety_notice="test",
    )
    query = (
        "다음 본문은 출애굽기 어디에 기록되어 있는가? "
        "“너희는 여호와를 찬송하라 그는 높고 영화로우심이요 말과 그 탄 자를 바다에 던지셨음이로다”\n\n"
        "① 13:1-2\n② 14:31\n③ 15:21\n④ 40:35"
    )

    plan = build_beta6_candidate_search_plan(
        product,
        query,
        ["Exodus", "Exod", "Ex 15:1", "Ex 15:11", "Song of Moses"],
        target_limit=30,
        per_keyword_limit=10,
    )
    queries = [item[1] for item in plan]

    assert any("Exod 15:21" in query_text for query_text in queries)
    assert any(query_text == "Exod 15:21" for query_text in queries)
    exact_index = queries.index("Exod 15:21")
    broad_indices = [
        index
        for index, query_text in enumerate(queries)
        if "다음 본문은 출애굽기" in query_text and not re.search(r"\bExod\s+\d{1,3}:\d{1,3}\b", query_text)
    ]
    assert broad_indices
    assert exact_index < min(broad_indices)


def test_catholic_beta6_search_plan_expands_korean_bible_abbreviations():
    product = ProductProfile(
        key="catholic",
        name="Catholic Test",
        db_path=Path("unused.sqlite3"),
        db_shape="precedents",
        languages=("ko", "en"),
        default_language="ko",
        theme="",
        safety_notice="test",
    )
    eccl_query = (
        "“사람마다 먹고 마시는 것과 수고함으로 낙을 누리는 그것이 하나님의 ( )인 줄도 "
        "또한 알았도다”(전 3:13)에서 괄호 안에 들어갈 말은?\n\n"
        "① 선물\n② 은혜\n③ 행사\n④ 수고"
    )
    ruth_query = "엘리멜렉과 나오미의 아들이자 룻의 남편은 누구인가(룻4:10)?\n\n① 말론\n② 기룐"
    samuel_query = "사울과 아말렉의 전쟁이 기록된 것은 사무엘 상 몇 장인가?\n\n① 14장\n② 15장"

    eccl_plan = build_beta6_candidate_search_plan(product, eccl_query, [], target_limit=30, per_keyword_limit=30)
    ruth_plan = build_beta6_candidate_search_plan(product, ruth_query, [], target_limit=30, per_keyword_limit=30)
    samuel_plan = build_beta6_candidate_search_plan(product, samuel_query, [], target_limit=30, per_keyword_limit=30)

    assert any(search_query == "Eccl 3:13" for _label, search_query, _limit in eccl_plan)
    assert any("Ruth 4:10" in search_query for _label, search_query, _limit in ruth_plan)
    assert any(search_query == "1Sam 15:1" for _label, search_query, _limit in samuel_plan)


def test_catholic_beta6_search_plan_prioritizes_public_chapter_citations_before_entity_buckets():
    product = ProductProfile(
        key="catholic",
        name="Catholic Test",
        db_path=Path("unused.sqlite3"),
        db_shape="precedents",
        languages=("ko", "en"),
        default_language="ko",
        theme="",
        safety_notice="test",
    )
    query = (
        "“너희의 하나님이 이르시되 너희는 위로하라 내 백성의 위로하라”는 "
        "이사야 몇 장에 나오는 말씀인가?\n\n"
        "① 40장\n② 41장\n③ 55장\n④ 56장"
    )

    plan = build_beta6_candidate_search_plan(product, query, [], target_limit=30, per_keyword_limit=30)
    queries = [search_query for _label, search_query, _limit in plan]

    assert "Isa 40:1" in queries
    broad_index = min(index for index, search_query in enumerate(queries) if search_query.startswith("40장 41장"))
    assert queries.index("Isa 40:1") < broad_index
    assert next(limit for _label, search_query, limit in plan if search_query == "Isa 40:1") >= 120


def test_catholic_beta6_candidate_collection_uses_stem_chapter_seed_for_day_options(tmp_path):
    db_path = tmp_path / "catholic.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE precedents (
          canonical_id TEXT PRIMARY KEY,
          source_dataset TEXT,
          source_path TEXT,
          title TEXT,
          case_number TEXT,
          court TEXT,
          decision_date TEXT,
          case_name TEXT,
          case_type TEXT,
          full_text TEXT NOT NULL,
          text_hash TEXT NOT NULL
        );
        CREATE VIRTUAL TABLE precedents_fts USING fts5(
          canonical_id UNINDEXED,
          full_text,
          tokenize='unicode61'
        );
        INSERT INTO precedents VALUES
          ('doc-noise-01','catholic/all/vatican-ii/official_doctrine','noise/01','Noise 1','Noise 1','','','Noise','official_doctrine_unit','둘째 날 셋째 날 넷째 날 다섯째 날 창조되었는 broad noise 1','hash-n1'),
          ('doc-noise-02','catholic/all/vatican-ii/official_doctrine','noise/02','Noise 2','Noise 2','','','Noise','official_doctrine_unit','둘째 날 셋째 날 넷째 날 다섯째 날 창조되었는 broad noise 2','hash-n2'),
          ('doc-noise-03','catholic/all/vatican-ii/official_doctrine','noise/03','Noise 3','Noise 3','','','Noise','official_doctrine_unit','둘째 날 셋째 날 넷째 날 다섯째 날 창조되었는 broad noise 3','hash-n3'),
          ('doc-gen-1-1','catholic/korean//scripture','korrv/genesis','Korean Revised Version','Gen 1:1','','','Genesis','scripture_window','[META]
authority_level: 90
source_kind: scripture
citation: Gen 1:1
태초에 하나님이 천지를 창조하시니라','hash-seed'),
          ('doc-gen-1-19','catholic/korean//scripture','korrv/genesis','Korean Revised Version','Gen 1:19','','','Genesis','scripture_window','[META]
authority_level: 90
source_kind: scripture
citation: Gen 1:19
저녁이 되며 아침이 되니 이는 넷째 날이니라 광명체가 하늘의 궁창에 있었다','hash-target');
        INSERT INTO precedents_fts(canonical_id, full_text)
          SELECT canonical_id, full_text FROM precedents;
        """
    )
    conn.commit()
    conn.close()
    product = ProductProfile(
        key="catholic",
        name="Catholic Test",
        db_path=db_path,
        db_shape="precedents",
        languages=("ko", "en"),
        default_language="ko",
        theme="",
        safety_notice="test",
    )
    query = (
        "창세기 1장의 천지창조 일정 가운데 광명체들은 몇째 날 창조되었는가?\n\n"
        "① 둘째 날\n② 셋째 날\n③ 넷째 날\n④ 다섯째 날"
    )

    plan = build_beta6_candidate_search_plan(product, query, [], target_limit=30, per_keyword_limit=30)
    assert any(search_query == "Gen 1:1" for _label, search_query, _limit in plan)
    assert next(limit for _label, search_query, limit in plan if search_query == "Gen 1:1") >= 120

    rows = collect_candidate_rows(
        product,
        query,
        language="ko",
        limit=5,
        keywords=[],
        initial=[],
        fast_mode=True,
    )

    assert "doc-gen-1-19" in [row.canonical_id for row in rows]


def test_catholic_beta6_candidate_scan_uses_question_context_for_chapter_answer_rows(tmp_path):
    db_path = tmp_path / "catholic.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE precedents (
          canonical_id TEXT PRIMARY KEY,
          source_dataset TEXT,
          source_path TEXT,
          title TEXT,
          case_number TEXT,
          court TEXT,
          decision_date TEXT,
          case_name TEXT,
          case_type TEXT,
          full_text TEXT NOT NULL,
          text_hash TEXT NOT NULL
        );
        CREATE VIRTUAL TABLE precedents_fts USING fts5(
          canonical_id UNINDEXED,
          full_text,
          tokenize='unicode61'
        );
        INSERT INTO precedents VALUES
          ('doc-2sam-7-1','catholic/korean//scripture','korrv/2samuel','Korean Revised Version','2Sam 7:1','','','2 Samuel','scripture_window','[META]
authority_level: 90
source_kind: scripture

2Sam 7:1 여호와께서 다윗에게 말씀하신 장의 시작 절이다.','hash-seed'),
          ('doc-2sam-7-26','catholic/korean//scripture','korrv/2samuel','Korean Revised Version','2Sam 7:26','','','2 Samuel','scripture_window','[META]
authority_level: 90
source_kind: scripture

사람으로 영원히 주의 이름을 높여 이르기를 다윗의 집이 주 앞에 견고하다 하게 하옵소서.','hash-target');
        INSERT INTO precedents_fts(canonical_id, full_text)
          SELECT canonical_id, full_text FROM precedents;
        """
    )
    conn.commit()
    conn.close()
    product = ProductProfile(
        key="catholic",
        name="Catholic Test",
        db_path=db_path,
        db_shape="precedents",
        languages=("ko", "en"),
        default_language="ko",
        theme="",
        safety_notice="test",
    )
    question = (
        "여호와께서 나단을 통해 다윗의 왕조가 영원히 지속되리라고 약속하신 말씀은 "
        "사무엘하 몇 장에 나오는가?\n\n"
        "① 6장\n② 7장\n③ 8장\n④ 9장"
    )

    rows = _search_documents_for_beta6_candidate_scan(
        product,
        "2Sam 7:1",
        limit=30,
        language="ko",
        label="domain_bucket_04",
        question=question,
    )

    assert "doc-2sam-7-26" in [row.canonical_id for row in rows]


def test_catholic_search_expands_korean_scripture_sibling_from_multilingual_quote_hit(tmp_path):
    db_path = tmp_path / "catholic.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE precedents (
          canonical_id TEXT PRIMARY KEY,
          source_dataset TEXT,
          source_path TEXT,
          title TEXT,
          case_number TEXT,
          court TEXT,
          decision_date TEXT,
          case_name TEXT,
          case_type TEXT,
          full_text TEXT NOT NULL,
          text_hash TEXT NOT NULL
        );
        CREATE VIRTUAL TABLE precedents_fts USING fts5(
          canonical_id UNINDEXED,
          full_text,
          tokenize='unicode61'
        );
        INSERT INTO precedents VALUES
          ('doc-isa-7-14-vulg','catholic/latin//scripture','vulgate/isaiah','Clementine Vulgate','Isa 7:14','','','Isaiah','scripture_window','[META]
authority_level: 90
source_kind: scripture

(ko, Korean Revised Version): 보라 처녀가 잉태하여 아들을 낳을 것이요 그 이름을 임마누엘이라 하리라','hash-vulg'),
          ('doc-isa-7-14-kor','catholic/korean//scripture','korrv/isaiah','Korean Revised Version','Isa 7:14','','','Isaiah','scripture_window','[META]
authority_level: 90
source_kind: scripture

그러므로 주께서 친히 징조로 너희에게 주실 것이라 보라 처녀가 잉태하여 아들을 낳을 것이요 그 이름을 임마누엘이라 하리라','hash-kor');
        INSERT INTO precedents_fts(canonical_id, full_text)
          SELECT canonical_id, full_text FROM precedents
          WHERE canonical_id = 'doc-isa-7-14-vulg';
        """
    )
    conn.commit()
    conn.close()
    product = ProductProfile(
        key="catholic",
        name="Catholic Test",
        db_path=db_path,
        db_shape="precedents",
        languages=("ko", "en"),
        default_language="ko",
        theme="",
        safety_notice="test",
    )

    rows = search_documents(
        product,
        "보라 처녀가 잉태하여 아들을 낳을 것이요 그의 이름을 임마누엘이라 하리라",
        limit=5,
        language="ko",
        candidate_multiplier=1,
    )

    assert "doc-isa-7-14-kor" in [row.canonical_id for row in rows]


def test_catholic_beta6_candidate_collection_keeps_later_public_citation_option(tmp_path):
    db_path = tmp_path / "catholic.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE precedents (
          canonical_id TEXT PRIMARY KEY,
          source_dataset TEXT,
          source_path TEXT,
          title TEXT,
          case_number TEXT,
          court TEXT,
          decision_date TEXT,
          case_name TEXT,
          case_type TEXT,
          full_text TEXT NOT NULL,
          text_hash TEXT NOT NULL
        );
        CREATE VIRTUAL TABLE precedents_fts USING fts5(
          canonical_id UNINDEXED,
          full_text,
          tokenize='unicode61'
        );
        INSERT INTO precedents VALUES
          ('doc-noise-01','catholic/all/vatican-ii/official_doctrine','noise/01','Noise 1','Noise 1','','','Noise','official_doctrine_unit','본문은 출애굽기 어디에 기록되어 있는가 너희는 여호와를 찬송하라 말 바다 broad noise 1','hash-n1'),
          ('doc-noise-02','catholic/all/vatican-ii/official_doctrine','noise/02','Noise 2','Noise 2','','','Noise','official_doctrine_unit','본문은 출애굽기 어디에 기록되어 있는가 너희는 여호와를 찬송하라 말 바다 broad noise 2','hash-n2'),
          ('doc-noise-03','catholic/all/vatican-ii/official_doctrine','noise/03','Noise 3','Noise 3','','','Noise','official_doctrine_unit','본문은 출애굽기 어디에 기록되어 있는가 너희는 여호와를 찬송하라 말 바다 broad noise 3','hash-n3'),
          ('doc-noise-04','catholic/all/vatican-ii/official_doctrine','noise/04','Noise 4','Noise 4','','','Noise','official_doctrine_unit','본문은 출애굽기 어디에 기록되어 있는가 너희는 여호와를 찬송하라 말 바다 broad noise 4','hash-n4'),
          ('doc-noise-05','catholic/all/vatican-ii/official_doctrine','noise/05','Noise 5','Noise 5','','','Noise','official_doctrine_unit','본문은 출애굽기 어디에 기록되어 있는가 너희는 여호와를 찬송하라 말 바다 broad noise 5','hash-n5'),
          ('doc-noise-06','catholic/all/vatican-ii/official_doctrine','noise/06','Noise 6','Noise 6','','','Noise','official_doctrine_unit','본문은 출애굽기 어디에 기록되어 있는가 너희는 여호와를 찬송하라 말 바다 broad noise 6','hash-n6'),
          ('doc-exod-14-31','catholic/korean//scripture','korrv/exodus','Korean Revised Version','Exod 14:31','','','Exodus','scripture_window','[META]
authority_level: 90
source_kind: scripture
citation: Exod 14:31
이스라엘이 여호와께서 애굽 사람들에게 베푸신 큰 일을 보았으므로','hash-other'),
          ('doc-exod-15-21','catholic/korean//scripture','korrv/exodus','Korean Revised Version','Exod 15:21','','','Exodus','scripture_window','[META]
authority_level: 90
source_kind: scripture
citation: Exod 15:21
target citation row without broad stem terms','hash-target');
        INSERT INTO precedents_fts(canonical_id, full_text)
          SELECT canonical_id, full_text FROM precedents;
        """
    )
    conn.commit()
    conn.close()
    product = ProductProfile(
        key="catholic",
        name="Catholic Test",
        db_path=db_path,
        db_shape="precedents",
        languages=("ko", "en"),
        default_language="ko",
        theme="",
        safety_notice="test",
    )
    query = (
        "다음 본문은 출애굽기 어디에 기록되어 있는가? "
        "“너희는 여호와를 찬송하라 그는 높고 영화로우심이요 말과 그 탄 자를 바다에 던지셨음이로다”\n\n"
        "① 13:1-2\n② 14:31\n③ 15:21\n④ 40:35"
    )

    rows = collect_candidate_rows(
        product,
        query,
        language="ko",
        limit=5,
        keywords=["Exodus", "Exod", "Ex 15:1", "Ex 15:11", "Song of Moses"],
        initial=[],
        fast_mode=True,
    )

    assert "doc-exod-15-21" in [row.canonical_id for row in rows]


def test_catholic_beta6_candidate_collection_expands_public_chapter_options(tmp_path):
    db_path = tmp_path / "catholic.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE precedents (
          canonical_id TEXT PRIMARY KEY,
          source_dataset TEXT,
          source_path TEXT,
          title TEXT,
          case_number TEXT,
          court TEXT,
          decision_date TEXT,
          case_name TEXT,
          case_type TEXT,
          full_text TEXT NOT NULL,
          text_hash TEXT NOT NULL
        );
        CREATE VIRTUAL TABLE precedents_fts USING fts5(
          canonical_id UNINDEXED,
          full_text,
          tokenize='unicode61'
        );
        INSERT INTO precedents VALUES
          ('doc-noise-01','catholic/all/vatican-ii/official_doctrine','noise/01','Noise 1','Noise 1','','','Noise','official_doctrine_unit','신명기 하나님 여호와 신 가운데 신 주 가운데 주 broad noise 1','hash-n1'),
          ('doc-noise-02','catholic/all/vatican-ii/official_doctrine','noise/02','Noise 2','Noise 2','','','Noise','official_doctrine_unit','신명기 하나님 여호와 신 가운데 신 주 가운데 주 broad noise 2','hash-n2'),
          ('doc-noise-03','catholic/all/vatican-ii/official_doctrine','noise/03','Noise 3','Noise 3','','','Noise','official_doctrine_unit','신명기 하나님 여호와 신 가운데 신 주 가운데 주 broad noise 3','hash-n3'),
          ('doc-noise-04','catholic/all/vatican-ii/official_doctrine','noise/04','Noise 4','Noise 4','','','Noise','official_doctrine_unit','신명기 하나님 여호와 신 가운데 신 주 가운데 주 broad noise 4','hash-n4'),
          ('doc-noise-05','catholic/all/vatican-ii/official_doctrine','noise/05','Noise 5','Noise 5','','','Noise','official_doctrine_unit','신명기 하나님 여호와 신 가운데 신 주 가운데 주 broad noise 5','hash-n5'),
          ('doc-deut-10-1','catholic/korean//scripture','korrv/deuteronomy','Korean Revised Version','Deut 10:1','','','Deuteronomy','scripture_window','[META]
authority_level: 90
source_kind: scripture
citation: Deut 10:1
그 때에 여호와께서 내게 이르시기를','hash-seed'),
          ('doc-deut-10-17','catholic/korean//scripture','korrv/deuteronomy','Korean Revised Version','Deut 10:17','','','Deuteronomy','scripture_window','[META]
authority_level: 90
source_kind: scripture
citation: Deut 10:17
너희의 하나님 여호와는 신의 신이시며 주의 주시요','hash-target');
        INSERT INTO precedents_fts(canonical_id, full_text)
          SELECT canonical_id, full_text FROM precedents;
        """
    )
    conn.commit()
    conn.close()
    product = ProductProfile(
        key="catholic",
        name="Catholic Test",
        db_path=db_path,
        db_shape="precedents",
        languages=("ko", "en"),
        default_language="ko",
        theme="",
        safety_notice="test",
    )
    query = (
        "“너희의 하나님 여호와는 신 가운데 신이시며 주 가운데 주시요 "
        "크고 능하시며 두려우신 하나님이시라” 라는 말씀은 신명기 몇 장에 나오는가?\n\n"
        "① 8장\n② 9장\n③ 10장\n④ 11장"
    )

    plan = build_beta6_candidate_search_plan(
        product,
        query,
        ["Deuteronomy", "Deut", "God of gods"],
        target_limit=30,
        per_keyword_limit=10,
    )
    assert any(item[1] == "Deut 10:1" for item in plan)

    rows = collect_candidate_rows(
        product,
        query,
        language="ko",
        limit=5,
        keywords=["Deuteronomy", "Deut", "God of gods"],
        initial=[],
        fast_mode=True,
    )

    assert "doc-deut-10-17" in [row.canonical_id for row in rows]


def test_islam_search_expands_korean_religious_terms_to_arabic_and_english(tmp_path):
    db_path = tmp_path / "islam-school.sqlite3"
    _make_islam_school_db(db_path)
    profile = ProductProfile(
        key="islam",
        name="Hikmah AI",
        db_path=db_path,
        db_shape="precedents",
        languages=("en", "ko", "ar"),
        default_language="en",
        theme="islam",
        safety_notice="notice",
    )

    plan = describe_query_expansion(profile, "결혼할 때 보호자가 필요한가 학파별로 알려줘")
    rows = search_documents(profile, "결혼할 때 보호자가 필요한가 학파별로 알려줘", limit=3, language="ko")

    assert any("ولي" in token or "نكاح" in token for token in plan["expandedTerms"])
    assert rows
    assert rows[0].canonical_id in {"doc-wali-hanafi", "doc-wali-shafii"}
    assert {row.school for row in rows[:2]} >= {"hanafi", "shafii"}


def test_islam_query_expansion_drops_korean_source_control_surface_terms(tmp_path):
    db_path = tmp_path / "islam-school.sqlite3"
    _make_islam_school_db(db_path)
    profile = ProductProfile(
        key="islam",
        name="Hikmah AI",
        db_path=db_path,
        db_shape="precedents",
        languages=("en", "ko", "ar"),
        default_language="en",
        theme="islam",
        safety_notice="notice",
    )

    plan = describe_query_expansion(profile, "사회주의는 하람임? 꾸란과 하디스, 학파별 근거를 나눠서 단정하지 말고 알려줘")

    surface = set(plan["surfaceTerms"])
    assert "꾸란과" not in surface
    assert "하디스" not in surface
    assert "학파별" not in surface
    assert "근거" not in surface


def test_islam_search_results_carry_school_and_authority_metadata(tmp_path):
    db_path = tmp_path / "islam-school.sqlite3"
    _make_islam_school_db(db_path)
    profile = ProductProfile(
        key="islam",
        name="Hikmah AI",
        db_path=db_path,
        db_shape="precedents",
        languages=("en", "ko", "ar"),
        default_language="en",
        theme="islam",
        safety_notice="notice",
    )

    rows = search_documents(profile, "ولي النكاح", limit=2, language="ar")

    assert rows[0].tradition == "sunni"
    assert rows[0].school in {"hanafi", "shafii"}
    assert rows[0].source_kind == "fiqh"
    assert rows[0].authority_level >= 80
    selected = to_beta6_selected_record(rows[0])
    assert selected["metadata"]["school"] == rows[0].school
    assert selected["metadata"]["authorityLevel"] == rows[0].authority_level


def test_tcm_search_expands_korean_terms_to_hanja_chinese_and_english(tmp_path):
    db_path = tmp_path / "tcm-domain.sqlite3"
    _make_tcm_domain_db(db_path)
    profile = ProductProfile(
        key="tcm",
        name="Hanui AI",
        db_path=db_path,
        db_shape="precedents",
        languages=("ko", "en"),
        default_language="ko",
        theme="tcm",
        safety_notice="notice",
    )

    plan = describe_query_expansion(profile, "감초 임신 중 금기와 고문헌 근거")
    rows = search_documents(profile, "감초 임신 중 금기와 고문헌 근거", limit=4, language="ko")

    assert {"甘草", "licorice", "妊娠", "禁忌"} & set(plan["expandedTerms"])
    assert rows
    assert {row.source_kind for row in rows[:3]} >= {"classic_canon", "materia_medica"}


def test_tcm_open_symptom_query_expands_to_chinese_clinical_terms(tmp_path):
    profile = ProductProfile(
        key="tcm",
        name="Hanui AI",
        db_path=tmp_path / "unused.sqlite3",
        db_shape="precedents",
        languages=("ko", "en"),
        default_language="ko",
        theme="tcm",
        safety_notice="notice",
    )

    plan = describe_query_expansion(
        profile,
        "변비와 복만이 있고 땀이 나며 식사 양호, 맥이 활실하다.",
    )

    assert {"便秘", "腹滿", "汗出", "納可", "脈滑", "滑實"} <= set(plan["expandedTerms"])
    han_variant = next(row for row in plan["queryVariants"] if row["label"] == "tcm_han_terms")
    assert all(f'"{term}"' in han_variant["fts"] for term in ("便秘", "腹滿", "汗出", "納可", "脈滑", "滑實"))
    grouped_variant = next(row for row in plan["queryVariants"] if row["label"] == "tcm_han_all")
    assert grouped_variant["fts"].count(" AND ") == 4
    assert grouped_variant["fts"].startswith('("便秘"')
    assert '"滑實"' in grouped_variant["fts"]
    assert len([row for row in plan["queryVariants"] if row["label"].startswith("tcm_han_pair_")]) == 6

    clinical_plan = describe_query_expansion(
        profile,
        "60세 남자가 변비로 병원에 왔다. 배가 부르고 그득하며 땀을 많이 흘리나, "
        "식사는 잘한다고 한다. 맥활실(滑實)하다. 치방은?",
    )

    assert {"便秘", "腹滿", "汗出", "納可", "脈滑", "滑實"} <= set(clinical_plan["expandedTerms"])
    assert {"60세", "남자가", "병원에", "왔다", "많이"}.isdisjoint(clinical_plan["surfaceTerms"])
    assert {"변비", "그득", "땀", "식사", "맥활실", "滑實"} <= set(clinical_plan["surfaceTerms"])


def test_tcm_search_prefers_classic_authority_and_carries_metadata(tmp_path):
    db_path = tmp_path / "tcm-domain.sqlite3"
    _make_tcm_domain_db(db_path)
    profile = ProductProfile(
        key="tcm",
        name="Hanui AI",
        db_path=db_path,
        db_shape="precedents",
        languages=("ko", "en"),
        default_language="ko",
        theme="tcm",
        safety_notice="notice",
    )

    rows = search_documents(profile, "감초 고문헌 근거", limit=3, language="ko")

    assert rows[0].canonical_id == "doc-gamcho-classic"
    assert rows[0].tradition == "kmm"
    assert rows[0].school == "korean-classic"
    assert rows[0].source_kind == "classic_canon"
    assert rows[0].authority_level == 100
    selected = to_beta6_selected_record(rows[0])
    assert selected["metadata"]["sourceKind"] == "classic_canon"
    assert selected["metadata"]["authorityLabel"] == "classic canon"


def test_tcm_search_expands_adjacent_passage_graph_neighbors(tmp_path):
    db_path = tmp_path / "tcm-passage-graph.sqlite3"
    _make_tcm_passage_graph_db(db_path)
    profile = ProductProfile(
        key="tcm",
        name="Hanui AI",
        db_path=db_path,
        db_shape="precedents",
        languages=("ko", "en"),
        default_language="ko",
        theme="tcm",
        safety_notice="notice",
    )

    rows = search_documents(profile, "불면 침 치료 근거", limit=3, language="ko", candidate_multiplier=1)
    ids = [row.canonical_id for row in rows]

    assert "doc.tcm.demo.0002" in ids
    assert "doc.tcm.demo.0001" in ids
    assert ids.index("doc.tcm.demo.0001") < 3


def test_tcm_mcq_parser_normalizes_ocr_markers_and_aliases():
    question = (
        "4. 50세 남자가 오심번열과 이명, 요통을 호소한다. 치방은? "
        "D 귀비탕 @ 오미자탕 @ 보혈안신탕 ® 육미지황환 © 과루해백반하탕"
    )
    parsed = parse_tcm_mcq(question)

    assert parsed is not None
    assert [option.number for option in parsed.options] == [1, 2, 3, 4, 5]
    assert parsed.options[3].text == "육미지황환"
    assert {"육미지황원", "六味地黃元"} <= set(tcm_mcq_option_terms(question))


def test_tcm_mcq_parser_uses_line_order_for_noisy_kuksiwon_markers():
    q001 = """1. 노인에게 한약을 처방할 때 주의할 것은?
07 음식과 약물의 상호작용을 고려하지 않는다.
@ 군약을 위주로 사용하고 MAS 사용하지 않는다.
@ 노인은 오장육부의 기능이 많이 저하되어 있으므로 1회
복용할 약량을 늘린다.
® 간과 신의 SS 보하는 약에는 BALE 목단피 SS 가하여
전체적으로 농후하지 않도록 한다.
© 약물의 가짓수가 많으므로 약물의 복용을 단순화하기보다는
복잡하더라도 약물마다 다른 AAO] 복용하도록 지도한다."""
    q003 = """3. 32세 여자가 의식을 잃어 Helo] 왔다. GAD 돈문제로 다투다
억울함을 호소하던 도중 갑자기 의식을 잃고 쓰러졌다가
= AMS 회복하였다고 한다. 다른 신경학적 이상 소견은
발견되지 않았다. 치방은?
© 목향순기산
Q 목향파기산
@ 소자강기탕
® 익위승양탕
© 조중익기탕"""
    q007 = """7. 32세 여자가 수개월 전 출산 후부터 AS 조금만 해도 목소리가
HICHD 한다. 출산 시 출혈이 심해 FHS 받았고, 가슴이
자주 두근거린다고 한다. 안색과 안검이 창백하다. 치방은?
0 합개환
@ 형소탕
3 소속명탕
0) 복령보심탕
09) 향성파적환"""
    q009 = """9. 45세 남자가 장명음으로 병원에 왔다. 본래 마른 편인데 갑자기
살이 CED 한다. +S CKO] TBS 머물러서 소리가
나는 것으로 보고 치료했다. 치방은?
© 신출환
@ 십조탕
@ 소청룡탕
@: 삼화신우환
@ 복령오미자탕"""
    q011 = """11. 32세 여자가 명치 부위가 타는 듯이 아프다며 병원에 왔다.
명치 부위가 더부룩하고, 배가 고픈 듯하지만 식욕이 없으며
트림이나 APAVS 자주 하고 입안이 마른다고 한다.
설홍무태하다. 치방은?
0: 양위탕
@ sux
@ 청위산
@: 가미단삼음
© 조위승기탕"""

    parsed_001 = parse_tcm_mcq(q001)
    parsed_003 = parse_tcm_mcq(q003)
    parsed_007 = parse_tcm_mcq(q007)
    parsed_009 = parse_tcm_mcq(q009)
    parsed_011 = parse_tcm_mcq(q011)

    assert parsed_001 is not None
    assert [option.text for option in parsed_001.options] == [
        "음식과 약물의 상호작용을 고려하지 않는다.",
        "군약을 위주로 사용하고 MAS 사용하지 않는다.",
        "노인은 오장육부의 기능이 많이 저하되어 있으므로 1회 복용할 약량을 늘린다.",
        "간과 신의 SS 보하는 약에는 BALE 목단피 SS 가하여 전체적으로 농후하지 않도록 한다.",
        "약물의 가짓수가 많으므로 약물의 복용을 단순화하기보다는 복잡하더라도 약물마다 다른 AAO] 복용하도록 지도한다.",
    ]
    assert parsed_003 is not None
    assert [option.text for option in parsed_003.options] == [
        "목향순기산",
        "목향파기산",
        "소자강기탕",
        "익위승양탕",
        "조중익기탕",
    ]
    assert parsed_007 is not None
    assert [option.text for option in parsed_007.options] == [
        "합개환",
        "형소탕",
        "소속명탕",
        "복령보심탕",
        "향성파적환",
    ]
    assert parsed_009 is not None
    assert [option.text for option in parsed_009.options] == [
        "신출환",
        "십조탕",
        "소청룡탕",
        "삼화신우환",
        "복령오미자탕",
    ]
    assert parsed_011 is not None
    assert [option.text for option in parsed_011.options] == [
        "양위탕",
        "sux",
        "청위산",
        "가미단삼음",
        "조위승기탕",
    ]


def test_tcm_mcq_parser_handles_late_kuksiwon_ocr_markers_and_answer_markers():
    q012 = """12. HAS 중 맑은 거품 같은 침이 많이 나오고, 입마름은 없으며,
소변색이 맑다고 한다. 치방은?
0: asa
@ 맥문동탕
@ 감초건강탕
@ 문동청폐음
6 인삼평폐산"""
    q036 = """36. 40M] 남자가 SHO] 자주 나온다며 병원에 왔다. 3개월 전부터
ERO] 식사와 상관없이 수시로 나오며, 피로하고 기운이
없다고 한다. 치방은?
0) 균기환
2 사역산
@3) 여성탕
@® 이진탕
© 청담환
(6/"""
    q041 = """41. 55세 SAVE PES 병원에 왔다. 치방은?
D 격하축어탕
(2 글피죽여탕
@ 몽석곤담환
© 정향안위탕
© 정향투격탕"""
    q030 = """30. 35세 여자가 양 손가락의 감각이 이상하다며 병원에 왔다. 진단은?
D 정맥혈전증
@ 레이노증후군
63 말초동맥색전증
© 경추 척주관협착증
© 당뇨병성 말초신경병증"""
    q035 = """35. 다음 중 환자가 복용했을 가능성이 높은 혈압약은?
(01) BAreEt(losartan)
Q@ 캡토프릴(630100ㅁ!)
@ 나이페디핀(016010106)
@® Z2D2}+ 5 (propranolol)
© so] E232 2M0|0fAfO| € (hydrochlorothiazide)"""
    q049 = """49. 40세 여자가 목 부위에 덩어리가 있어 병원에 왔다. 진단은?
0) 갑상선암
@ 갑상선염
@ 갑상선낭종
® 갑상선중독
© 그레이브스병"""

    parsed_012 = parse_tcm_mcq(q012)
    parsed_036 = parse_tcm_mcq(q036)
    parsed_041 = parse_tcm_mcq(q041)
    parsed_030 = parse_tcm_mcq(q030)
    parsed_035 = parse_tcm_mcq(q035)
    parsed_049 = parse_tcm_mcq(q049)

    assert parsed_012 is not None
    assert [option.text for option in parsed_012.options] == ["asa", "맥문동탕", "감초건강탕", "문동청폐음", "인삼평폐산"]
    assert parsed_036 is not None
    assert [option.text for option in parsed_036.options] == ["균기환", "사역산", "여성탕", "이진탕", "청담환"]
    assert parsed_041 is not None
    assert [option.text for option in parsed_041.options] == ["격하축어탕", "글피죽여탕", "몽석곤담환", "정향안위탕", "정향투격탕"]
    assert parsed_030 is not None
    assert [option.text for option in parsed_030.options] == ["정맥혈전증", "레이노증후군", "말초동맥색전증", "경추 척주관협착증", "당뇨병성 말초신경병증"]
    assert parsed_035 is not None
    assert [option.text for option in parsed_035.options] == [
        "BAreEt(losartan)",
        "캡토프릴(630100ㅁ!)",
        "나이페디핀(016010106)",
        "Z2D2}+ 5 (propranolol)",
        "so] E232 2M0|0fAfO| € (hydrochlorothiazide)",
    ]
    assert parsed_049 is not None
    assert canonicalize_tcm_answer_number("정답: 0", q049) == 1
    assert canonicalize_tcm_answer_number("정답: 6", q012) == 5
    assert canonicalize_tcm_answer_number("정답: ④", q049) == 4


def test_tcm_answer_canonicalizer_reads_circled_answer_as_numeric_position():
    question = """1. 다음 치방은?
D 귀비탕
@ 오미자탕
@ 보혈안신탕
® 육미지황환
© 과루해백반하탕"""

    assert canonicalize_tcm_answer_number("정답: ④", question) == 4


def test_tcm_mcq_parser_strips_benchmark_instruction_suffix(tmp_path):
    question = """36. 40M] 남자가 SHO] 자주 나온다며 병원에 왔다. 3개월 전부터
ERO] 식사와 상관없이 수시로 나오며, 피로하고 기운이
없다고 한다. 치방은?
0) 균기환
2 사역산
@3) 여성탕
@® 이진탕
© 청담환
(6/
위 한의사 국가시험 객관식 문제의 정답 번호를 1~5 중 하나로 고르세요.
답변 첫 줄은 반드시 `정답: <번호>` 형식으로 시작하세요."""

    parsed = parse_tcm_mcq(question)
    search_text = tcm_mcq_search_text(question)
    profile = ProductProfile(
        key="tcm",
        name="Hanui AI",
        db_path=tmp_path / "unused.sqlite3",
        db_shape="precedents",
        languages=("ko",),
        default_language="ko",
        theme="tcm",
        safety_notice="notice",
    )
    expansion = describe_query_expansion(profile, question)

    assert parsed is not None
    assert [option.text for option in parsed.options] == ["균기환", "사역산", "여성탕", "이진탕", "청담환"]
    assert "위 한의사" not in search_text
    assert "정답" not in search_text
    assert "정답" not in expansion["surfaceTerms"]
    assert "한의사" not in expansion["surfaceTerms"]


def test_islam_search_expansion_uses_generic_mcq_stem_not_options(tmp_path):
    profile = ProductProfile(
        key="islam",
        name="Hikmah AI",
        db_path=tmp_path / "unused.sqlite3",
        db_shape="precedents",
        languages=("ko",),
        default_language="ko",
        theme="islam",
        safety_notice="notice",
    )
    question = """006. 이유는?

A. 자금 혼합
B. 고객의 기밀 유지
C. 상업적 위험
D. 기업 지배구조

위 객관식 문제의 정답 보기ID 하나만 고르세요.
답변 첫 줄은 반드시 `정답: <보기ID>` 형식으로 시작하세요."""

    expansion = describe_query_expansion(profile, question)

    joined = " ".join(expansion["surfaceTerms"])
    assert "이유는" in joined
    assert "자금" not in joined
    assert "고객의" not in joined
    assert "기업" not in joined
    assert "정답" not in joined


def test_islam_query_expansion_ignores_generic_mcq_options(tmp_path):
    profile = ProductProfile(
        key="islam",
        name="Hikmah AI",
        db_path=tmp_path / "unused.sqlite3",
        db_shape="precedents",
        languages=("ko",),
        default_language="ko",
        theme="islam",
        safety_notice="notice",
    )
    question = """006. 이유는?

A. 자카트 계산
B. 고객의 기밀 유지
C. 상업적 위험
D. 기업 지배구조"""

    expansion = describe_query_expansion(profile, question)

    assert "zakat" not in expansion["expandedTerms"]
    assert "زكاة" not in expansion["expandedTerms"]


def test_islam_precedent_rank_surface_terms_ignore_generic_mcq_options(tmp_path, monkeypatch):
    db_path = tmp_path / "islam.sqlite3"
    _make_precedents_db(db_path)
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        INSERT INTO precedents VALUES
          ('doc-stem','islam/fiqh','fiqh/stem','screening principle','screening principle','fiqh','','screening','fiqh','Screening requires substantive review of the business and asset profile.','hash-stem'),
          ('doc-option','islam/fiqh','fiqh/option','zakat option distractor','zakat option distractor','fiqh','','zakat option','fiqh','Screening and zakat zakat zakat zakat distractor wording from an option.','hash-option');
        INSERT INTO precedents_fts(canonical_id, full_text)
          SELECT canonical_id, full_text FROM precedents
          WHERE canonical_id IN ('doc-stem', 'doc-option');
        """
    )
    conn.commit()
    conn.close()
    profile = ProductProfile(
        key="islam",
        name="Hikmah AI",
        db_path=db_path,
        db_shape="precedents",
        languages=("ko", "en"),
        default_language="ko",
        theme="islam",
        safety_notice="notice",
    )
    query = """006. screening?

A. zakat
B. client confidentiality
C. commercial risk
D. governance"""

    rows = search_documents(profile, query, limit=2, language="en", candidate_multiplier=1)

    assert [row.canonical_id for row in rows[:2]] == ["doc-stem", "doc-option"]


def test_tcm_search_uses_mcq_option_formula_aliases_when_enabled(tmp_path, monkeypatch):
    db_path = tmp_path / "tcm-domain.sqlite3"
    _make_tcm_domain_db(db_path)
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        INSERT INTO precedents VALUES
          ('doc-urine-generic','tcm-kmm/kmm/korean-classic/classic_canon','donguibogam/urine','東醫寶鑑 (Dongui Bogam, 1613)','Dongui Bogam #urine','Dongui Bogam','','urine generic','classic_canon_unit','[META]
religion: tcm-kmm
tradition: kmm
school: korean-classic
authority_level: 100
source_kind: classic_canon
authority_label: classic canon

소변 방광 기화 수액 대장 위완 분문 해부 설명.','hash-urine'),
          ('doc-yukmi-formula','tcm-kmm/kmm/korean-classic/classic_authoritative','ujong/yukmi','醫宗損益 (Hwang Doyeon, 1867)','Ujong Soneik #六味地黃元','Ujong Soneik','','육미지황원','classic_authoritative_unit','[META]
religion: tcm-kmm
tradition: kmm
school: korean-classic
authority_level: 85
source_kind: classic_authoritative
authority_label: authoritative classic

六味地黃元 육미지황원 신허 요통 이명 유정 오심번열에 관련된 처방 근거.','hash-yukmi');
        INSERT INTO precedents_fts(canonical_id, full_text)
          SELECT canonical_id, full_text FROM precedents
          WHERE canonical_id IN ('doc-urine-generic', 'doc-yukmi-formula');
        """
    )
    conn.commit()
    conn.close()
    profile = ProductProfile(
        key="tcm",
        name="Hanui AI",
        db_path=db_path,
        db_shape="precedents",
        languages=("ko", "en"),
        default_language="ko",
        theme="tcm",
        safety_notice="notice",
    )

    query = (
        "50세 남자가 가슴 두근거림, 오심번열, 이명, 요통, 소변에 정액이 섞여 나왔다. 치방은? "
        "D 귀비탕 @ 오미자탕 @ 보혈안신탕 ® 육미지황환 © 과루해백반하탕"
    )
    monkeypatch.setenv("RELIGION_MCQ_HEURISTICS_ENABLED", "1")
    rows = search_documents(profile, query, limit=4, language="ko", candidate_multiplier=1)
    ids = [row.canonical_id for row in rows]

    assert ids[0] == "doc-yukmi-formula"
    assert "doc-urine-generic" not in ids[:1]


def test_tcm_search_rescues_exact_mcq_option_rows_outside_fts_when_enabled(tmp_path, monkeypatch):
    db_path = tmp_path / "tcm-domain.sqlite3"
    _make_tcm_domain_db(db_path)
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO precedents VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (
            "doc-nangan-exact",
            "tcm-kmm/tcm/tcm-classic/classic_authoritative",
            "books/nangan",
            "난간전 exact source",
            "暖肝煎",
            "classic",
            "",
            "난간전",
            "classic_authoritative_unit",
            """[META]
religion: tcm-kmm
tradition: tcm
school: tcm-classic
authority_level: 75
source_kind: classic_authoritative
authority_label: authoritative classic

暖肝煎 난간전은 소복 냉통과 한체 간맥 증상에 대한 처방 근거로 제시된다.""",
            "hash-nangan",
        ),
    )
    conn.commit()
    conn.close()
    profile = ProductProfile(
        key="tcm",
        name="Hanui AI",
        db_path=db_path,
        db_shape="precedents",
        languages=("ko", "en"),
        default_language="ko",
        theme="tcm",
        safety_notice="notice",
    )

    query = """40세 여자가 아랫배 통증과 냉감을 호소한다. 치방은?
© 난간전
@ 온담탕
@ 온청음
0: 용담사간탕
© 익기보혈탕"""
    monkeypatch.setenv("RELIGION_MCQ_HEURISTICS_ENABLED", "1")
    rows = search_documents(profile, query, limit=3, language="ko", candidate_multiplier=1)

    assert rows
    assert rows[0].canonical_id == "doc-nangan-exact"


def test_tcm_search_can_disable_exact_mcq_option_rescue(tmp_path, monkeypatch):
    db_path = tmp_path / "tcm-domain.sqlite3"
    _make_tcm_domain_db(db_path)
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO precedents VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (
            "doc-nangan-exact",
            "tcm-kmm/tcm/tcm-classic/classic_authoritative",
            "books/nangan",
            "난간전 exact source",
            "暖肝煎",
            "classic",
            "",
            "난간전",
            "classic_authoritative_unit",
            """[META]
religion: tcm-kmm
tradition: tcm
school: tcm-classic
authority_level: 75
source_kind: classic_authoritative
authority_label: authoritative classic

暖肝煎 난간전은 소복 냉통과 한체 간맥 증상에 대한 처방 근거로 제시된다.""",
            "hash-nangan",
        ),
    )
    conn.commit()
    conn.close()
    profile = ProductProfile(
        key="tcm",
        name="Hanui AI",
        db_path=db_path,
        db_shape="precedents",
        languages=("ko", "en"),
        default_language="ko",
        theme="tcm",
        safety_notice="notice",
    )
    query = """40세 여자가 아랫배 통증과 냉감을 호소한다. 치방은?
© 난간전
@ 온담탕
@ 온청음
0: 용담사간탕
© 익기보혈탕"""

    monkeypatch.setenv("RELIGION_MCQ_HEURISTICS_ENABLED", "0")
    rows = search_documents(profile, query, limit=3, language="ko", candidate_multiplier=1)

    assert "doc-nangan-exact" not in [row.canonical_id for row in rows]


def test_tcm_search_widens_mcq_rank_pool_by_default_but_structure_flag_can_disable_it(tmp_path, monkeypatch):
    db_path = tmp_path / "tcm-domain.sqlite3"
    _make_tcm_domain_db(db_path)
    conn = sqlite3.connect(db_path)
    for index in range(40):
        conn.execute(
            "INSERT INTO precedents VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                f"doc-common-{index:02d}",
                "tcm-kmm/tcm/tcm-classic/classic_authoritative",
                f"books/common-{index:02d}",
                f"공통 처방 근거 {index:02d}",
                f"공통 처방 근거 {index:02d}",
                "classic",
                "",
                f"공통 처방 근거 {index:02d}",
                "classic_authoritative_unit",
                f"[META]\nsource_kind: classic_authoritative\n\n공통 증상 처방 근거 {index:02d}",
                f"hash-common-{index:02d}",
            ),
        )
        conn.execute(
            "INSERT INTO precedents_fts(canonical_id, full_text) VALUES (?, ?)",
            (f"doc-common-{index:02d}", f"공통 증상 처방 근거 {index:02d}"),
        )
    conn.commit()
    conn.close()
    profile = ProductProfile(
        key="tcm",
        name="Hanui AI",
        db_path=db_path,
        db_shape="precedents",
        languages=("ko", "en"),
        default_language="ko",
        theme="tcm",
        safety_notice="notice",
    )
    seen_pool_sizes: list[int] = []

    def spy_merge(profile, query, results, *, limit):
        seen_pool_sizes.append(len(results))
        return results[:limit]

    monkeypatch.delenv("RELIGION_MCQ_HEURISTICS_ENABLED", raising=False)
    monkeypatch.delenv("RELIGION_MCQ_STRUCTURE_ENABLED", raising=False)
    monkeypatch.setattr(search_mod, "_merge_tcm_authoritative_passages", spy_merge)
    query = "공통 증상에 맞는 처방은?\n1) 보기A\n2) 보기B\n3) 보기C\n4) 보기D\n5) 보기E"
    search_documents(
        profile,
        query,
        limit=3,
        language="ko",
        candidate_multiplier=1,
    )
    monkeypatch.setenv("RELIGION_MCQ_STRUCTURE_ENABLED", "0")
    search_documents(profile, query, limit=3, language="ko", candidate_multiplier=1)

    assert seen_pool_sizes == [36, 3]


def test_mcq_heuristics_flag_defaults_to_disabled(monkeypatch):
    import shared_platform.beta6 as beta6_mod
    import shared_platform.domain_adapters as adapter_mod
    import shared_platform.search as search_mod

    monkeypatch.delenv("RELIGION_MCQ_HEURISTICS_ENABLED", raising=False)

    assert search_mod._mcq_heuristics_enabled() is False
    assert beta6_mod._mcq_heuristics_enabled() is False
    assert adapter_mod._env_flag_default("RELIGION_MCQ_HEURISTICS_ENABLED", False) is False


def test_mcq_heuristics_flag_treats_blank_as_default_disabled(monkeypatch):
    import shared_platform.beta6 as beta6_mod
    import shared_platform.domain_adapters as adapter_mod
    import shared_platform.search as search_mod

    monkeypatch.setenv("RELIGION_MCQ_HEURISTICS_ENABLED", "")

    assert search_mod._mcq_heuristics_enabled() is False
    assert beta6_mod._mcq_heuristics_enabled() is False
    assert adapter_mod._env_flag_default("RELIGION_MCQ_HEURISTICS_ENABLED", False) is False


def test_mcq_heuristics_flag_treats_unknown_nonempty_as_enabled(monkeypatch):
    import shared_platform.beta6 as beta6_mod
    import shared_platform.domain_adapters as adapter_mod
    import shared_platform.search as search_mod

    monkeypatch.setenv("RELIGION_MCQ_HEURISTICS_ENABLED", "2")

    assert search_mod._mcq_heuristics_enabled() is True
    assert beta6_mod._mcq_heuristics_enabled() is True
    assert adapter_mod._env_flag_default("RELIGION_MCQ_HEURISTICS_ENABLED", False) is True


def test_tcm_generic_formula_word_does_not_synthesize_gancao_passage_lookup(monkeypatch):
    import shared_platform.search as search_mod

    monkeypatch.delenv("RELIGION_MCQ_HEURISTICS_ENABLED", raising=False)

    assert search_mod._tcm_passage_lookups("변비와 복만이 있을 때 처방은?") == []
    assert (
        search_mod.TCM_MATERIA_PASSAGE_SOURCE_IDS,
        "甘草",
    ) in search_mod._tcm_passage_lookups("감초의 금기와 처방상 주의점은?")


def test_tcm_open_query_sort_prefers_meaningfully_higher_relevance_before_source_kind(monkeypatch):
    import shared_platform.search as search_mod

    monkeypatch.delenv("RELIGION_MCQ_HEURISTICS_ENABLED", raising=False)
    common = {
        "citation": "",
        "authority_body": "",
        "source_date": "",
        "case_name": "",
        "case_type": "",
        "full_text": "",
    }
    relevant_reference = search_mod.SearchResult(
        canonical_id="relevant-reference",
        title="질의와 직접 일치하는 자료",
        score=-250.0,
        source_kind="modern_reference",
        authority_level=70,
        **common,
    )
    weak_classic = search_mod.SearchResult(
        canonical_id="weak-classic",
        title="표면적으로만 권위가 높은 자료",
        score=-10.0,
        source_kind="classic_canon",
        authority_level=100,
        **common,
    )

    rows = search_mod._sort_tcm_results_for_query(
        "변비와 복만이 있을 때 치방은?",
        [weak_classic, relevant_reference],
    )

    assert [row.canonical_id for row in rows] == ["relevant-reference", "weak-classic"]


def test_tcm_open_query_sort_uses_relevance_within_same_authority(monkeypatch):
    import shared_platform.search as search_mod

    monkeypatch.delenv("RELIGION_MCQ_HEURISTICS_ENABLED", raising=False)
    common = {
        "citation": "",
        "authority_body": "",
        "source_date": "",
        "case_name": "",
        "case_type": "",
        "full_text": "",
        "source_kind": "classic_canon",
        "authority_level": 100,
    }
    weak = search_mod.SearchResult(
        canonical_id="weak",
        title="약한 일치",
        score=-277.0,
        **common,
    )
    strong = search_mod.SearchResult(
        canonical_id="strong",
        title="강한 일치",
        score=-347.0,
        **common,
    )

    rows = search_mod._sort_tcm_results_for_query("변비 근거", [weak, strong])

    assert [row.canonical_id for row in rows] == ["strong", "weak"]


def test_tcm_precedent_score_prefers_translated_symptoms_over_unrelated_classic_metadata(tmp_path):
    import shared_platform.search as search_mod

    profile = ProductProfile(
        key="tcm",
        name="Hanui AI",
        db_path=tmp_path / "unused.sqlite3",
        db_shape="precedents",
        languages=("ko", "en"),
        default_language="ko",
        theme="tcm",
        safety_notice="notice",
    )
    common = {
        "title": "",
        "case_number": "",
        "case_name": "",
        "court": "",
        "decision_date": "",
        "source_path": "",
    }
    relevant_case = {
        "canonical_id": "relevant-case",
        "source_dataset": "tcm-kmm/tcm/tcm-clinical/case_record",
        "case_type": "case_record_unit",
        "full_text": "[META]\nauthority_level: 50\nsource_kind: case_record\n\n便秘 腹滿 脈滑",
        **common,
    }
    unrelated_classic = {
        "canonical_id": "unrelated-classic",
        "source_dataset": "tcm-kmm/kmm/korean-classic/classic_canon",
        "case_type": "classic_canon_unit",
        "full_text": "[META]\nauthority_level: 100\nsource_kind: classic_canon\n\n질의와 무관한 고전 문헌",
        **common,
    }
    semantic_terms = ["便秘", "腹滿", "脈滑"]

    relevant_score = search_mod._precedent_rank_score(
        profile,
        relevant_case,
        [],
        semantic_terms,
    )
    classic_score = search_mod._precedent_rank_score(
        profile,
        unrelated_classic,
        [],
        semantic_terms,
    )

    assert relevant_score > classic_score
    assert search_mod._tcm_intent_bonus(unrelated_classic, semantic_terms) == 0.0


def test_tcm_search_augments_herb_safety_queries_with_authoritative_materia_passages(tmp_path):
    db_path = tmp_path / "tcm-domain.sqlite3"
    _make_tcm_domain_db(db_path)
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE sources (
          source_id TEXT PRIMARY KEY,
          religion TEXT NOT NULL,
          tradition TEXT NOT NULL DEFAULT '',
          school TEXT NOT NULL DEFAULT '',
          source_kind TEXT NOT NULL,
          authority_level INTEGER NOT NULL,
          authority_label TEXT NOT NULL,
          title TEXT NOT NULL,
          subtitle TEXT NOT NULL DEFAULT '',
          author_body TEXT NOT NULL DEFAULT '',
          edition TEXT NOT NULL DEFAULT '',
          language TEXT NOT NULL,
          script TEXT NOT NULL DEFAULT '',
          source_url TEXT NOT NULL DEFAULT '',
          license TEXT NOT NULL DEFAULT '',
          license_notes TEXT NOT NULL DEFAULT '',
          valid_from TEXT NOT NULL DEFAULT '',
          valid_to TEXT NOT NULL DEFAULT '',
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE passages (
          passage_id TEXT PRIMARY KEY,
          source_id TEXT NOT NULL,
          canonical_ref TEXT NOT NULL,
          parent_ref TEXT NOT NULL DEFAULT '',
          ref_sort INTEGER NOT NULL DEFAULT 0,
          language TEXT NOT NULL,
          script TEXT NOT NULL DEFAULT '',
          text TEXT NOT NULL,
          normalized_text TEXT NOT NULL,
          heading TEXT NOT NULL DEFAULT '',
          tags_json TEXT NOT NULL DEFAULT '[]',
          text_hash TEXT NOT NULL
        );
        INSERT INTO sources(source_id, religion, tradition, school, source_kind, authority_level, authority_label, title, language)
        VALUES ('tcm.kmm.mediclassics.boncho-gangmok', 'tcm-kmm', 'kmm', 'bencao', 'materia_medica', 90, 'official_pharmacopoeia', '本草綱目', 'lzh');
        INSERT INTO passages(passage_id, source_id, canonical_ref, language, text, normalized_text, heading, text_hash)
        VALUES ('passage-gamcho-bencao', 'tcm.kmm.mediclassics.boncho-gangmok', '本草綱目 #甘草', 'lzh',
                '甘草 本草 條文. 禁忌는 별도 확인해야 한다.', '甘草 本草 禁忌', '草部 > 甘草', 'hash-passage');
        """
    )
    conn.commit()
    conn.close()
    profile = ProductProfile(
        key="tcm",
        name="Hanui AI",
        db_path=db_path,
        db_shape="precedents",
        languages=("ko", "en"),
        default_language="ko",
        theme="tcm",
        safety_notice="notice",
    )

    rows = search_documents(profile, "감초 임신 본초 금기", limit=4, language="ko")

    assert rows
    assert rows[0].canonical_id == "doc-gamcho-classic"
    assert any(row.canonical_id == "passage-gamcho-bencao" for row in rows)
    assert any(row.source_kind == "materia_medica" for row in rows)


def test_lawkey_search_expands_event_frame_analogous_cases(tmp_path):
    db_path = tmp_path / "lawkey.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE precedents (
          canonical_id TEXT PRIMARY KEY,
          source_dataset TEXT,
          source_path TEXT,
          title TEXT,
          case_number TEXT,
          court TEXT,
          decision_date TEXT,
          case_name TEXT,
          case_type TEXT,
          full_text TEXT NOT NULL,
          text_hash TEXT NOT NULL
        );
        CREATE VIRTUAL TABLE precedents_fts USING fts5(
          canonical_id UNINDEXED,
          full_text,
          tokenize='unicode61'
        );
        INSERT INTO precedents VALUES
          ('seed-related','lawkey/test','seed.pdf','질문 표면 seed','seed','법원','','seed','case','경찰 카톡 로그인 합법 관련 일반 자료','hash-seed'),
          ('target-frame','lawkey/test','target.pdf','익명화 전자정보 사건','2021노1520','서울고등법원','','target','case','익명화된 전자정보 압수수색 절차 사건 본문','hash-target');
        INSERT INTO precedents_fts(canonical_id, full_text)
          SELECT canonical_id, full_text FROM precedents;
        """
    )
    taxonomy = LegalTaxonomy.default()
    ensure_event_frame_schema(conn)
    upsert_event_frames(
        conn,
        [
            StoredEventFrame(
                frame_id="target-frame-1",
                doc_id="target-frame",
                chunk_id="target-frame#chunk1",
                frame=extract_legal_event_frames(
                    "검사가 유심칩을 공기계에 꽂아 인증번호를 받아 카카오톡 계정에 접속한 전자정보 증거 사건",
                    taxonomy,
                )[0],
                text="검사 유심 공기계 카카오톡 계정 접속",
            )
        ],
    )
    conn.commit()
    conn.close()
    profile = ProductProfile(
        key="lawkey",
        name="Lawkey",
        db_path=db_path,
        db_shape="precedents",
        languages=("ko",),
        default_language="ko",
        theme="lawkey",
        safety_notice="notice",
    )

    rows = search_documents(profile, "경찰이 피의자 유심 빼서 카톡 로그인하는거 합법임?", limit=2, language="ko")

    assert "target-frame" in [row.canonical_id for row in rows]


def test_lawkey_event_frame_expansion_survives_when_source_graph_is_full(tmp_path, monkeypatch):
    import shared_platform.domain_adapters as domain_mod
    from shared_platform.domain_adapters import get_domain_adapter

    db_path = tmp_path / "lawkey.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE precedents (
          canonical_id TEXT PRIMARY KEY,
          source_dataset TEXT,
          source_path TEXT,
          title TEXT,
          case_number TEXT,
          court TEXT,
          decision_date TEXT,
          case_name TEXT,
          case_type TEXT,
          full_text TEXT NOT NULL,
          text_hash TEXT NOT NULL
        );
        CREATE VIRTUAL TABLE precedents_fts USING fts5(
          canonical_id UNINDEXED,
          full_text,
          tokenize='unicode61'
        );
        INSERT INTO precedents VALUES
          ('seed-related','lawkey/test','seed.pdf','질문 표면 seed','seed','법원','','seed','case','경찰 카톡 로그인 합법 관련 일반 자료','hash-seed'),
          ('graph-noise','lawkey/test','noise.pdf','기존 그래프 잡음','noise','법원','','noise','case','기존 source graph 잡음','hash-noise'),
          ('target-frame','lawkey/test','target.pdf','익명화 전자정보 사건','2021노1520','서울고등법원','','target','case','익명화된 전자정보 압수수색 절차 사건 본문','hash-target');
        INSERT INTO precedents_fts(canonical_id, full_text)
          SELECT canonical_id, full_text FROM precedents;
        """
    )
    taxonomy = LegalTaxonomy.default()
    ensure_event_frame_schema(conn)
    upsert_event_frames(
        conn,
        [
            StoredEventFrame(
                frame_id="target-frame-1",
                doc_id="target-frame",
                chunk_id="target-frame#chunk1",
                frame=extract_legal_event_frames("검사가 유심칩을 공기계에 꽂아 카카오톡 계정에 접속한 전자정보 증거 사건", taxonomy)[0],
                text="검사 유심 공기계 카카오톡 계정 접속",
            )
        ],
    )
    conn.commit()
    conn.close()

    original_expand = domain_mod.expand_lawkey_precedent_rows

    def fake_full_source_graph(conn, seed_rows, *, seed_scores, max_neighbors, max_expanded):
        rows = conn.execute(
            """
            SELECT canonical_id, source_dataset, source_path, title, case_number, court,
                   decision_date, case_name, case_type, full_text
            FROM precedents
            WHERE canonical_id = 'graph-noise'
            """
        ).fetchall()
        return rows, {"graph-noise": 9999.0}

    monkeypatch.setattr(domain_mod, "expand_lawkey_precedent_rows", fake_full_source_graph)
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        seed_rows = conn.execute(
            """
            SELECT canonical_id, source_dataset, source_path, title, case_number, court,
                   decision_date, case_name, case_type, full_text
            FROM precedents
            WHERE canonical_id = 'seed-related'
            """
        ).fetchall()
        rows, scores = get_domain_adapter("lawkey").expand_graph_rows(
            conn,
            seed_rows,
            query="경찰이 피의자 유심 빼서 카톡 로그인하는거 합법임?",
            seed_scores={"seed-related": 10.0},
            max_neighbors=1,
            max_expanded=1,
        )
        conn.close()
    finally:
        monkeypatch.setattr(domain_mod, "expand_lawkey_precedent_rows", original_expand)

    assert [row["canonical_id"] for row in rows] == ["target-frame"]
    assert scores["target-frame"] > 0


def test_lawkey_context_search_matches_short_sim_removal_to_password_bypass(tmp_path):
    db_path = tmp_path / "lawkey.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE precedents (
          canonical_id TEXT PRIMARY KEY,
          source_dataset TEXT,
          source_path TEXT,
          title TEXT,
          case_number TEXT,
          court TEXT,
          decision_date TEXT,
          case_name TEXT,
          case_type TEXT,
          full_text TEXT NOT NULL,
          text_hash TEXT NOT NULL
        );
        CREATE VIRTUAL TABLE precedents_fts USING fts5(
          canonical_id UNINDEXED,
          full_text,
          tokenize='unicode61'
        );
        INSERT INTO precedents VALUES
          ('seed-related','lawkey/test','seed.pdf','질문 표면 seed','seed','법원','','seed','case','경찰 유심 뽑음 전자정보 일반 자료','hash-seed'),
          ('same-sim','lawkey/test','same.pdf','검찰 유심 분리 사건','same','법원','','same','case','익명화된 수사 절차 사건 본문','hash-same'),
          ('password-bypass','lawkey/test','password.pdf','비밀번호 우회 사건','password','법원','','password','case','익명화된 전자정보 접근 사건 본문','hash-password'),
          ('height-noise','lawkey/test','height.pdf','신체 키 성장 사건','height','법원','','height','case','군 복무 중 신체 키 성장 상담','hash-height');
        INSERT INTO precedents_fts(canonical_id, full_text)
          SELECT canonical_id, full_text FROM precedents;
        """
    )
    taxonomy = LegalTaxonomy.default()
    ensure_event_frame_schema(conn)
    upsert_event_frames(
        conn,
        [
            StoredEventFrame(
                frame_id="same-sim#frame1",
                doc_id="same-sim",
                chunk_id="same-sim#chunk1",
                frame=extract_legal_event_frames("검찰이 피의자 유심을 뽑아 별도 보관한 전자정보 증거 사건", taxonomy)[0],
                text="검찰 유심 분리 전자정보 증거",
            ),
            StoredEventFrame(
                frame_id="password-bypass#frame1",
                doc_id="password-bypass",
                chunk_id="password-bypass#chunk1",
                frame=extract_legal_event_frames("수사기관이 피의자 비밀번호를 해킹함", taxonomy)[0],
                text="수사기관 비밀번호 해킹 전자정보 접근",
            ),
            StoredEventFrame(
                frame_id="height-noise#frame1",
                doc_id="height-noise",
                chunk_id="height-noise#chunk1",
                frame=extract_legal_event_frames("군 복무 중 신체 키와 체격 성장에 관한 상담", taxonomy)[0],
                text="신체 키 성장 사건",
            ),
        ],
    )
    conn.commit()
    conn.close()
    profile = ProductProfile(
        key="lawkey",
        name="Lawkey",
        db_path=db_path,
        db_shape="precedents",
        languages=("ko",),
        default_language="ko",
        theme="lawkey",
        safety_notice="notice",
    )

    rows = search_documents(profile, "경찰이 유심을 뽑음", limit=4, language="ko")
    ids = [row.canonical_id for row in rows]

    assert ids[:2] == ["same-sim", "password-bypass"]
    assert "height-noise" not in ids


def test_lawkey_context_search_uses_event_frames_without_fts_seed_rows(tmp_path):
    db_path = tmp_path / "lawkey.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE precedents (
          canonical_id TEXT PRIMARY KEY,
          source_dataset TEXT,
          source_path TEXT,
          title TEXT,
          case_number TEXT,
          court TEXT,
          decision_date TEXT,
          case_name TEXT,
          case_type TEXT,
          full_text TEXT NOT NULL,
          text_hash TEXT NOT NULL
        );
        CREATE VIRTUAL TABLE precedents_fts USING fts5(
          canonical_id UNINDEXED,
          full_text,
          tokenize='unicode61'
        );
        INSERT INTO precedents VALUES
          ('same-sim','lawkey/test','same.pdf','익명 처리된 사건','same','법원','','same','case','전자정보 증거능력 판단 본문','hash-same'),
          ('password-bypass','lawkey/test','password.pdf','익명 처리된 사건','password','법원','','password','case','압수수색 절차 적법성 판단 본문','hash-password'),
          ('height-noise','lawkey/test','height.pdf','신체 키 성장 사건','height','법원','','height','case','군 복무 중 신체 성장 상담','hash-height');
        INSERT INTO precedents_fts(canonical_id, full_text)
          SELECT canonical_id, full_text FROM precedents;
        """
    )
    taxonomy = LegalTaxonomy.default()
    ensure_event_frame_schema(conn)
    upsert_event_frames(
        conn,
        [
            StoredEventFrame(
                frame_id="same-sim#frame1",
                doc_id="same-sim",
                chunk_id="same-sim#chunk1",
                frame=extract_legal_event_frames("검찰이 피의자 유심을 뽑아 별도 보관한 전자정보 증거 사건", taxonomy)[0],
                text="검찰 유심 분리 전자정보 증거",
            ),
            StoredEventFrame(
                frame_id="password-bypass#frame1",
                doc_id="password-bypass",
                chunk_id="password-bypass#chunk1",
                frame=extract_legal_event_frames("수사기관이 피의자 비밀번호를 해킹함", taxonomy)[0],
                text="수사기관 비밀번호 해킹 전자정보 접근",
            ),
            StoredEventFrame(
                frame_id="height-noise#frame1",
                doc_id="height-noise",
                chunk_id="height-noise#chunk1",
                frame=extract_legal_event_frames("군 복무 중 신체 키와 체격 성장에 관한 상담", taxonomy)[0],
                text="신체 키 성장 사건",
            ),
        ],
    )
    conn.commit()
    conn.close()
    profile = ProductProfile(
        key="lawkey",
        name="Lawkey",
        db_path=db_path,
        db_shape="precedents",
        languages=("ko",),
        default_language="ko",
        theme="lawkey",
        safety_notice="notice",
    )

    rows = search_documents(profile, "경찰이 유심을 뽑음", limit=4, language="ko")
    ids = [row.canonical_id for row in rows]

    assert ids[:2] == ["same-sim", "password-bypass"]
    assert "height-noise" not in ids


def test_lawkey_event_frame_expansion_scans_beyond_initial_doc_id_slice(tmp_path):
    db_path = tmp_path / "lawkey.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE precedents (
          canonical_id TEXT PRIMARY KEY,
          source_dataset TEXT,
          source_path TEXT,
          title TEXT,
          case_number TEXT,
          court TEXT,
          decision_date TEXT,
          case_name TEXT,
          case_type TEXT,
          full_text TEXT NOT NULL,
          text_hash TEXT NOT NULL
        );
        CREATE VIRTUAL TABLE precedents_fts USING fts5(
          canonical_id UNINDEXED,
          full_text,
          tokenize='unicode61'
        );
        INSERT INTO precedents VALUES
          ('seed-related','lawkey/test','seed.pdf','질문 표면 seed','seed','법원','','seed','case','경찰 카톡 로그인 합법 관련 일반 자료','hash-seed'),
          ('zzz-target-frame','lawkey/test','target.pdf','익명화 전자정보 사건','2021노1520','서울고등법원','','target','case','익명화된 전자정보 압수수색 절차 사건 본문','hash-target');
        INSERT INTO precedents_fts(canonical_id, full_text)
          SELECT canonical_id, full_text FROM precedents;
        """
    )
    taxonomy = LegalTaxonomy.default()
    ensure_event_frame_schema(conn)
    noise_frames = [
        StoredEventFrame(
            frame_id=f"aaa-noise-{index:03d}#frame1",
            doc_id=f"aaa-noise-{index:03d}",
            chunk_id=f"aaa-noise-{index:03d}#chunk1",
            frame=extract_legal_event_frames("군 복무 중 신체 키와 체격 성장에 관한 상담", taxonomy)[0],
            text="신체 키 성장 사건",
        )
        for index in range(700)
    ]
    upsert_event_frames(
        conn,
        [
            *noise_frames,
            StoredEventFrame(
                frame_id="zzz-target-frame#frame1",
                doc_id="zzz-target-frame",
                chunk_id="zzz-target-frame#chunk1",
                frame=extract_legal_event_frames("검사가 유심칩을 공기계에 꽂아 카카오톡 계정에 접속한 전자정보 증거 사건", taxonomy)[0],
                text="검사 유심 공기계 카카오톡 계정 접속",
            ),
        ],
    )
    conn.commit()
    conn.close()
    profile = ProductProfile(
        key="lawkey",
        name="Lawkey",
        db_path=db_path,
        db_shape="precedents",
        languages=("ko",),
        default_language="ko",
        theme="lawkey",
        safety_notice="notice",
    )

    rows = search_documents(profile, "경찰이 피의자 유심 빼서 카톡 로그인하는거 합법임?", limit=2, language="ko")

    assert "zzz-target-frame" in [row.canonical_id for row in rows]


def test_lawkey_pairwise_and_variants_recover_late_multi_term_match_from_or_noise(tmp_path):
    db_path = tmp_path / "lawkey-pairwise.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE precedents (
          canonical_id TEXT PRIMARY KEY,
          source_dataset TEXT,
          source_path TEXT,
          title TEXT,
          case_number TEXT,
          court TEXT,
          decision_date TEXT,
          case_name TEXT,
          case_type TEXT,
          full_text TEXT
        );
        CREATE VIRTUAL TABLE precedents_fts USING fts5(canonical_id, full_text);
        """
    )
    for index in range(120):
        canonical_id = f"noise-{index:03d}"
        text = "유심 일반 사건"
        conn.execute(
            "INSERT INTO precedents VALUES (?, '', '', '', '', '', '', '', '', ?)",
            (canonical_id, text),
        )
        conn.execute("INSERT INTO precedents_fts VALUES (?, ?)", (canonical_id, text))
    conn.execute(
        "INSERT INTO precedents VALUES ('target', '', '', '', '', '', '', '', '', '유심 카카오톡 전자정보')"
    )
    conn.execute("INSERT INTO precedents_fts VALUES ('target', '유심 카카오톡 전자정보')")
    conn.commit()
    conn.close()
    profile = ProductProfile(
        key="lawkey",
        name="Lawkey",
        db_path=db_path,
        db_shape="precedents",
        languages=("ko",),
        default_language="ko",
        theme="lawkey",
        safety_notice="notice",
    )

    rows = search_documents(profile, "유심 카카오톡 공기계", limit=5, language="ko")

    assert rows[0].canonical_id == "target"


def test_lawkey_long_query_pair_variants_are_balanced_instead_of_all_anchored_on_first_term():
    profile = ProductProfile(
        key="lawkey",
        name="Lawkey",
        db_path=Path("unused.sqlite3"),
        db_shape="precedents",
        languages=("ko",),
        default_language="ko",
        theme="lawkey",
        safety_notice="notice",
    )

    expansion = describe_query_expansion(
        profile,
        "휴대폰 유심 공기계 카카오톡 압수수색 영장 범위",
    )
    pair_variants = [
        item for item in expansion["queryVariants"] if item["label"].startswith("lawkey_surface_pair_")
    ]

    assert len(pair_variants) == 6
    assert any('"유심" AND "공기계"' == item["fts"] for item in pair_variants)
    assert any('"공기계" AND "카카오톡"' == item["fts"] for item in pair_variants)
    assert len({item["label"].split("_")[-2] for item in pair_variants}) > 1
