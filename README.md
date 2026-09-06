# lamp-skills

[Igness LAMP / BRAIN](https://www.igness.ai) を AI コーディングエージェントから操作するためのスキル集です。
Claude Code・Codex・Blaze をはじめ、Salesforce CLI（`sf`）を実行できるエージェントであれば同じ手順書で動作します。

| スキル | できること | 必要なパッケージ |
| --- | --- | --- |
| [`lamp-setup`](skills/lamp-setup/SKILL.md) | パッケージインストール後の初期設定（権限割当・サーバー認証・パス有効化）と LINE 公式アカウント接続を自動で進める | Igness LAMP **1.153 以降** |
| [`lamp-media-upload`](skills/lamp-media-upload/SKILL.md) | 画像・動画をコンテンツ配信基盤へアップロードし、テンプレートメッセージ・クーポン・リッチメニュー・送信元アイコンに設定する | Igness LAMP **1.155 以降** |
| [`lamp-template`](skills/lamp-template/SKILL.md) | テンプレートと9種類のテンプレートメッセージ（テキスト／画像／動画／リンク付き画像／カード／設問（2択）／カード（画像のみ）／クーポン／フレックス）を作成し、有効化エラーを読んで修正、返信ボタン・項目の代入・テスト配信まで行う | Igness LAMP **1.156 以降** |

## インストール

### Claude Code（推奨）

```
/plugin marketplace add igness-ai/lamp-skills
/plugin install lamp@lamp-skills
```

以後は「LAMP をセットアップして」「LAMP に画像をアップロードして」「LAMP でカードメッセージのテンプレートを作って」のように依頼するだけで、対応するスキルが使われます。
更新は `/plugin update lamp@lamp-skills` で取り込めます。

### Blaze

[Blaze](https://blaze.igness.ai/) は Skills に対応しています。設定 → Skills の「Skill を追加」で、`skills/<name>` フォルダを ZIP にして「アップロード」するか、「新規作成」で `SKILL.md` の内容を貼り付けてください。チャットでは `/<name>`（例: `/lamp-setup`）で呼び出せます。詳しくは [Blaze ヘルプ「スキル（Skills）」](https://blaze.igness.ai/help/settings/skills) を参照してください。

### 手動コピー（Codex / その他のエージェント）

`skills/<name>/SKILL.md` を、作業フォルダのスキル置き場にコピーします。

| エージェント | コピー先 |
| --- | --- |
| Claude Code | `.claude/skills/<name>/SKILL.md` |
| Codex | `.agents/skills/<name>/SKILL.md` |

```bash
git clone https://github.com/igness-ai/lamp-skills.git
mkdir -p .claude/skills
cp -R lamp-skills/skills/* .claude/skills/
```

## 事前準備

- [Salesforce CLI](https://developer.salesforce.com/tools/salesforcecli) がインストールされ、対象組織に接続済みであること（`sf org list` で確認）
- 対象組織に Igness LAMP パッケージがインストール済みであること（バージョン要件は上の表を参照）
- 実行ユーザーがシステム管理者であること（`lamp-media-upload` は `LAMP_SystemAdministrator` または `LAMP_MarketingAdministrator` 権限セットグループでも可）

## 使用上の注意

- スキルは **お客様の Salesforce 組織を実際に変更します**。複数の組織に接続している場合、エージェントは最初に対象組織の確認を行います。組織の別名を正しく伝えてください
- スキルは冪等に作られています。途中で失敗しても、もう一度依頼すれば完了済みのステップは確認だけで通過し、途中から再開されます
- サーバー認証のブラウザでの承認、LINE Developers コンソールでの設定、スマホでの QR コード読み取りは人の操作が必要です。エージェントがその場面で依頼します
- チャネルシークレットやアップロード用の署名付き URL は認証情報です。会話ログに残したくない場合は、エージェントの案内に従って直接入力してください

## パッケージバージョンとの対応

スキルは LAMP パッケージが提供する global アクション（`igns__Lamp*Action`）を Actions API 経由で呼び出します。
アクションが存在しないバージョンでは `The requested resource does not exist`（404）になります。その場合はパッケージをアップグレードしてください。

| lamp-skills | LAMP パッケージ |
| --- | --- |
| 1.1.x | 1.156 以降を推奨（`lamp-setup` は 1.153 以降、`lamp-media-upload` は 1.155 以降、`lamp-template` は 1.156 以降で動作） |
| 1.0.x | `lamp-setup` / `lamp-media-upload` のみ |

## 関連リンク

- [Igness LAMP ヘルプ](https://help.igness.ai)
- [AIエージェントで自動セットアップ](https://help.igness.ai/lamp/getting-started/auto-setup-ai-agent)

## ライセンス

[MIT](LICENSE)
