from __future__ import annotations

import hashlib
import json

from tools.prompt_identity import canonical_json_sha256, prompt_identity, text_sha256


def test_prompt_identity_binds_source_item_raw_prompt_transform_and_exact_model_input(tmp_path):
    builder = tmp_path / "builder.py"
    builder.write_text("def build(value): return value + '!'\n", encoding="utf-8")
    manifest = {
        "benchmarkId": "open.example.v1",
        "sourceBenchmarkId": "mcq.example.v1",
        "cases": [{"id": "q-1", "prompt": "A하면 일어나는 일은?"}],
    }
    case = manifest["cases"][0]
    model_input = "보기 없이 답하라.\nA하면 일어나는 일은?"

    identity = prompt_identity(
        manifest=manifest,
        case=case,
        model_input=model_input,
        builder_id="open_response_query_v1",
        builder_source=builder,
    )

    assert identity["sourceItemId"] == "q-1"
    assert identity["publicPromptSha256"] == hashlib.sha256(case["prompt"].encode()).hexdigest()
    assert identity["publicCasePayloadSha256"] == canonical_json_sha256(case)
    assert identity["publicManifestCanonicalSha256"] == canonical_json_sha256(manifest)
    assert identity["modelInputSha256"] == text_sha256(model_input)
    assert identity["builderSourceSha256"] == hashlib.sha256(builder.read_bytes()).hexdigest()
    assert json.dumps(identity, ensure_ascii=False)
