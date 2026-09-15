# lamp-skills

[Igness LAMP / BRAIN](https://www.igness.ai) を AI コーディングエージェントから操作するためのスキル集です。
[Blaze](https://blaze.igness.ai/)・Claude Code・Codex をはじめ、Salesforce CLI（`sf`）を実行できるエージェントであれば同じ手順書で動作します。

| スキル | できること | 必要なパッケージ |
| --- | --- | --- |
| [`lamp-setup`](skills/lamp-setup/SKILL.md) | パッケージインストール後の初期設定（権限割当・サーバー認証・パス有効化）と LINE 公式アカウント接続を自動で進める | Igness LAMP **1.153 以降** |
| [`lamp-media-upload`](skills/lamp-media-upload/SKILL.md) | 画像・動画をコンテンツ配信基盤へアップロードし、テンプレートメッセージ・クーポン・リッチメニュー・送信元アイコンに設定する | Igness LAMP **1.155 以降** |
| [`lamp-template`](skills/lamp-template/SKILL.md) | テンプレートと9種類のテンプレートメッセージ（テキスト／画像／動画／リンク付き画像／カード／設問（2択）／カード（画像のみ）／クーポン／フレックス）を作成し、有効化エラーを読んで修正、返信ボタン・項目の代入・テスト配信まで行う | Igness LAMP **1.156 以降** |
| [`lamp-broadcast`](skills/lamp-broadcast/SKILL.md) | 一斉配信を作成・スケジュール・キャンセルし、配信の状態確認、配信結果（成功／失敗、個人別 CSV）、既読数・クリック数の取得まで行う。対象は CSV と Salesforce レポートの両方に対応し、レポート＋繰り返しでセグメント定期配信・友だち追加 N 日後のステップ配信を組む | Igness LAMP **1.157 以降** |
| [`lamp-richmenu`](skills/lamp-richmenu/SKILL.md) | リッチメニューを作成・検証・LINE に発行し、デフォルト設定・友だち個別の割当・差し替え・削除まで行う | Igness LAMP **1.157 以降** |
| [`lamp-coupon`](skills/lamp-coupon/SKILL.md) | LINE クーポンを作成・検証・発行し、テンプレートへの組み込み、内容変更（複製→再発行）、終了まで行う | Igness LAMP **1.157 以降** |
| [`lamp-agentforce`](skills/lamp-agentforce/SKILL.md) | 自動応答の種別を Agentforce に設定し、開始条件・ボタン起動・会話継続の確認・停止まで行う | Igness LAMP **1.157 以降**＋利用可能な Agentforce エージェント |
| [`lamp-bot`](skills/lamp-bot/SKILL.md) | Bot自動応答の条件と固定テンプレートを設定し、受付カード・リッチメニューからAgentforceへつなぐ構成をまとめて作る | Igness LAMP **1.157 以降**。AIへの接続には利用可能なAgentforceエージェントも必要 |
| [`lamp-chat`](skills/lamp-chat/SKILL.md) | チャットコンポーネントの配置・高さ・QuickText・送信元を設定し、Prompt Builderの返信ドラフトを接続する | Igness LAMP **1.157 以降**。返信ドラフトは利用可能なプロンプトテンプレートも必要 |

## インストール

### Blaze（推奨）

[Blaze](https://blaze.igness.ai/) では、このリポジトリの URL を入れるだけで全スキルをまとめて追加できます（Blaze 0.17.1 以降）。

- 設定 → Skills → 「追加」で `https://github.com/igness-ai/lamp-skills` を入力する
- または、チャットに次を送る

```
/skill-install https://github.com/igness-ai/lamp-skills
```

`skills/` 配下の全スキルが `references/`・`scripts/` ごと導入され、以後はチャットで `/lamp-setup` のように呼び出すか、「LAMP でカードメッセージのテンプレートを作って」のように依頼するだけで対応するスキルが使われます。
更新するときは同じ URL でもう一度追加し、「置き換え」を選びます。組織の他のメンバーへ配るには、導入したスキルを「ライブラリに共有」してください。
詳しくは [Blaze ヘルプ「スキル（Skills）」](https://help.igness.ai/blaze/settings/skills) を参照してください。

### Claude Code

```
/plugin marketplace add igness-ai/lamp-skills
/plugin install lamp@lamp-skills
```

以後は「LAMP をセットアップして」「LAMP に画像をアップロードして」「LAMP でカードメッセージのテンプレートを作って」「毎朝 9 時に配信して」「リッチメニューを発行して」「クーポンを作って」「LINE の自動応答を Agentforce にして」「Botで問い合わせ内容を選んでAgentforceにつなぐ受付を一式作って」「チャットの返信ドラフトと送信元を設定して」のように依頼するだけで、対応するスキルが使われます。
更新は `/plugin update lamp@lamp-skills` で取り込めます。

### 手動コピー（Codex / その他のエージェント）

`skills/` 以下のスキルフォルダを、`references/`・`scripts/` を含めて同じ階層へコピーします。組み合わせて使うスキルも導入してください。

| エージェント | コピー先 |
| --- | --- |
| Claude Code | `.claude/skills/<name>/` |
| Codex | `.agents/skills/<name>/` |

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
| 1.5.x | 1.4.x に `lamp-bot`、受付からAgentforceへの接続手順、レポートの宛先検証、参照項目の確認、テンプレートの詳細制約を追加 |
| 1.4.x | 1.3.x に `lamp-agentforce` / `lamp-chat` を追加（基本パッケージ 1.157 以降を対象。自動応答にはAgentforceエージェント、返信ドラフトにはプロンプトテンプレートが必要） |
| 1.3.x | 1.2.x と同じ。REST 呼び出しを API v67.0 に統一、`lamp-broadcast` にレポート配信・繰り返し・ステップ配信を追加 |
| 1.2.x | 1.157 以降を推奨（`lamp-broadcast` / `lamp-richmenu` / `lamp-coupon` は 1.157 以降で動作。他は 1.1.x と同じ） |
| 1.1.x | 1.156 以降を推奨（`lamp-setup` は 1.153 以降、`lamp-media-upload` は 1.155 以降、`lamp-template` は 1.156 以降で動作） |
| 1.0.x | `lamp-setup` / `lamp-media-upload` のみ |

## 関連リンク

- [Igness LAMP ヘルプ](https://help.igness.ai)
- [AIエージェントで自動セットアップ](https://help.igness.ai/lamp/getting-started/auto-setup-ai-agent)

## ライセンス

[MIT](LICENSE)
