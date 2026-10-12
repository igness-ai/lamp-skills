---
name: lamp-slack-notify
description: Igness LAMP で友だちから LINE メッセージを受信したら Slack に通知するフローを、Salesforce CLI でヘッドレスに作る。LAMP のプラットフォームイベント（igns__LampNotification__e）で起動するフローのひな形を使い、Salesforce 標準の Slack アクション（slackPostMessage）で投稿する。「LINEでメッセージが来たらSlackに通知したい」「受信メッセージをSlackのチャンネルに流したい」などで使う。
---

# LINE の受信メッセージを Slack に通知（ヘッドレス）

LAMP は友だちから LINE メッセージを受信するたびに、プラットフォームイベント **`igns__LampNotification__e`** を発行する。これを受けるフローで受信メッセージかを判定し、友だちを特定して、Salesforce 標準の Slack アクション **`slackPostMessage`** でチャンネルに投稿する。

```
友だちが LINE でメッセージを送る → LAMP が igns__LampNotification__e を発行
  → フロー（プラットフォームイベントで起動）
      ① 通知対象か（受信・1:1のトーク・メッセージの種類・公式アカウント）
      ② 友だちを特定（LAMP ID + LINE ユーザーID）
      ③ slackPostMessage でチャンネルへ投稿（友だちへのリンクと本文）
```

このスキルで作るのは、プラットフォームイベントで起動する、友だちとの1:1トークのメッセージ受信の通知だけ。

グループトークのメッセージも同じイベント（同じ `MSG_TEXT` などの種類）で届き、`igns__GroupId__c` に値が入る。ひな形は `igns__GroupId__c` が空のイベントだけを通知するので、グループでの発言が友だちからの1:1メッセージとして通知されることはない。`igns__GroupId__c` は、グループトークに対応した LAMP パッケージに入っている項目なので、それより古いパッケージの組織ではデプロイの検証で失敗する（パッケージを更新してから作る）。

## ひな形

[metadata](references/metadata/) の `LAMP_Slack_OnMessage` を使う。公式アカウントごとに通知先チャンネルを分ける場合は、コピーしてファイル名（= API 名）を変え、公式アカウントごとに1本ずつ作る。

| プレースホルダー | 内容 | 例 |
|---|---|---|
| `{{FLOW_LABEL}}` | フローの表示ラベル | `LAMP Slack通知 メッセージ受信` |
| `{{EVENT_TYPES}}` | 通知するメッセージの種類をカンマ区切り（空白なし） | `MSG_TEXT`（画像・スタンプも含めるなら `MSG_TEXT,MSG_IMAGE,MSG_STICKER`） |
| `{{LAMP_ID}}` | 公式アカウントで絞るときの LAMP ID。空なら全公式アカウント | `7piwg` |
| `{{SLACK_APP_ID}}` | Salesforce の Slack アプリの ID | 手順2 |
| `{{SLACK_WORKSPACE_ID}}` | ワークスペース ID（`T` で始まる） | 手順2 |
| `{{SLACK_CHANNEL_ID}}` | チャンネル ID（`C` で始まる） | 手順2 |
| `{{SLACK_MESSAGE}}` | 投稿する本文。下記の差し込みが使える | |

メッセージの種類（`igns__EventType__c`、受信時）:

| 種類 | 内容 | `Message__c` に入るもの |
|---|---|---|
| `MSG_TEXT` | テキスト | 本文 |
| `MSG_IMAGE` / `MSG_VIDEO` / `MSG_AUDIO` | 画像・動画・音声 | 種類の説明（本文は無い） |
| `MSG_STICKER` | スタンプ | 種類の説明 |
| `MSG_FILE` | ファイル | ファイル名 |
| `MSG_LOCATION` | 位置情報 | 種類の説明 |

本文に使える差し込み:

| 差し込み | 内容 |
|---|---|
| `{!FriendLink}` | 友だちレコードへのリンク（Slack 上は友だちの表示名） |
| `{!$Record.igns__Message__c}` | 受信したテキスト（上の表） |
| `{!GetSocialFriend.<項目>}` | 友だちの項目。例 `{!GetSocialFriend.Name}` |

本文の例:

````
💬 {!FriendLink} さんからLINEメッセージが届きました
```
{!$Record.igns__Message__c}
```
````

## 前提条件

- LAMP 基本パッケージがインストール済みで、公式アカウントが接続済み
- `sf` CLI で対象 org に認証済み（以下 `<org>`）。実行ユーザーはシステム管理者
- **Salesforce と Slack の連携が済んでいること**（設定 →「Slack」で Slack 連携の利用を有効化、Salesforce の Slack アプリをワークスペースに導入）。通知先チャンネル（特に非公開チャンネル）にはそのアプリを追加しておく。これらは画面での操作なので、ユーザーに行ってもらう
- **必ず最初に対象 org をユーザーに確認する**

## 守ること

- 顧客 org へのデプロイは、手順2で内容（フロー名・対象・チャンネル・本文）を見せて了承を得てから行う
- Slack のトークンや Webhook URL は扱わない。フローに書くのはアプリ・ワークスペース・チャンネルの ID だけ
- 既に受信メッセージを通知しているフローがあれば、重複通知になるのでユーザーに確認する
- 本番のチャンネルにテスト投稿する前に、ユーザーに確認する

## 手順1: 事前診断（読み取りのみ）

```bash
# 公式アカウントと LAMP ID
sf data query -q "SELECT Id, Name, igns__LampId__c FROM igns__SocialAccount__c" -o <org>

# 既存の LAMP イベントのフロー（重複と、既存フローの Slack の ID の確認）
sf data query -q "SELECT ApiName, Label, TriggerType, IsActive FROM FlowDefinitionView WHERE IsActive = true AND TriggerObjectOrEvent.QualifiedApiName = 'igns__LampNotification__e'" -o <org>
```

既存の Slack 通知フローがあれば取得して `slackAppIdForToken` / `slackWorkspaceIdForToken` を読み、同じ値を使う（ユーザーに ID を聞く手間が省ける）:

```bash
sf project retrieve start -m "Flow:<ApiName>" -o <org> --output-dir /tmp/lsn-existing
grep -A3 "slackAppIdForToken\|slackWorkspaceIdForToken" /tmp/lsn-existing/flows/<ApiName>.flow-meta.xml
```

## 手順2: ユーザーに確認する

1. **メッセージの種類**: テキストだけか、画像・スタンプなども含めるか（`{{EVENT_TYPES}}`）
2. **公式アカウント**: 全部か、特定の公式アカウントだけか（`{{LAMP_ID}}`）。公式アカウントごとにチャンネルを分けたい場合は、公式アカウントごとにフローを1本ずつ作る
3. **Slack の ID**
   - アプリ ID: 既存フローから取れればそれを使う。無ければ既定値 `A03269G3DNE`（Salesforce の Slack アプリ）を使い、手順3の検証で確かめる
   - ワークスペース ID・チャンネル ID: Slack でチャンネル名をクリック →「チャンネル詳細」の最下部にチャンネル ID（`C…`）。ワークスペース ID（`T…`）はブラウザ版 Slack の URL `app.slack.com/client/T…/C…` から分かる
4. **本文**（上の例をもとに提案する）
5. **フロー名**: 既定 `LAMP_Slack_OnMessage`。公式アカウントごとに作る場合は `LAMP_Slack_OnMessage_<公式アカウント>` など

## 手順3: 反映

```bash
cp -R <このスキルのディレクトリ>/references/metadata /tmp/lamp-slack-notify && cd /tmp/lamp-slack-notify

python3 - force-app/main/default/flows/LAMP_Slack_OnMessage.flow-meta.xml <<'EOF'
import sys
from xml.sax.saxutils import escape
p = sys.argv[1]
values = {
    '{{FLOW_LABEL}}': 'LAMP Slack通知 メッセージ受信',
    '{{EVENT_TYPES}}': 'MSG_TEXT',
    '{{LAMP_ID}}': '',
    '{{SLACK_APP_ID}}': 'A03269G3DNE',
    '{{SLACK_WORKSPACE_ID}}': '<T…>',
    '{{SLACK_CHANNEL_ID}}': '<C…>',
    '{{SLACK_MESSAGE}}': '💬 {!FriendLink} さんからLINEメッセージが届きました\n```\n{!$Record.igns__Message__c}\n```',
}
s = open(p, encoding='utf-8').read()
for k, v in values.items():
    s = s.replace(k, escape(v).replace('"', '&quot;'))
assert '{{' not in s, 'プレースホルダーが残っている'
open(p, 'w', encoding='utf-8').write(s)
EOF

sf project deploy start -d force-app -o <org> --dry-run --wait 10   # 先に検証だけ
sf project deploy start -d force-app -o <org> --wait 10
```

- `{{LAMP_ID}}` に `"` を含めない（判定式の文字列になるため）
- 検証で「slackPostMessage アクションが見つかりませんでした」と出たら、Salesforce と Slack の連携がまだ。前提条件の画面操作をユーザーに依頼する
- 公式アカウントごとに複数作るときは、ファイル名（API 名）とラベルを必ず変える
- フローは有効（`Active`）で入る。先に無効で入れたい場合は `<status>Draft</status>` にする

## 手順4: 確認

本番チャンネルに流れてよいかを先にユーザーに確認し、テスト用の友だち（ユーザーのスマートフォン）から公式アカウントにメッセージを送ってもらい、Slack に届くかを見る。

届かないとき:

```bash
# LAMP 側がイベントを受け取っているか
sf data query -q "SELECT Name, Status, Position, Tip, LastError FROM EventBusSubscriber WHERE Topic = 'igns__LampNotification__e'" -o <org>
```

## トラブルシューティング

| 症状 | 原因と対処 |
|---|---|
| デプロイの検証で `slackPostMessage` が見つからない | Salesforce と Slack の連携が未設定。設定 →「Slack」でユーザーに有効化してもらう |
| 何も届かない | 通知先チャンネルに Salesforce の Slack アプリが追加されていない（非公開チャンネルでは必須）。ワークスペース・チャンネル ID の取り違え |
| 画像やスタンプが通知されない | `{{EVENT_TYPES}}` が `MSG_TEXT` だけになっている |
| デプロイの検証で `igns__GroupId__c` が見つからない | LAMP パッケージがグループトーク対応より前のバージョン。パッケージを更新する |
| グループでの発言が友だちのメッセージとして通知される | このスキルの以前のひな形で作ったフロー。通知対象の条件に `ISBLANK({!$Record.igns__GroupId__c})` を足して作り直す |
| 失敗に気づけない | プラットフォームイベントのフローの失敗は画面に出ない。設定 →「プロセスの自動化設定」のフローエラーメールの宛先を確認する |

## 元に戻す

フローを無効化すれば通知は止まる。画面の「フロー」から無効化するか、次の手順で無効化・削除する。

```bash
# 無効化（有効なフローはこのままでは削除できない）
sf data query -q "SELECT Id FROM FlowDefinition WHERE DeveloperName = '<フローAPI名>'" --use-tooling-api -o <org>
echo '{"Metadata":{"activeVersionNumber":0}}' > /tmp/fd-off.json
sf api request rest "/services/data/v67.0/tooling/sobjects/FlowDefinition/<FlowDefinitionId>" --method PATCH -b @/tmp/fd-off.json -o <org>
# 削除する場合（ユーザーの指示があるときだけ）: バージョンごとに消す
sf data query -q "SELECT Id, VersionNumber, Status FROM Flow WHERE Definition.DeveloperName = '<フローAPI名>'" --use-tooling-api -o <org>
sf data delete record -s Flow -i <FlowのバージョンId> --use-tooling-api -o <org>
```
