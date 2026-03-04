# Scaffold開発サイクル基盤 完成計画

## TL;DR

> **Quick Summary**: Epic Issue #1〜#10の未完了分をすべて実装し、Scaffoldの証跡契約中心開発サイクルを1 issueで端から端まで再現可能にする。
> 
> **Deliverables**:
> - 5つの新規gate validator（research/spec/issue-targets/bot-iteration/adr-index） + テスト + スキーマ
> - ドリフト検知validator (FR-5) + テスト + スキーマ
> - Waiver/Exception契約（スキーマ + validator + テンプレート）
> - review系validator共有ライブラリ抽出 + test-review/final-review CIランナー
> - テンプレート充実（PRD/Epic/Issue/ADR）
> - CI gate workflow + 消費者向けサンプルworkflow + 運用ドキュメント
> - Git remote設定 + 初回push
> 
> **Estimated Effort**: Large
> **Parallel Execution**: YES - 5 waves
> **Critical Path**: T1(shared lib) → T5-T8(validators) → T13(drift) → T15(CI workflow) → T17(ops docs) → Final

---

## Context

### Original Request
Epicで定義された開発サイクル基盤のIssue #1〜#10を本格的に実装する。未整備のIssue（#1, #8, #9, #10）と部分実装のIssue（#4-#7のワークフロー統合）を完成させる。

### Interview Summary
**Key Discussions**:
- スコープ: 未整備Issue全て + 部分実装の完成 + ドリフト検知 + Git remote
- Tooling (install/sync/migrate) は除外
- 既存validatorは完全実装だがワークフロー統合が不完全
- FR-5ドリフト検知はMust要件だが完全未実装

**Research Findings**:
- 3レビューvalidator (test/cycle/final) はほぼ同一コピー（4-6行差）→ 共有lib抽出推奨
- run_review_engine.pyはreview-cycle + review-evidence-linkのみ統合、test-review/final-reviewは未接続
- 全validatorが同一パターン: `_read_json → _build_result → main()`, argparse `--input/--output`, exit 0/2
- mypy strict対象は `framework/scripts/gates` と `tests/framework` のみ、`lib/` は対象外

### Metis Review
**Identified Gaps (addressed)**:
- FR-5 ドリフト検知の定義が曖昧 → issue change targets vs git diff パス集合比較に限定
- 3レビューvalidator共有lib化がスコープ未定 → スコープに含め、Wave 1で先行実施
- pyproject.toml の mypy files にlib/が未含 → lib/ロジック追加時に更新
- final-reviewのstatus判定非対称性 → 意図的設計としてドキュメント化
- run_review_engine.py (594行) の肥大化 → 新規CIランナーを別ファイルで作成
- framework/.github/workflows/ vs .github/workflows/ の位置づけ → Scaffold本体用と消費者向けサンプルを分離

---

## Work Objectives

### Core Objective
Scaffoldの証跡契約中心開発サイクルを完成させ、1つのissueで「要件定義→issue作成→見積→実装→レビューチェーン→PR作成→Botフィードバック→マージ」の全工程を再現可能にする。

### Concrete Deliverables
- 新規validator 6本 + テスト + スキーマ
- 共有ヘルパーライブラリ `framework/scripts/lib/gate_helpers.py`
- CIランナー 2本 (test-review, final-review)
- テンプレート 4本充実
- Waiver/Exceptionスキーマ + テンプレート
- CI workflow 2本 (Scaffold本体用gates, 消費者向けサンプル)
- 運用ドキュメント
- manifest.yaml全契約 `status: implemented`
- Git remote設定 + 初回push

### Definition of Done
- [x] `make verify` が exit 0 (lint + format + typecheck + schema-check + test)
- [x] manifest.yaml の全16契約が `status: implemented`（既存14 + drift-detection + waiver-exception）
- [x] 16/16 gate validator が存在し、テストとスキーマが揃っている
- [x] test-review → review-cycle → final-review のレビューチェーンが CI runner 経由で実行可能

### Must Have
- 全16契約のvalidator + test + schema 完備（既存14 + drift-detection + waiver-exception）
- FR-5 ドリフト検知（パス集合比較）
- review chain ワークフロー統合
- テンプレート充実（各50行以内）
- CI gate execution workflow
- Waiver/Exception schema + validator
- `make verify` 全パス

### Must NOT Have (Guardrails)
- 既存validatorの動作変更（新機能は新ファイルで）
- テンプレート50行超
- CI workflow内での実際のreview engine (codex/claude) 呼び出し
- waiver bypassの既存ゲートへの統合
- AIベースの意味的ドリフト分析
- 実際のGitHub API連携やWebhookハンドラ
- GitHub Rulesets/Branch Protectionの実設定
- tooling/ (install/sync/migrate) の実装
- 200行超の新規スクリプト（lib/分割で対応）

---

## Verification Strategy

> **ZERO HUMAN INTERVENTION** — ALL verification is agent-executed. No exceptions.

### Test Decision
- **Infrastructure exists**: YES
- **Automated tests**: YES (Tests-after — 既存パターン踏襲)
- **Framework**: `python3 -m unittest`
- **Pattern**: 各validatorに正常系 + 異常系テスト

### QA Policy
Every task MUST include agent-executed QA scenarios.
Evidence saved to `.sisyphus/evidence/task-{N}-{scenario-slug}.{ext}`.

- **Validators**: Bash — `python3 framework/scripts/gates/validate_xxx.py --input <json> --output /tmp/result.json && echo $?`
- **Schemas**: Bash — `check-jsonschema --schemafile <schema> <json>`
- **Quality**: Bash — `make verify`

---

## Execution Strategy

### Parallel Execution Waves

```text
Wave 1 (Foundation — shared lib + environment):
├── T1: Gate helper共有ライブラリ抽出 [deep]
├── T2: Git remote設定 + 初回push [quick]
├── T3: check-jsonschema インストール確認 + pyproject.toml更新 [quick]
└── T4: テンプレート充実 (PRD/Epic/Issue/ADR) [quick]

Wave 2 (Issue #1 validators — after T1,T3):
├── T5: validate_research_contract.py + test + schema [unspecified-high]
├── T6: validate_spec_quality.py + test + schema [unspecified-high]
├── T7: validate_issue_targets.py + test + schema [unspecified-high]
└── T8: 既存review validators共有lib移行 [deep]

Wave 3 (Review chain + Drift — after T1,T8):
├── T9: run_test_review.py CIランナー [unspecified-high]
├── T10: run_final_review.py CIランナー [unspecified-high]
├── T11: validate_pr_bot_iteration.py + test + schema [unspecified-high]
├── T12: validate_adr_index.py + test + schema [unspecified-high]
└── T13: validate_drift_detection.py + test + schema (FR-5) [deep]

Wave 4 (Waiver + CI + Docs — after T9-T13):
├── T14: Waiver/Exception契約 (schema + validator + test + template) [unspecified-high]
├── T15: Scaffold本体 CI gate workflow [unspecified-high]
├── T16: 消費者向けサンプルworkflow [quick]
└── T17: 運用ドキュメント + manifest.yaml最終更新 [writing]

Wave FINAL (After ALL tasks — parallel review):
├── F1: Plan compliance audit [oracle]
├── F2: Code quality review (make verify) [unspecified-high]
├── F3: Real QA — full review chain execution [unspecified-high]
└── F4: Scope fidelity check [deep]

Critical Path: T1 → T8 → T9/T10 → T15 → F1-F4
Parallel Speedup: ~65% faster than sequential
Max Concurrent: 5 (Wave 3)
```

### Dependency Matrix

| Task | Depends On | Blocks | Wave |
|---|---|---|---|
| T1 | — | T5-T8, T9-T13 | 1 |
| T2 | — | T15, T16 | 1 |
| T3 | — | T5-T7, T12 | 1 |
| T4 | — | T17 | 1 |
| T5 | T1, T3 | T17 | 2 |
| T6 | T1, T3 | T17 | 2 |
| T7 | T1, T3 | T13, T17 | 2 |
| T8 | T1 | T9, T10 | 2 |
| T9 | T8 | T15 | 3 |
| T10 | T8 | T15 | 3 |
| T11 | T1 | T15 | 3 |
| T12 | T1, T3 | T17 | 3 |
| T13 | T1, T7 | T15 | 3 |
| T14 | T1 | T17 | 4 |
| T15 | T2, T9, T10, T11, T13 | F1-F4 | 4 |
| T16 | T2, T15 | F1-F4 | 4 |
| T17 | T4, T5-T7, T12, T14 | F1-F4 | 4 |
| F1-F4 | ALL | — | FINAL |

### Agent Dispatch Summary

- **Wave 1**: 4 tasks — T1 `deep`, T2 `quick`, T3 `quick`, T4 `quick`
- **Wave 2**: 4 tasks — T5-T7 `unspecified-high`, T8 `deep`
- **Wave 3**: 5 tasks — T9-T11 `unspecified-high`, T12 `unspecified-high`, T13 `deep`
- **Wave 4**: 4 tasks — T14 `unspecified-high`, T15 `unspecified-high`, T16 `quick`, T17 `writing`
- **FINAL**: 4 tasks — F1 `oracle`, F2-F3 `unspecified-high`, F4 `deep`

---

## TODOs

> Implementation + Test = ONE Task. Never separate.
> EVERY task MUST have: Recommended Agent Profile + Parallelization info + QA Scenarios.
> **A task WITHOUT QA Scenarios is INCOMPLETE. No exceptions.**

- [x] 1. Gate Helper共有ライブラリ抽出 (gate_helpers.py)

  **What to do**:
  - `framework/scripts/lib/gate_helpers.py` を新規作成
  - 既存の3レビューvalidator (validate_test_review/review_cycle/final_review) から共通関数を抽出:
    - `error_dict()` — エラーdict生成（provider引数で呼び出し元を区別）
    - `read_json()` — 入力JSON読み込み + dict検証
    - `require_text()` — 必須文字列フィールド取得
    - `optional_text()` — 任意文字列フィールド取得
    - `require_object()` — 必須オブジェクトフィールド取得
    - `write_result()` — 結果JSON書き出し + exit code判定
    - `parse_gate_args()` — --input / --output 共通argparse
  - 型注釈: mypy strict互換 (from typing import Any, proper return types)
  - テスト: tests/framework/test_gate_helpers.py — 各ヘルパー関数の正常系 + 異常系
  - 注意: この時点では既存validatorは変更しない（T8で移行）
  - **import戦略** (重要): 既存validatorは `python3 framework/scripts/gates/validate_xxx.py` で直接実行されるため、gate_helpers.py 先頭に `sys.path` にリポジトリルートを追加する bootstrap を設ける:
    ```python
    import sys
    from pathlib import Path
    # リポジトリルートをsys.pathに追加して framework.scripts.lib をimport可能にする
    _REPO_ROOT = Path(__file__).resolve().parents[3]  # framework/scripts/lib/ -> repo root
    if str(_REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(_REPO_ROOT))
    ```
    または、各validator側でこのbootstrapを行う。T8の移行時に各validatorの先頭に追加する。
    既存パターン: `run_review_engine.py:1-12` の import 構造を参考。

  **Must NOT do**:
  - 既存validatorの動作変更
  - ビジネスロジック（status判定等）の抽出（各validatorに残す）
  - 200行超のファイル

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: 3つのvalidatorの共通パターンを精密に分析し正確にAPI設計する必要がある
  - **Skills**: []

  **Parallelization**:
  - Can Run In Parallel: YES
  - Parallel Group: Wave 1 (with T2, T3, T4)
  - Blocks: T5, T6, T7, T8, T9, T10, T11, T12, T13, T14
  - Blocked By: None

  **References**:
  - `framework/scripts/gates/validate_test_review.py:1-50` — 共通関数群の抽出元。3 review validatorで完全一致
  - `framework/scripts/gates/validate_review_cycle.py:1-50` — test_reviewとの差異は error() のprovider値のみ
  - `framework/scripts/gates/validate_final_review.py:1-50` — 同上
  - `framework/scripts/gates/validate_estimate_approval.py:10-26` — error/read_json の型シグネチャ参考
  - `tests/framework/test_validate_scope_lock.py:15-30` — テスト構造: _run() ヘルパー, tmpdir パターン

  **Acceptance Criteria**:
  - [x] framework/scripts/lib/gate_helpers.py が存在
  - [x] tests/framework/test_gate_helpers.py が存在
  - [x] python3 -m unittest tests/framework/test_gate_helpers.py → PASS
  - [x] mypy --strict framework/scripts/lib/gate_helpers.py → 0 errors
  - [x] ruff check framework/scripts/lib/gate_helpers.py → 0 violations

  **QA Scenarios:**
  Scenario: gate_helpersの関数がimport・テスト可能
    Tool: Bash
    Steps: PYTHONPATH=. python3 -c "from framework.scripts.lib.gate_helpers import read_json, require_text, error_dict, write_result, parse_gate_args; print('ok')"
           python3 -m unittest tests/framework/test_gate_helpers.py -v
           mypy --strict framework/scripts/lib/gate_helpers.py
    Expected: import成功, 全テストPASS, mypy 0 errors
    Evidence: .sisyphus/evidence/task-1-helpers-import.txt

  Scenario: 既存validatorに影響なし
    Tool: Bash
    Steps: python3 -m unittest tests/framework/test_validate_test_review.py tests/framework/test_validate_review_cycle.py tests/framework/test_validate_final_review.py -v
    Expected: 既存テスト全てPASS
    Evidence: .sisyphus/evidence/task-1-no-regression.txt

  **Commit**: YES
  - Message: refactor(gates): extract shared gate helpers to lib/gate_helpers.py
  - Files: framework/scripts/lib/gate_helpers.py, tests/framework/test_gate_helpers.py
  - Pre-commit: python3 -m unittest tests/framework/test_gate_helpers.py


- [x] 2. Git Remote設定 + 初回push

  **What to do**:
  - GitHubに Scaffold リポジトリを作成 (gh repo create)
  - ローカルリポジトリにremote originを設定
  - 既存コミットを全てpush (git push -u origin main)
  - push後に git remote -v と git log --oneline -5 で確認

  **Must NOT do**:
  - GitHub Rulesets/Branch Protectionの設定
  - GitHub Actionsの有効化設定（T15で対応）
  - force push

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: [git-master]

  **Parallelization**:
  - Can Run In Parallel: YES
  - Parallel Group: Wave 1 (with T1, T3, T4)
  - Blocks: T15, T16
  - Blocked By: None

  **References**:
  - `.git/config` — remote originが未設定であることを確認してから実行
  - `.github/workflows/quality.yml` — push後にCIが走ることを認識

  **Acceptance Criteria**:
  - [x] git remote -v に origin が表示
  - [x] git log origin/main --oneline -1 が最新コミットを表示
  - [x] gh repo view がリポジトリ情報を表示

  **QA Scenarios:**
  Scenario: Remote設定とpushが完了
    Tool: Bash
    Steps: gh auth status && git remote -v && git log origin/main --oneline -3 && gh repo view --json name,url
    Expected: origin設定済み, コミット一致, リポジトリ表示
    Evidence: .sisyphus/evidence/task-2-remote-setup.txt

  Scenario: Push後に既存CIが壊れていない
    Tool: Bash
    Steps: gh run list --limit 1 --json status,conclusion
    Expected: workflow runが存在, status=completed/in_progress
    Evidence: .sisyphus/evidence/task-2-ci-check.txt

  **Commit**: NO（git操作自体がタスク。コード変更なし）

- [x] 3. 環境整備: pyproject.toml mypy対象更新

  **What to do**:
  - pyproject.toml の [tool.mypy] セクションの files リストに framework/scripts/lib を追加
  - check-jsonschema がインストール済みか確認。未インストールなら pip install check-jsonschema
  - make verify を実行して既存品質ゲートが全てパスすることを確認

  **Must NOT do**:
  - mypy設定のstrict以外のオプション変更
  - ruff設定の変更
  - 他の依存ライブラリの追加

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - Can Run In Parallel: YES
  - Parallel Group: Wave 1 (with T1, T2, T4)
  - Blocks: T5, T6, T7, T12
  - Blocked By: None

  **References**:
  - `pyproject.toml` — [tool.mypy] の files リストに framework/scripts/lib を追加
  - `framework/scripts/lib/review_engine_stub.py` — 既存lib/ファイル。mypy対象に含まれることで型チェックが走る

  **Acceptance Criteria**:
  - [x] pyproject.toml の [tool.mypy] files に framework/scripts/lib が含まれる
  - [x] check-jsonschema --version が正常に実行される
  - [x] make verify → exit 0

  **QA Scenarios:**
  Scenario: mypy対象にlib/が含まれ型チェックが通る
    Tool: Bash
    Steps: grep 'framework/scripts/lib' pyproject.toml && mypy framework/scripts/lib/ && make verify
    Expected: grep一致, mypy 0 errors, make verify exit 0
    Evidence: .sisyphus/evidence/task-3-mypy-scope.txt

  Scenario: check-jsonschemaが利用可能
    Tool: Bash
    Steps: check-jsonschema --version
    Expected: バージョン表示
    Evidence: .sisyphus/evidence/task-3-jsonschema-check.txt

  **Commit**: YES
  - Message: chore: update pyproject.toml mypy scope for lib/
  - Files: pyproject.toml
  - Pre-commit: make verify

- [x] 4. テンプレート充実 (PRD/Epic/Issue/ADR)

  **What to do**:
  - 以下4テンプレートを充実（厐50行以内）:
    - framework/templates/prd/template.md: Problem, Users, Goals, FR表, Out of Scope, Acceptance Criteria, Risks, References
    - framework/templates/epic/template.md: Overview, Issues一覧, Scope, Dependencies, DoD
    - framework/templates/issue/template.md: Context, Change Targets, Expected Behavior, Scope, Acceptance Criteria, Test Plan, Dependencies
    - framework/templates/adr/template.md: Title(ADR-NNN), Status, Context, Decision, Consequences, References
  - 実際のPRD/Epicの構造を参考に再利用可能な骨格にする
  - issue template の Change Targets セクション: validate_issue_targets.py (T7) が検証する change_targets フィールドと整合

  **Must NOT do**:
  - 50行超のテンプレート
  - 具体的な内容（プレースホルダーのみ）
  - validatorロジックに依存する記述

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - Can Run In Parallel: YES
  - Parallel Group: Wave 1 (with T1, T2, T3)
  - Blocks: T17
  - Blocked By: None

  **References**:
  - `docs/prd/prd-scaffold-dev-cycle-v1.md` — 実PRD (248行)。テンプレート構造の参考
  - `docs/epics/epic-scaffold-dev-cycle-v1.md` — 実Epic (540行)。Issues一覧/Scopeの構造参考
  - `framework/templates/issue/template.md` — 現在11行。Change Targetsセクション追加必須
  - `framework/templates/prd/template.md` — 現在13行。FR表セクション追加

  **Acceptance Criteria**:
  - [x] 4つのテンプレートが全て更新済み
  - [x] 各テンプレート50行以下: wc -l framework/templates/*/template.md
  - [x] issue/template.md に Change Targets セクションが存在
  - [x] prd/template.md に Out of Scope と Acceptance Criteria が存在

  **QA Scenarios:**
  Scenario: テンプレートが充実され行数制限を満たす
    Tool: Bash
    Steps: wc -l framework/templates/*/template.md && grep 'Change Targets' framework/templates/issue/template.md && grep 'Out of Scope' framework/templates/prd/template.md
    Expected: 全ファイル50行以下, 必須セクション存在
    Evidence: .sisyphus/evidence/task-4-templates.txt

  Scenario: テンプレートにvalidator依存記述がない
    Tool: Bash
    Steps: grep -r 'validate_' framework/templates/ || echo 'clean'
    Expected: validator参照なし
    Evidence: .sisyphus/evidence/task-4-no-validator-refs.txt

  **Commit**: YES
  - Message: docs(templates): enrich PRD/Epic/Issue/ADR templates
  - Files: framework/templates/prd/template.md, framework/templates/epic/template.md, framework/templates/issue/template.md, framework/templates/adr/template.md
  - Pre-commit: wc -l framework/templates/*/template.md


- [x] 5. validate_research_contract.py + test + schema

  **What to do**:
  - `framework/scripts/gates/validate_research_contract.py` を新規作成
  - 入力: request_id, scope_id, run_id, artifact_path, research オブジェクト
  - researchオブジェクトの検証: artifact_ref(存在確認), created_at(存在), topics(1件以上の非空文字列配列)
  - gate_helpersの共通関数を使用 (read_json, require_text, require_object, write_result, parse_gate_args)
  - スキーマ: framework/.agent/schemas/gates/research-contract-result.schema.json
  - テスト: tests/framework/test_validate_research_contract.py
  - manifest.yaml の research-before-spec を status: implemented に更新し result_schema を追加

  **Must NOT do**:
  - research内容の意味的検証（品質判定なし、存在確認のみ）
  - ファイルシステムアクセス（artifact_refの文字列存在確認のみ）

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **Parallelization**:
  - Can Run In Parallel: YES
  - Parallel Group: Wave 2 (with T6, T7, T8)
  - Blocks: T17
  - Blocked By: T1, T3

  **References**:
  - `framework/scripts/gates/validate_estimate_approval.py` — 標準validatorパターン (164行)。_read_json/_require_text/_build_result/main 構造を踏襲
  - `framework/scripts/lib/gate_helpers.py` — T1で作成した共通ヘルパー。importして使用
  - `framework/.agent/schemas/gates/estimate-approval-result.schema.json` — スキーマ構造の参考。$schema, $id, required, properties の形式を踏襲
  - `tests/framework/test_validate_scope_lock.py` — テストパターン: subprocess実行 + tmpdir + JSON入出力
  - `framework/scripts/manifest.yaml:11-14` — research-before-spec 契約。status: planned → implemented に更新

  **Acceptance Criteria**:
  - [x] framework/scripts/gates/validate_research_contract.py が存在
  - [x] framework/.agent/schemas/gates/research-contract-result.schema.json が存在
  - [x] tests/framework/test_validate_research_contract.py が存在
  - [x] python3 -m unittest tests/framework/test_validate_research_contract.py → PASS
  - [x] check-jsonschema でスキーマ自体が有効なJSON Schemaであることを確認
  - [x] manifest.yaml の research-before-spec が status: implemented

  **QA Scenarios:**
  Scenario: 正常なresearch入力でpass
    Tool: Bash
    Steps: 正常なresearch JSONを作成し python3 framework/scripts/gates/validate_research_contract.py --input /tmp/test-input.json --output /tmp/test-output.json && echo $?
    Expected: exit 0, output JSONのstatus=pass
    Evidence: .sisyphus/evidence/task-5-research-pass.txt

  Scenario: researchオブジェクト欠損でfail
    Tool: Bash
    Steps: researchフィールド欠損のJSONを入力し validator実行
    Expected: exit 2, output JSONのstatus=fail
    Evidence: .sisyphus/evidence/task-5-research-fail.txt

  **Commit**: YES
  - Message: feat(gates): add research-before-spec validator
  - Files: framework/scripts/gates/validate_research_contract.py, framework/.agent/schemas/gates/research-contract-result.schema.json, tests/framework/test_validate_research_contract.py, framework/scripts/manifest.yaml
  - Pre-commit: python3 -m unittest tests/framework/test_validate_research_contract.py

- [x] 6. validate_spec_quality.py + test + schema

  **What to do**:
  - `framework/scripts/gates/validate_spec_quality.py` を新規作成
  - 入力: request_id, scope_id, run_id, artifact_path, spec オブジェクト
  - specオブジェクトの検証:
    - artifact_ref(存在確認)
    - has_acceptance_criteria(boolean, true必須)
    - has_out_of_scope(boolean, true必須)
    - acceptance_criteria_count(integer, 1以上)
  - gate_helpersの共通関数を使用
  - スキーマ: framework/.agent/schemas/gates/spec-quality-result.schema.json
  - テスト: tests/framework/test_validate_spec_quality.py
  - manifest.yaml の spec-quality-minimum を status: implemented に更新

  **Must NOT do**:
  - PRD/Epicの内容品質の意味的判定
  - ファイル読み込み（メタデータのみ検証）

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **Parallelization**:
  - Can Run In Parallel: YES
  - Parallel Group: Wave 2 (with T5, T7, T8)
  - Blocks: T17
  - Blocked By: T1, T3

  **References**:
  - `framework/scripts/gates/validate_estimate_approval.py` — 標準パターン。入力検証 + _build_result 構造
  - `framework/scripts/lib/gate_helpers.py` — 共通ヘルパー (T1)
  - `framework/.agent/schemas/gates/estimate-approval-result.schema.json` — スキーマ構造参考
  - `framework/scripts/manifest.yaml:16-19` — spec-quality-minimum 契約
  - `docs/prd/prd-scaffold-dev-cycle-v1.md` — FR-1要件: 「計測可能なacceptance criteriaとout-of-scopeセクション」

  **Acceptance Criteria**:
  - [x] framework/scripts/gates/validate_spec_quality.py が存在
  - [x] framework/.agent/schemas/gates/spec-quality-result.schema.json が存在
  - [x] tests/framework/test_validate_spec_quality.py が存在
  - [x] python3 -m unittest tests/framework/test_validate_spec_quality.py → PASS
  - [x] manifest.yaml の spec-quality-minimum が status: implemented

  **QA Scenarios:**
  Scenario: ACとOoSがあるspecでpass
    Tool: Bash
    Steps: has_acceptance_criteria=true, has_out_of_scope=true, acceptance_criteria_count=3 の入力でvalidator実行
    Expected: exit 0, status=pass
    Evidence: .sisyphus/evidence/task-6-spec-pass.txt

  Scenario: AC欠損でfail
    Tool: Bash
    Steps: has_acceptance_criteria=false の入力でvalidator実行
    Expected: exit 2, status=fail
    Evidence: .sisyphus/evidence/task-6-spec-fail.txt

  **Commit**: YES
  - Message: feat(gates): add spec-quality-minimum validator
  - Files: framework/scripts/gates/validate_spec_quality.py, framework/.agent/schemas/gates/spec-quality-result.schema.json, tests/framework/test_validate_spec_quality.py, framework/scripts/manifest.yaml
  - Pre-commit: python3 -m unittest tests/framework/test_validate_spec_quality.py

- [x] 7. validate_issue_targets.py + test + schema

  **What to do**:
  - `framework/scripts/gates/validate_issue_targets.py` を新規作成
  - 入力: request_id, scope_id, run_id, artifact_path, issue オブジェクト
  - issueオブジェクトの検証:
    - issue_id(存在確認)
    - change_targets(1件以上の非空文字列配列 — ファイルパスまたはディレクトリパス)
    - estimated_scope(存在確認)
  - gate_helpersの共通関数を使用
  - スキーマ: framework/.agent/schemas/gates/issue-targets-result.schema.json
  - テスト: tests/framework/test_validate_issue_targets.py
  - manifest.yaml の issue-change-targets-declared を status: implemented に更新

  **Must NOT do**:
  - change_targetsのパス実在確認（文字列存在確認のみ）
  - overlap-safetyとの統合（それは別validator）

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **Parallelization**:
  - Can Run In Parallel: YES
  - Parallel Group: Wave 2 (with T5, T6, T8)
  - Blocks: T13, T17
  - Blocked By: T1, T3

  **References**:
  - `framework/scripts/gates/validate_estimate_approval.py` — 標準パターン
  - `framework/scripts/gates/validate_overlap_safety.py` — change_targetsフィールドの消費側。issue_targetsが宣言したパスをoverlap-safetyが比較する関係
  - `framework/scripts/lib/gate_helpers.py` — 共通ヘルパー (T1)
  - `framework/scripts/manifest.yaml:21-24` — issue-change-targets-declared 契約

  **Acceptance Criteria**:
  - [x] framework/scripts/gates/validate_issue_targets.py が存在
  - [x] framework/.agent/schemas/gates/issue-targets-result.schema.json が存在
  - [x] tests/framework/test_validate_issue_targets.py が存在
  - [x] python3 -m unittest tests/framework/test_validate_issue_targets.py → PASS
  - [x] manifest.yaml の issue-change-targets-declared が status: implemented

  **QA Scenarios:**
  Scenario: change_targetsありでpass
    Tool: Bash
    Steps: change_targets=["src/auth.py", "tests/test_auth.py"] の入力でvalidator実行
    Expected: exit 0, status=pass
    Evidence: .sisyphus/evidence/task-7-targets-pass.txt

  Scenario: change_targets空配列でfail
    Tool: Bash
    Steps: change_targets=[] の入力でvalidator実行
    Expected: exit 2, status=fail
    Evidence: .sisyphus/evidence/task-7-targets-fail.txt

  **Commit**: YES
  - Message: feat(gates): add issue-change-targets-declared validator
  - Files: framework/scripts/gates/validate_issue_targets.py, framework/.agent/schemas/gates/issue-targets-result.schema.json, tests/framework/test_validate_issue_targets.py, framework/scripts/manifest.yaml
  - Pre-commit: python3 -m unittest tests/framework/test_validate_issue_targets.py

- [x] 8. 既存review validators共有lib移行

  **What to do**:
  - validate_test_review.py, validate_review_cycle.py, validate_final_review.py の3つを更新
  - 各validatorの先頭50行の共通関数群（`_error`, `_read_json`, `_require_text`, `_optional_text`, `_require_object`）を削除
  - 代わりに各validator先頭に sys.path bootstrap を追加し、gate_helpers からimport:
    ```python
    import sys
    from pathlib import Path
    _REPO_ROOT = Path(__file__).resolve().parents[3]
    if str(_REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(_REPO_ROOT))
    from framework.scripts.lib.gate_helpers import error_dict, read_json, require_text, optional_text, require_object, write_result, parse_gate_args
    ```
  - 各validatorのビジネスロジック (_build_result, main) はそのまま維持
  - 既存テストが全てパスすることを確認

  **Must NOT do**:
  - validatorのビジネスロジック変更
  - exit codeの変更
  - スキーマの変更
  - validate_estimate_approval.py等の他validatorの移行（このタスクでは3つのみ）

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: 3ファイル同時変更で既存動作保存が必須。精密なリファクタリング
  - **Skills**: []

  **Parallelization**:
  - Can Run In Parallel: YES
  - Parallel Group: Wave 2 (with T5, T6, T7)
  - Blocks: T9, T10
  - Blocked By: T1

  **References**:
  - `framework/scripts/gates/validate_test_review.py` — 移行対象 (143行)。先頭50行が共通関数、後半がビジネスロジック
  - `framework/scripts/gates/validate_review_cycle.py` — 移行対象 (143行)。test_reviewとの差異: `_error()` のprovider値
  - `framework/scripts/gates/validate_final_review.py` — 移行対象 (143行)。status判定ロジックに非対称性あり（意図的）
  - `framework/scripts/lib/gate_helpers.py` — T1で作成した共通ヘルパー
  - `tests/framework/test_validate_test_review.py` — 既存テスト。移行後も全テストパス必須

  **Acceptance Criteria**:
  - [x] 3つのvalidatorがgate_helpersからimportしている
  - [x] 3つのvalidator内に共通関数のローカル定義がない
  - [x] python3 -m unittest tests/framework/test_validate_test_review.py tests/framework/test_validate_review_cycle.py tests/framework/test_validate_final_review.py → ALL PASS
  - [x] ruff check 対象ファイル → 0 violations

  **QA Scenarios:**
  Scenario: 移行後の3 validatorが全テストパス
    Tool: Bash
    Steps: python3 -m unittest tests/framework/test_validate_test_review.py tests/framework/test_validate_review_cycle.py tests/framework/test_validate_final_review.py -v
    Expected: 全テストPASS、動作変更なし
    Evidence: .sisyphus/evidence/task-8-review-migration.txt

  Scenario: 共通関数のローカル定義が消えている
    Tool: Bash
    Steps: grep -c 'def _read_json' framework/scripts/gates/validate_test_review.py framework/scripts/gates/validate_review_cycle.py framework/scripts/gates/validate_final_review.py
    Expected: 各ファイルで0件マッチ
    Evidence: .sisyphus/evidence/task-8-no-local-defs.txt

  **Commit**: YES
  - Message: refactor(gates): migrate review validators to shared lib
  - Files: framework/scripts/gates/validate_test_review.py, framework/scripts/gates/validate_review_cycle.py, framework/scripts/gates/validate_final_review.py
  - Pre-commit: python3 -m unittest tests/framework/test_validate_test_review.py tests/framework/test_validate_review_cycle.py tests/framework/test_validate_final_review.py


- [x] 9. run_test_review.py CIランナー

  **What to do**:
  - `framework/scripts/ci/run_test_review.py` を新規作成
  - test-review専用のCIランナー:
    - review engineを呼び出してtest-reviewスコープで実行
    - 結果を validate_test_review.py + validate_review_evidence.py で検証
    - 成果物を .scaffold/review_results/<scope_id>/<run_id>/test-review/ に保存
  - run_review_engine.pyの構造を参考するが、別ファイルとして作成（既存594行に追加しない）
  - argparse: --engine, --scope-id, --run-id, --base-ref
  - テスト: tests/framework/test_run_test_review.py

  **Must NOT do**:
  - run_review_engine.pyの変更
  - 実際のreview engine (codex/claude) の呼び出しをCIで実行（stubでテスト）
  - 200行超のスクリプト

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **Parallelization**:
  - Can Run In Parallel: YES
  - Parallel Group: Wave 3 (with T10, T11, T12, T13)
  - Blocks: T15
  - Blocked By: T8

  **References**:
  - `framework/scripts/ci/run_review_engine.py:1-60` — 既存CIランナー (594行)。RunnerConfig/ReviewContext dataclass、ディレクトリ構造、バリデーター呼び出しパターンを参考
  - `framework/scripts/gates/validate_test_review.py` — このランナーが呼び出すvalidator
  - `framework/scripts/gates/validate_review_evidence.py` — evidence-link検証も実行
  - `framework/scripts/lib/review_engine_stub.py` — テスト時に使用するreview engine stub
  - `tests/framework/test_run_review_engine.py` — 既存CIランナーテストのパターン参考

  **Acceptance Criteria**:
  - [x] framework/scripts/ci/run_test_review.py が存在
  - [x] tests/framework/test_run_test_review.py が存在
  - [x] python3 -m unittest tests/framework/test_run_test_review.py → PASS
  - [x] wc -l framework/scripts/ci/run_test_review.py ≤ 200

  **QA Scenarios:**
  Scenario: test-reviewランナーがヘルプ表示できる
    Tool: Bash
    Steps: python3 framework/scripts/ci/run_test_review.py --help
    Expected: 使用法が表示される（--engine, --scope-id等）
    Evidence: .sisyphus/evidence/task-9-help.txt

  Scenario: テストがPASS
    Tool: Bash
    Steps: python3 -m unittest tests/framework/test_run_test_review.py -v
    Expected: 全テストPASS
    Evidence: .sisyphus/evidence/task-9-tests.txt

  **Commit**: YES
  - Message: feat(ci): add test-review CI runner
  - Files: framework/scripts/ci/run_test_review.py, tests/framework/test_run_test_review.py
  - Pre-commit: python3 -m unittest tests/framework/test_run_test_review.py

- [x] 10. run_final_review.py CIランナー

  **What to do**:
  - `framework/scripts/ci/run_final_review.py` を新規作成
  - final-review専用のCIランナー:
    - review engineを呼び出してfinal-reviewスコープで実行
    - 結果を validate_final_review.py + validate_review_evidence.py で検証
    - 成果物を .scaffold/review_results/<scope_id>/<run_id>/final-review/ に保存
  - run_test_review.py (T9) と同一構造。scopeとvalidatorのみ異なる
  - テスト: tests/framework/test_run_final_review.py

  **Must NOT do**:
  - run_review_engine.pyの変更
  - 200行超のスクリプト

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **Parallelization**:
  - Can Run In Parallel: YES
  - Parallel Group: Wave 3 (with T9, T11, T12, T13)
  - Blocks: T15
  - Blocked By: T8

  **References**:
  - `framework/scripts/ci/run_test_review.py` — T9で作成した同構造ランナー。scopeとvalidatorをfinal-review用に変更
  - `framework/scripts/ci/run_review_engine.py` — 既存ランナー参考
  - `framework/scripts/gates/validate_final_review.py` — 呼び出すvalidator
  - `tests/framework/test_run_test_review.py` — テストパターン参考 (T9)

  **Acceptance Criteria**:
  - [x] framework/scripts/ci/run_final_review.py が存在
  - [x] tests/framework/test_run_final_review.py が存在
  - [x] python3 -m unittest tests/framework/test_run_final_review.py → PASS
  - [x] wc -l framework/scripts/ci/run_final_review.py ≤ 200

  **QA Scenarios:**
  Scenario: final-reviewランナーがヘルプ表示できる
    Tool: Bash
    Steps: python3 framework/scripts/ci/run_final_review.py --help
    Expected: 使用法が表示される
    Evidence: .sisyphus/evidence/task-10-help.txt

  Scenario: テストがPASS
    Tool: Bash
    Steps: python3 -m unittest tests/framework/test_run_final_review.py -v
    Expected: 全テストPASS
    Evidence: .sisyphus/evidence/task-10-tests.txt

  **Commit**: YES
  - Message: feat(ci): add final-review CI runner
  - Files: framework/scripts/ci/run_final_review.py, tests/framework/test_run_final_review.py
  - Pre-commit: python3 -m unittest tests/framework/test_run_final_review.py

- [x] 11. validate_pr_bot_iteration.py + test + schema

  **What to do**:
  - `framework/scripts/gates/validate_pr_bot_iteration.py` を新規作成
  - 入力: request_id, scope_id, run_id, artifact_path, bot_feedback オブジェクト
  - bot_feedbackオブジェクトの検証:
    - pr_url(存在確認)
    - iterations(1件以上の配列)
    - 各iteration: bot_name, feedback_ref, resolution_status(addressed/deferred/rejected), resolution_ref
    - 全iterationがresolution_statusを持つことの検証
  - gate_helpersの共通関数を使用
  - スキーマ: framework/.agent/schemas/gates/pr-bot-iteration-result.schema.json
  - テスト: tests/framework/test_validate_pr_bot_iteration.py
  - manifest.yaml の pr-bot-iteration を status: implemented に更新

  **Must NOT do**:
  - 実際のbot API呼び出し
  - PR URLの形式検証（文字列存在のみ）

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **Parallelization**:
  - Can Run In Parallel: YES
  - Parallel Group: Wave 3 (with T9, T10, T12, T13)
  - Blocks: T15
  - Blocked By: T1

  **References**:
  - `framework/scripts/gates/validate_estimate_approval.py` — 標準パターン
  - `framework/scripts/lib/bot_stub.py` — bot adapter stub (115行)。bot_feedbackの入出力形式参考
  - `framework/.agent/schemas/adapters/bot-feedback-batch.schema.json` — bot feedbackスキーマ。iterationsの構造参考
  - `framework/scripts/manifest.yaml:80-83` — pr-bot-iteration 契約
  - `framework/docs/contract/adapter-interfaces.md` — bot adapter契約ドキュメント

  **Acceptance Criteria**:
  - [x] framework/scripts/gates/validate_pr_bot_iteration.py が存在
  - [x] framework/.agent/schemas/gates/pr-bot-iteration-result.schema.json が存在
  - [x] tests/framework/test_validate_pr_bot_iteration.py が存在
  - [x] python3 -m unittest tests/framework/test_validate_pr_bot_iteration.py → PASS
  - [x] manifest.yaml の pr-bot-iteration が status: implemented

  **QA Scenarios:**
  Scenario: 全iterationがresolution済みでpass
    Tool: Bash
    Steps: iterationsに各resolution_statusがaddressedの入力でvalidator実行
    Expected: exit 0, status=pass
    Evidence: .sisyphus/evidence/task-11-bot-pass.txt

  Scenario: resolution_status欠損のiterationでfail
    Tool: Bash
    Steps: resolution_statusがないiterationを含む入力でvalidator実行
    Expected: exit 2, status=fail
    Evidence: .sisyphus/evidence/task-11-bot-fail.txt

  **Commit**: YES
  - Message: feat(gates): add pr-bot-iteration validator
  - Files: framework/scripts/gates/validate_pr_bot_iteration.py, framework/.agent/schemas/gates/pr-bot-iteration-result.schema.json, tests/framework/test_validate_pr_bot_iteration.py, framework/scripts/manifest.yaml
  - Pre-commit: python3 -m unittest tests/framework/test_validate_pr_bot_iteration.py

- [x] 12. validate_adr_index.py + test + schema

  **What to do**:
  - `framework/scripts/gates/validate_adr_index.py` を新規作成
  - 入力: request_id, scope_id, run_id, artifact_path, adr_index オブジェクト
  - adr_indexオブジェクトの検証:
    - entries(1件以上の配列)
    - 各entry: adr_id(非空), title(非空), status(非空), file_path(非空)
    - adr_idの重複がないこと
  - gate_helpersの共通関数を使用
  - スキーマ: framework/.agent/schemas/gates/adr-index-result.schema.json
  - テスト: tests/framework/test_validate_adr_index.py
  - manifest.yaml の adr-index-consistency を status: implemented に更新

  **Must NOT do**:
  - ADRファイルの実在確認（file_pathの文字列存在のみ）
  - ADR内容の意味的検証

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **Parallelization**:
  - Can Run In Parallel: YES
  - Parallel Group: Wave 3 (with T9, T10, T11, T13)
  - Blocks: T17
  - Blocked By: T1, T3

  **References**:
  - `framework/scripts/gates/validate_estimate_approval.py` — 標準パターン
  - `framework/scripts/lib/gate_helpers.py` — 共通ヘルパー (T1)
  - `framework/scripts/manifest.yaml:85-88` — adr-index-consistency 契約
  - `framework/templates/adr/template.md` — ADRテンプレート。indexエントリが参照するフィールドとの整合

  **Acceptance Criteria**:
  - [x] framework/scripts/gates/validate_adr_index.py が存在
  - [x] framework/.agent/schemas/gates/adr-index-result.schema.json が存在
  - [x] tests/framework/test_validate_adr_index.py が存在
  - [x] python3 -m unittest tests/framework/test_validate_adr_index.py → PASS
  - [x] manifest.yaml の adr-index-consistency が status: implemented

  **QA Scenarios:**
  Scenario: 重複なしのADR indexでpass
    Tool: Bash
    Steps: entriesに異なるadr_idのエントリ2件でvalidator実行
    Expected: exit 0, status=pass
    Evidence: .sisyphus/evidence/task-12-adr-pass.txt

  Scenario: 重複adr_idでfail
    Tool: Bash
    Steps: 同一adr_idを持つエントリ2件でvalidator実行
    Expected: exit 2, status=fail
    Evidence: .sisyphus/evidence/task-12-adr-fail.txt

  **Commit**: YES
  - Message: feat(gates): add adr-index-consistency validator
  - Files: framework/scripts/gates/validate_adr_index.py, framework/.agent/schemas/gates/adr-index-result.schema.json, tests/framework/test_validate_adr_index.py, framework/scripts/manifest.yaml
  - Pre-commit: python3 -m unittest tests/framework/test_validate_adr_index.py

- [x] 13. validate_drift_detection.py + test + schema (FR-5)

  **What to do**:
  - `framework/scripts/gates/validate_drift_detection.py` を新規作成
  - FR-5 ドリフト検知: issueのchange_targets vs 実際のgit diffパス集合を比較
  - 入力: request_id, scope_id, run_id, artifact_path, declared_targets(文字列配列), actual_changes(文字列配列)
  - 検証ロジック:
    - declared_targetsにないactual_changes → undeclared_additions (ドリフト)
    - declared_targetsにあるがactual_changesにない → unused_declarations (警告のみ)
    - ディレクトリプレフィックスマッチ: declared=src/auth/ なら actual=src/auth/login.py はマッチ
    - undeclared_additionsが1件以上あればfail
  - gate_helpersの共通関数を使用
  - スキーマ: framework/.agent/schemas/gates/drift-detection-result.schema.json
  - テスト: tests/framework/test_validate_drift_detection.py
  - manifest.yamlに drift-detection 契約を追加 (status: implemented)

  **Must NOT do**:
  - 実際のgit diff実行（入力は外部から提供されたパス配列）
  - AIベースの意味的ドリフト分析
  - ファイル内容の比較（パス集合のみ）

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: ディレクトリプレフィックスマッチロジックの設計とエッジケースの網羅が必要
  - **Skills**: []

  **Parallelization**:
  - Can Run In Parallel: YES
  - Parallel Group: Wave 3 (with T9, T10, T11, T12)
  - Blocks: T15
  - Blocked By: T1, T7

  **References**:
  - `framework/scripts/gates/validate_overlap_safety.py` — パス集合比較の参考。current_targetsとactive_scopesのパスマッチングロジックを参考
  - `framework/scripts/gates/validate_issue_targets.py` — T7で作成。change_targetsのデータ構造を参考
  - `framework/scripts/lib/gate_helpers.py` — 共通ヘルパー (T1)
  - `docs/prd/prd-scaffold-dev-cycle-v1.md` — FR-5要件定義: 「ドリフト検知」

  **Acceptance Criteria**:
  - [x] framework/scripts/gates/validate_drift_detection.py が存在
  - [x] framework/.agent/schemas/gates/drift-detection-result.schema.json が存在
  - [x] tests/framework/test_validate_drift_detection.py が存在
  - [x] python3 -m unittest tests/framework/test_validate_drift_detection.py → PASS
  - [x] manifest.yamlに drift-detection 契約が追加され status: implemented

  **QA Scenarios:**
  Scenario: 宣言と実際が一致でpass
    Tool: Bash
    Steps: declared=["src/auth/"], actual=["src/auth/login.py"] でvalidator実行
    Expected: exit 0, status=pass, undeclared_additions=[]
    Evidence: .sisyphus/evidence/task-13-drift-pass.txt

  Scenario: 未宣言ファイル変更でfail
    Tool: Bash
    Steps: declared=["src/auth/"], actual=["src/auth/login.py", "src/billing/pay.py"] でvalidator実行
    Expected: exit 2, status=fail, undeclared_additions=["src/billing/pay.py"]
    Evidence: .sisyphus/evidence/task-13-drift-fail.txt

  Scenario: unused_declarationsは警告のみでpass
    Tool: Bash
    Steps: declared=["src/auth/", "src/billing/"], actual=["src/auth/login.py"] でvalidator実行
    Expected: exit 0, status=pass, unused_declarations=["src/billing/"]
    Evidence: .sisyphus/evidence/task-13-drift-unused.txt

  **Commit**: YES
  - Message: feat(gates): add drift detection validator (FR-5)
  - Files: framework/scripts/gates/validate_drift_detection.py, framework/.agent/schemas/gates/drift-detection-result.schema.json, tests/framework/test_validate_drift_detection.py, framework/scripts/manifest.yaml
  - Pre-commit: python3 -m unittest tests/framework/test_validate_drift_detection.py


- [x] 14. Waiver/Exception契約 (schema + validator + test + template)

  **What to do**:
  - `framework/scripts/gates/validate_waiver.py` を新規作成
  - 入力: request_id, scope_id, run_id, artifact_path, waiver オブジェクト
  - waiverオブジェクトの検証:
    - gate_id(非空 — 免除対象のゲート契約ID)
    - reason(非空 — 免除理由)
    - approved_by(非空)
    - approved_at(非空)
    - expiry(任意 — 有効期限)
    - scope_restriction(任意 — 適用範囲制限)
  - gate_helpersの共通関数を使用
  - スキーマ: framework/.agent/schemas/gates/waiver-result.schema.json
  - テスト: tests/framework/test_validate_waiver.py
  - テンプレート: framework/templates/waiver/template.json (例外申請用JSONテンプレート)
  - manifest.yamlに waiver-exception 契約を追加 (status: implemented)

  **Must NOT do**:
  - waiver bypassを既存ゲートに統合（単純な証跡検証のみ）
  - 有効期限の自動判定（文字列存在確認のみ）

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **Parallelization**:
  - Can Run In Parallel: YES
  - Parallel Group: Wave 4 (with T15, T16, T17)
  - Blocks: T17
  - Blocked By: T1

  **References**:
  - `framework/scripts/gates/validate_estimate_approval.py` — 標準パターン
  - `framework/scripts/lib/gate_helpers.py` — 共通ヘルパー (T1)
  - `framework/scripts/gates/validate_overlap_safety.py:110-140` — allow_overlap_withのwaiverパターン参考。既存の例外メカニズム

  **Acceptance Criteria**:
  - [x] framework/scripts/gates/validate_waiver.py が存在
  - [x] framework/.agent/schemas/gates/waiver-result.schema.json が存在
  - [x] tests/framework/test_validate_waiver.py が存在
  - [x] framework/templates/waiver/template.json が存在
  - [x] python3 -m unittest tests/framework/test_validate_waiver.py → PASS
  - [x] manifest.yamlに waiver-exception 契約が追加され status: implemented

  **QA Scenarios:**
  Scenario: 有効なwaiverでpass
    Tool: Bash
    Steps: gate_id, reason, approved_by, approved_at が全て存在する入力でvalidator実行
    Expected: exit 0, status=pass
    Evidence: .sisyphus/evidence/task-14-waiver-pass.txt

  Scenario: reason欠損でfail
    Tool: Bash
    Steps: reasonが空文字列の入力でvalidator実行
    Expected: exit 2, status=fail
    Evidence: .sisyphus/evidence/task-14-waiver-fail.txt

  **Commit**: YES
  - Message: feat(gates): add waiver/exception contract
  - Files: framework/scripts/gates/validate_waiver.py, framework/.agent/schemas/gates/waiver-result.schema.json, tests/framework/test_validate_waiver.py, framework/templates/waiver/template.json, framework/scripts/manifest.yaml
  - Pre-commit: python3 -m unittest tests/framework/test_validate_waiver.py

- [x] 15. Scaffold本体 CI gate workflow

  **What to do**:
  - `.github/workflows/gates.yml` を新規作成
  - PRトリガーでゲートvalidatorを実行:
    - Step 1: schema validation (check-jsonschemaで全スキーマ検証)
    - Step 2: 各validatorをサンプル入力で実行（スモークテスト）
    - Step 3: make verify (既存のquality.ymlとの重複を避けるが、ゲート固有検証を追加)
  - 既存の quality.yml は変更しない
  - review engineの実際呼び出しは含めない（stubベースのテストのみ）

  **Must NOT do**:
  - quality.ymlの変更
  - 実際のreview engine (codex/claude) 実行
  - GitHub secretsの設定要求

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **Parallelization**:
  - Can Run In Parallel: YES
  - Parallel Group: Wave 4 (with T14, T16, T17)
  - Blocks: F1-F4
  - Blocked By: T2, T9, T10, T11, T13

  **References**:
  - `.github/workflows/quality.yml` — 既存CI workflow。構造とnaming規約を参考。重複を避ける
  - `framework/scripts/manifest.yaml` — 全契約一覧。ゲートworkflowがどのvalidatorを実行するかのマップ
  - `framework/scripts/gates/` — 全validator。workflowの各stepで呼び出す対象

  **Acceptance Criteria**:
  - [x] .github/workflows/gates.yml が存在
  - [x] YAML構文が有効: grep -q 'on:' .github/workflows/gates.yml && grep -q 'jobs:' .github/workflows/gates.yml
  - [x] quality.ymlが未変更: git diff --name-only に quality.yml が含まれない

  **QA Scenarios:**
  Scenario: gates.ymlが有効なGitHub Actions workflow
    Tool: Bash
    Steps: test -f .github/workflows/gates.yml && grep -q 'on:' .github/workflows/gates.yml && grep -q 'jobs:' .github/workflows/gates.yml && echo 'valid workflow structure'
    Expected: job名のリストが表示される
    Evidence: .sisyphus/evidence/task-15-gates-yml.txt

  Scenario: quality.ymlが未変更
    Tool: Bash
    Steps: git diff HEAD -- .github/workflows/quality.yml
    Expected: 差分なし（空出力）
    Evidence: .sisyphus/evidence/task-15-quality-unchanged.txt

  **Commit**: YES
  - Message: feat(ci): add scaffold gate execution workflow
  - Files: .github/workflows/gates.yml
  - Pre-commit: grep -q 'jobs:' .github/workflows/gates.yml

- [x] 16. 消費者向けサンプルworkflow

  **What to do**:
  - `framework/.github/workflows/scaffold-gates.yml` を新規作成
  - 消費者リポジトリがそのまま使えるサンプルworkflow:
    - framework/scripts/gates/ のvalidatorをPRトリガーで実行
    - コメントでカスタマイズポイントを説明
  - Scaffold本体のgates.yml (T15) をベースに簡略化

  **Must NOT do**:
  - Scaffold固有のパスや設定のハードコーディング
  - secretsや環境変数の前提

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - Can Run In Parallel: YES
  - Parallel Group: Wave 4 (with T14, T15, T17)
  - Blocks: F1-F4
  - Blocked By: T2, T15

  **References**:
  - `.github/workflows/gates.yml` — T15で作成したScaffold本体用。これをベースに簡略化
  - `framework/scripts/manifest.yaml` — 契約一覧。サンプルがどのvalidatorを含むかの参考

  **Acceptance Criteria**:
  - [x] framework/.github/workflows/scaffold-gates.yml が存在
  - [x] YAML構文が有効
  - [x] コメントでカスタマイズポイントが説明されている

  **QA Scenarios:**
  Scenario: サンプルworkflowが有効なYAML
    Tool: Bash
    Steps: test -f framework/.github/workflows/scaffold-gates.yml && grep -q 'on:' framework/.github/workflows/scaffold-gates.yml && grep -q 'jobs:' framework/.github/workflows/scaffold-gates.yml && echo 'valid workflow structure'
    Expected: パース成功
    Evidence: .sisyphus/evidence/task-16-sample-workflow.txt

  **Commit**: YES
  - Message: feat(ci): add consumer sample gate workflow
  - Files: framework/.github/workflows/scaffold-gates.yml
  - Pre-commit: grep -q 'jobs:' framework/.github/workflows/scaffold-gates.yml

- [x] 17. 運用ドキュメント + manifest.yaml最終更新

  **What to do**:
  - `framework/docs/operations/gate-operations.md` を新規作成:
    - 各ゲートvalidatorの用途・入力・出力・使用例の一覧
    - CI workflowの実行方法
    - waiver申請手順
    - トラブルシューティング
  - `framework/scripts/manifest.yaml` の最終確認:
    - 全契約が status: implemented
    - 全契約に result_schema が設定されている
    - drift-detection と waiver-exception 契約が追加されている
  - `framework/scripts/README.md` を更新:
    - 新規 validatorを Implemented validators セクションに追加
    - 新規 CI runner をドキュメントに追加

  **Must NOT do**:
  - validatorコードの変更
  - 新規スクリプトの作成

  **Recommended Agent Profile**:
  - **Category**: `writing`
  - **Skills**: []

  **Parallelization**:
  - Can Run In Parallel: YES
  - Parallel Group: Wave 4 (with T14, T15, T16)
  - Blocks: F1-F4
  - Blocked By: T4, T5, T6, T7, T12, T14

  **References**:
  - `framework/scripts/manifest.yaml` — 全契約一覧。statusとresult_schemaの最終確認
  - `framework/scripts/README.md` — 既存ドキュメント。新規validator/runnerの追加箇所
  - `framework/docs/contract/workflow-map.md` — ワークフロー全体像。運用ドキュメントが参照すべきマップ
  - `framework/docs/contract/hard-gates.md` — ハードゲートポリシー。運用ドキュメントの背景

  **Acceptance Criteria**:
  - [x] framework/docs/operations/gate-operations.md が存在
  - [x] manifest.yaml の全契約が status: implemented
  - [x] manifest.yaml の全契約に result_schema が設定されている
  - [x] framework/scripts/README.md に新規validatorが記載されている

  **QA Scenarios:**
  Scenario: manifest.yamlの全契約がimplemented
    Tool: Bash
    Steps: grep 'status:' framework/scripts/manifest.yaml | sort | uniq -c
    Expected: 全て 'status: implemented' のみ（plannedが0件）
    Evidence: .sisyphus/evidence/task-17-manifest-status.txt

  Scenario: 運用ドキュメントが存在し内容がある
    Tool: Bash
    Steps: wc -l framework/docs/operations/gate-operations.md
    Expected: 50行以上（実質的な内容がある）
    Evidence: .sisyphus/evidence/task-17-ops-doc.txt

  Scenario: README.mdに新規validatorが記載
    Tool: Bash
    Steps: grep 'validate_research_contract' framework/scripts/README.md && grep 'validate_drift_detection' framework/scripts/README.md
    Expected: 両方が見つかる
    Evidence: .sisyphus/evidence/task-17-readme-updated.txt

  **Commit**: YES
  - Message: docs: add operational documentation and finalize manifest
  - Files: framework/docs/operations/gate-operations.md, framework/scripts/manifest.yaml, framework/scripts/README.md
  - Pre-commit: grep -c 'status: planned' framework/scripts/manifest.yaml (expect 0)


---

## Final Verification Wave (MANDATORY — after ALL implementation tasks)

> 4 review agents run in PARALLEL. ALL must APPROVE. Rejection → fix → re-run.

- [x] F1. **Plan Compliance Audit** — `oracle`
  Read the plan end-to-end. For each "Must Have": verify implementation exists (read file, run command). For each "Must NOT Have": search codebase for forbidden patterns — reject with file:line if found. Check evidence files exist in .sisyphus/evidence/. Compare deliverables against plan.
  Output: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | VERDICT: APPROVE/REJECT`

- [x] F2. **Code Quality Review** — `unspecified-high`
  Run `make verify` (lint + format + typecheck + schema-check + test). Review all changed files for: `as any`/`@ts-ignore` (N/A — Python), empty catches, commented-out code, unused imports. Check AI slop: excessive comments, over-abstraction, generic names. Verify mypy strict passes with lib/ in scope.
  Output: `Build [PASS/FAIL] | Lint [PASS/FAIL] | Tests [N pass/N fail] | VERDICT`

- [x] F3. **Real Manual QA** — `unspecified-high`
  Start from clean state. Execute EVERY QA scenario from EVERY task — follow exact steps, capture evidence. Test cross-task integration: test-review → review-cycle → final-review chain. Test edge cases: empty ADR index, missing fields.
  Output: `Scenarios [N/N pass] | Integration [N/N] | Edge Cases [N tested] | VERDICT`

- [x] F4. **Scope Fidelity Check** — `deep`
  For each task: read "What to do", read actual diff. Verify 1:1 — everything in spec was built, nothing beyond spec was built. Check "Must NOT do" compliance. Detect cross-task contamination.
  Output: `Tasks [N/N compliant] | Contamination [CLEAN/N issues] | Unaccounted [CLEAN/N files] | VERDICT`

---

## Commit Strategy

- **T1**: `refactor(gates): extract shared gate helpers to lib/gate_helpers.py`
- **T2**: `chore: configure git remote and initial push`
- **T3**: `chore: update pyproject.toml mypy scope for lib/`
- **T4**: `docs(templates): enrich PRD/Epic/Issue/ADR templates`
- **T5**: `feat(gates): add research-before-spec validator`
- **T6**: `feat(gates): add spec-quality-minimum validator`
- **T7**: `feat(gates): add issue-change-targets-declared validator`
- **T8**: `refactor(gates): migrate review validators to shared lib`
- **T9**: `feat(ci): add test-review CI runner`
- **T10**: `feat(ci): add final-review CI runner`
- **T11**: `feat(gates): add pr-bot-iteration validator`
- **T12**: `feat(gates): add adr-index-consistency validator`
- **T13**: `feat(gates): add drift detection validator (FR-5)`
- **T14**: `feat(gates): add waiver/exception contract`
- **T15**: `feat(ci): add scaffold gate execution workflow`
- **T16**: `feat(ci): add consumer sample gate workflow`
- **T17**: `docs: add operational documentation and finalize manifest`

---

## Success Criteria

### Verification Commands
```bash
make verify                    # Expected: exit 0
python3 -m unittest discover -s tests/framework -p "test_*.py"  # Expected: 0 failures
check-jsonschema --schemafile https://json-schema.org/draft/2020-12/schema framework/.agent/schemas/*/*.json  # Expected: exit 0
```

### Final Checklist
- [x] All 16 contracts in manifest.yaml have `status: implemented` (既存14 + drift-detection + waiver-exception)
- [x] All "Must Have" present
- [x] All "Must NOT Have" absent
- [x] All tests pass
- [x] `make verify` exit 0
- [x] Review chain (test-review → review-cycle → final-review) executable end-to-end
