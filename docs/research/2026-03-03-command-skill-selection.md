# 調査メモ: Agentic-SDD資産の流用選定（Scaffold向け）

作成日: 2026-03-03

## 目的

Scaffoldで、Agentic-SDDのコマンド/スキルをどこまで流用するかを決める。
前提は「既存コーディングエージェント（Codex CLI / Claude Code / OpenCode）を主軸に運用する」こと。

## 選定基準

1. 生成物契約（証跡）が強化されるか
2. agent-specific依存をアダプタ層へ隔離できるか
3. 初期導入コストに対して運用メリットが大きいか
4. 手順固定ではなく運用柔軟性を残せるか

## コマンド選定

### Must（初期導入）

- `/research`
- `/create-prd`
- `/create-epic`
- `/create-issues`
- `/estimation`
- `/impl`
- `/tdd`
- `/worktree`
- `/test-review`
- `/review-cycle`
- `/final-review`
- `/create-pr`
- `/pr-bots-review`

理由:
- Scaffoldの開発サイクル（要件→issue→見積→実装→レビュー→PR→Botループ）を直接カバーするため。

### Should（第二段階）

- `/sync-docs`
- `/debug`
- `/cleanup`
- `/lint-setup`

理由:
- 運用品質を上げるが、初期の必須ラインではないため。

### Optional（必要時）

- `/ui-iterate`
- `/generate-project-config`
- `/init`

理由:
- UI案件や初期セットアップ自動化など、用途限定のため。

## スキル選定

### Must（初期導入）

- `testing`
- `error-handling`
- `security`
- `debugging`
- `anti-patterns`

### Should（第二段階）

- `estimation`
- `tdd-protocol`
- `worktree-parallel`
- `lsp-verification`

### Optional（必要時）

- `data-driven`
- `resource-limits`
- `crud-screen`
- `api-endpoint`
- `ui-redesign`

## 実装方針（重要）

### Core契約層

- 成果物契約（estimate/review/final/waiver）
- スキーマ（JSON Schema + Markdown契約）
- required checks

### Agent-specific層

- Review engine adapter（codex/claude/other）
- VCS adapter（GitHub依存を抽象化）
- PR Bot adapter（Codex/Coderabbit差分吸収）

## 非目標

- Agentic-SDDとの完全互換
- 特定エージェントへの最適化固定
- ローカルスクリプトの大規模モノリス化
