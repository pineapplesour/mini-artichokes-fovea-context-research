# 내구성 벤치마크 실행 감독기

`tools/run_durable_benchmark.py`는 벤치마크의 질문, 검색, 모델, 답변, 채점 로직을 바꾸지 않는다. 기존 direct, frozen beta6, universal 러너를 공개 manifest의 한 case씩 `--case-id --resume`으로 실행하고 운영 상태만 별도 원장에 저장한다.

## 보존 계약

- `results/*.json`의 유효한 기존 산출물은 그대로 채택하며 다시 실행하지 않는다.
- 한 case가 끝날 때마다 산출물 유효성을 검사하고 config epoch를 기록한다.
- 감독기나 자식 프로세스가 중단되면 재시작 시 유효 산출물을 건너뛰고 첫 미완료 case부터 계속한다.
- 손상된 부분 JSON과 재시도 대상 오류 산출물은 `runtime/failed_results/`에 보존한 뒤 같은 case만 재시도한다.
- pause와 stop은 기본적으로 현재 case를 끝낸 다음 안전 경계에서 적용한다. `--cancel-current`만 현재 자식 process group을 종료한다.
- 설정 변경은 현재 case를 바꾸지 않고 다음 case부터 적용된다. 각 case의 설정은 `runtime/case_epochs.jsonl`에 남는다.
- 감독기 추가 자체는 기존 결과의 비교 계약이나 유효성을 바꾸지 않는다.
- DB를 쓰는 공식 실행은 `databaseAttestation`을 켜서 기존 artifact 채택이나 자식 실행보다 먼저 DB snapshot을 검증한다. 경로가 존재한다는 사실만으로는 충분하지 않다.

## 실행 spec

```json
{
  "schemaVersion": 1,
  "arm": "universal",
  "publicPath": "benchmarks/unified/mcq_tcm_kuksiwon81_unique92.public.json",
  "outputDir": "runs/example/universal",
  "dbPath": "/absolute/path/to/the/official.sqlite3",
  "databaseAttestation": {
    "required": true,
    "mode": "sampled_sha256_v1",
    "expectedSha256": "<immutable-release full-file SHA-256>",
    "expectedSizeBytes": 17287352320,
    "expectedSampleSha256": "<deterministic runtime sample SHA-256>"
  },
  "settings": {
    "model": "gpt-5.6-luna",
    "candidateLimit": 40,
    "evidenceLimit": 12
  },
  "environment": {
    "UNIVERSAL_EVAL_LLM_PROVIDER": "codex_exec",
    "UNIVERSAL_EVAL_CODEX_REASONING_EFFORT": "low",
    "UNIVERSAL_EVAL_CODEX_VERBOSITY": "low",
    "UNIVERSAL_EVAL_CODEX_MAX_ATTEMPTS": "2",
    "UNIVERSAL_EVAL_CODEX_WORKER_THREADS": "1"
  },
  "operational": {
    "pollSeconds": 1,
    "maxAttempts": 2,
    "childTimeoutSeconds": 0,
    "retryErrorArtifacts": true,
    "terminationGraceSeconds": 10
  }
}
```

arm별 실시간 변경 가능 설정은 다음과 같다.

- `direct`: `model`, `timeoutSeconds`
- `beta6`: `model`, `baselineRef`, `limit`, `analysisMode`
- `universal`: `model`, `candidateLimit`, `evidenceLimit`

실험용 러너도 `arm: "custom"`과 shell을 거치지 않는 `runnerCommand` argv 배열로 같은 내구성 계약을 사용할 수 있다. `{publicPath}`, `{outputDir}`, `{dbPath}`, `{caseId}`와 `settings`의 scalar key를 placeholder로 쓴다. 실행 파일과 인수는 신뢰할 수 있는 로컬 spec에 명시하며, 감독기는 문자열을 shell command로 평가하지 않는다.

API key 같은 secret은 spec이나 control 원장에 저장할 수 없다. provider와 decoding 관련 비밀이 아닌 환경 설정만 허용된다.

### DB snapshot attestation

- `full_sha256`: 작은 DB의 전체 파일을 스트리밍 SHA-256으로 검증한다. `mode`를 생략하면 이 방식이다.
- `sampled_sha256_v1`: multi-GiB DB의 정확한 파일 크기와 파일 전체에 균등하게 배치된 16개 256KiB span을 검증한다. `expectedSha256`은 immutable release의 전체 snapshot 정체를 기록하고, 실제 빠른 검증은 `expectedSampleSha256`과 크기로 수행한다.
- 성공/실패 영수증은 `runtime/database_attestation.json`에 원자적으로 저장된다. 성공 영수증의 path, size, inode, device, mtime 및 기대값이 모두 같으면 재시작 시 재사용한다.
- snapshot이 다르면 기존 `results/*.json`이 있어도 채택하지 않고, 자식/model call 전에 실패한다. 잘못된 DB 결과를 올바른 seed와 섞지 않는다.
- 이 검증은 저장소 형식/파일 정체만 확인하며 subject, benchmark, 질문, 정답이나 검색 정책을 보지 않는다.

## 실행과 실시간 확인

```bash
python3 tools/run_durable_benchmark.py run --spec /path/to/durable_spec.json
python3 tools/run_durable_benchmark.py status --output-dir /path/to/arm-output
```

실시간 상태는 `runtime/status.json`에도 원자적으로 갱신된다. 현재 case, artifact, 단계, attempt, PID/PGID, 경과시간, 완료/오류/대기 수, config epoch와 control revision을 확인할 수 있다.

## pause, stop, 이어하기

```bash
python3 tools/run_durable_benchmark.py control --output-dir /path/to/arm-output --state paused
python3 tools/run_durable_benchmark.py control --output-dir /path/to/arm-output --state running
python3 tools/run_durable_benchmark.py control --output-dir /path/to/arm-output --state stopped
python3 tools/run_durable_benchmark.py control --output-dir /path/to/arm-output --state stopped --cancel-current
```

graceful stop 뒤에는 control을 `running`으로 바꾸고 같은 `run --spec` 명령을 다시 실행하면 된다. 감독기 자체가 비정상 종료된 경우에도 같은 명령만 다시 실행한다.

## 다음 case부터 설정 변경

```bash
python3 tools/run_durable_benchmark.py control \
  --output-dir /path/to/arm-output \
  --set candidateLimit=48 \
  --set evidenceLimit=10
```

운영 설정도 다음 경계부터 변경할 수 있다.

```bash
python3 tools/run_durable_benchmark.py control \
  --output-dir /path/to/arm-output \
  --operational pollSeconds=2 \
  --operational maxAttempts=3
```

`runtime/events.jsonl`, `config_epochs.jsonl`, `case_epochs.jsonl`, `artifact_epochs.jsonl`, `attempts.json`이 복구와 감사에 필요한 전체 원장이다.
