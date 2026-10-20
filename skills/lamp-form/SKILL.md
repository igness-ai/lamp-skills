---
name: lamp-form
description: Igness LAMP のフォーム（LINE から開く回答フォーム）を Salesforce CLI でヘッドレスに作成・編集・公開・停止し、配布URLの取得と回答の確認まで行う。質問（全部品・表示条件・隠し項目・ページ構成）、保存先と項目の対応（作成／作成・更新、Lookup、友だちの項目、回答の情報、固定値）、送信後の画面（見出し・テキスト・画像・ボタン）、回答後に LINE で送るテンプレート、回答した友だちとの紐づけ、キャンペーンメンバーへの追加、配布する公式アカウント・回答回数・色・ボタン文言まで、フォーム編集画面でできることをすべて扱う。「LAMPでフォームを作って」「資料請求フォームを作りたい」「フォームの回答をケースにしたい」「フォームを公開して」「送信後にテンプレートを送りたい」「回答をキャンペーンに入れたい」「フォームの回答を確認して」などで使う。
---

# LAMP フォーム（ヘッドレス）

LAMP のフォームは、LINE の友だちが LIFF で開いて回答し、その回答を Salesforce のレコードとして保存する機能。フォームの定義（質問・保存先・設定）は LAMP のサーバーにあり、Salesforce の「フォーム」レコード（`igns__Form__c`）はその写し。このスキルは、定義を JSON で書いて LAMP のアクションで保存・公開する。

定義の書き方は [references/form-json.md](references/form-json.md)、すぐ使えるひな形は [references/examples/](references/examples/)。

## 前提条件

- LAMP 基本パッケージ **1.168以降**（フォームのアクション。古いとアクションが404）、公式アカウント接続済み
- `sf` CLI で対象 org に認証済み（以下 `<org>`）。実行ユーザーに権限セット「LAMP システム管理者」か「LAMP マーケティング管理者」（無いとアクションが `FORBIDDEN`）
- 配布する公式アカウントに LIFF ID が設定済み（無いと配布URLが作れない。`lamp-social-account-setup`）
- **必ず最初に対象 org をユーザーに確認する**

## 守ること

- **公開・停止・削除は、対象のフォームと内容をユーザーに示して了承を得てから**行う。公開すると配布URLから誰でも回答できるようになり、回答は Salesforce のレコードとして作られる
- 公開中のフォームを変えると、開いたままの回答画面は送信時に読み直しになる。公開中のフォームの変更もユーザーに確かめてから
- 回答（`submissionsJson`）は個人情報。確認に必要な範囲だけを表示する
- 隠し項目の値は URL で誰でも書き換えられる。他人のレコードを更新できてしまう使い方（隠し項目のレコードIDで更新など）は避け、本人のレコードの更新には友だちの項目・本人の友だちIDを使う

## 全体の流れ

```
① 情報を集める（保存先の項目・選択リスト・必須項目、公式アカウント、テンプレート、キャンペーン）
② フォームのレコードを作る → ③ 取得（定義ができ、配布キーが決まる）
④ 定義を書く → 保存 → errorsJson を直して保存し直す
⑤ 公開（Salesforce の項目定義と照らすチェック）→ errorsJson を直して再公開
⑥ 配布URLをユーザーに渡す → ⑦ 回答を確認する
```

## ① 情報を集める（読み取りのみ）

```bash
# 保存先の項目（型・長さ・選択リスト値・必須・参照先・外部ID）
sf sobject describe -s <オブジェクト> -o <org> | python3 -c "
import json,sys
for f in json.load(sys.stdin)['fields']:
    if f['createable'] or f['name']=='Id':
        req = f['createable'] and not f['nillable'] and not f['defaultedOnCreate'] and f['type']!='boolean'
        pick = [p['value'] for p in f.get('picklistValues',[]) if p['active']]
        print(f['name'], f['type'], f.get('length'), '必須' if req else '', '制限付き' if f.get('restrictedPicklist') else '', 'externalId' if f.get('externalId') else '', f.get('referenceTo') or '', pick[:20] if pick else '')"

# 公式アカウント（LAMP ID と LIFF ID）
sf data query -q "SELECT Id, Name, igns__LampId__c, igns__LiffId__c FROM igns__SocialAccount__c WHERE igns__LampId__c != null" -o <org>
# レコードタイプ（使うときだけ）
sf data query -q "SELECT Id, Name, DeveloperName FROM RecordType WHERE SobjectType = '<オブジェクト>' AND IsActive = true" -o <org>
# 回答後に送るテンプレート（使うときだけ。作り方は lamp-template）
sf data query -q "SELECT Id, Name FROM igns__Template__c ORDER BY LastModifiedDate DESC LIMIT 50" -o <org>
# キャンペーンとメンバーの状況（使うときだけ。状況は Label をそのまま使う）
sf data query -q "SELECT Id, Name FROM Campaign WHERE IsActive = true" -o <org>
sf data query -q "SELECT Label, IsDefault FROM CampaignMemberStatus WHERE CampaignId = '<キャンペーンID>' ORDER BY SortOrder" -o <org>
# 既存のフォーム
sf data query -q "SELECT Id, Name, igns__Status__c, igns__PublicKey__c, igns__TargetObjectApiName__c FROM igns__Form__c ORDER BY LastModifiedDate DESC" -o <org>
```

ユーザーに確かめること: 保存先（リード・ケースなど）と作成か作成・更新か、質問の一覧、配布する公式アカウント、1人1回か、送信後の画面の内容、回答後のテンプレート、友だちとの紐づけ、キャンペーン。資料請求・お問い合わせなら `references/examples/` のひな形から始めて差分だけ聞く。

## ② フォームのレコードを作る

```bash
sf api request rest "/services/data/v67.0/sobjects/igns__Form__c" --method POST -b '{"Name":"<フォーム名>"}' -o <org>
# → {"id":"a0A…","success":true}
```

## ③ 取得する

```bash
sf api request rest "/services/data/v67.0/actions/custom/apex/igns__LampGetFormAction" --method POST \
  -b '{"inputs":[{"formId":"<フォームのID>"}]}' -o <org> > /tmp/lamp-form-get.json
```

作ったばかりのフォームは、ここで定義が作られ配布キーが決まる（下書き・revision 1）。戻り値の `outputValues`: `success`、`message`、`errorCode`、`errorsJson`、`formJson`（定義の全体）、`name`、`status`（`draft` / `published` / `stopped`）、`revision`、`publicKey`、`distributionJson`（公式アカウントごとの配布URL）。

## ④ 定義を書いて保存する

1. [references/form-json.md](references/form-json.md) に従い、`name`・`definition`・`target`・`mapping`・`settings`・`completion` を `/tmp/lamp-form.json` に書く。ひな形を使うときはコピーして直す。次を必ず守る:
   - 質問IDは `q_` + 小文字英数8文字
   - 文字列の項目に入れる質問の `maxLength`（氏名・住所は `partMaxLength`）を、①の項目の長さ以下にする（既定値のままだと公開できないことが多い）
   - 値を持つ質問（隠し項目を含む、同意を除く）は、すべて `mapping.fields` で保存先の項目を1つ割り当てる
   - ①の「必須」の項目は、すべて必須の質問（表示条件なし）か固定値で埋める
   - 表示条件の `value` は参照先の回答と同じ型（数値・真偽値・選択肢の value）
   - 送信後の画面の画像は LAMP にアップロードした URL（`lamp-media-upload` を `contentType:"image"` で）
2. 取得した `formJson` に重ねて保存する（`revision` は取得した値が使われる）:

```bash
python3 - <<'EOF'
import json
form = json.loads(json.load(open('/tmp/lamp-form-get.json'))[0]['outputValues']['formJson'])
form.update(json.load(open('/tmp/lamp-form.json')))
json.dump({"inputs": [{"formId": form['formId'], "formJson": json.dumps(form, ensure_ascii=False)}]},
          open('/tmp/lamp-form-save.json', 'w'), ensure_ascii=False)
EOF
sf api request rest "/services/data/v67.0/actions/custom/apex/igns__LampSaveFormAction" --method POST -b @/tmp/lamp-form-save.json -o <org>
```

3. `success:false` なら `errorsJson` の `path` と `message` を見て直し、③で取得し直してから（`revision` が変わっているため）保存し直す。戻り値は取得と同じ形で、保存後の内容が返る

## ⑤ 公開する

ユーザーの了承を得てから実行する。`revision` を省くと今の値で公開する。

```bash
sf api request rest "/services/data/v67.0/actions/custom/apex/igns__LampSetFormStatusAction" --method POST \
  -b '{"inputs":[{"formId":"<フォームのID>","status":"published"}]}' -o <org>
```

公開時に、保存先の項目・必須項目・選択リスト・項目の長さ・テンプレート・公式アカウントなどを Salesforce の定義と照らす。`PUBLISH_VALIDATION_FAILED` なら `errorsJson` を [form-json.md §8](references/form-json.md) の表で直し、④で保存してから公開し直す。公開中のフォームを保存すると同じチェックが毎回走り、通らなければ保存されない。

## ⑥ 配布URL

`distributionJson` の各要素 `{socialAccountId, name, lampId, url}` の `url` が配布URL（`https://liff.line.me/<LIFF ID>?f=<配布キー>`）。`url` が null の公式アカウントは LIFF ID が未設定。隠し項目に値を渡すときは `&<paramName>=<URLエンコードした値>` を足す。

配布URLは、テンプレートメッセージのボタン（`lamp-template`）、リッチメニューの領域（`lamp-richmenu`）、一斉配信（`lamp-broadcast`）などに入れて友だちに届ける。回答は LINE アプリの中で開いたときだけできる。

## ⑦ 回答を確認する

```bash
sf api request rest "/services/data/v67.0/actions/custom/apex/igns__LampListFormSubmissionsAction" --method POST \
  -b '{"inputs":[{"formId":"<フォームのID>","limitSize":50}]}' -o <org>
```

`submissionsJson`（新しい順）、`count`、`nextCursor`（続きがあるとき。次の呼び出しの `cursor` に渡す）。回答ごとの `status`（`saved` / `failed` / `unknown`）、`recordId`（作成・更新したレコード）、`error`（失敗の理由）、`notification.status`（回答後テンプレート）、`friendLink.status`（友だちとの紐づけ）、`campaignMember.status`（キャンペーン）の意味は [form-json.md §10](references/form-json.md)。保存したレコードは SOQL で確かめる。

`failed` が続くときは `error.code` を見る: `REQUIRED_FIELD_MISSING`（固定値・友だちの項目で埋めた必須項目が空）、`FIELD_CUSTOM_VALIDATION_EXCEPTION`（入力規則）、`DUPLICATES_DETECTED`（重複ルール）、`UPDATE_KEY_UNAVAILABLE`（更新先の友だち・レコードが見つからない）。定義か Salesforce 側を直す。失敗した回答を後から再送する手段は無い。

## 変更・停止・削除

| 操作 | やり方 |
|---|---|
| 内容の変更・名前の変更 | ③で取得 → `/tmp/lamp-form.json` を直す → ④で保存（公開中ならチェック込み） |
| 停止（回答の受付を止める。配布URLを開いても回答できなくなる） | ⑤で `"status":"stopped"`。再開は `"published"` |
| 削除 | `sf data delete record -s igns__Form__c -i <フォームのID> -o <org>`（ユーザーの明示の依頼があるときだけ。定義も消える。回答は残るが取得できなくなる） |
| 下書きに戻す・配布キーの再発行 | できない（画面でもできない）。新しいフォームを作る |

`igns__Form__c` の状態・配布キー・保存先の項目を直接更新しない（トリガーが拒否する）。名前は④で変える（レコードの Name を直接変えると revision が裏で上がり、続く保存が `REVISION_CONFLICT` になる）。

## トラブルシューティング

| 症状 | 原因と対処 |
|---|---|
| アクションが404 | LAMP が1.168より前。パッケージを更新する |
| `FORBIDDEN` | 実行ユーザーに「LAMP システム管理者」か「LAMP マーケティング管理者」が無い |
| `REVISION_CONFLICT` | ③で取得し直し、直した内容を重ねて保存する |
| `INVALID_DEFINITION` | 形式のエラー。`errorsJson` の `path` の箇所を [form-json.md](references/form-json.md) §2〜§7 に合わせる |
| `PUBLISH_VALIDATION_FAILED` | [form-json.md §8](references/form-json.md) の表 |
| 「項目 … が見つかりません」なのに describe には有る | 公開時のチェックは LAMP の連携ユーザー（サーバー認証をしたユーザー）の権限で行う。そのユーザーに項目の参照・編集権限を付ける |
| 隠し項目を複数選択リストに入れると公開できない | 現状の制限。チェックボックスの質問で受ける |
| 表示条件で質問が出ない | `value` の型が参照先と違う（数値に `"5"`、はい/いいえに `"true"` など） |
| 送信後の画像が表示されない | LAMP にアップロードした画像でない（外部ドメインは表示されない） |
| `campaignMember.status: failed` | `status` がそのキャンペーンのメンバーの状況に無い。①の SOQL の Label にする |
| `notification.status: skipped` | 回答者の友だちレコードが見つからない（友だち追加前など） |
| 配布URLを開いても「見つかりません」 | 下書きのまま、`allowedLampIds` に含まれない公式アカウントの LIFF、または別組織 |
