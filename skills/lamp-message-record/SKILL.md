---
name: lamp-message-record
description: Igness LAMP で LINE のメッセージ1通ごとに紐づく Salesforce のレコード（ケース・商談など）を、Salesforce CLI でヘッドレスに扱う。紐づいたレコードの確認（会話履歴API）、友だちから届いたメッセージの付け替え・外し、送るときの紐づけ（フローの Send Push Message）、届いたメッセージを友だちの対応中のケースなどへ自動で紐づけるフローの作成まで行う。「メッセージをケースに紐づけたい」「このメッセージの紐づけを変えて」「どの案件への返信か分かるようにしたい」「届いたメッセージを対応中のケースに自動で紐づけたい」などで使う。
---

# メッセージとレコードの紐づけ（ヘッドレス）

LAMP は、やり取りしたメッセージ1通ごとに、ケースや商談などの Salesforce のレコードを紐づけて持つ。同じ友だちと複数の案件を並行して進めていても、どのメッセージがどの案件の話かを後から追える。1to1 のトークでもグループトークでも同じしくみ。

## しくみ

| どう付くか | `recordIdSource` |
|---|---|
| レコードページに置いた LAMP のチャットから送ると、そのページのレコードが付く（友だち・グループ自身のページ、自動応答、一斉配信からのメッセージには付かない） | なし |
| フローの「Send Push Message」で入力「Record ID」を渡すと、そのレコードが付く | なし |
| 友だちが、レコードの付いたメッセージを引用して返信すると、返信にも同じレコードが付く | `quote` |
| レコード推定がオンの公式アカウントでは、引用のないテキストにも、会話から推定したレコードが付く（1to1・グループトークとも） | `inferred` |
| レコード推定がオンのとき、続けて届いた画像・動画・ファイルには、直前のメッセージ（グループトークでは同じメンバーの直前のメッセージ）と同じレコードが付く | `burst` |
| 画面・このスキル・フローで付け替えたもの | `manual` |

公式アカウントから送ったメッセージの紐づけは変えられない（どのレコードの画面から送ったかの記録として残す）。変えられるのは友だちから届いたメッセージだけ。ケースや商談のページに LAMP のチャットを置く手順は `lamp-chat` を使う。

## 前提条件

- LAMP 基本パッケージ **1.168以降**（付け替えアクション `LampSetMessageRecordAction`、グループの会話履歴API）。1.166〜1.167では、送るときの紐づけと1to1の履歴の確認だけができ、付け替えは画面で行う（アクションは404になる）
- `sf` CLI で対象 org に認証済み（以下 `<org>`）。付け替えには対象の友だち・グループの編集権限が要る
- **必ず最初に対象 org をユーザーに確認する**

## 守ること

- 付け替え・外しは、対象のメッセージ（日時と本文の冒頭）と紐づけるレコードをユーザーに示し、了承を得てから行う
- 会話の本文はお客様の会話データ。確認に必要な範囲だけを表示する
- 顧客 org へのフローの反映は、手順を見せて了承を得てから行う

## 紐づいたレコードを確認する

```bash
# 友だち（1to1）・グループのレコードID
sf data query -q "SELECT Id, Name, igns__LampId__c FROM igns__SocialFriend__c WHERE Name LIKE '%<名前>%'" -o <org>
sf data query -q "SELECT Id, Name FROM igns__SocialGroup__c WHERE Name LIKE '%<名前>%'" -o <org>

# 会話履歴（新しい順）。limit は件数、from / to は日付（2026-10-01）か日時（2026-10-01T09:00:00+09:00）
sf api request rest "/services/apexrest/igns/timeline/<友だちまたはグループのレコードID>?limit=20" -o <org>
```

`messages` の各要素:

| 項目 | 意味 |
|---|---|
| `id` | メッセージのキー。付け替えに使う |
| `direction` | `incoming`（友だちから）/ `outgoing`（公式アカウントから） |
| `datetime` / `content` | 日時と本文 |
| `recordId` / `recordIdSource` | 紐づいたレコードのIDと、付き方（上の表） |

さらに古い履歴は、応答の `nextToken` を URL エンコードして `&nextToken=` に付ける。レコード名は `recordId` をそのオブジェクトの SOQL で引いて示す。Agentforce からは、履歴アクション（会話タイムラインを取得）でも紐づいたレコードの種類と名前が出る。

## 付け替える・外す

対象のメッセージの `id` を上の履歴から取り、ユーザーの了承を得てから実行する。

```bash
# 紐づける・付け替える
cat > /tmp/lamp-record.json <<'JSON'
{"inputs":[{"chatRecordId":"<友だちまたはグループのレコードID>","messageKey":"<履歴の id>","recordId":"<紐づけるレコードID>"}]}
JSON
sf api request rest "/services/data/v67.0/actions/custom/apex/igns__LampSetMessageRecordAction" --method POST -b @/tmp/lamp-record.json -o <org>

# 外す（recordId は渡さず clear を true にする）
cat > /tmp/lamp-record.json <<'JSON'
{"inputs":[{"chatRecordId":"<友だちまたはグループのレコードID>","messageKey":"<履歴の id>","clear":true}]}
JSON
sf api request rest "/services/data/v67.0/actions/custom/apex/igns__LampSetMessageRecordAction" --method POST -b @/tmp/lamp-record.json -o <org>
rm -f /tmp/lamp-record.json
```

戻り値は `success` / `message` / `errorCode` / `messageKey` / `recordId`。実行後に会話履歴を読み直し、`recordId` と `recordIdSource: manual` を確認して報告する。

| `errorCode` | 意味と対処 |
|---|---|
| `INVALID_REQUEST` | レコードIDも `clear` も無い、両方ある、友だち・グループ以外のIDを渡した、別の友だち・グループのキーを渡した |
| `NOT_FOUND` | 友だち・グループが見つからない、または参照権限が無い |
| `FORBIDDEN` | 友だち・グループの編集権限が無い |
| `INVALID_RECORD` | 紐づけられないID（友だち・グループ自身、IDの形でない） |
| `MESSAGE_NOT_FOUND` | 公式アカウントから送ったメッセージ（変えられない）か、キーの誤り |
| `INTERNAL_ERROR` | 通信エラー。会話履歴で現在の状態を確かめてから再実行する |

## 送るときに紐づける

フローやスクリプトから送るときは、`Send Push Message`（`igns__SendPushMessageFromSocialAccount`）の入力 `recordId` に紐づけたいレコードのIDを渡す。送り方とテスト配信の確かめ方は `lamp-template` の「テスト配信」に従い、入力に `"recordId":"<レコードID>"` を足す。友だち自身のIDは渡しても付かない。グループへのフローからの送信は対象外。

## 届いたメッセージを、フローで自動で紐づける

友だちの参照項目（例: `lamp-case-support` で入れる「対応中ケース」`CurrentCase__c`）が指すレコードを、その友だちから届いたメッセージに自動で紐づけるフローのひな形が [metadata](references/metadata/) の `LAMP_MessageRecord_FromFriend`。

- LAMP のプラットフォームイベント（`igns__LampNotification__e`）で起動し、アクション「メッセージのレコードを変更」に**受信イベント `{!$Record}` をそのまま渡す**。アクションがそのメッセージを履歴から探して紐づける（キーを組み立てる必要はない）
- 引用・推定ですでにレコードが付いたメッセージ（イベントの `igns__RecordId__c` が空でないもの）には触れない
- 1to1だけが対象。グループでの発言には付けない
- 自社のルール（例: 商談のフェーズで選ぶ、問い合わせの種類で選ぶ）で紐づけたい場合も、このひな形のアクション呼び出し部分を流用し、`recordId` に渡す値を変える

| プレースホルダー | 内容 | 例 |
|---|---|---|
| `{{FLOW_LABEL}}` | フローの表示ラベル | `LAMP メッセージを対応中ケースに紐づけ` |
| `{{FRIEND_FIELD}}` | 紐づけるレコードを指す、友だちの参照項目のAPI名 | `CurrentCase__c` |
| `{{EVENT_TYPES}}` | 紐づけるメッセージの種類（カンマ区切り・空白なし） | `MSG_TEXT,MSG_IMAGE,MSG_VIDEO` |
| `{{LAMP_ID}}` | 公式アカウントで絞るときの LAMP ID。空なら全公式アカウント | `7piwg` |

### 手順1: 事前診断（読み取りのみ）

```bash
# 公式アカウントと LAMP ID
sf data query -q "SELECT Id, Name, igns__LampId__c FROM igns__SocialAccount__c" -o <org>
# 友だちの参照項目（紐づけ先の候補）
sf sobject describe -s igns__SocialFriend__c -o <org> | python3 -c "import json,sys; [print(f['name'], f['referenceTo'], f['label']) for f in json.load(sys.stdin)['fields'] if f['type']=='reference' and f['custom']]"
# 既存の LAMP イベントのフロー（同じ役割のフローが無いか）
sf data query -q "SELECT ApiName, Label, IsActive FROM FlowDefinitionView WHERE IsActive = true AND TriggerObjectOrEvent.QualifiedApiName = 'igns__LampNotification__e'" -o <org>
```

### 手順2: ユーザーに確認する

1. **紐づけるレコード**: 友だちのどの参照項目の値を紐づけるか（`{{FRIEND_FIELD}}`）。`lamp-case-support` を入れていれば `CurrentCase__c`
2. **メッセージの種類**（`{{EVENT_TYPES}}`）と**公式アカウント**（`{{LAMP_ID}}`）
3. **フロー名**: 既定 `LAMP_MessageRecord_FromFriend`
4. レコード推定をオンにしている公式アカウントでは、推定で付いたものが優先される（このフローは付いていないメッセージだけに付ける）ことを伝える

### 手順3: 反映

```bash
cp -R <このスキルのディレクトリ>/references/metadata /tmp/lamp-message-record && cd /tmp/lamp-message-record

python3 - force-app/main/default/flows/LAMP_MessageRecord_FromFriend.flow-meta.xml <<'EOF'
import sys
from xml.sax.saxutils import escape
p = sys.argv[1]
values = {
    '{{FLOW_LABEL}}': 'LAMP メッセージを対応中ケースに紐づけ',
    '{{FRIEND_FIELD}}': 'CurrentCase__c',
    '{{EVENT_TYPES}}': 'MSG_TEXT,MSG_IMAGE,MSG_VIDEO',
    '{{LAMP_ID}}': '',
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

- 検証で `igns__LampSetMessageRecordAction` が見つからないと出たら、LAMP が1.168より前。パッケージを更新する
- 複数作るときは、ファイル名（API 名）とラベルを必ず変える
- フローはイベントを発行したユーザー（LAMP のサーバー認証をしたユーザー）として動く

### 手順4: 確認

紐づけ先の項目に値が入っている友だち（ユーザー自身のスマートフォンなど）から、引用せずにメッセージを送ってもらう。フローの起動には数十秒かかることがある。会話履歴で、そのメッセージに `recordId`（友だちの項目の値）と `recordIdSource: manual` が付いたことを確かめる。

付かないとき:

```bash
# フローがイベントを受け取っているか（フローの行があり Status が Running か）
sf data query -q "SELECT Name, Status, Position, Tip, LastError FROM EventBusSubscriber WHERE Topic = 'igns__LampNotification__e'" -o <org>
```

## レコード推定のオン・オフ

公式アカウントごとの設定で、アクションでは変えられない。ユーザーに、公式アカウントのレコードを開いて編集画面の「友だちからのメッセージのレコードを推定する」を切り替えてもらう（LAMP管理者だけが変更できる）。

## トラブルシューティング

| 症状 | 原因と対処 |
|---|---|
| アクションが404 | LAMP が1.168より前。付け替えは画面（メッセージのレコードのアイコン）で行うか、パッケージを更新する |
| グループのIDで会話履歴が400 / 404 | LAMP が1.168より前（グループの会話履歴APIが無い） |
| 受信イベントを渡して `MESSAGE_NOT_FOUND` | イベントが届いたメッセージでない（友だち追加など）、または公式アカウントからの送信のイベント |
| フローで付かない | 対象の友だちの参照項目が空、すでに引用・推定でレコードが付いている、メッセージの種類が `{{EVENT_TYPES}}` に無い、グループでの発言 |
| 失敗に気づけない | プラットフォームイベントのフローの失敗は画面に出ない。設定 →「プロセスの自動化設定」のフローエラーメールの宛先を確認する |

## 元に戻す

付け替えは「付け替える・外す」で戻す（`clear` で外すと、引用・推定で付いていた元のレコードには戻らない。元の `recordId` を控えておき、それを付け直す）。フローは無効化すれば止まる。

```bash
# 無効化（有効なフローはこのままでは削除できない）
sf data query -q "SELECT Id FROM FlowDefinition WHERE DeveloperName = '<フローAPI名>'" --use-tooling-api -o <org>
echo '{"Metadata":{"activeVersionNumber":0}}' > /tmp/fd-off.json
sf api request rest "/services/data/v67.0/tooling/sobjects/FlowDefinition/<FlowDefinitionId>" --method PATCH -b @/tmp/fd-off.json -o <org>
# 削除する場合（ユーザーの指示があるときだけ）: バージョンごとに消す
sf data query -q "SELECT Id, VersionNumber, Status FROM Flow WHERE Definition.DeveloperName = '<フローAPI名>'" --use-tooling-api -o <org>
sf data delete record -s Flow -i <FlowのバージョンId> --use-tooling-api -o <org>
```
