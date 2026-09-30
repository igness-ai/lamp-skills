---
name: lamp-slack-notify
description: Igness LAMP の LINE の出来事（メッセージ受信・友だち追加・ブロック・特定ボタンの押下・LIFFログインなど）を Slack に通知するフローを、Salesforce CLI でヘッドレスに作る。LAMP のプラットフォームイベント（igns__LampNotification__e）で起動するフローと、友だち作成で起動するフローのひな形を使い、Salesforce 標準の Slack アクション（slackPostMessage）で投稿する。「LINEでメッセージが来たらSlackに通知したい」「友だち追加をSlackで知りたい」「ボタンが押されたらSlackに流して」などで使う。
---

# LAMP の出来事を Slack に通知（ヘッドレス）

LAMP は LINE の送受信や友だち追加のたびに、プラットフォームイベント **`igns__LampNotification__e`** を発行する。これを受けるフローで条件を判定し、友だちを特定して、Salesforce 標準の Slack アクション **`slackPostMessage`** でチャンネルに投稿する。

```
LINE の出来事 → LAMP が igns__LampNotification__e を発行
  → フロー（プラットフォームイベントで起動）
      ① 通知対象か（方向・イベント種別・公式アカウント・ボタンの表示文）
      ② 友だちを特定（LAMP ID + LINE ユーザーID）
      ③ slackPostMessage でチャンネルへ投稿（友だちへのリンク付き）

友だち追加だけは、友だちレコードの作成で起動するフロー（コミット後の非同期パス）を使う
```

## ひな形

[metadata](references/metadata/) の2本を用途ごとにコピーし、ファイル名（= API 名）を変えて使う。1つの用途に1本のフローにする。

| ひな形 | 起動 | 使う用途 |
|---|---|---|
| `LAMP_Slack_OnLineEvent` | プラットフォームイベント `igns__LampNotification__e` | メッセージ受信、ブロック／ブロック解除、特定ボタンの押下、LIFF ログイン、送信の通知 |
| `LAMP_Slack_OnNewFriend` | 友だち（`igns__SocialFriend__c`）の作成・コミット後の非同期パス | 友だち追加 |

友だち追加をプラットフォームイベント（`ADD_FRIEND`）で拾うと、LAMP が友だちレコードを作る処理と並行して動くため、まだ友だちが見つからず通知が抜けることがある。友だち追加は必ず `LAMP_Slack_OnNewFriend` を使う。

`LAMP_Slack_OnNewFriend` は友だちレコードの作成すべてで動く。公式アカウントの「友だち情報を取得」（過去の友だちの一括取り込み）やデータ取り込みを行うと、その人数分の通知が出る。一括取り込みの前にはフローを無効化し、終わってから有効に戻すようユーザーに伝える。

置き換えるプレースホルダー:

| プレースホルダー | 内容 | 例 |
|---|---|---|
| `{{FLOW_LABEL}}` | フローの表示ラベル | `LAMP Slack通知 メッセージ受信` |
| `{{DIRECTION}}` | `incoming`（LINE→Salesforce）／`outgoing`（Salesforce→LINE） | `incoming` |
| `{{EVENT_TYPES}}` | 通知するイベント種別をカンマ区切り（空白なし） | `MSG_TEXT,MSG_IMAGE,MSG_STICKER` |
| `{{LAMP_ID}}` | 公式アカウントで絞るときの LAMP ID。空なら全公式アカウント | `7piwg` |
| `{{MESSAGE_EQUALS}}` | ボタンの表示文（`Message__c`）で絞るとき。空なら問わない | `お問い合わせ` |
| `{{SLACK_APP_ID}}` | Salesforce の Slack アプリの ID | 下記「Slack の ID」 |
| `{{SLACK_WORKSPACE_ID}}` | ワークスペース ID（`T` で始まる） | |
| `{{SLACK_CHANNEL_ID}}` | チャンネル ID（`C` で始まる） | |
| `{{SLACK_MESSAGE}}` | 投稿する本文。下記の差し込みが使える | |

`LAMP_Slack_OnNewFriend` は `{{DIRECTION}}` / `{{EVENT_TYPES}}` / `{{MESSAGE_EQUALS}}` を持たない。

本文に使える差し込み:

| 差し込み | 内容 |
|---|---|
| `{!FriendLink}` | 友だちレコードへのリンク（Slack 上は友だちの表示名） |
| `{!$Record.igns__Message__c}` | 受信・送信したテキスト。ボタンでは表示文、画像などは種別の説明（`OnLineEvent` のみ） |
| `{!$Record.igns__EventType__c}` | イベント種別（`OnLineEvent` のみ） |
| `{!GetSocialFriend.<項目>}` | 友だちの項目（`OnLineEvent`）。例 `{!GetSocialFriend.Name}` |
| `{!$Record.<項目>}` | 友だちの項目（`OnNewFriend`） |

本文の例:

| 用途 | 本文 |
|---|---|
| メッセージ受信 | ``💬 {!FriendLink} さんからLINEメッセージが届きました`` ＋ 改行 ＋ ```` ``` ```` で囲んだ `{!$Record.igns__Message__c}` |
| 友だち追加 | `🎉 {!FriendLink} さんが友だち追加しました` |
| ブロック | `🚫 {!FriendLink} さんにブロックされました` |
| ボタンの押下 | `🔔 {!FriendLink} さんが「{!$Record.igns__Message__c}」を押しました` |

## イベント種別（`igns__EventType__c`）

| 方向 | 種別 | 意味 |
|---|---|---|
| incoming | `MSG_TEXT` / `MSG_IMAGE` / `MSG_VIDEO` / `MSG_AUDIO` / `MSG_FILE` / `MSG_STICKER` / `MSG_LOCATION` | 友だちからのメッセージ |
| incoming | `MSG_POSTBACK` | リッチメニュー・テンプレートのボタン（テンプレート呼出・AI呼出）の押下。表示文は `Message__c` |
| incoming | `ADD_FRIEND` / `BLOCKED` / `UNBLOCKED` | 友だち追加・ブロック・ブロック解除 |
| incoming | `RICHMENU_CHANGED` | タブ切り替えなどでリッチメニューが変わった |
| incoming | `LOGIN` | 流入経路の URL（LIFF）を開いた |
| outgoing | `MSG_TEXT` / `MSG_IMAGE` / `MSG_VIDEO` / `MSG_FLEX` など | 公式アカウントからの送信（1to1・自動応答・配信） |

コンバージョンはプラットフォームイベントを通らない（現行パッケージではバックエンドが Apex REST `/tracking/events` へ送り、友だちアクティビティ `igns__SocialFriendActivity__c` に `igns__Conversion__c` 付きで記録する。`CONVERSION` のイベントが出るのは、この Apex REST を持たない古いパッケージの org だけ）。コンバージョンを通知するときは `LAMP_Slack_OnNewFriend` をもとに、起動オブジェクトを `igns__SocialFriendActivity__c`（作成時・非同期パス）に変え、`igns__Conversion__c` が空でないものだけを対象にする。友だちへのリンクは `$Record.igns__SocialFriend__c` から組み立てる。

`outgoing` を通知にすると、一斉配信では宛先の人数分の通知が出る。送信の通知は用途（例: 特定の公式アカウントだけ）を絞る。

ボタンの押下を通知するときは、押したボタンに**表示文**（テンプレートの `ActionMessage`、リッチメニューの `ActionMessage{n}`）を設定しておき、その文言を `{{MESSAGE_EQUALS}}` に入れる。表示文が無いボタンは `Message__c` が空になり区別できない。

## 前提条件

- LAMP 基本パッケージがインストール済みで、公式アカウントが接続済み
- `sf` CLI で対象 org に認証済み（以下 `<org>`）。実行ユーザーはシステム管理者
- **Salesforce と Slack の連携が済んでいること**（設定 →「Slack」で Slack 連携の利用を有効化、Salesforce の Slack アプリをワークスペースに導入）。通知先チャンネル（特に非公開チャンネル）にはそのアプリを追加しておく。これらは画面での操作なので、ユーザーに行ってもらう
- **必ず最初に対象 org をユーザーに確認する**

## 守ること

- 顧客 org へのデプロイは、手順2で内容（フロー名・条件・チャンネル・本文）を見せて了承を得てから行う
- Slack のトークンや Webhook URL は扱わない。フローに書くのはアプリ・ワークスペース・チャンネルの ID だけ
- 既に同じ出来事を通知しているフローがあれば、重複通知になるのでユーザーに確認する
- 本番のチャンネルにテスト投稿する前に、ユーザーに確認する

## 手順1: 事前診断（読み取りのみ）

```bash
# 公式アカウントと LAMP ID
sf data query -q "SELECT Id, Name, igns__LampId__c FROM igns__SocialAccount__c" -o <org>

# 既存の Slack 通知・LAMP イベントのフロー（重複と、既存フローの Slack の ID の確認）
sf data query -q "SELECT ApiName, Label, TriggerType, IsActive FROM FlowDefinitionView WHERE IsActive = true AND (TriggerObjectOrEvent.QualifiedApiName IN ('igns__LampNotification__e','igns__SocialFriend__c'))" -o <org>
```

既存の Slack 通知フローがあれば取得して `slackAppIdForToken` / `slackWorkspaceIdForToken` を読み、同じ値を使う（ユーザーに ID を聞く手間が省ける）:

```bash
sf project retrieve start -m "Flow:<ApiName>" -o <org> --output-dir /tmp/lsn-existing
grep -A3 "slackAppIdForToken\|slackWorkspaceIdForToken" /tmp/lsn-existing/flows/<ApiName>.flow-meta.xml
```

## 手順2: ユーザーに確認する

1. **通知したい出来事**（複数可）→ ひな形と `{{DIRECTION}}` / `{{EVENT_TYPES}}` を決める
2. **公式アカウント**: 全部か、特定の公式アカウントだけか（`{{LAMP_ID}}`）。公式アカウントごとにチャンネルを分けたい場合は、公式アカウントごとにフローを1本ずつ作る
3. **Slack の ID**
   - アプリ ID: 既存フローから取れればそれを使う。無ければ既定値 `A03269G3DNE`（Salesforce の Slack アプリ）を使い、手順3の検証で確かめる
   - ワークスペース ID・チャンネル ID: Slack でチャンネル名をクリック →「チャンネル詳細」の最下部にチャンネル ID（`C…`）。ワークスペース ID（`T…`）はブラウザ版 Slack の URL `app.slack.com/client/T…/C…` から分かる
4. **本文**（上の例をもとに提案する）
5. **フロー名**: 例 `LAMP_Slack_OnMessage`、`LAMP_Slack_OnNewFriend`、`LAMP_Slack_OnBlocked`、`LAMP_Slack_OnInquiryButton`

## 手順3: 反映

```bash
cp -R <このスキルのディレクトリ>/references/metadata /tmp/lamp-slack-notify && cd /tmp/lamp-slack-notify
# 使うひな形を用途の名前でコピーし、使わないものは消す（例: メッセージ受信）
cd force-app/main/default/flows
mv LAMP_Slack_OnLineEvent.flow-meta.xml LAMP_Slack_OnMessage.flow-meta.xml
rm LAMP_Slack_OnNewFriend.flow-meta.xml   # 友だち追加も作るなら残す
cd /tmp/lamp-slack-notify

python3 - force-app/main/default/flows/LAMP_Slack_OnMessage.flow-meta.xml <<'EOF'
import sys
from xml.sax.saxutils import escape
p = sys.argv[1]
values = {
    '{{FLOW_LABEL}}': 'LAMP Slack通知 メッセージ受信',
    '{{DIRECTION}}': 'incoming',
    '{{EVENT_TYPES}}': 'MSG_TEXT,MSG_IMAGE,MSG_STICKER',
    '{{LAMP_ID}}': '',
    '{{MESSAGE_EQUALS}}': '',
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

- `{{LAMP_ID}}` / `{{MESSAGE_EQUALS}}` に `"` を含めない（判定式の文字列になるため）
- 検証で「slackPostMessage アクションが見つかりませんでした」と出たら、Salesforce と Slack の連携がまだ。前提条件の画面操作をユーザーに依頼する
- 同じひな形から複数の用途を作るときは、ファイル名（API 名）とラベルを必ず変える
- フローは有効（`Active`）で入る。先に無効で入れたい場合は `<status>Draft</status>` にする

## 手順4: 確認

テスト用の友だち（ユーザーのスマートフォン）で実際に出来事を起こしてもらい、Slack に届くかを見る。本番チャンネルに流れてよいか、先にユーザーに確認する。

| 用途 | 確認のしかた |
|---|---|
| メッセージ受信 | 公式アカウントにメッセージを送ってもらう |
| 友だち追加 | ブロック→ブロック解除ではなく、友だち追加（新しい友だちレコードの作成）で確認する |
| ブロック | ブロックしてもらう（確認後に解除してもらう） |
| ボタンの押下 | 対象のボタンを押してもらう |

届かないとき:

```bash
# イベントが届いているか（LAMP 側の受信処理）
sf data query -q "SELECT Name, Status, Position, Tip, LastError FROM EventBusSubscriber WHERE Topic = 'igns__LampNotification__e'" -o <org>
```

## トラブルシューティング

| 症状 | 原因と対処 |
|---|---|
| デプロイの検証で `slackPostMessage` が見つからない | Salesforce と Slack の連携が未設定。設定 →「Slack」でユーザーに有効化してもらう |
| 何も届かない | 通知先チャンネルに Salesforce の Slack アプリが追加されていない（非公開チャンネルでは必須）。ワークスペース・チャンネル ID の取り違え |
| 友だち追加だけ届かない | プラットフォームイベント `ADD_FRIEND` で作っている。`LAMP_Slack_OnNewFriend` に切り替える |
| ボタンの押下が区別できない | ボタンに表示文が無い、または `{{MESSAGE_EQUALS}}` と表示文が一致していない |
| 送信の通知が大量に来る | `outgoing` を対象にしていて一斉配信の分も通知している。公式アカウントや種別を絞る |
| 失敗に気づけない | プラットフォームイベントのフローの失敗は画面に出ない。設定 →「プロセスの自動化設定」のフローエラーメールの宛先を確認する |

## 元に戻す

フローを無効化すれば通知は止まる。画面の「フロー」から無効化するか、`<status>Obsolete</status>` にして再デプロイする。

```bash
# 無効化（有効なフローはこのままでは削除できない）
sf data query -q "SELECT Id FROM FlowDefinition WHERE DeveloperName = '<フローAPI名>'" --use-tooling-api -o <org>
echo '{"Metadata":{"activeVersionNumber":0}}' > /tmp/fd-off.json
sf api request rest "/services/data/v67.0/tooling/sobjects/FlowDefinition/<FlowDefinitionId>" --method PATCH -b @/tmp/fd-off.json -o <org>
# 削除する場合（ユーザーの指示があるときだけ）: バージョンごとに消す
sf data query -q "SELECT Id, VersionNumber, Status FROM Flow WHERE Definition.DeveloperName = '<フローAPI名>'" --use-tooling-api -o <org>
sf data delete record -s Flow -i <FlowのバージョンId> --use-tooling-api -o <org>
```
