# フォームの定義（formJson）リファレンス

`igns__LampGetFormAction` が返し、`igns__LampSaveFormAction` に渡すフォームの定義の形。フォーム編集画面で設定できることは、すべてこの JSON で表せる。

## 1. 全体の形と保存の約束

```json
{
  "formId": "a0A…", "orgId": "00D…", "publicKey": "Ab3dE5gH", "status": "draft", "revision": 3,
  "name": "資料請求フォーム",
  "definition": { "questions": [] },
  "target": { "objectApiName": "Lead", "recordTypeId": null, "saveMode": "create" },
  "mapping": { "fields": [] },
  "settings": {
    "allowedLampIds": null, "responseLimit": "unlimited",
    "completionPage": { "blocks": [{ "type": "heading", "text": "送信ありがとうございました" }] },
    "submitLabel": "送信する", "title": null, "theme": { "primaryColor": "#06C755" },
    "layout": "single", "linkFriend": { "enabled": true, "overwrite": false }, "campaign": null
  },
  "completion": { "templateId": null },
  "createdAt": "…", "updatedAt": "…"
}
```

- 保存で使われるのは `revision`・`name`・`definition`・`target`・`mapping`・`settings`・`completion`。ほかのキー（`formId`・`status`・`publicKey` など）は送っても無視される
- **保存は丸ごと置き換え**。5つのオブジェクト（`definition`・`target`・`mapping`・`settings`・`completion`）はすべて必須で、`settings.responseLimit` も省略できない。取得した `formJson` を直して返すのが安全
- `settings.completionPage` を省くと空（`{"blocks":[]}`）で保存される。新規作成時の見出しには戻らない
- `revision` は取得した値をそのまま入れる。保存・公開・停止のたびに1増え、古い値で保存すると `REVISION_CONFLICT`
- `name`（管理用の名前）は1〜80文字。名前の変更もここで行う（`igns__Form__c` の Name を直接変えると裏で revision が上がり、続く保存が `REVISION_CONFLICT` になる）
- **公開中のフォームを保存すると、公開時と同じチェック（§8）がすべて走り**、1つでも引っかかれば何も保存されない。下書き・停止中は形式のチェックだけ
- 形式エラーは `INVALID_DEFINITION`、公開時チェックのエラーは `PUBLISH_VALIDATION_FAILED`。どちらも `errorsJson` に `[{path, message}]` が全件入る（`path` 例: `definition.questions[2].options[0].value`）
- 全体（name と5つのオブジェクト）は 300KB まで（`DEFINITION_TOO_LARGE`）

## 2. 質問（`definition.questions[]`）

### 2.1 共通

| 項目 | 規則 |
|---|---|
| 件数 | 最大100（表示部品・隠し項目を含む）。隠し項目は最大10 |
| `id` | `q_` + **小文字英数8文字**（例 `q_comp0001`）。フォーム内で重複不可。回答はこの ID で保存されるので、作った後は変えない |
| `type` | 回答部品16種・表示部品4種・`hidden`（下表） |
| `label` | 回答部品と隠し項目は必須（1〜200文字）。表示部品は任意だが、**入れておく**（編集画面の一覧に出る名前。無いと「（名前なし）」と表示される） |
| `required` | true / false。`consent` は常に true。表示部品・隠し項目には付けない（隠し項目に true はエラー） |
| `description` | 補足説明（装飾付きテキスト §2.5、合計1000文字）。回答部品（隠し項目以外）だけ |
| `condition` | 表示条件（§3）。隠し項目には付けられない |
| その他 | 型ごとの属性（§2.2）以外は黙って捨てられる |

### 2.2 型ごとの属性

| `type` | 名前（編集画面） | 属性 | 回答値 |
|---|---|---|---|
| `text` | 1行テキスト | `placeholder?`（≤200）、`maxLength?`（1〜1000、既定255）、`minLength?`（0〜maxLength） | 文字列 |
| `textarea` | 複数行テキスト | 同上（maxLength 1〜10000、既定2000） | 文字列 |
| `email` | メールアドレス | `placeholder?`、`maxLength?`（1〜254、既定254） | 文字列（形式チェックあり） |
| `tel` | 電話番号 | `placeholder?`、`hyphenate?`（true で回答画面が日本の番号として `090-1234-5678` 形式に整え、日本の番号でなければ回答画面で弾く）。最大文字数は40固定 | 文字列 |
| `url` | URL | `placeholder?`、`maxLength?`（1〜2000、既定2000） | `http(s)://` の文字列 |
| `number` | 数値 | `scale`（小数点以下の桁数 0〜8、既定0）、`min?`、`max?`、`unit?`（1〜10文字、表示だけ）、`unitPosition?`（`prefix` / `suffix`） | 数値 |
| `name` | 氏名 | `partMaxLength?`（`lastName`・`firstName` ごとに1〜255。既定 姓80・名40）。`maxLength` は**エラー** | `{lastName, firstName}` |
| `address` | 住所 | `partMaxLength?`（`prefecture`・`city`・`street` ごとに1〜255。既定 都道府県10・市区町村40・番地255）。郵便番号は8文字固定で指定不可 | `{postalCode:"123-4567", prefecture, city, street}`。郵便番号7桁で住所を自動入力 |
| `date` | 日付 | `min?`・`max?`（`YYYY-MM-DD`） | `YYYY-MM-DD` |
| `time` | 時刻 | なし | `HH:mm` |
| `datetime` | 日時 | なし | `YYYY-MM-DDTHH:mm`（日本時間） |
| `radio` | ラジオボタン | `options: [{label, value}]`（1〜100件、各1〜255文字、value 重複不可） | 選んだ value |
| `select` | ドロップダウン | 同上 | 選んだ value |
| `checkboxes` | チェックボックス | `options`、`minSelected?`（≥0）、`maxSelected?`（≥1） | value の配列 |
| `boolean` | はい / いいえ | なし。`required:true` は「どちらかを選ぶこと」 | true / false |
| `consent` | 同意 | `consentText`（**必須** 1〜5000文字、改行可） | true のみ。同意文と日時が回答に残る |
| `heading` | 見出し | `text`（≤5000） | なし |
| `paragraph` | 説明文 | `content`（装飾付きテキスト、合計5000） | なし |
| `divider` | 区切り線 | なし | なし |
| `pageBreak` | ページ区切り | なし（`layout:"single"` のときページを分ける） | なし |
| `hidden` | 隠し項目 | §2.4 | 文字列 |

- 必須の氏名は姓・名の両方、必須の住所は4欄とも入力が要る
- 文字列の回答は前後の空白を除いて保存。空なら未回答
- 選択肢の `label` は回答画面の表示、`value` は保存される値。選択リスト項目に保存するなら value は選択リストの値にする

### 2.3 ページの構成

- `settings.layout: "single"`（既定）: 全質問を1ページ。`pageBreak` があればそこでページを分ける（次へ・戻る・ページ数）
- `settings.layout: "step"`: 1ページに回答部品1問。直前の見出し・説明文は同じページに出る。`divider`・`pageBreak` は無視

### 2.4 隠し項目（`hidden`）

回答画面に出さず、配布URLのパラメータの値を保存する（流入元・キャンペーンコード・紹介元のレコードIDなど）。

```json
{ "id": "q_src00001", "type": "hidden", "label": "流入元", "paramName": "src",
  "valueFormat": "any", "maxLength": 40, "allowedValues": ["instagram", "web"], "defaultValue": "web" }
```

| 属性 | 規則 |
|---|---|
| `label` | 必須（管理用の名前） |
| `paramName` | 必須。英数字と `_` で1〜32文字。`f`・`l` と `liff` で始まる名前は使えない。フォーム内で重複不可（大文字小文字を区別しない） |
| `valueFormat` | `any`（既定）/ `alnum`（英数字・`_`・`-`）/ `salesforceId`（15/18桁のID） |
| `maxLength` | 1〜1000（既定255） |
| `allowedValues` | この中の値だけ受け付ける（1〜100件） |
| `defaultValue` | URL に値が無い・形式に合わないときに使う値（上の条件を満たすこと） |

- 形式・長さ・許可値に合わない値は、エラーにせず `defaultValue`（無ければ未回答）になる
- 隠し項目にも**保存先の項目が必要**（§5.3）
- 配布URLは `distributionJson` の `url` に `&<paramName>=<URLエンコードした値>` を足して作る
- Lookup（参照項目）に入れられるのは隠し項目だけ。`valueFormat:"salesforceId"` にする。回答時に、ID の形・参照先のオブジェクト・レコードの実在を確かめ、合わなければ `defaultValue`、それも駄目なら未回答
- **複数選択リスト項目には隠し項目を保存できない**（公開時に「…（multipicklist）にはこの回答を保存できません。」）。複数選択はチェックボックスの質問で受ける
- URL は書き換えられるので、誰が書き換えても困らない値だけを入れる。回答者本人のレコードを更新するときは §4.1 の友だちの項目・本人の友だちIDを使う

### 2.5 装飾付きテキスト

補足説明（`description`）・説明文（`paragraph.content`）・送信後のテキスト（`text.content`）は文字片の配列。

```json
[{ "text": "必ず", "bold": true, "color": "#E5352E" }, { "text": "ご記入ください。", "size": "sm" }]
```

- 属性: `text`（必須）、`bold`・`italic`・`underline`・`strike`（true のときだけ）、`color`（`#RRGGBB`）、`size`（`xs` `sm` `md` `lg` `xl` `xxl`）。最大500片
- 改行は `\n`。HTML は使えない
- 編集画面の色: `#111111` `#666666` `#06C755` `#1E6FFF` `#E5352E` `#F5A623` `#8E44AD` `#FFFFFF`（ほかの色も使える）

## 3. 表示条件（`condition`）

```json
{ "questionId": "q_prod0001", "operator": "equals", "value": "other" }
```

| `operator` | 意味 | `value` |
|---|---|---|
| `equals` | 回答が value と同じ | 必須 |
| `notEquals` | 回答が value と違う（未回答も表示） | 必須 |
| `includes` | チェックボックスで value を選んだ（チェックボックスの質問だけ） | 必須 |
| `answered` | 回答した | 付けない |
| `notAnswered` | 回答していない | 付けない |

- 参照できるのは**この質問より前**の回答部品だけ（氏名・住所・隠し項目・表示部品は不可）。並べ替えで参照先が後ろに来ると保存エラー
- **`value` の型を参照先の回答に合わせる**: 数値の質問→数値（`5`）、はい/いいえ・同意→`true`/`false`、選択肢→その選択肢の `value`（文字列）、日付→`"YYYY-MM-DD"`。型が違っても保存・公開は通るが、**永久に一致しない**
- 参照先が非表示なら、この質問も非表示。非表示の質問は検証も保存もしない
- 見出し・説明文・区切り線にも条件を付けられる（ページ区切りには付けない）
- Salesforce の必須項目に保存する質問には付けられない（§8）

## 4. 保存先（`target`）

| キー | 内容 |
|---|---|
| `objectApiName` | 保存先オブジェクトの API 名（名前空間付きの正しい綴り。例 `Lead`、`Case`、`igns__SocialFriend__c`）。公開に必須 |
| `recordTypeId` | レコードタイプの ID か `null`（既定）。作成でも更新でもこのレコードタイプにする |
| `saveMode` | `create`（毎回作成）/ `upsert`（作成・更新） |
| `externalIdField` | `upsert` のとき一致を調べる項目。`"Id"` か外部ID項目の API 名 |

保存先にできないもの: 作成できないオブジェクト、カスタム設定、User・Group・Profile・PermissionSet・ContentVersion・Attachment・Document など。

### 4.1 作成・更新（`saveMode:"upsert"`）

| `externalIdField` | キーの入れ方（`mapping.fields` で `fieldApiName` がキーの行） | 動き |
|---|---|---|
| `"Id"` | ①隠し項目（同じオブジェクトの実在するレコードのIDか確かめる）、②友だちの項目（`source:"friend"`、同じオブジェクトを指す友だちの参照項目。例: 取引先責任者 ← `igns__Contact__c`）、③**保存先が `igns__SocialFriend__c` のときだけ** `{"source":"context","contextKey":"socialFriendId"}`（回答した本人の友だちレコードを更新） | ID があれば更新、無ければ作成。③で友だちが見つからないときは作成せず失敗（`UPDATE_KEY_UNAVAILABLE`） |
| 外部ID項目 | 質問（隠し項目か、**必須の**質問）。定数・回答の情報・友だちの項目は不可 | Salesforce の upsert。キーが空なら作成 |

- オブジェクトと、対応付けたほかの項目が更新できること
- `Id` の行は `upsert` ＋ `externalIdField:"Id"` のときだけ書ける
- 作成時の必須項目（§8 E-1）は upsert でも対応付けが要る

## 5. 項目対応（`mapping.fields[]`）

### 5.1 行の形

```json
{ "fieldApiName": "Company",     "source": "question", "questionId": "q_comp0001" }
{ "fieldApiName": "LastName",    "source": "question", "questionId": "q_name0001", "part": "lastName" }
{ "fieldApiName": "LeadSource",  "source": "constant", "value": "Web" }
{ "fieldApiName": "Title",       "source": "context",  "contextKey": "receiptNo" }
{ "fieldApiName": "ContactId",   "source": "friend",   "friendField": "igns__Contact__c" }
```

| `source` | 内容 |
|---|---|
| `question` | 質問の回答。氏名・住所は `part` が必須（氏名 `lastName`/`firstName`、住所 `postalCode`/`prefecture`/`city`/`street`） |
| `constant` | 固定値（1000文字以内の文字列・数値・真偽値。**値なしはエラー**）。文字列・選択リスト項目へは**文字列で**（`"100"`）、数値項目へは数値、チェックボックスへは `true`/`false`、日付は `"YYYY-MM-DD"`、複数選択リストは `"A;C"` |
| `context` | 回答の情報。`receiptNo`（受付番号8文字）/ `submissionId`（36文字）/ `submittedAt`（送信日時。日時項目か文字列項目へ）/ `socialFriendId`（回答した友だちのレコードID。友だち参照項目か文字列項目へ） |
| `friend` | 回答した友だちのレコード（`igns__SocialFriend__c`）の項目の値。`friendField` は友だちの項目の API 名（例 `Name`、`igns__Contact__c`、`igns__Email__c`） |

- 同じ項目（`fieldApiName`）は1回だけ。行は最大200
- 未回答・非表示の質問、値の無い回答の情報・友だちの項目は書き込まない
- `referenceKeyPrefixes`・`referenceObjects` は公開時にサーバーが付ける。書かなくてよい

### 5.2 Salesforce の項目の型と、入れられるもの

| 項目の型（describe の `type`） | 質問 | 定数 | 回答の情報 | 友だちの項目 |
|---|---|---|---|---|
| string・textarea・email・phone・url・picklist・combobox | 1行・複数行テキスト、メール、電話、URL、ラジオ、ドロップダウン、日付・時刻・日時（文字のまま）、氏名・住所の各欄、隠し項目 | 文字列 | 4種すべて | 文字・ID・参照の項目（長さで切る） |
| multipicklist | チェックボックス、ラジオ、ドロップダウン（隠し項目は不可） | 文字列（`;` 区切り） | 不可 | 選択リスト・複数選択リスト |
| boolean | はい/いいえ、同意 | 真偽値 | 不可 | チェックボックス |
| int・double・currency・percent | 数値 | 数値（整数項目は整数） | 不可 | 数値 |
| date | 日付 | `YYYY-MM-DD` | 不可 | 日付 |
| datetime | 日時 | `YYYY-MM-DDTHH:mm`（日本時間）か ISO | `submittedAt` | 日時 |
| time | 時刻 | 不可 | 不可 | 時刻 |
| reference | 隠し項目のみ | 不可 | `socialFriendId`（参照先が友だちのとき） | 同じオブジェクトを指す参照 |

### 5.3 保存先の割り当て規則

- 値を持つ質問（回答部品と隠し項目。表示部品と同意を除く）は、`source:"question"` の行が**ちょうど1つ**必要
- 氏名・住所は欄ごとに最大1行、少なくとも1行（全欄を保存しなくてよい）
- 同意は任意。保存するならチェックボックス項目へ

## 6. 設定（`settings`）

| キー | 値 | 既定 |
|---|---|---|
| `allowedLampIds` | 配布する公式アカウントの LAMP ID の配列。`null` なら組織の全公式アカウント（**空配列は公開不可**） | `null` |
| `responseLimit` | `once`（公式アカウント×LINEユーザーごとに1回。保存に失敗した回答は数えない）/ `unlimited`。**必須** | — |
| `completionPage` | 送信後の画面（§6.1） | 空 |
| `submitLabel` | 送信ボタンの文言（≤20文字） | 「送信する」 |
| `title` | 回答画面のタイトル（≤80文字）。`null` ならフォーム名 | `null` |
| `theme.primaryColor` | `#RRGGBB`。送信ボタン・選択中の部品の色。編集画面の候補: `#06C755` `#0176D3` `#1B5297` `#E4007F` `#FF6B00` `#222222` | `#06C755` |
| `layout` | `single` / `step`（§2.3） | `single` |
| `linkFriend` | `{enabled, overwrite}`。保存先がリード・取引先責任者のとき、回答した友だちの「リード」「取引先責任者」に保存したレコードを入れる。`overwrite:false` なら既に入っている友だちは変えない | `{enabled:true, overwrite:false}` |
| `campaign` | `null` か `{campaignId, status}`（§6.2） | `null` |

### 6.1 送信後の画面（`completionPage.blocks[]`、最大20個）

```json
{ "blocks": [
  { "type": "image", "url": "https://…mylp.jp/…png", "alt": "キャンペーン", "linkUrl": "https://example.com/" },
  { "type": "heading", "text": "送信ありがとうございました" },
  { "type": "text", "content": [{ "text": "担当者より2営業日以内にご連絡します。" }] },
  { "type": "button", "label": "サイトを見る", "action": "url", "url": "https://example.com/" },
  { "type": "button", "label": "LINEに戻る", "action": "close" }
] }
```

| `type` | 属性 |
|---|---|
| `heading` | `text`（1〜100文字） |
| `text` | `content`（装飾付きテキスト、1〜2000文字） |
| `image` | `url`（https、必須）、`alt?`（≤100）、`linkUrl?`（https） |
| `button` | `label`（1〜20文字）、`action`（`url` は https の `url` 必須 / `close` は LINE に戻る） |

- **画像は LAMP にアップロードした URL を使う**（`lamp-media-upload` の手順を `contentType:"image"` で行い、完了アクションの `originalUrl` を `url` に入れる）。回答画面は `*.mylp.jp`・`*.igness.ai`・`*.line-scdn.net` 以外の画像を表示しない
- `blocks` が空なら、回答画面は見出し「送信しました」だけを出す
- 送信後の画面は、保存に失敗した回答では出ない（回答者は入力画面に戻って直す）

### 6.2 キャンペーンメンバー（`settings.campaign`）

```json
{ "campaignId": "701…", "status": "レスポンスあり" }
```

- 保存先が `Lead` か `Contact` のときだけ。回答を保存したレコードを、そのキャンペーンのメンバーに追加する（既にメンバーなら何もしない）
- `status` はそのキャンペーンの「メンバーの状況」の**表示ラベル**: `SELECT Label FROM CampaignMemberStatus WHERE CampaignId = '<ID>'`。**保存・公開時には確かめられない**ので、必ずこの SOQL の値から選ぶ（違う値だと回答ごとに追加が失敗する）

## 7. 回答後の LINE テンプレート（`completion.templateId`）

```json
"completion": { "templateId": "a0N…" }
```

- 回答を Salesforce に保存できたとき、回答した友だちにこのテンプレート（`igns__Template__c`）を LINE で送る。`null` なら送らない
- テンプレートの種類に制限は無い（作り方は `lamp-template`）。差し込みは友だちの項目だけで、フォームの回答は差し込めない
- 公開時にテンプレートの存在を確かめる。友だちが見つからないときは送らない（回答の `notification.status: "skipped"`）

## 8. 公開時のチェック（`PUBLISH_VALIDATION_FAILED`）

公開するとき、または公開中のフォームを保存するとき、Salesforce の項目定義（LAMP の連携ユーザーで取得）と照らす。主なエラーと直し方:

| path | メッセージ | 直し方 |
|---|---|---|
| `definition.questions` | 回答する質問を1つ以上追加してください。 | 回答部品を足す |
| `definition.questions[i]` | 保存先の項目を選んでください | その質問（隠し項目を含む）の `question` 行を足す |
| `definition.questions[i]` | 1つの質問は1つの項目にだけ保存できます／入力欄ごとに1つの項目にだけ保存できます | 行を1つにする |
| `target.objectApiName` | 保存先オブジェクトを選択してください。／…が見つかりません。／…にはフォームからレコードを作成できません。 | 綴り・オブジェクトを直す |
| `target.recordTypeId` | レコードタイプがこのオブジェクトで利用できません。 | 有効なレコードタイプを選ぶ |
| `target.externalIdField` | 一致を調べる外部ID項目を選んでください。／…は外部ID項目ではありません。／外部ID項目…に対応する質問を割り当ててください。／…に対応する質問「…」を必須にしてください。／レコードIDは隠し項目か友だちの項目から入れてください。／…は更新できない項目です。 | §4.1 |
| `mapping.fields[i]` | 項目 … が見つかりません。 | 綴り、または連携ユーザーの項目権限 |
| `mapping.fields[i]` | … は作成時に書き込めません。 | 別の項目にする |
| `mapping.fields[i]` | …（型）にはこの回答を保存できません。／…には友だちの「…」を保存できません。 | §5.2 |
| `mapping.fields[i]` | …: 文字列の定数を指定してください。（数値・整数・true / false・日付・日時の形式） | 定数の型を項目に合わせる |
| `mapping.fields[i]` | … は N 文字までです。回答の最大文字数（M）を項目長以下にしてください。 | `maxLength` / `partMaxLength` を項目長以下に（§9） |
| `mapping.fields[i]` | 郵便番号は8文字（123-4567）で保存します。… | 8文字以上の項目にする |
| `mapping.fields[i]` | … の選択肢にない値があります: … | 選択肢の value・隠し項目の許可値・定数を有効な選択リスト値に |
| `mapping.fields[i]` | … は選択肢が制限されています。隠し項目「…」に許可する値を設定してください。 | 隠し項目に `allowedValues` |
| `mapping.fields[i]` | レコードIDに入れるのは、保存方法を「レコードIDで更新」にしたときだけです。 | `Id` 行を消すか upsert＋`Id` にする |
| `mapping.fields` | 必須項目 …（API名）を対応付けてください。 | その項目に必須の質問か定数を割り当てる |
| `mapping.fields[i]` | 必須項目 … に対応する質問「…」を、表示条件なしの必須回答にしてください。 | 質問を `required:true`・条件なしに |
| `mapping.fields[i]` | 必須項目 … に対応する隠し項目「…」に初期値を設定してください。／必須のLookup項目 … には隠し項目を対応付けられません。 | `defaultValue` を入れる／別の入れ方にする |
| `settings.campaign` | キャンペーンに追加できるのは、保存先がリードか取引先責任者のときだけです。 | `campaign` を `null` に |
| `settings.allowedLampIds` | 配布する公式アカウントを1つ以上選択してください。／この組織にない公式アカウントが指定されています | `null` か正しい LAMP ID |
| `completion.templateId` | 回答後に送るテンプレートが見つかりません。 | テンプレートの ID を直す |

公開時に**確かめられない**もの: キャンペーンメンバーの状況の値、定数・回答の情報・友だちの項目で埋める必須項目に値が入るか、入力規則・重複ルール、表示条件の値の型。

## 9. 編集画面が自動でしていること（自分で行う）

| 編集画面の動き | ヘッドレスでのやり方 |
|---|---|
| 項目を割り当てると、最大文字数を項目の長さまで下げる | `sf sobject describe` の `length` を見て `maxLength`・`partMaxLength` を項目長以下にする。既定値（1行255・メール254・URL2000・隠し項目255・都道府県10）は多くの標準項目より長い（例: リードのメールは80、市区郡は40） |
| 住所を足すと標準の住所項目に割り当てる | リード `PostalCode/State/City/Street`、取引先責任者 `MailingPostalCode/MailingState/MailingCity/MailingStreet`、取引先 `BillingPostalCode/BillingState/BillingCity/BillingStreet` |
| 選択肢の質問を選択リスト項目に割り当てると、有効な選択リスト値を選択肢にする | describe の `picklistValues`（`active:true`）を `options` に（label・value） |
| 隠し項目を参照項目に割り当てると `valueFormat:"salesforceId"` | 同じようにする |
| 必須項目の一覧を出す | describe で `createable && !nillable && !defaultedOnCreate && type != "boolean"` の項目 |
| 質問IDを採番する | `q_` + 小文字英数8文字を自分で付ける |
| 質問の削除・並べ替えで、壊れた表示条件と項目対応を外す | 自分で外す（残すと保存エラー） |
| テンプレート「お問い合わせ」「資料請求」 | `references/examples/` の JSON を使う |

## 10. 回答（`igns__LampListFormSubmissionsAction` の `submissionsJson`）

| キー | 内容 |
|---|---|
| `receiptNo` | 受付番号（8文字） |
| `submissionId`, `lampId`, `lineUserId`, `socialFriendId` | 回答の ID と回答者 |
| `answers` | `{質問ID: 値}`（表示された質問と隠し項目） |
| `consents` | `[{questionId, text, agreedAt}]` |
| `status` | `saved`（保存できた）/ `failed`（Salesforce が拒否）/ `unknown`（書き込み後に通信が切れた等。作られたか不明）/ `saving` |
| `recordId` | 保存したレコードの ID |
| `error` | `failed`・`unknown` の理由（`{code, message, fields?}`。例 `REQUIRED_FIELD_MISSING`、`FIELD_CUSTOM_VALIDATION_EXCEPTION`、`UPDATE_KEY_UNAVAILABLE`） |
| `notification.status` | 回答後テンプレート: `none`（未設定・保存失敗）/ `queued`（送信を受け付けた）/ `skipped`（友だちが見つからない）/ `failed` / `unknown` |
| `friendLink.status` | 友だちとの紐づけ: `linked` / `skipped_existing`（既に入っていた）/ `skipped_no_friend` / `failed` / `disabled` |
| `campaignMember.status` | キャンペーン: `added` / `already_member` / `failed`（状況の値の誤りなど）/ `disabled` / `unsupported` |
| `snapshot` | 回答時点の保存先・項目対応などの設定 |
| `createdAt` | 回答日時 |

`failed`・`unknown` の回答を後から再送する手段は無い。原因（入力規則・必須項目など）を直してフォームを保存し直し、以後の回答で確かめる。
