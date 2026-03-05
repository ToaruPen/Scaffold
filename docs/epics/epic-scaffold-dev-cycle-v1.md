# Epic: Scaffold開発サイクル実装

> 本Epicは `docs/prd/prd-scaffold-dev-cycle-v1.md` を実装可能な作業単位へ分解する。

---

## メタ情報

- 作成日: 2026-03-03
- 作成者: @sankenbisha
- ステータス: Draft
- 参照PRD: `docs/prd/prd-scaffold-dev-cycle-v1.md`

---

## 1. 概要

### 1.1 目的

Scaffoldに、証跡契約中心の開発サイクルを実装する。具体的には、並列実装の物理衝突ブロック、見積承認、レビュー証跡、ドリフト検知、PR Bot連携の最小構成を整備し、1 issueで端から端まで再現可能にする。

### 1.2 スコープ

**含む:**
- PRD/Epic/Issueを起点にした実装サイクル契約の定義
- ハードゲート用validator群（research/spec/estimate/review/drift/adr）
- 並列実装の重複検知とScope Lock
- PR Bot連携のイベント駆動ループ雛形

**含まない（PRDのスコープ外を継承）:**
- 既存Agentic-SDDとの完全互換
- 全言語向けの最初からの完全対応
- Botのみでの自動マージ

### 1.3 PRD制約の確認

項目: 規模感
PRDの値: 中規模
Epic対応: Issueを段階分割し、フェーズごとに品質ゲートを固定

項目: 技術方針
PRDの値: バランス
Epic対応: 決定論ゲートは維持しつつ、手順の固定は最小化

項目: 既存言語/FW
PRDの値: No
Epic対応: Python + Shellを初期実装の標準にする

項目: デプロイ先
PRDの値: No
Epic対応: GitHub Actions前提だが自己ホスト可能な設計にする

---

## 2. 必須提出物（3一覧）

### 2.1 外部サービス一覧

外部サービス-1
名称: GitHub (Issues/PR/Actions/Rulesets)
用途: issue管理、PRレビュー、必須チェック強制
必須理由: 開発サイクルのSoTおよびイベント基盤
代替案: GitLab/Jira連携（将来）

外部サービス-2
名称: なし
用途: -
必須理由: -
代替案: -

### 2.2 コンポーネント一覧

コンポーネント-1
名称: framework/scripts/gates
責務: 成果物契約の決定論バリデーション
デプロイ形態: ローカル + CI実行

コンポーネント-2
名称: framework/scripts/ci
責務: ゲート実行順序のオーケストレーション
デプロイ形態: GitHub Actions

コンポーネント-3
名称: framework/docs/contract
責務: ハードゲート契約のSoT
デプロイ形態: Markdown

コンポーネント-4
名称: tooling/sync
責務: subtree配布と更新運用
デプロイ形態: Shell/Python

コンポーネント-5
名称: PR Bot adapter
責務: Bot指摘イベントの取り込みと再提出ループ
デプロイ形態: CI job / webhook handler

### 2.3 新規技術一覧

新規技術-1
名称: check-jsonschema
カテゴリ: スキーマ検証
既存との差: 新規導入
導入理由: 証跡JSON契約を決定論で検証

新規技術-2
名称: pre-commit
カテゴリ: ローカル品質ゲート
既存との差: 新規導入
導入理由: 開発初期に軽量な再現可能チェックを確保

新規技術-3
名称: GitHub Required Reviewer Rule / Rulesets
カテゴリ: ガバナンス強制
既存との差: 新規導入
導入理由: Branch Protection単位より細かい強制ルールに対応

---

## 3. 技術設計

### 3.1 アーキテクチャ概要

システム境界: Scaffold本体（framework）と配布運用（tooling）を分離。

主要データフロー-1
from: PRD/Epic/Issue
to: estimation artifact
用途: 実装モード決定とスコープ固定
プロトコル: ファイル契約 + CLI

主要データフロー-2
from: 実装差分 + テスト結果
to: review artifacts
用途: `review-cycle` / `final-review` 証跡化
プロトコル: JSON/Markdown + CI

主要データフロー-3
from: PR Botイベント
to: 修正ループ
用途: 指摘反映と再提出
プロトコル: GitHub event payload

### 3.2 技術選定

技術選定-1
カテゴリ: 言語
選択: Python + Bash
理由: 検証ロジックの可読性と運用簡便性のバランス

技術選定-2
カテゴリ: CI
選択: GitHub Actions
理由: Rulesets/Branch Protection/PR eventと統合しやすい

技術選定-3
カテゴリ: スキーマ
選択: JSON Schema + Markdown契約
理由: 決定論検証と可読性を両立

### 3.3 データモデル（概要）

エンティティ-1
名前: EstimateRecord
主要属性: issue_id, mode, assumptions, approval
関連: 1 issue に対し1 active record

エンティティ-2
名前: ReviewEvidence
主要属性: scope_id, head_sha, base_sha, status, findings
関連: 1 issue に複数run

エンティティ-3
名前: WaiverRecord
主要属性: gate_id, reason, impact, approver, expires_at
関連: review/final gateに紐付く

### 3.4 API設計（概要）

API-1
エンドポイント: なし（初期はCLI中心）
メソッド: -
説明: v1はローカル/CIのCLI運用

### 3.5 プロジェクト固有指標（任意）

固有指標-1
指標名: Gate lead time
測定方法: issue単位でゲート開始/終了時刻を記録
目標値: small issueで10分以内
Before/After記録方法: CI artifact

固有指標-2
指標名: Drift detection precision
測定方法: 逸脱検知の適合率を手動ラベルで確認
目標値: 90%以上
Before/After記録方法: 月次レビュー

### 3.6 フォルダ構造設計（必須）

トップレベル構造
- `framework/`: 配布対象（契約/validator/workflow）
- `tooling/`: install/sync/migrate
- `docs/`: Scaffold本体の設計文書
- `tests/`: framework/toolingの検証

設計理由
- 配布境界を `framework/` に固定し、他repo同期時の影響範囲を限定
- Scaffold自身の保守用コードを分離し、消費側への漏洩を防止

運用ルール
- consumerへ同期するのは `framework/` のみ
- `framework/scripts/gates` は1契約1validator
- ローカル拡張は consumer 側 overlay で実施

### 3.7 AGENTS.md配置計画（必須）

AGENTS配置-1
配置先: `AGENTS.md`
対象範囲: Scaffoldリポジトリ全体
役割: 二層モデルと保守ルールの定義
リンク先SoT: `docs/README.md`

AGENTS配置-2
配置先: `framework/AGENTS.md`
対象範囲: 配布先リポジトリ
役割: hard gate契約と運用ルールの伝達
リンク先SoT: `framework/docs/contract/hard-gates.md`

### 3.8 静的解析ツールチェーン選定（必須）

ツールチェーン-1
カテゴリ: lint (python)
選択: ruff
選定理由: 高速・普及・CI統合容易
ローカル実行方法: pre-commit / make lint
CI実行方法: github actions lint job

ツールチェーン-2
カテゴリ: format
選択: ruff format + shfmt
選定理由: Python/Shellの一貫整形
ローカル実行方法: pre-commit
CI実行方法: format-check job

ツールチェーン-3
カテゴリ: typecheck
選択: mypy (validator層)
選定理由: Python validatorの静的保証
設定方針: `mypy` は段階導入し、初期は必須チェックから開始
ローカル実行方法: make typecheck
CI実行方法: typecheck job

ツールチェーン-4
カテゴリ: schema
選択: check-jsonschema
選定理由: review/estimate/waiver契約を機械検証
しきい値方針: スキーマ不一致は即fail
ローカル実行方法: make schema-check
CI実行方法: schema-check job

代替案（よりシンプルな方法）
- 代替案: スキーマ検証なしでMarkdownのみ運用
- 採用しなかった理由: ドリフト検知と自動判定の再現性が不足

---

## 4. Issue分割案

### 4.1 Issue一覧

Issue-1
番号: 1
Issue名: PRD/Epic/Issue契約テンプレート確定
概要: 最小契約をテンプレート化
推定行数: 150-250行
依存: -

Issue-2
番号: 2
Issue名: overlap検知とScope Lock実装
概要: 変更対象重複の物理ブロック
推定行数: 200-350行
依存: #1

Issue-3
番号: 3
Issue名: estimation契約と承認記録
概要: impl/tdd/custom選択と証跡保存
推定行数: 200-350行
依存: #1

Issue-4
番号: 4
Issue名: review-evidence-linkゲート実装
概要: commit/range整合の決定論チェック
推定行数: 250-400行
依存: #3

Issue-5
番号: 5
Issue名: review-cycleゲート実装
概要: 実装妥当性レビューと再実行ループ
推定行数: 300-500行
依存: #3

Issue-6
番号: 6
Issue名: final-reviewゲート実装
概要: issue/estimate/実装ドリフト検知
推定行数: 250-450行
依存: #4, #5

Issue-7
番号: 7
Issue名: PR作成ゲートと証跡整合
概要: commit/range一致と必須証跡確認
推定行数: 250-400行
依存: #6

Issue-8
番号: 8
Issue名: PR Botイベントループ実装
概要: 指摘取得・修正・再提出
推定行数: 250-450行
依存: #7

Issue-9
番号: 9
Issue名: Waiver/Exception契約
概要: 例外記録スキーマと期限管理
推定行数: 150-250行
依存: #6

Issue-10
番号: 10
Issue名: CI required checksと運用ドキュメント整備
概要: フロー運用ドキュメントとrequired checks運用を整備
推定行数: 200-350行
依存: #8, #9

### 4.2 依存関係図

依存関係（関係を1行ずつ列挙）:
- Issue 2 depends_on Issue 1
- Issue 3 depends_on Issue 1
- Issue 4 depends_on Issue 3
- Issue 5 depends_on Issue 3
- Issue 6 depends_on Issue 4
- Issue 6 depends_on Issue 5
- Issue 7 depends_on Issue 6
- Issue 8 depends_on Issue 7
- Issue 9 depends_on Issue 6
- Issue 10 depends_on Issue 8
- Issue 10 depends_on Issue 9

### 4.3 実装順序ガイド（2026-03-04更新）

impl/tdd/custom先行方針を反映し、依存を壊さずに並列性を最大化する。

- Step 1: Issue 1
- Step 2: Issue 2 と Issue 3 を並列実装
- Step 3: 子Issue #12（lint/format/typecheck/schema基盤）を先行適用
- Step 4: Issue 4 と Issue 5 を並列実装（Issue 3完了後）
- Step 5: Issue 6
- Step 6: Issue 7 と Issue 9 を並列実装
- Step 7: Issue 8
- Step 8: Issue 10

運用ルール:
- `review-cycle` 未実装時は代替経路を作らず fail-fast する。
- `impl/tdd/custom` 先行は「契約と骨格」までに限定し、reviewゲートのスキップ経路を作らない。

---

## 5. プロダクション品質設計（PRD Q6に応じて記載）

### 5.1 パフォーマンス設計（PRD Q6-7: Yesの場合必須）

PRD Q6-7: Yes

対象操作:
- pre-merge quality gate: 10分以内（small issue）
- overlap check: 1分以内（典型ケース）

測定方法:
- ツール: CIタイムスタンプ計測
- 環境: GitHub Actions
- 条件: PRごとのrequired checks

ボトルネック候補:
- 大規模diffのreview-cycle
- Botイベントの再レビュー連鎖

対策方針:
- 変更規模に応じた必須/追加ゲート実行範囲の切替
- 必須ゲートと補助ゲートを分離

### 5.2 セキュリティ設計（PRD Q6-5: Yesの場合必須）

PRD Q6-5: No

N/A（個人情報/機密データなし）

### 5.3 観測性設計（PRD Q6-6: Yesの場合必須）

PRD Q6-6: Yes

ログ:
- 出力先: CI artifacts + local `.scaffold-state/`（非配布）
- フォーマット: JSON + Markdown
- 保持期間: 初期30日（運用で調整）

メトリクス:
- gate_duration_seconds
- drift_detected_count
- waiver_open_count

アラート:
- required gate fail増加時に通知
- waiver期限切れ時に通知

### 5.4 可用性設計（PRD Q6-8: Yesの場合必須）

PRD Q6-8: No

N/A（可用性要件なし）

---

## 6. リスクと対策

リスク-1
リスク: ゲートの過重化でリードタイムが悪化
影響度: 高
対策: フロー固定 + 必須ゲート中心の段階導入

リスク-2
リスク: PR Botへの過信で決定論チェックが抜ける
影響度: 高
対策: required checksでbot非依存の最小ゲートを固定

リスク-3
リスク: 並列実装の重複宣言漏れ
影響度: 中
対策: issueテンプレ必須項目 + create-pr前の再検知

---

## 7. マイルストーン

Phase-1
フェーズ: Contract Foundation
完了条件: PRD/Epic/Issue/Estimate/Review契約とスキーマ定義
目標日: 未設定（意図的に固定しない）

Phase-2
フェーズ: Gate Implementation
完了条件: overlap/estimation/review/finalゲートがCIで実行可能
目標日: 未設定（意図的に固定しない）

Phase-3
フェーズ: PR Bot Loop + Operation Docs
完了条件: Botイベント駆動ループと運用ドキュメントを提供
目標日: 未設定（意図的に固定しない）

---

## 8. 技術方針別の制限チェック

### バランスの場合

- [x] 外部サービス数が3以下
- [x] 新規導入ライブラリが5以下
- [x] 新規コンポーネント数が5以下（論理コンポーネント単位）
- [x] 並列運用の衝突対策が明示されている

### 共通チェック

- [x] 新規技術/サービス名が5つ以下
- [x] 各選択に理由がある
- [x] 代替案が提示されている
- [x] 必須提出物が揃っている
- [x] フォルダ構造とAGENTS配置計画が定義されている
- [x] lint/format/typecheck/schemaの実行計画がある

---

## 9. Unknown項目の確認（PRDから引き継ぎ）

Unknown-1
項目: 期限（最終リリース日）
PRDの値: Unknown
確認結果: 期限は意図的に固定しない。品質ゲート達成を進行条件とする。

---

## 10. Agentic-SDD資産の流用方針（初版）

### 10.1 方針

- 「手順」ではなく「契約」を移植する。
- コマンド/スキルは agent-specific 層と core契約層を分離して導入する。
- Codex CLI / Claude Code / OpenCode のいずれでも動くことを前提に、直接依存をアダプタ層へ隔離する。

### 10.2 コマンド流用優先度

Must（初期導入）
- `/research`, `/create-prd`, `/create-epic`, `/create-issues`
- `/estimation`, `/impl`, `/tdd`
- `/worktree`, `/review-cycle`, `/final-review`, `/create-pr`, `/pr-bots-review`

Should（第二段階）
- `/sync-docs`, `/debug`, `/cleanup`, `/lint-setup`

Optional（必要時）
- `/ui-iterate`, `/generate-project-config`, `/init`

### 10.3 スキル流用優先度

Must（初期導入）
- `testing`, `error-handling`, `security`, `debugging`, `anti-patterns`

Should（第二段階）
- `estimation`, `tdd-protocol`, `worktree-parallel`, `lsp-verification`

Optional（必要時）
- `data-driven`, `resource-limits`, `crud-screen`, `api-endpoint`, `ui-redesign`

### 10.4 アダプタ境界（重要）

- Review engine adapter: `codex` / `claude` / `other` を切替
- VCS/hosting adapter: `gh` 依存操作を抽象化
- Bot adapter: Codex/Coderabbit などのイベント形式差分を吸収

---

## 変更履歴

- 2026-03-03: v1.0 初版作成（@sankenbisha）
