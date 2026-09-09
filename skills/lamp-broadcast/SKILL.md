---
name: lamp-broadcast
description: Igness LAMP の一斉配信（配信設定）を Salesforce CLI でヘッドレスに作成・スケジュール・キャンセルし、配信の状態確認、配信結果（成功／失敗、個人別 CSV）、既読数・クリック数の取得まで行う。対象は CSV（固定リスト）と Salesforce レポート（条件で毎回抽出）の両方に対応し、レポート＋繰り返しで「セグメントへの定期配信」「友だち追加 N 日後のステップ配信」も組める。「LAMPで配信を予約して」「毎朝9時に配信して」「友だち追加の3日後にメッセージを送りたい」「先月購入した人だけに毎週送って」「配信が届いたか確認して」「既読率を教えて」などで使う。
---

# LAMP 一斉配信（ヘッドレス）

LAMP の一斉配信は **配信設定（`igns__Broadcast__c`）** というレコードで表す。「誰に（対象）」「何を（テンプレート）」「いつ（1 回 or 繰り返し）」を持ち、`igns__Status__c` を `scheduled` にした瞬間にスケジュールされる。
配信のたびに **配信履歴（`igns__BroadcastHistory__c`）** が 1 件できて、送信数・成功数・失敗数・既読数・クリック数が入る。

```
① 対象の決定       CSV モード: SOQL で友だち（igns__SocialFriend__c）を選び CSV にする（固定リスト）
                   Report モード: Salesforce レポートを作る／指定する（発火のたびに条件で抽出し直す）
② 配信設定の作成   igns__Broadcast__c（draft）＋ CSV を ContentVersion として添付 or レポート Id
③ 事前検証         テンプレートの有効メッセージ数・対象の件数と形式・日時・ジョブ枠
④ スケジュール     Status__c を scheduled に更新（ここで初めて確定。必ずユーザー確認）
⑤ 状態確認         Actions API igns__LampGetBroadcastStatusAction（phase で判定）
⑥ 結果と統計       igns__BroadcastHistory__c、個人別 CSV、既読数・クリック数
```

**対象の決め方はまず用途で選ぶ:**

| やりたいこと | モード | 理由 |
|---|---|---|
| 今回だけ、この人たちに送る（名簿・SOQL の結果） | CSV | 対象が固定。件数上限が実質なし（1 万件超の実績あり） |
| 条件に合う人へ毎週／毎月送る（セグメント定期配信） | Report | 発火のたびにレポートを実行し直すので、増減した友だちを自動で反映する |
| 友だち追加の N 日後に順番に送る（ステップ配信） | Report | 「作成日 = N 日前」のレポート＋毎日の繰り返し＋送信済みフラグで組む（後述） |
| 繰り返し配信全般 | Report | CSV の繰り返しは毎回同じ人に同じ内容を送るだけになる |

## 前提条件

- LAMP 基本パッケージ **1.157 以降**（状態確認アクション・エラー記録・統計取得状況。配信設定そのものは 1.152 以降でも作れる）
- `sf` CLI で対象 org に認証済み（以下 `<org>`）。API バージョン v67.0 以上
- 実行ユーザーに `LAMP_SystemAdministrator` または `LAMP_MarketingAdministrator` 権限セットグループ
- 送るテンプレート（`igns__Template__c`）が作成済みで、有効なテンプレートメッセージが 1〜5 件あること（作り方は `lamp-template` スキル）
- **必ず最初に対象 org をユーザーに確認する**（顧客の本番 org を扱うため）

## 守ること

- **scheduled にすると顧客の LINE 友だちに実際に届く。** ④ の前に「対象人数」「テンプレート名と本文の要約」「配信日時（繰り返しなら頻度と終了日）」をユーザーに提示して明示の承認を得る
- 配信は **スケジュールした人**（Status__c を scheduled にしたユーザー）の権限で実行される。Report モードのレポートはその人が実行できる場所（自分の非公開フォルダ、または共有フォルダ）に置く。他人の非公開フォルダのレポートは実行できず、発火時に失敗する
- Report モードは同期実行のため **1 回の発火で 2,000 行まで**。それ以上は CSV モードにするか、レポートを分割して配信設定を複数にする
- 単発で固定リストなら CSV、繰り返し・ステップ・セグメントなら Report（上表）
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
sf api request rest "/services/data/v67.0/sobjects/ContentVersion" --method POST -b @/tmp/cv.json -o <org>
# → {"id":"068...","success":true}  ← この ContentVersion の Id を igns__CsvFileId__c に入れる
```

## ①′ 対象をレポートで決める（Report モード）

レポートは **発火のたびに「スケジュールした人」として実行し直される**。だから繰り返し配信では「そのとき条件に合う人」に届き、ステップ配信の土台になる。

**レポートの要件（1.157 の `ReportToJSON` の仕様）:**

- 形式は **表形式（TABULAR）**。1 列目が **友だち: ID（`CUST_ID`）**。2 列目以降はそのまま `insert_1`, `insert_2` … の差し込み値になる（表示ラベルが入る。例: 友だち: 表示名 → `{!insert_1}`）
- レポートタイプは友だちの標準レポートタイプ **`CustomEntity$igns__SocialFriend__c`**（「友だち」）。リード／取引先責任者の項目で絞りたい場合は `CustomEntity$igns__SocialFriend__c@igns__SocialFriend__c.igns__Lead__c`（リードが関連する友だち）などの派生タイプがある
- 同じ友だちが複数行あっても 1 通だけ送る（`igns__AllowDuplicate__c` は CSV と同じ）
- 「範囲（scope）」は **すべての友だち（`organization`）** にする。API で作ると既定が「私の友だち（`user`）」になり、スケジュールした人が所有する友だちしか対象にならない
- 集計・グループ化・グラフは不要。フィルタで絞るだけにする

### レポートの列名を調べる

```bash
sf api request rest '/services/data/v67.0/analytics/reportTypes/CustomEntity$igns__SocialFriend__c' -o <org> > /tmp/rt.json
python3 -c "import json; d=json.load(open('/tmp/rt.json'))['reportTypeMetadata']; [print(k,'|',v['label'],'|',v['dataType']) for c in d['categories'] for k,v in c['columns'].items()]"
```

よく使う列（友だちオブジェクトの項目は `igns__SocialFriend__c.<項目 API 名>`。顧客が追加したカスタム項目も同じ形。例: `igns__SocialFriend__c.Step1Sent__c`）:

| 列名 | 意味 | 型 |
|---|---|---|
| `CUST_ID` | 友だち: ID（**必ず 1 列目**） | id |
| `CUST_NAME` | 友だち: 表示名（LINE の表示名。差し込みに便利） | string |
| `CUST_CREATED_DATE` | 友だち: 作成日（= 友だち追加日。ステップ配信の起点） | date |
| `igns__SocialFriend__c.igns__IsBlocked__c` | ブロック? | boolean |
| `igns__SocialFriend__c.igns__IsTest__c` | テスト用? | boolean |
| `igns__SocialFriend__c.igns__SocialAccount__c` | 公式アカウント（複数アカウント運用なら必ず絞る） | string |
| `igns__SocialFriend__c.igns__FirstSocialFriendActivityDateTime__c` | 初回流入日時 | datetime |
| `igns__SocialFriend__c.igns__FirstSocialFriendActivitySourceName__c` | 初回流入名（流入経路別の配信に） | string |
| `igns__SocialFriend__c.igns__LastMessageDate__c` | 最終メッセージ受信日時 | datetime |
| `igns__SocialFriend__c.igns__LastSentMessageDateTime__c` | 最終メッセージ送信日時 | datetime |
| `igns__SocialFriend__c.igns__Lead__c` / `igns__Contact__c` | リード／取引先責任者（紐付け済みか） | string |

### レポートを API で作る

```bash
cat > /tmp/report.json <<'EOF'
{ "reportMetadata": {
    "name": "配信対象: 東京流入・ブロック除く",
    "reportType": { "type": "CustomEntity$igns__SocialFriend__c" },
    "reportFormat": "TABULAR",
    "scope": "organization",
    "folderId": "<組織Id(00D…) なら「公開レポート」。省略すると自分の非公開フォルダ>",
    "detailColumns": ["CUST_ID", "CUST_NAME"],
    "reportFilters": [
      { "column": "igns__SocialFriend__c.igns__IsBlocked__c", "operator": "equals", "value": "false" },
      { "column": "igns__SocialFriend__c.igns__IsTest__c", "operator": "equals", "value": "false" },
      { "column": "igns__SocialFriend__c.igns__SocialAccount__c", "operator": "equals", "value": "<SocialAccountId>" },
      { "column": "igns__SocialFriend__c.igns__FirstSocialFriendActivitySourceName__c", "operator": "contains", "value": "東京" }
    ],
    "reportBooleanFilter": null,
    "standardDateFilter": { "column": "CUST_CREATED_DATE", "durationValue": "CUSTOM", "startDate": null, "endDate": null }
} }
EOF
sf api request rest "/services/data/v67.0/analytics/reports" --method POST -b @/tmp/report.json -o <org>
# → reportMetadata.id（00O…）が igns__ReportId__c に入れる値
```

- `folderId`: 「公開レポート」フォルダは `Folder` オブジェクトに出てこない。**組織 Id（`sf org display -o <org>` の Id、`00D…`）を指定すると公開レポートに入る**。共有フォルダに置くなら `SELECT Id, Name FROM Folder WHERE Type = 'Report'` で Id を引く。省略時は作成者の非公開フォルダ（スケジュールする人が同じなら動くが、他の管理者が見られない）
- `standardDateFilter` は省略しても「すべての期間」になる。書くなら `CUSTOM` ＋ `null`（期間で絞りたいときだけ `startDate`/`endDate` を入れる）
- 既存レポートの修正は同じ JSON を `PATCH /analytics/reports/<reportId>` に送る（`reportFilters` だけでもよい）。削除は `--method DELETE -b '{}'`（`sf` CLI はボディ無しの DELETE を受け付けない）
- 作成のレスポンスは実行結果を含まない。**必ず次の「実行して確認」をする**

フィルタの書き方:

| 型 | `operator` | `value` の例 |
|---|---|---|
| チェックボックス | `equals` / `notEqual` | `"true"` / `"false"` |
| 文字列・選択リスト | `equals` `notEqual` `contains` `notContain` `startsWith` | `"東京"`。複数値は `"A,B"`（いずれか） |
| 参照（公式アカウント等） | `equals` | レコード Id |
| 日付・日時 | `equals` `notEqual` `lessThan` `greaterThan` `lessOrEqual` `greaterOrEqual` | `"2026-09-01"` または相対値 `"TODAY"` `"YESTERDAY"` `"N_DAYS_AGO:3"` `"LAST_N_DAYS:7"` `"THIS_WEEK"` `"LAST_MONTH"` |
| 空かどうか | `equals` / `notEqual` | `""` |

AND/OR を混ぜるときは `"reportBooleanFilter": "1 AND (2 OR 3)"`（番号は `reportFilters` の並び順、1 始まり）。相対日付は **スケジュールした人のタイムゾーン**で評価される。

### 実行して確認（必ず）

```bash
sf api request rest "/services/data/v67.0/analytics/reports/<reportId>?includeDetails=true" -o <org> > /tmp/run.json
python3 -c "
import json; d=json.load(open('/tmp/run.json')); rows=d['factMap']['T!T']['rows']
print('rows', len(rows), 'allData', d['allData']); print('cols', d['reportMetadata']['detailColumns'])
for r in rows[:5]: print([(c.get('label'), c.get('value')) for c in r['dataCells']])"
```

- `rows` が対象人数（承認時にユーザーへ提示する値）。`allData: false` なら 2,000 行で切れている → CSV モードか分割
- 1 列目の `value` が友だち Id（`a0G…`）であること。`CUST_NAME` を 1 列目にすると表示名が Id として送られて全員失敗する
- 0 行なら条件かスコープ（`scope: user` になっていないか）を疑う


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
sf api request rest "/services/data/v67.0/sobjects/igns__Broadcast__c" --method POST -b @/tmp/bc.json -o <org>
```

Report モード＋繰り返しの例（毎週月曜 10:00、年内まで）:

```json
{ "Name": "店舗流入向け 週次お知らせ",
  "igns__Template__c": "<templateId>",
  "igns__Mode__c": "Report",
  "igns__ReportId__c": "<reportId 00O…>",
  "igns__StreamType__c": "Repeat",
  "igns__Cron__c": "0 0 10 ? * MON",
  "igns__EndDateTime__c": "2026-12-31T14:59:00.000Z",
  "igns__Status__c": "draft" }
```

| 項目 | 必須 | 内容 |
|---|---|---|
| `igns__Template__c` | ✔ | 送るテンプレート |
| `igns__Mode__c` | ✔ | `CSV` または `Report`（空は Report 扱い） |
| `igns__CsvFileId__c` / `igns__ReportId__c` | どちらか | 対象。Report モードはレポートの Id（`00O…`、テキスト項目なので存在チェックはされない） |
| `igns__StreamType__c` | ✔ | `Once`（1 回）/ `Repeat`（繰り返し） |
| `igns__StartDateTime__c` | Once で必須 | 配信日時（UTC で書く。JST 10:00 は `01:00:00Z`）。**現在より未来**。すぐ送りたいときは現在＋2 分 |
| `igns__Cron__c` | Repeat で必須 | 下表の形式。時刻は **スケジュールする人のタイムゾーン**で解釈される |
| `igns__EndDateTime__c` | Repeat で任意 | 繰り返しの終了日時。現在より未来 |
| `igns__AllowDuplicate__c` | 任意 | 同一友だちへの重複送信を許可 |

繰り返しの `igns__Cron__c`（`H` は 0〜23。分は UI が 0 固定で作るので 0 にそろえる。0 以外も動くが UI の表示が「未設定」になる）:

| 頻度 | 形式 | 例 |
|---|---|---|
| 毎日 | `0 0 H * * ?` | `0 0 9 * * ?`（毎日 9:00） |
| 曜日指定 | `0 0 H ? * MON,WED,FRI` | `0 0 18 ? * MON,WED,FRI` |
| 毎月 | `0 0 H D * ?` | `0 0 10 1 * ?`（毎月 1 日 10:00。31 日指定は 31 日が無い月は飛ぶ） |

配信後に友だちの項目を更新したい場合は `igns__BroadcastFieldSetting__c`（`igns__Broadcast__c`、`Name`=友だち項目 API 名、`igns__Condition__c`=`EQ`/`ADD`/`BLANK`、`igns__Value__c`）を作る。**送信に成功した友だちだけ**に、発火のたびに適用される（配信サーバーが結果を返した直後、数秒〜数十秒後）。ステップ配信の「送信済みフラグ」はこれで立てる。

## 繰り返し配信・ステップ配信の組み方（Report モード）

繰り返し配信は発火のたびにレポートを実行し直す。**除外条件を持たないレポートを繰り返すと、同じ人に毎回同じメッセージが届く。** 「誰に一度だけ送るか」をレポートの条件か送信済みフラグで表現する。

### パターン A: セグメントへの定期配信（毎週・毎月）

レポート = 「条件に合う人全員」、`StreamType__c=Repeat`、`Cron__c` は曜日・日付指定。例: 「ブロックされておらず、流入経路が『店舗』の友だち」に毎週月曜 10:00 のお知らせ。同じ人に毎回届くのが意図どおりの使い方。

### パターン B: ステップ配信（友だち追加の N 日後）

「1 日後・3 日後・7 日後」なら **配信設定を 3 つ**作る。それぞれ:

1. 送信済みフラグ用のチェックボックス項目を友だちオブジェクトに作る（ステップごとに 1 つ。例: `Step1Sent__c`）
2. レポート = 「作成日 = N 日前 AND フラグ = false AND ブロックでない」
3. `StreamType__c=Repeat`、`Cron__c=0 0 10 * * ?`（毎日 10:00）、テンプレートはそのステップの文面
4. `igns__BroadcastFieldSetting__c` で `Name=Step1Sent__c, Condition=EQ, Value=true`

フラグを使わず「作成日 = N 日前」だけでも 1 日 1 回なら二重には送られないが、ジョブが 1 日止まると（サーバー障害・スケジュールした人の無効化）その日の対象は永久に飛ぶ。フラグがあれば範囲条件（`greaterOrEqual N_DAYS_AGO:5` かつ `lessOrEqual N_DAYS_AGO:3`）に広げて取りこぼしを翌日以降に拾える。

**カスタム項目の作成（メタデータ配備）:**

```bash
mkdir -p /tmp/md/objects
cat > /tmp/md/objects/igns__SocialFriend__c.object <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<CustomObject xmlns="http://soap.sforce.com/2006/04/metadata">
    <fields>
        <fullName>Step1Sent__c</fullName>
        <label>ステップ1送信済み</label>
        <type>Checkbox</type>
        <defaultValue>false</defaultValue>
        <externalId>false</externalId>
        <trackTrending>false</trackTrending>
    </fields>
</CustomObject>
EOF
cat > /tmp/md/package.xml <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<Package xmlns="http://soap.sforce.com/2006/04/metadata">
    <types><members>igns__SocialFriend__c.Step1Sent__c</members><name>CustomField</name></types>
    <version>67.0</version>
</Package>
EOF
sf project deploy start --metadata-dir /tmp/md -o <org>
sf sobject describe -s igns__SocialFriend__c -o <org> --json | python3 -c "import sys,json; print([(f['name'],f['updateable']) for f in json.load(sys.stdin)['result']['fields'] if 'Step1' in f['name']])"
```

- 配備したユーザーには項目レベルセキュリティ（FLS）が自動で付く。**他のユーザーがスケジュールする／サーバー認証している場合はそのユーザーにも編集権限が必要**（権限セットで付与）。フラグ更新はサーバー認証ユーザーの権限で走り、権限が無い項目は黙ってスキップされる
- 既存の友だちに初回から送りたくない場合は、スケジュール前に既存友だちのフラグを一括で true にしておく（`sf data update bulk` など）

**ステップ配信のレポート（3 日後の例）:**

```json
"reportFilters": [
  { "column": "igns__SocialFriend__c.igns__IsBlocked__c", "operator": "equals", "value": "false" },
  { "column": "igns__SocialFriend__c.Step1Sent__c", "operator": "equals", "value": "false" },
  { "column": "CUST_CREATED_DATE", "operator": "equals", "value": "N_DAYS_AGO:3" }
]
```

**送信済みフラグの設定:**

```bash
cat > /tmp/fs.json <<'EOF'
{ "igns__Broadcast__c": "<broadcastId>", "Name": "Step1Sent__c", "igns__Condition__c": "EQ", "igns__Value__c": "true" }
EOF
sf api request rest "/services/data/v67.0/sobjects/igns__BroadcastFieldSetting__c" --method POST -b @/tmp/fs.json -o <org>
```

**運用上の注意:**

- 起点は「友だち: 作成日」= LAMP が友だちレコードを作った日。ブロック解除で戻ってきた人は作成日が古いのでステップに乗らない
- **対象が 0 人の日は、履歴もエラーも残らない**（送信ジョブは正常終了し、配信サーバーは何も作らない）。繰り返しは `working` のまま `lastSentAt` が更新されず次回へ進む。単発（Once）は `end` になるが履歴が無いので `phase=sending` → しばらくして `no_history` になる。「今日の対象が 0 人だったのか、配信が壊れたのか」は状態からは区別できないので、レポートをその場で実行して行数を見る（0 行なら正常）
- 3 ステップなら CronTrigger は「同じ人 × 同じ cron」で 1 本にまとまる（1.157）。時刻をそろえると枠を消費しない
- 途中でレポートの条件を変えるのは自由（配信設定はレポート Id しか持たない）。テンプレートや cron を変えるときはキャンセル → 下書き


## ③ 事前検証（scheduled にする前に必ず）

```bash
# テンプレートの有効メッセージ数（1〜5 件。0 件だと送信できず、6 件以上は LINE 上限超え）
sf data query -q "SELECT COUNT() FROM igns__TemplateMessage__c WHERE igns__Template__c = '<templateId>' AND igns__IsValid__c = true" -o <org>
# 無効なメッセージが混ざっていないか（無効は送信時に黙って除外される）
sf data query -q "SELECT Id, igns__Type__c, igns__ValidationErrors__c FROM igns__TemplateMessage__c WHERE igns__Template__c = '<templateId>' AND igns__IsValid__c = false" -o <org>
# スケジュールジョブの空き（org 全体で 100 が上限。配信は「1 回配信 1 本」「繰り返しは同じ人×同じ頻度で 1 本」を使う）
sf data query -q "SELECT COUNT() FROM CronTrigger WHERE CronJobDetail.JobType = '7' AND State IN ('WAITING','ACQUIRED','EXECUTING')" -o <org>
```

Report モードはさらに:

- ①′ の「実行して確認」で行数（対象人数）と 1 列目が友だち Id であることを確認する
- スケジュールする人（＝いまの `sf` の認証ユーザー）がそのレポートを実行できること（上の GET が通れば OK）
- 繰り返しなら「毎回同じ人に届く条件か、一度だけ届く条件か」を言葉にしてユーザーに確認する

対象人数・本文・日時をユーザーに提示し、承認を得る。

## ④ スケジュール

```bash
cat > /tmp/sch.json <<'EOF'
{ "igns__Status__c": "scheduled" }
EOF
sf api request rest "/services/data/v67.0/sobjects/igns__Broadcast__c/<broadcastId>" --method PATCH -b @/tmp/sch.json -o <org>
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
sf api request rest "/services/data/v67.0/actions/custom/apex/igns__LampGetBroadcastStatusAction" --method POST -b @/tmp/st.json -o <org>
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
| `lastError` が「配信対象の抽出…: レポートデータの取得に失敗しました」 | スケジュールした人がレポートを実行できない（他人の非公開フォルダ・削除済み・Id の誤り）。`GET /analytics/reports/<id>` をその人で実行して確認 |
| Report の対象が画面より少ない／0 人 | レポートの範囲が「私の友だち」（`scope: user`）。`organization` に直す。相対日付はスケジュールした人のタイムゾーン |
| 繰り返しで同じ人に毎回届く | レポートに除外条件が無い。送信済みフラグ（`BroadcastFieldSetting__c`）か日付条件を入れる |
| ステップ配信でフラグが立たない | サーバー認証ユーザーに項目の編集権限が無い（黙ってスキップされる）。`Name` は項目 API 名（顧客項目は接頭辞なし、例 `Step1Sent__c`） |
| `phase=completed` なのに `lastFailure` が多い | 個人別 CSV の `reason` を見る。ブロック済み・退会済みの友だちは失敗になる |
| `phase=completed` でメッセージが 1 通足りない | テンプレートに無効なメッセージがあり除外された。③ の無効チェック |
| `Opened__c` がずっと空 | `Status__c` を見る。`below_threshold`（20 人未満）は取得できない。`pending` は翌日以降に更新 |
| Repeat なのに `end` になった | `EndDateTime__c` を過ぎた、または `Cron__c` の次回が終了日時を超えた |
| `working` のまま `nextExecutionDate` が過去 | `phase=no_history`。数分待つ。続くなら管理者へ |
