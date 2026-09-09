---
name: lamp-agentforce
description: Igness LAMP の自動応答を種別 Agentforce で作成・設定し、開始条件、LINEからの動作確認、停止・会話終了まで行う。「LINEでAgentforceに回答させたい」「Agentforceの自動応答を設定して」「キーワードやリッチメニューからAgentforceを呼びたい」などで使う。Salesforce側で作成・有効化済みのAgentforceエージェントを接続するためのスキル。
---

# LAMP 自動応答（Agentforce）

`igns__Reply__c` の `igns__Type__c=Agentforce` と `igns__AgentforceAgentApiName__c` を設定し、LINE から届いたメッセージに Salesforce の Agentforce で回答する。
設定は Salesforce REST で保存する。回答生成は LAMP が `generateAiAgentResponse` を呼び、LINE への配送には LAMP サーバーを使う。

Prompt Builderで作成した返信ドラフトを担当者のチャット入力欄に出す設定は、`lamp-chat` の「文面提案エージェントID／テンプレート」で行う。

## 前提と対象の確認

- 本スキルは LAMP 基本パッケージ **1.157 以降**を対象にする。対象 org に `sf` で接続済みであること（以下 `<org>`）。
- 対象 org・公式アカウント・Agentforce の **API 参照名**・開始方法を依頼内容から特定し、不明なものだけ確認する。API 参照名は Salesforce のエージェント詳細で確認する。表示名やレコード Id を代入しない。
- Salesforce 側の Agentforce エージェントが作成・有効化済みで、プレビューで想定どおり回答すること。未作成ならその準備を案内し、LAMP 側の設定だけで Agentforce が作られるとは説明しない。
- `lamp-setup` によるサーバー認証・公式アカウント接続・自動化ユーザーへの LAMP 権限付与が完了していること。Agentforce を使う場合も LINE 配送の認証は必要。
- 設定する管理者の権限と、LINE 受信後に処理するユーザーの権限を分けて確認する。Platform Event トリガの実行ユーザー（既定は Automated Process。org 固有の指定があればそちら）に、対象 Agentforce を呼び出す権限と利用するオブジェクト・項目の権限が必要。管理者のプレビュー成功だけで受信経路の動作確認済みとしない。Agentforce 権限・ライセンスの名称や割当可否は対象 org で確認し、開発 org 用の設定をそのまま配備しない。

対象 org の項目・選択肢・編集権限を確認する:

```bash
sf sobject describe -s igns__Reply__c -o <org> --json > /tmp/lamp-reply-describe.json
sf sobject describe -s igns__AutoKeyword__c -o <org> --json > /tmp/lamp-keyword-describe.json
sf sobject describe -s igns__ReplyHistory__c -o <org> --json > /tmp/lamp-reply-history-describe.json
```

`Reply__c.Type__c` の有効な選択肢に `Agentforce` があり、`AgentforceAgentApiName__c` と `ReplyHistory__c.AgentforceSessionId__c` が利用できることを確認する。項目が見えなければパッケージ版と FLS を調べる。

## 1. 開始方法を選ぶ

**開始条件によって、最初の回答が変わる。**

| `igns__Condition__c` | 開始方法 | 最初の動作 |
|---|---|---|
| `NONE` | 常に反応 | 受信した内容をすぐ Agentforce に渡して回答する。開始テンプレートは送らない |
| `AND` / `OR` | キーワード・友だち項目の条件 | 条件一致で会話を開始し、`igns__Template__c` の開始テンプレートを送る。**次に受信するメッセージから** Agentforce が回答する |
| `CALLOUT` | テンプレートやリッチメニューの `callagent` アクション | ボタンで会話を開始し、開始テンプレートを送る。次のメッセージから Agentforce が回答する |

有効な自動応答は **同じ公式アカウント内で `Sort__c` の昇順に判定し、最初の一致だけを採用**する。既存設定を先に取得する:

```bash
sf data query -q "SELECT Id, Name, igns__Type__c, igns__Status__c, igns__Condition__c, igns__Sort__c, igns__Template__c, igns__AgentforceAgentApiName__c FROM igns__Reply__c WHERE igns__SocialAccount__c = '<socialAccountId>' ORDER BY igns__Sort__c ASC" -o <org>
```

同名の設定があれば再利用を検討し、重複作成しない。優先順は既存の空値・同順位も確認して決める。`NONE` を先頭へ追加すると後続の条件が使われなくなるため、通常は個別条件の後に置く。

既に AI 応答中の友だちは現在の会話を継続する。毎回キーワード条件を判定し直す仕組みではない。

## 2. 下書きを作る

キーワードで開始する例。`<startTemplateId>` は `lamp-template` で作成した「ご相談内容を送ってください」等の開始テンプレートとする。

```bash
cat > /tmp/lamp-agentforce-reply.json <<'EOF'
{
  "Name": "Agentforce お問い合わせ",
  "igns__SocialAccount__c": "<socialAccountId>",
  "igns__Type__c": "Agentforce",
  "igns__AgentforceAgentApiName__c": "<agentforceApiName>",
  "igns__Status__c": "draft",
  "igns__Condition__c": "AND",
  "igns__Sort__c": 10,
  "igns__Template__c": "<startTemplateId>",
  "igns__ConversationEndHour__c": 48
}
EOF
sf api request rest "/services/data/v67.0/sobjects/igns__Reply__c" --method POST -b @/tmp/lamp-agentforce-reply.json -o <org>
```

返った Id を `<replyId>` として保持する。修正は同じレコードへ `PATCH /services/data/v67.0/sobjects/igns__Reply__c/<replyId>`。稼働中の設定を変更する場合は、影響を確認して下書きへ戻し、編集後に再度有効化する。

| 項目 | 設定 |
|---|---|
| `igns__AgentforceAgentApiName__c` | Agentforce の API 参照名。保存時に必須として強制されないので、有効化前に空でないことを確認する |
| `igns__Template__c` | `AND` / `OR` / `CALLOUT` では開始テンプレートを指定する。有効なメッセージを 1〜5 件用意。`NONE` では不要 |
| `igns__ConversationEndHour__c` | 最終応答日時（まだ応答がなければ会話作成日時）から、自動終了の対象になるまでの時間。既定48時間。**終了は日次ジョブで判定するため、指定時間ちょうどには終了しない** |
| `igns__Sender__c` | 任意。Agentforce の回答に使用する送信元の表示名・アイコン。送信元の作成は `lamp-chat` を参照。開始テンプレートの送信元はテンプレート側で設定する |
| `igns__FinishedRichMenu__c` | 任意。会話終了時のリッチメニュー。同じ公式アカウントの発行済みメニューを選び、設定する場合は実機で終了後の表示も確認する |

Agentforce の呼び出しに `Reply__c.APIKey__c` は使用しない。秘密情報をこのレコードに追加する必要はない。

## 3. 開始条件・ボタンを設定する

### キーワード・友だち項目（AND / OR）

条件は `igns__AutoKeyword__c` に1行ずつ作る。先に既存条件を確認し、同じ条件を二重に追加しない:

```bash
sf data query -q "SELECT Id, Name, igns__ConditionType__c, igns__Condition__c, igns__Value__c FROM igns__AutoKeyword__c WHERE igns__Reply__c = '<replyId>'" -o <org>

cat > /tmp/lamp-agentforce-keyword.json <<'EOF'
{
  "igns__Reply__c": "<replyId>",
  "igns__ConditionType__c": "Keyword",
  "Name": "相談,問い合わせ",
  "igns__Condition__c": "EQ"
}
EOF
sf api request rest "/services/data/v67.0/sobjects/igns__AutoKeyword__c" --method POST -b @/tmp/lamp-agentforce-keyword.json -o <org>
```

| `ConditionType__c` | `Name` | `Condition__c` | `Value__c` |
|---|---|---|---|
| `Keyword` | 開始キーワード。カンマ区切りはその行の中で「いずれか」 | `EQ`（完全一致）/ `CONTAINS`（部分一致） | 不要 |
| `FriendField` | 友だちの項目 API 名（例 `igns__IsTest__c`、顧客項目なら `Interest__c`） | `EQ` / `CONTAINS` / `BLANK` / `NOT_BLANK` | 比較する文字列。チェックボックスなら `"true"` / `"false"`。空白判定は不要 |

`Regex__c` は保存時に自動生成されるので書かない。現行実装はキーワードを正規表現へそのまま組み込むため、`.`・`+`・`(` 等を含む語句は通常の文字列一致と異なる。記号を含めたい場合は生成結果と実際の一致を確認する。旧選択肢の「完全一致」「部分一致」は使わない。

テスト用の友だちだけに限定するには、上の `AND` に次の条件を追加する:

```json
{
  "igns__Reply__c": "<replyId>",
  "igns__ConditionType__c": "FriendField",
  "Name": "igns__IsTest__c",
  "igns__Condition__c": "EQ",
  "igns__Value__c": "true"
}
```

これで「開始キーワード一致 **かつ** テスト用の友だち」のときだけ新規会話が始まる。`OR` にするとテスト用以外もキーワードだけで一致する。`IsTest__c` は、この条件を設定しない限り自動応答の対象を制限しない。`NONE` / `CALLOUT` に条件レコードを追加してもテスト限定にはならない。

### ボタン起動（CALLOUT）

テンプレートの返信ボタン／カードのボタン、またはリッチメニューの領域に次を設定する:

- `igns__ActionType{n}__c = "callagent"`
- `igns__ActionReply{n}__c = "<replyId>"`
- ラベルや `ActionMessage{n}__c` は表示用途に合わせる。ボタンの表示メッセージを最初の Agentforce への質問として扱わない。

添字と保存先は `lamp-template` / `lamp-richmenu` を参照。リッチメニューの変更は再発行が必要。呼出元と自動応答の公式アカウントを揃える。公開中のボタンへテスト用設定を接続すると一般の友だちからも起動できるため、テスト専用のテンプレート・メニューを使う。

### 常に反応（NONE）

`igns__Condition__c="NONE"` とし、開始条件レコードは作らない。受信した最初の質問から回答する。テスト中だけ `AND` にすると初回動作が変わるので、`NONE` 自体の確認はテスト専用アカウント等、承認された範囲で行う。

## 4. Agentforce に渡す友だち情報（必要な場合）

LAMP が渡す変数名は次のとおり。利用する変数を Salesforce 側の Agentforce に用意し、**Allow value to be set by API** を有効にする。

| 変数名 | 値 |
|---|---|
| `SocialFriendId` | 友だちの Salesforce レコード Id |
| `Contact` | 友だちに関連する取引先責任者の Id（関連がある場合のみ） |
| `Lead` | 友だちに関連するリードの Id（関連がある場合のみ） |

`ContactId` / `LeadId` へ勝手に読み替えない。変数は識別子であり、人物情報そのものではない。関連レコードを読むアクションには、そのレコードへのアクセス権も必要。

## 5. 有効化と動作確認

公式アカウント・API 参照名・開始条件・優先順・開始テンプレートを提示し、有効化が依頼の承認範囲に含まれることを確認して実行する。下書き作成だけの依頼ならここで止める。既に明示された承認は取り直さない。

```bash
sf api request rest "/services/data/v67.0/sobjects/igns__Reply__c/<replyId>" --method PATCH -b '{"igns__Status__c":"valid"}' -o <org>
```

1. 承認されたテスト用の友だちに現在の AI 会話がないことを確認し、LINE から開始操作を行ってもらう。既存会話がある場合は、終了してよいかを確認してから次節の手順を使う。
2. `NONE` は初回の回答、`AND` / `OR` / `CALLOUT` は開始テンプレート→次の質問への回答を確認する。
3. 続けてもう1通送り、同じ会話を継続できるか確認する。`Contact` / `Lead` を利用する場合は関連先の情報が想定どおり扱われるかも確認する。

```bash
sf data query -q "SELECT Id, igns__IsAIReply__c, igns__CurrentAIReplyHistory__c FROM igns__SocialFriend__c WHERE Id = '<socialFriendId>'" -o <org>
sf data query -q "SELECT Id, CreatedDate, igns__AgentforceSessionId__c, igns__SendCount__c, igns__LastMessageDateTime__c, igns__EndDateTime__c, igns__IsProcessing__c, igns__IsError__c, igns__ErrorType__c FROM igns__ReplyHistory__c WHERE igns__Reply__c = '<replyId>' AND igns__SocialFriend__c = '<socialFriendId>' ORDER BY CreatedDate DESC LIMIT 5" -o <org> --json > /tmp/lamp-agentforce-history.json
```

セッション Id はローカルで継続の確認に使い、会話には値を出さず「保持／継続できた」と報告する。`AgentforceSessionId__c` は条件起動直後の開始テンプレートの段階では空でよい。Agentforce が回答した後に保存される。

`SendCount__c` は回答処理・エラー処理でも更新されるため、配送成功件数ではない。`IsError__c=false` や生成ジョブの完了だけで LINE 到着を断定しない。LINE 上の表示と配送ジョブを併せて確認する。`lamp-template` のテスト配信はテンプレート送信のみで、Agentforce の開始・継続のテストにはならない。

テスト限定の条件を本運用向けに変更する際は、対象が広がることを示して承認範囲を確認し、下書き→条件変更→再有効化の順で進める。

## 6. 停止・会話終了

**設定を下書きに戻すと新規起動は止まるが、既に始まった会話は継続する。** 両方止める依頼なら、まず設定を下書きへ戻し、対象の現在会話を確認して終了する。

```bash
sf api request rest "/services/data/v67.0/sobjects/igns__Reply__c/<replyId>" --method PATCH -b '{"igns__Status__c":"draft"}' -o <org>
```

現在の会話 Id は友だちの `CurrentAIReplyHistory__c` から取得し、その履歴が対象の `<replyId>` に属し、`EndDateTime__c` が空であることを再確認する。過去の履歴を一括で終了すると、現在の別の会話まで解除される可能性がある。

処理中ならまず完了を待つ。会話終了は実行済み・待機中のジョブの配送キャンセルを保証しない。処理が止まったままなら次節で原因を確認し、ロック項目を直接書き換えない。

```bash
# <現在のUTC日時> を実行時点の ISO 8601 値に置き換える
sf api request rest "/services/data/v67.0/sobjects/igns__ReplyHistory__c/<currentReplyHistoryId>" --method PATCH -b '{"igns__EndDateTime__c":"<現在のUTC日時>"}' -o <org>
```

トリガーが友だちの現在会話を解除する。`IsAIReply__c=false`・`CurrentAIReplyHistory__c` が空になったことを確認する。`IsAIReply__c` は数式項目なので直接書かない。終了メニューを設定している場合は表示も確認する。
これは LAMP 側の会話終了であり、Salesforce の Agentforce セッション削除を呼ぶ操作ではない。設定を有効のままにして会話だけ終了した場合は、次のメッセージが開始条件に一致すると新規会話が始まる。

## トラブルシューティングと制限

| 症状 | 確認すること |
|---|---|
| 開始しない | `Status=valid`、公式アカウント、優先順、条件を確認。`AND` / `OR` は条件が0件だと反応しない。既存会話中なら新規条件判定を通らない |
| 開始テンプレートだけ届く | 条件起動では正常。次のメッセージで Agentforce が回答するか確認する |
| `agentforce_config_error` | API 参照名が空、または設定を読み取れない。`Reply__c` の値と実行ユーザーの権限を確認 |
| `agentforce_error` | Agentforce 呼び出し失敗。エージェントの有効化・API 参照名・実行ユーザーのアクセス権を確認 |
| `agentforce_timeout` / `agentforce_network_error` | タイムアウト／処理例外の分類。詳細がこの項目に残るとは限らない。対象時間帯のジョブ・ログを確認してから再テストする |
| `IsProcessing__c=true` のまま／エラー履歴がないのに届かない | 回答生成に入る前の loading 処理や配送ジョブの失敗もあり得る。`AsyncApexJob` の `AgentforceMessageServiceJob` / `LampReplyMessageJob` / `ErrorMessageSendJob` をテスト開始時刻・実行ユーザーで絞り、`Status` / `ExtendedStatus` を確認。共有ジョブの最新1件だけで当該友だちの成功を断定しない |
| 友だちの関連情報が渡らない | `Contact` / `Lead` の関連、変数名、API からの値設定の許可、アクションの参照権限を確認 |
| 指定時間が過ぎても会話が続く | 自動終了は日次。`ReplyHistoryScheduler` の稼働と最終応答日時を確認 |

- 現行の Agentforce 経路はテキスト入力・テキスト返信。受信画像は `[画像メッセージ]`、動画等は種別の文字列に置換され、画像内容の解析は行わない。回答の画像・カード・クイックリプライへの自動変換はない。
- 処理中の連投は保留され、次のターンで改行連結される。セッション無効を検知した場合、製品側が新しいセッションで1回だけ再試行することがある。
- 継続キーは `AgentforceSessionId__c`。`ConversationId__c` は空で正常であり、Agentforce セッション Id を `/conversation/{id}` に渡さない。LINE 上の送受信履歴と Agentforce 内部の推論履歴は別物。

Salesforce 側の前提を調べる場合は [Agentforce の Apex / Flow 呼び出し](https://developer.salesforce.com/blogs/2025/04/invoke-agentforce-agents-with-apex-and-flow) と [API から設定する変数](https://developer.salesforce.com/docs/ai/agentforce/guide/agent-api-variables.html) を参照する。LAMP 固有の開始・終了動作は上記手順に従う。
