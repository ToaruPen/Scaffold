# PRD: Scaffold開発サイクル基盤

> 本PRDは、Scaffoldで採用する開発サイクルの要求定義です。
> 「手順の固定」ではなく「証跡契約の固定」を中心に設計します。

---

## メタ情報

- 作成日: 2026-03-03
- 作成者: @sankenbisha
- ステータス: Draft
- バージョン: 1.0

---

## 1. 目的・背景

AI主体の実装速度を維持しつつ、品質とトレーサビリティの下限を保証するため、Scaffoldに「証跡中心の開発サイクル」を定義する。既存ワークフローで発生しやすい過剰なスクリプト複雑化を避け、最小限のハードゲートで運用可能な基盤を作る。

---

## 2. 7つの質問への回答

### Q1: 解決したい問題は？

AIエージェント開発では、手順を厳密に縛りすぎると保守コストが増え、緩すぎると品質が崩れる。Scaffoldでは、実装手順を柔軟にしつつ、必要な証跡（見積、レビュー、ドリフト確認、意思決定）だけを決定論的に担保したい。

### Q2: 誰が使う？

- プロダクトオーナー（PRD/Epicの承認者）
- AIエージェント（issue単位の実装担当）
- 人間レビュアー（最終判断者）
- リポジトリ保守者（ゲート運用・例外承認）

### Q3: 何ができるようになる？

- PRD/Epicからissue分割、見積、実装、レビュー、PRまで一貫運用できる
- 並列実装時の衝突を事前/事後に機械検知し、物理的にブロックできる
- `tests-review` / `review-cycle` / `final-review` の証跡を残し、ドリフト検知できる
- PR Botレビューをイベント駆動で取り込み、修正ループを回せる

### Q4: 完成と言える状態は？

以下の一連の流れが、1つのissueで再現可能な状態。

1. PRD/Epic作成
2. issue作成（並列可否判定を含む）
3. issue単位branch作成（重複対象はfail-fast）
4. 見積作成と実装モード選択（impl/tdd/custom）
5. 実装後に `tests-review` / `review-cycle` / `final-review` を通過
6. コミット・プッシュ・PR作成
7. PR Bot指摘をイベント駆動で反映し、再レビュー
8. 最終的に人間がPRを承認可能

### Q5: 作らない範囲は？

- 全言語・全フレームワークへの初期段階での完全対応
- 既存Agentic-SDDとの完全互換レイヤー
- Bot判断のみで自動マージする仕組み
- 成果物契約なしの自由運用モード

### Q6: 技術的制約は？

Q6-1: 既存言語/フレームワーク固定
選択: No
詳細（Yesの場合）: -

Q6-2: デプロイ先固定
選択: No
詳細（Yesの場合）: -

Q6-3: 期限
選択: Unknown
詳細（日付の場合）: 初期運用で確定

Q6-4: 予算上限
選択: ない
詳細（あるの場合）: -

Q6-5: 個人情報/機密データ
選択: No
詳細（Yesの場合）: -

Q6-6: 監査ログ要件
選択: Yes
詳細（Yesの場合）: ゲート証跡（見積・レビュー・例外）を追跡可能にする

Q6-7: パフォーマンス要件
選択: Yes
詳細（Yesの場合）:
  - 対象操作: pre-mergeゲート実行
  - 目標概要: 小規模issueでゲート全体が短時間で完了すること

Q6-8: 可用性要件
選択: No
詳細（Yesの場合）: -

### Q7: 成功指標（測り方）は？

指標-1
指標: pre-mergeリードタイム（小規模issue）
目標値: 中央値 45分以内
測定方法: issue開始からPR作成までの時刻差を記録

指標-2
指標: 重大ゲートバイパス率
目標値: 0%
測定方法: required checks未通過のmerge件数を集計

指標-3
指標: 並列実装衝突の事前検知率
目標値: 95%以上
測定方法: PR作成前に検知した重複件数 / 総衝突件数

指標-4
指標: PR Bot再提出サイクルの収束率
目標値: 2サイクル以内で80%以上が収束
測定方法: Bot指摘→修正→再レビュー回数の分布集計

---

## 3. ユーザーストーリー

### US-1: 開発者（エージェント）

```
As an AI implementation agent,
I want to select impl/tdd mode from issue and estimate evidence,
So that I can execute quickly without violating required contracts.
```

### US-2: レビュアー

```
As a human reviewer,
I want deterministic review evidence and drift checks before PR review,
So that I can focus on high-risk decisions instead of mechanical checks.
```

### US-3: リポジトリ保守者

```
As a repository maintainer,
I want overlap and scope violations to fail fast,
So that parallel development does not silently create integration risk.
```

---

## 4. 機能要件

FR-1
機能名: 要件フェーズ管理
説明: PRD/Epic作成と参照関係を管理し、issue作成の入力にする
優先度: Must

FR-2
機能名: 並列実装可否判定
説明: issueの変更対象宣言を用いて重複を検知し、重複時は開始/PR作成をブロックする
優先度: Must

FR-3
機能名: 見積・実装モード選択
説明: issueごとに見積成果物を保存し、impl/tdd/customの選択根拠を記録する
優先度: Must

FR-4
機能名: レビュー証跡管理
説明: `tests-review` / `review-cycle` / `final-review` の結果をcommit/rangeと紐付けて保存する
優先度: Must

FR-5
機能名: ドリフト検知
説明: issue/estimateと実装内容の差分を検証し、逸脱時にfail-fastする
優先度: Must

FR-6
機能名: PR Bot連携
説明: 外部レビューBot（Codex/Coderabbit等）を設定可能にし、イベント駆動で修正ループを回す
優先度: Should

FR-7
機能名: 例外契約（Waiver/Exception）
説明: 例外を禁止せず、理由・影響・期限・承認者を必須記録して監査可能にする
優先度: Should

---

## 5. 受け入れ条件（AC）

### 正常系

- [ ] AC-1: issue作成時に並列可否判定が実行され、重複なしのissueのみ `parallel-ok` として開始できる
- [ ] AC-2: issueごとに見積成果物と実装モード選択根拠が保存され、実装開始前に参照できる
- [ ] AC-3: `tests-review` / `review-cycle` / `final-review` の結果がcommit/rangeに紐づいて保存される
- [ ] AC-4: PR Bot指摘の取り込み→修正→再提出ループを1回以上再現できる

### 異常系（必須: 最低1つ）

- [ ] AC-E1: 変更対象ファイルが重複するissueでPR作成を試みると、理由付きでfail-fastする
- [ ] AC-E2: 見積証跡がないissueで実装開始を試みると、開始不可となる
- [ ] AC-E3: review証跡とHEAD/rangeが不一致の場合、PR作成前に再レビューを要求する

---

## 6. 非機能要件（該当する場合）

- パフォーマンス: 小規模issueのpre-mergeゲートは短時間で完了（目安: 10分以内）
- 監査性: すべての例外・承認・レビュー結果に参照可能な証跡リンクがある
- 拡張性: PR Bot実装はプロバイダ非依存で差し替え可能
- 保守性: validatorは1責務・決定論・副作用最小で実装

---

## 7. 規模感と技術方針

- 規模感: 中規模
- 技術方針: バランス

---

## 8. 用語集

用語-1
用語: Scope Lock
定義: issue/branch/worktree/range の一致を確認し、ズレをfail-fastする契約

用語-2
用語: Waiver
定義: 本来必須のゲートを一時免除する際の監査可能な例外記録

用語-3
用語: Exception
定義: ルール逸脱を明示承認付きで実施する恒久または準恒久の例外記録

---

## 完成チェックリスト

- [x] 目的・背景が1-3文で書かれている
- [x] ユーザーストーリーが1つ以上ある
- [x] 機能要件が3つ以上列挙されている
- [x] ACが検証可能な形式で3つ以上ある
- [x] ACに異常系が最低1つある
- [x] スコープ外が明記されている
- [x] 成功指標が測定可能な形式で書かれている
- [x] Q6のUnknownが2つ未満である
