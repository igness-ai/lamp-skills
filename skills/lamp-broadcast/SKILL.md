---
name: lamp-broadcast
description: Igness LAMP の一斉配信（配信設定）を Salesforce CLI でヘッドレスに作成・スケジュール・キャンセルし、配信の状態確認、配信結果（成功／失敗、個人別 CSV）、既読数・クリック数の取得まで行う。「LAMPで配信を予約して」「毎朝9時に配信して」「配信が届いたか確認して」「既読率を教えて」などで使う。
---

# LAMP 一斉配信（ヘッドレス）

LAMP の一斉配信は **配信設定（`igns__Broadcast__c`）** というレコードで表す。「誰に（対象）」「何を（テンプレート）」「いつ（1 回 or 繰り返し）」を持ち、`igns__Status__c` を `scheduled` にした瞬間にスケジュールされる。
配信のたびに **配信履歴（`igns__BroadcastHistory__c`）** が 1 件できて、送信数・成功数・失敗数・既読数・クリック数が入る。

```
① 対象の抽出       SOQL で友だち（igns__SocialFriend__c）を選び、CSV にする
② 配信設定の作成   igns__Broadcast__c（draft）＋ CSV を ContentVersion として添付
③ 事前検証         テンプレートの有効メッセージ数・CSV 形式・日時・ジョブ枠
④ スケジュール     Status__c を scheduled に更新（ここで初めて確定。必ずユーザー確認）
⑤ 状態確認         Actions API igns__LampGetBroadcastStatusAction（phase で判定）
⑥ 結果と統計       igns__BroadcastHistory__c、個人別 CSV、既読数・クリック数
```

## 前提条件

- LAMP 基本パッケージ **1.157 以降**（状態確認アクション・エラー記録・統計取得状況。配信設定そのものは 1.152 以降でも作れる）
- `sf` CLI で対象 org に認証済み（以下 `<org>`）。API バージョン v66.0 以上
- 実行ユーザーに `LAMP_SystemAdministrator` または `LAMP_MarketingAdministrator` 権限セットグループ
- 送るテンプレート（`igns__Template__c`）が作成済みで、有効なテンプレートメッセージが 1〜5 件あること（作り方は `lamp-template` スキル）
- **必ず最初に対象 org をユーザーに確認する**（顧客の本番 org を扱うため）

## 守ること

- **scheduled にすると顧客の LINE 友だちに実際に届く。** ④ の前に「対象人数」「テンプレート名と本文の要約」「配信日時（繰り返しなら頻度と終了日）」をユーザーに提示して明示の承認を得る
- 配信はスケジュールした人の権限で実行される。Report モードのレポートは、その人が実行できる共有フォルダに置く
- 対象は **CSV モードを標準**にする（Report モードは同期実行のため 2,000 行までしか取れない）
- スケジュール中（`scheduled` / `working`）は繰り返し設定（`igns__Cron__c`）を変更できない。変えるときはキャンセル → 下書きに戻す → 再スケジュール
- 記録した Id は会話に残し、同じ配信を二重に作らない。既存の下書きがないか `Name` で検索してから作る
- 日本語や改行を含む値は `sf data create record -v` ではなく **REST（`sf api request rest` + JSON ファイル）** で書く

## ① 対象の抽出と CSV

対象は友だちレコード（`igns__SocialFriend__c`）の **レコード Id** で指定する。ブロック済み・テスト用は通常除く:

```bash
sf data query -q "SELECT Id, Name FROM igns__SocialFriend__c WHERE igns__SocialAccount__c = '<SocialAccountId>' AND igns__IsBlocked__c = false AND igns__IsTest__c = false" -o <org> --json > /tmp/friends.json
```

CSV の形式（1 行目はヘッダ。1 列目が友だち Id、2 列目以降は差し込み変数 `insert_1`, `insert_2` …。テンプレート本文の `{!insert_1}` に入る）:

```csv
user_id,insert_1
a0GBU000002nVcb2AE,江口
a0GBU000002nVcc2AE,山田
```

- 友だち Id は 15 桁または 18 桁の英数字。空行・空セルは不可。ヘッダ行を含めて 2 行以上
- 差し込みが不要なら 1 列だけでよい
- 同じ友だちが 2 回出てくると既定では 1 回だけ送る（2 回送りたい場合だけ `igns__AllowDuplicate__c=true`）

CSV を Salesforce のファイル（ContentVersion）として保存し、その Id を配信設定に付ける:

```bash
B64=$(base64 -i /tmp/targets.csv | tr -d '\n')
cat > /tmp/cv.json <<EOF
{ "Title": "配信対象_秋の温泉", "PathOnClient": "targets.csv", "VersionData": "$B64", "ContentLocation": "S", "Origin": "H" }
EOF
sf api request rest "/services/data/v66.0/sobjects/ContentVersion" --method POST -b @/tmp/cv.json -o <org>
# → {"id":"068...","success":true}  ← この ContentVersion の Id を igns__CsvFileId__c に入れる
```

Report モードを使う場合は、1 列目が友だち Id のレポートを用意して `igns__ReportId__c` に Id を入れる（2 列目以降が `insert_N` になる）。

## ② 配信設定の作成（下書き）

```bash
cat > /tmp/bc.json <<'EOF'
{ "Name": "秋の温泉キャンペーン 9/10",
  "igns__Template__c": "<templateId>",
  "igns__Mode__c": "CSV",
  "igns__CsvFileId__c": "<contentVersionId>",
  "igns__StreamType__c": "Once",
  "igns__StartDateTime__c": "2026-09-10T01:00:00.000Z",
  "igns__Status__c": "draft" }
EOF
sf api request rest "/services/data/v66.0/sobjects/igns__Broadcast__c" --method POST -b @/tmp/bc.json -o <org>
```

| 項目 | 必須 | 内容 |
|---|---|---|
| `igns__Template__c` | ✔ | 送るテンプレート |
| `igns__Mode__c` | ✔ | `CSV` または `Report`（空は Report 扱い） |
| `igns__CsvFileId__c` / `igns__ReportId__c` | どちらか | 対象 |
| `igns__StreamType__c` | ✔ | `Once`（1 回）/ `Repeat`（繰り返し） |
| `igns__StartDateTime__c` | Once で必須 | 配信日時（UTC で書く。JST 10:00 は `01:00:00Z`）。**現在より未来**。すぐ送りたいときは現在＋2 分 |
| `igns__Cron__c` | Repeat で必須 | 下表の形式。時刻は **スケジュールする人のタイムゾーン**で解釈される |
| `igns__EndDateTime__c` | Repeat で任意 | 繰り返しの終了日時。現在より未来 |
| `igns__AllowDuplicate__c` | 任意 | 同一友だちへの重複送信を許可 |

繰り返しの `igns__Cron__c`（分は 0 固定。`H` は 0〜23）:

| 頻度 | 形式 | 例 |
|---|---|---|
| 毎日 | `0 0 H * * ?` | `0 0 9 * * ?`（毎日 9:00） |
| 曜日指定 | `0 0 H ? * MON,WED,FRI` | `0 0 18 ? * MON,WED,FRI` |
| 毎月 | `0 0 H D * ?` | `0 0 10 1 * ?`（毎月 1 日 10:00。31 日指定は 31 日が無い月は飛ぶ） |

配信後に友だちの項目を更新したい場合は `igns__BroadcastFieldSetting__c`（`igns__Broadcast__c`、`Name`=友だち項目 API 名、`igns__Condition__c`=`EQ`/`ADD`/`BLANK`、`igns__Value__c`）を作る。

## ③ 事前検証（scheduled にする前に必ず）

```bash
# テンプレートの有効メッセージ数（1〜5 件。0 件だと送信できず、6 件以上は LINE 上限超え）
sf data query -q "SELECT COUNT() FROM igns__TemplateMessage__c WHERE igns__Template__c = '<templateId>' AND igns__IsValid__c = true" -o <org>
# 無効なメッセージが混ざっていないか（無効は送信時に黙って除外される）
sf data query -q "SELECT Id, igns__Type__c, igns__ValidationErrors__c FROM igns__TemplateMessage__c WHERE igns__Template__c = '<templateId>' AND igns__IsValid__c = false" -o <org>
# スケジュールジョブの空き（org 全体で 100 が上限。配信は「1 回配信 1 本」「繰り返しは同じ人×同じ頻度で 1 本」を使う）
sf data query -q "SELECT COUNT() FROM CronTrigger WHERE CronJobDetail.JobType = '7' AND State IN ('WAITING','ACQUIRED','EXECUTING')" -o <org>
```

対象人数・本文・日時をユーザーに提示し、承認を得る。

## ④ スケジュール

```bash
cat > /tmp/sch.json <<'EOF'
{ "igns__Status__c": "scheduled" }
EOF
sf api request rest "/services/data/v66.0/sobjects/igns__Broadcast__c/<broadcastId>" --method PATCH -b @/tmp/sch.json -o <org>
```

エラーになったときの読み方:

| エラー文 | 原因と対処 |
|---|---|
| スケジュールするときに、テンプレート・配信日の設定は必須です… | テンプレート・日時（Once）または Cron（Repeat）・対象（CSV/Report）のどれかが空 |
| 配信開始日時を現在の時刻よりも前に設定することはできません | `StartDateTime__c` が過去。現在＋2 分以降にする |
| 配信終了日時を現在の時刻よりも前に… | `EndDateTime__c` が過去 |
| 繰り返しの設定（…）を解釈できないため… | `Cron__c` の書式が上表と違う |
| この組織のスケジュール済み Apex ジョブが上限（100件）に達しているため… | 組織の Apex スケジュールジョブが満杯。不要なジョブの整理を管理者に依頼 |
| 値を変更するには状況を「下書き」に設定してください | scheduled 以降でテンプレート・日時を変えようとした。キャンセル → draft に戻す |

Status の遷移で許されるのは `draft→scheduled`、`scheduled→canceled`、`working→canceled`、`canceled→draft` だけ（`working` / `end` はシステムが付ける）。

## ⑤ 状態確認

```bash
cat > /tmp/st.json <<'EOF'
{ "inputs": [ { "broadcastId": "<broadcastId>" } ] }
EOF
sf api request rest "/services/data/v66.0/actions/custom/apex/igns__LampGetBroadcastStatusAction" --method POST -b @/tmp/st.json -o <org>
```

`outputValues.phase` で判断する:

| phase | 意味 | 次にすること |
|---|---|---|
| `draft` | 下書き | ④ へ |
| `waiting` | スケジュール済み・発火待ち | `nextExecutionDate` の後に再確認 |
| `sending` | 発火直後。配信履歴はまだ無い | 2〜3 分後に再確認 |
| `completed` | 配信履歴あり（`lastSuccess` / `lastFailure` / `lastSentAt`） | ⑥ へ。繰り返しなら `nextExecutionDate` が次回 |
| `failed` | `lastError` にエラーが記録されている | 理由を直す。単発はキャンセル → 下書き → 再スケジュール。繰り返しは次回に自動再試行 |
| `no_history` | 発火時刻を過ぎたのに履歴もエラーも無い | 数分待って変わらなければ管理者に連絡（配信サーバー側の問題） |
| `broken` | scheduled なのにジョブが無い | キャンセル → 下書き → 再スケジュール |
| `canceled` | キャンセル済み | 再開するなら draft に戻す |

`lastError` の例: 「配信サーバーがエラーを返しました（HTTP 400）: 動画メッセージにはHTTPSのプレビュー画像URL（previewImageUrl）が必要です。」「配信対象の抽出またはメッセージの組み立てに失敗しました: …」「配信対象ファイルの保存先URLを取得できませんでした（HTTP 401）…」（サーバー認証切れ）。

## ⑥ 結果と統計

```bash
sf data query -q "SELECT Id, igns__StartDateTime__c, igns__Sender__c, igns__Success__c, igns__Failure__c, igns__Opened__c, igns__Clicked__c, igns__OpenRate__c, igns__ClickRate__c, igns__Status__c, igns__CsvUrl__c FROM igns__BroadcastHistory__c WHERE igns__Broadcast__c = '<broadcastId>' ORDER BY igns__StartDateTime__c DESC" -o <org>
```

| 項目 | 意味 |
|---|---|
| `igns__Sender__c` / `igns__Success__c` / `igns__Failure__c` | 送信数 / 成功 / 失敗 |
| `igns__Opened__c` / `igns__Clicked__c` | ユニーク既読数 / ユニーククリック数（`OpenRate__c` = 既読÷成功、`ClickRate__c` = クリック÷成功） |
| `igns__Status__c` | 統計の取得状況（下表） |
| `igns__CsvUrl__c` | 個人別の結果 CSV（`Id,user_id,lamp_id,status,reason`）。`curl -s "<url>"` で取得できる。`reason` に失敗理由（ブロック済み等）が日本語で入る |

統計の取得状況 `igns__Status__c`:

| 値 | 意味 |
|---|---|
| `pending` | 未取得、または LINE がまだ値を返していない（集計中／反応した人が 20 人未満） |
| `fetched` | 取得済み。**送信から 14 日間は毎日更新される** |
| `below_threshold` | 受信者が 20 人未満。LINE の仕様で統計は返らない（取得しない） |
| `rate_limited` | LINE API の上限で今回は見送り。翌日の日次更新で再取得 |
| `expired` | 送信から 14 日を過ぎ、更新が終わった |

既読数・クリック数は日次で更新される（最終更新は `LastModifiedDate`）。配信直後は `pending` が正常。

## ⑦ キャンセル・再スケジュール

```bash
# キャンセル（scheduled / working から）
{ "igns__Status__c": "canceled" }
# 設定を直して再スケジュール（canceled → draft → 編集 → scheduled の順に PATCH）
{ "igns__Status__c": "draft" }
```

## テスト配信

本番の対象へ送る前に、テスト用の友だち 1 人へ送る手順は `lamp-template` スキルの「⑦ テスト配信」（`igns__SendPushMessageFromSocialAccount`）を使う。

## トラブルシューティング

| 症状 | 原因と対処 |
|---|---|
| `phase=failed` で `lastError` が「配信対象の抽出…に失敗」 | CSV 形式（Id 桁数・空セル）か、Report の 1 列目が友だち Id でない。Report は 2,000 行上限 |
| `phase=completed` なのに `lastFailure` が多い | 個人別 CSV の `reason` を見る。ブロック済み・退会済みの友だちは失敗になる |
| `phase=completed` でメッセージが 1 通足りない | テンプレートに無効なメッセージがあり除外された。③ の無効チェック |
| `Opened__c` がずっと空 | `Status__c` を見る。`below_threshold`（20 人未満）は取得できない。`pending` は翌日以降に更新 |
| Repeat なのに `end` になった | `EndDateTime__c` を過ぎた、または `Cron__c` の次回が終了日時を超えた |
| `working` のまま `nextExecutionDate` が過去 | `phase=no_history`。数分待つ。続くなら管理者へ |
