---
name: lamp-template
description: Igness LAMP のテンプレート（LINEで1回に送るメッセージのまとまり）とテンプレートメッセージ（テキスト／画像／動画／リンク付き画像／カード／設問（2択）／カード（画像のみ）／クーポン／フレックス）を Salesforce CLI でヘッドレスに作成・修正・検証し、返信ボタン・項目の代入・テスト配信まで行う。「LAMPでテンプレートを作って」「カードメッセージを作りたい」「テンプレートが有効にならない理由を調べて」などで使う。
---

# LAMP テンプレート作成（ヘッドレス）

LAMP のテンプレートは、**テンプレート（`igns__Template__c`）という箱**の中に**テンプレートメッセージ（`igns__TemplateMessage__c`）**を順番に並べたもの。
メッセージは保存するとトリガーが LINE 仕様に照らして検証し、**有効（`igns__IsValid__c`）** と **有効化エラー（`igns__ValidationErrors__c`、日本語の理由）** を書き込む。
保存はブロックされないので、「保存 → `ValidationErrors__c` を読む → 直す」を繰り返せば必ず有効化できる。

```
① 素材の準備        画像・動画は lamp-media-upload スキルでアップロードして公開URLを得る
② テンプレート作成   igns__Template__c を1件
③ メッセージ作成     igns__TemplateMessage__c をタイプ別の項目で作成（Sort__c で順番）
④ 検証ループ         IsValid__c / ValidationErrors__c を読んで修正
⑤ 返信ボタン（任意） igns__Template__c の ActionType1〜13
⑥ 項目の代入（任意） igns__TemplateFieldSetting__c
⑦ テスト配信         Actions API igns__SendPushMessageFromSocialAccount → AsyncApexJob で結果確認
```

## 前提条件

- LAMP 基本パッケージ **1.156 以降**（有効化エラー項目・送信時組み立ては 1.155 以降）
- `sf` CLI で対象 org に認証済み（以下 `<org>`）。API バージョン v67.0 以上
- 実行ユーザーに `LAMP_SystemAdministrator` または `LAMP_MarketingAdministrator` 権限セットグループ
- **必ず最初に対象 org をユーザーに確認する**（顧客の本番 org を扱うため）
- 画像・動画の URL は LAMP のコンテンツ配信基盤のもの（`lamp-media-upload` スキルでアップロード）を使う。リンク付き画像は **拡張子なしの imagemap 用 URL** が必須

## 守ること

- `igns__Json__c` / `igns__IsValid__c` / `igns__ValidationErrors__c` / `igns__ActionData*__c` は**書かない**（フレックスの `Json__c` だけ例外）。送信時に素材項目から組み立てられる
- 1つのテンプレートで**有効にできるメッセージは5件まで**（LINE が1回の配信で送れる上限）。org の入力規則は `1つのテンプレートに5つ以上の有効なテンプレートメッセージを作成することはできません` で止めるが、**ロールアップの評価タイミングの都合で6件目が通ってしまう**（7件目で止まる）。ヘッドレスでは追加前に必ず有効件数を数え、自分で5件以内に収める:
  `SELECT COUNT() FROM igns__TemplateMessage__c WHERE igns__Template__c = '<templateId>' AND igns__IsValid__c = true`
  6件以上送りたいときはテンプレートを分け、アクション「テンプレート呼出」でつなぐ
- 日本語・改行・JSON を含む値は `sf data create record -v` ではなく **REST（`sf api request rest` + JSON ファイル）** で書く（クォートの罠を避ける）
- 記録した `Id` は会話に残し、同じレコードを二重に作らない

## ② テンプレートの作成

```bash
cat > /tmp/tpl.json <<'EOF'
{ "Name": "秋の温泉キャンペーン" }
EOF
sf api request rest "/services/data/v67.0/sobjects/igns__Template__c" --method POST -b @/tmp/tpl.json -o <org>
# → {"id":"a0K...","success":true}
```

## ③ テンプレートメッセージの作成

共通項目:

| 項目 | 必須 | 内容 |
|---|---|---|
| `igns__Template__c` | ✔ | 親テンプレートの Id |
| `igns__Type__c` | ✔ | `text` / `image` / `video` / `imagemap` / `carousel` / `confirm` / `image_carousel` / `coupon` / `flex` |
| `igns__Sort__c` | 推奨 | 送信順（1, 2, 3…）。自動採番されないので明示する |
| `igns__Sender__c` | 任意 | 送信元（`igns__Sender__c`）の Id。アイコンと表示名を差し替える |
| `igns__AltText__c` | imagemap のみ必須 | PC版・通知欄での代替テキスト（255字）。他タイプは空なら送信時に自動補完 |

```bash
cat > /tmp/msg.json <<'EOF'
{ "igns__Template__c": "<templateId>", "igns__Type__c": "text", "igns__Sort__c": 1,
  "igns__Text__c": "箱根・草津・別府の秋の温泉プランをご用意しました♨\n11月30日まで最大20%OFFです。" }
EOF
sf api request rest "/services/data/v67.0/sobjects/igns__TemplateMessage__c" --method POST -b @/tmp/msg.json -o <org>
```

修正は PATCH:

```bash
sf api request rest "/services/data/v67.0/sobjects/igns__TemplateMessage__c/<msgId>" --method PATCH -b @/tmp/patch.json -o <org>
```

### タイプ別の項目

**アクション項目の添字ルール**（`ActionType`/`ActionLabel`/`ActionUrl`/`ActionMessage`/`ActionTemplate`/`ActionReply`/`ActionOption`/`ActionFillInText` に共通）:

| タイプ | 添字 | 例 |
|---|---|---|
| 設問（2択）のボタン1・2 | `11` / `12` | `igns__ActionType11__c` |
| カード n 枚目のボタン m | `nm`（n=1〜9, m=1〜3） | カード2のボタン3 → `igns__ActionType23__c` |
| カード n 枚目の画像タップ時（任意） | `n` | `igns__ActionType2__c`（ラベル不要） |
| カード（画像のみ）n 枚目 | `n` | `igns__ActionType3__c` |
| リンク付き画像の領域 n | `n` | `igns__ActionType4__c`（uri / message のみ） |

`igns__ActionType*__c` の値と、必要な相手項目:

| 値 | 意味 | 必須 | 任意 |
|---|---|---|---|
| `uri` | リンクを開く | `ActionUrl`（255字） | |
| `message` | メッセージ送信 | `ActionMessage`（255字） | |
| `postback` | テンプレート呼出 | `ActionTemplate`（Template__c の Id） | `ActionMessage`（タップ時に表示するテキスト）、`ActionOption`（`openKeyboard` などLINE側の動作）、`ActionFillInText`（キーボードに入れる文字）、項目の代入 |
| `callagent` | AIエージェント呼出 | `ActionReply`（`igns__Reply__c` の Id） | `ActionMessage`、`ActionOption`、`ActionFillInText` |

ボタンには `ActionLabel`（ボタンの文字、20字。カード（画像のみ）は12字）も必須。

#### text

| 項目 | 内容 |
|---|---|
| `igns__Text__c` | 本文（必須）。改行・絵文字可。差し込み `{!Name}` 等が使える |

#### image

| 項目 | 内容 |
|---|---|
| `igns__OriginalContentUrl__c` | 画像URL（必須）。`lamp-media-upload` の contentType=`image` で得た `.../contents/images/original/<id>.png` |
| `igns__PreviewImageUrl__c` | プレビュー画像URL（必須）。通常は同じURL |

#### video

| 項目 | 内容 |
|---|---|
| `igns__OriginalContentUrl__c` | mp4 のURL（必須、200MB以下） |
| `igns__PreviewImageUrl__c` | サムネイル JPEG/PNG のURL（必須）。`lamp-media-upload` の video + video_thumbnail で同じ customId にした `.../videos/preview/<id>.jpg`。動画と同じ縦横比にする |

#### imagemap（リンク付き画像）

| 項目 | 内容 |
|---|---|
| `igns__OriginalContentUrl__c` | **拡張子なし**の imagemap 用URL（必須）。`lamp-media-upload` の contentType=`imagemap` で得た `.../contents/imagemaps/original/<id>`。`.png` 付きURLは有効化エラーになる |
| `igns__BoundName__c` | 領域の分割パターン（必須。下表） |
| `igns__AltText__c` | 代替テキスト（必須） |
| `igns__ActionType{n}__c` + `ActionUrl{n}` / `ActionMessage{n}` | 領域 n のアクション。`uri` または `message` のみ。**1つ以上**あれば有効（全領域を埋めなくてよい） |

分割パターン（`igns__BoundName__c`）と推奨画像サイズ・領域数:

| 区分 | 値 | 領域数 | 画像サイズ |
|---|---|---|---|
| 正方形 | `IM_FULL_GRID` フルサイズ / `IM_VERTICAL_SPLIT` 縦に2分割 / `IM_HORIZONTAL_SPLIT` 横に2分割 / `IM_DOUBLE_BANNER` 2段バナー | 1 / 2 / 2 / 2 | 1040×1040 |
| 正方形 | `IM_TRIPLE_HORIZONTAL` 横に3分割 / `IM_TRIPLE_HORIZONTAL_BANNER` 3段バナー / `IM_TOP_BANNER_DOUBLE_BOTTOM` 上部バナー＋下部2分割 / `IM_LEFT_BANNER_DOUBLE_RIGHT` 上部バナー＋下部左右分割 / `IM_DOUBLE_LEFT_RIGHT_BANNER` 左2段＋右フル / `IM_DOUBLE_RIGHT_LEFT_BANNER` 左フル＋右2段 | 3 | 1040×1040 |
| 正方形 | `IM_QUAD_GRID` 4分割グリッド / `IM_TRIPLE_VERTICAL_GRID` 3×2グリッド | 4 / 6 | 1040×1040 |
| 縦長 | `IM_TALL_FULL_1300` フル / `IM_TAIM_TALL_VERTILL_VERTICAL_SPLIT_1300` 縦2分割 / `IM_TALL_HORIZONTAL_SPLIT_1300` 横2分割 / `IM_TALL_TRIPLE_HORIZONTAL_1300` 横3分割 | 1 / 2 / 2 / 3 | 1040×1300 |
| 縦長 | `IM_TALL_FULL_1850` フル / `IM_TALL_VERTICAL_SPLIT_1850` 縦2分割 / `IM_TALL_QUAD_HORIZONTAL_1850` 4分割 / `IM_TALL_GRID_2X4_1850` 2×4グリッド | 1 / 2 / 4 / 8 | 1040×1850 |
| 横長 | `IM_WIDE_SINGLE_350` フル | 1 | 1040×350 |
| 横長 | `IM_WIDE_FULL_585` フル / `IM_WIDE_EQUAL_585` 均等分割 / `IM_WIDE_MAIN_SUB_585` メイン＋サブ / `IM_WIDE_SUB_MAIN_585` サブ＋メイン | 1 / 2 / 2 / 2 | 1040×585 |
| 横長 | `IM_WIDE_FULL_700` フル / `IM_WIDE_SPLIT_700` 均等分割 | 1 / 2 | 1040×700 |

領域番号は左上から右へ、次に下の段へ進む。画像の縦横比がパターンと違うと LINE では切り抜かれて表示される。

#### carousel（カード）

| 項目 | 内容 |
|---|---|
| `igns__ImageAspectRatio1__c` | `rectangle`（横長 1.51:1、既定）または `square`（1:1）。全カード共通 |
| `igns__ImageUrl{n}__c` | カード n の画像URL（任意。1024×678 または 1024×1024） |
| `igns__Title{n}__c` | タイトル（任意、40字） |
| `igns__Text{n}__c` | テキスト（**必須**、60字） |
| `igns__ActionType{n}__c` … | 画像タップ時のアクション（任意、ラベル不要） |
| `igns__ActionType{nm}__c` + `ActionLabel{nm}` … | ボタン m（1〜3）。**各カードに1つ以上、かつ全カードで同数** |

カードは 1〜9 枚。項目が1つでも入っているカードは「存在する」とみなされるので、作りかけのカードを残さない。

#### confirm（設問（2択））

| 項目 | 内容 |
|---|---|
| `igns__Text1__c` | 質問文（必須、240字） |
| `igns__ActionType11__c` + `ActionLabel11` … | ボタン1（必須、ラベル20字） |
| `igns__ActionType12__c` + `ActionLabel12` … | ボタン2（必須） |

#### image_carousel（カード（画像のみ））

| 項目 | 内容 |
|---|---|
| `igns__ImageUrl{n}__c` | カード n の画像URL（必須、1024×1024 推奨） |
| `igns__ActionType{n}__c` + 相手項目 | カード n のアクション（必須） |
| `igns__ActionLabel{n}__c` | 画像下端に重なるラベル（任意、12字） |

#### coupon

| 項目 | 内容 |
|---|---|
| `igns__Coupon__c` | `igns__Coupon__c` レコードの Id（必須）。LINE に登録済み（`igns__CouponId__c` が入っている）クーポンだけが実配信できる |

```bash
sf data query -q "SELECT Id, Name, igns__CouponId__c, igns__EndDateTime__c FROM igns__Coupon__c WHERE igns__CouponId__c != null ORDER BY CreatedDate DESC" -o <org>
```

#### flex（フレックス）

| 項目 | 内容 |
|---|---|
| `igns__Json__c` | LINE の Flex Message オブジェクトそのもの（必須）: `{"type":"flex","altText":"…","contents":{ bubble または carousel }}`。`contents` の構造は LINE Messaging API の Flex 仕様に従う |
| `igns__FlexEditorData__c` | 任意。ビジュアルエディタのブロックモデル。ヘッドレスで `Json__c` だけ入れた場合、送信・プレビューは動くが画面のビジュアルエディタでは編集できない旨をユーザーに伝える |

`Json__c` 内のボタン等の `action` は LINE 標準の `uri` / `message` / `postback` を使う。テンプレート呼出は `postback` の `data` に `recordId=<templateId>&type=template` 形式が必要なので、フレックスで LAMP のテンプレート呼出をしたい場合は画面のビジュアルエディタを案内する。

## ④ 検証ループ

作成・修正のたびに確認する:

```bash
sf data query -q "SELECT Id, Name, igns__Type__c, igns__Sort__c, igns__IsValid__c, igns__ValidationErrors__c FROM igns__TemplateMessage__c WHERE igns__Template__c = '<templateId>' ORDER BY igns__Sort__c" -o <org>
```

- `igns__IsValid__c = true` になれば LINE に送れる状態
- `false` のときは `igns__ValidationErrors__c` に理由が 1行1件（API名つき）で入る。例 `カード1 ボタン1: URL（ActionUrl11__c）を入力してください` → その項目を PATCH して再確認
- 無効なメッセージは配信時に**黙って除外**される（配信は失敗しない）。全件 `true` を確認してから次へ進む

## ⑤ 返信ボタン（クイックリプライ、任意）

テンプレート（`igns__Template__c`）側の項目。最大13個（添字 1〜13）。メッセージのいちばん下にチップとして並ぶ。

| 項目 | 内容 |
|---|---|
| `igns__ActionType{n}__c` | `uri` / `message` / `postback`（テンプレート呼出） / `callagent` / `camera` / `cameraRoll` / `location` |
| `igns__ActionLabel{n}__c` | 表示テキスト（必須、20字） |
| `igns__ActionUrl{n}__c` / `ActionMessage{n}` / `ActionTemplate{n}` / `ActionReply{n}` | 種類ごとの相手項目（メッセージと同じ規則。`postback` の送信テキストは任意） |
| `igns__ActionOption{n}__c` / `ActionFillInText{n}` | LINE側の動作 `closeRichMenu` / `openKeyboard` / `openVoice` と、キーボードに入れる文字 |

```bash
cat > /tmp/qr.json <<'EOF'
{ "igns__ActionType1__c": "uri", "igns__ActionLabel1__c": "プランを見る", "igns__ActionUrl1__c": "https://example.com/plans",
  "igns__ActionType2__c": "postback", "igns__ActionLabel2__c": "他のプランを見る", "igns__ActionTemplate2__c": "<別テンプレートId>",
  "igns__ActionType3__c": "camera", "igns__ActionLabel3__c": "写真を送る" }
EOF
sf api request rest "/services/data/v67.0/sobjects/igns__Template__c/<templateId>" --method PATCH -b @/tmp/qr.json -o <org>
```

## ⑥ 項目の代入（任意）

ボタンがタップされたときに友だち（`igns__SocialFriend__c`）の項目へ値を入れる設定。`igns__TemplateFieldSetting__c` に1行1項目。

| 項目 | 内容 |
|---|---|
| `igns__Template__c` | テンプレートの Id（必須） |
| `Name` | 友だちオブジェクトの項目API名（例 `igns__TestDeliveryDisplayName__c`、カスタム項目なら `Interest__c`） |
| `igns__Condition__c` | `EQ`（次の文字列と一致する＝置き換え）/ `ADD`（追加）/ `BLANK`（空白にする） |
| `igns__Value__c` | 値 |
| `igns__SourcedRecordId__c` | どのボタンか: テンプレートメッセージの Id（返信ボタンならテンプレートの Id） |
| `igns__SourcedActionId__c` | そのボタンの添字文字列（カード2ボタン1なら `"21"`、設問のボタン2なら `"12"`、返信ボタン3なら `"3"`） |

`SourcedRecordId__c` と `SourcedActionId__c` を両方空にすると、**テンプレート送信時に必ず**適用される共通設定になる。
選択肢ごとの代入が効くのは、そのボタンのアクション種類が `postback`（テンプレート呼出）または `callagent` のときだけ。

## ⑦ テスト配信

テスト配信の対象になるのは「テスト用?」にチェックが入った友だちだけ:

```bash
sf data query -q "SELECT Id, Name FROM igns__SocialFriend__c WHERE igns__IsTest__c = true" -o <org>
```

候補が無ければ、ユーザーに「友だちレコードの『テスト用?』にチェックを入れる」か、公式アカウントを友だち追加してもらう。

```bash
cat > /tmp/send.json <<'EOF'
{ "inputs": [ { "socialFriendId": "<socialFriendId>", "templateId": "<templateId>", "flowName": "lamp-template-skill" } ] }
EOF
sf api request rest "/services/data/v67.0/actions/custom/apex/igns__SendPushMessageFromSocialAccount" --method POST -b @/tmp/send.json -o <org>
```

Actions API の `isSuccess: true` は**ジョブを投入できた**という意味しかない。実際の結果は非同期ジョブで確認する（10秒ほど待つ）:

```bash
sf data query -q "SELECT Status, ExtendedStatus, CompletedDate FROM AsyncApexJob WHERE ApexClass.Name = 'SendPushMessageFromSocialAccount' ORDER BY CreatedDate DESC LIMIT 1" -o <org>
```

- `Status = Completed` かつ `ExtendedStatus` が空 → 送信成功
- `Status = Failed` → `ExtendedStatus` に理由（`Coupon not found`、`送信できる有効なメッセージがありません` など）

## トラブルシューティング

| 症状 | 原因と対処 |
|---|---|
| 保存が `FIELD_CUSTOM_VALIDATION_EXCEPTION`「1つのテンプレートに5つ以上の…」 | 有効メッセージが既に5件。テンプレートを分ける |
| `IsValid__c` が `false` のまま | `ValidationErrors__c` の指示どおり項目を埋める。imagemap は `.png` 付きURLを拒否する |
| `INVALID_FIELD` / `No such column 'igns__…'` | 項目API名の添字を確認（設問は `11`/`12`、カードは `nm`、カード（画像のみ）・領域は `n`） |
| `bad value for restricted picklist field` | `ActionType` は `uri`/`message`/`postback`/`callagent`（テンプレート側はさらに `camera`/`cameraRoll`/`location`）。`ActionOption` は `closeRichMenu`/`openRichMenu`/`openKeyboard`/`openVoice`（テンプレート側に `openRichMenu` は無い） |
| プレビューや LINE で画像が出ない | URL がコンテンツ配信基盤のものか、imagemap は拡張子なしか、動画はサムネイルが JPEG/PNG かを確認 |
| 配信ジョブが `Completed` なのに届かない | 無効なメッセージは黙って除外される。全件 `IsValid__c = true` か確認。クーポンは `CouponId__c` が LINE 発行のものか確認 |
