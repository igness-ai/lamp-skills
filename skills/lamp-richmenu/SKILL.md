---
name: lamp-richmenu
description: Igness LAMP のリッチメニュー（LINE トーク画面下部のメニュー）を Salesforce CLI でヘッドレスに作成・検証・LINE に発行し、デフォルト設定・友だち個別の割当・差し替え・削除まで行う。「LAMPでリッチメニューを作って」「リッチメニューを有効化して」「メニューの画像を差し替えて」「この友だちにメニューを割り当てて」などで使う。
---

# LAMP リッチメニュー（ヘッドレス）

リッチメニューは **`igns__RichMenu__c`** レコードで定義する。レイアウト（領域の分割）はプリセットから選び、領域ごとにタップ時のアクションを設定し、画像を付けて **LINE に発行**すると使えるようになる。

```
① レイアウト選択   igns__LampBound__mdt のプリセット（領域数・画像サイズ）
② 画像の用意       lamp-media-upload（種別 richmenu）でアップロード → ImageUrl__c
③ レコード作成     igns__RichMenu__c（領域ごとの ActionType{n} …）
④ 検証ループ       IsValid__c / ValidationErrors__c を読んで修正
⑤ LINE に発行      Actions API igns__LampPublishRichMenuAction
⑥ 適用             デフォルトメニュー（公式アカウント全体）/ 友だち個別の割当
⑦ 差し替え・削除   update モードで再発行 / igns__LampDeleteRichMenuAction
```

## 前提条件

- LAMP 基本パッケージ **1.157 以降**（発行・削除アクション、有効化エラー項目）
- `sf` CLI で対象 org に認証済み（以下 `<org>`）。API バージョン v67.0 以上
- 実行ユーザーに `LAMP_SystemAdministrator` または `LAMP_MarketingAdministrator` 権限セットグループ
- 公式アカウント（`igns__SocialAccount__c`）が接続済み
- **必ず最初に対象 org をユーザーに確認する**（顧客の本番 org を扱うため）

## 守ること

- **発行・デフォルト設定・削除は顧客の LINE 友だちの画面を即座に変える。** 実行前にユーザーの明示の承認を得る
- `igns__Json__c` / `igns__IsValid__c` / `igns__ValidationErrors__c` / `igns__RichMenuId__c` は書かない（トリガーと発行処理が管理する）
- 発行済みメニューの内容を変えたら、必ず ⑤ を `mode=update` で再発行する（レコードを変えただけでは LINE 側は変わらない。`igns__IsNeedUpdate__c=true` が「未反映」の印）
- 記録した Id は会話に残し、同じメニューを二重に作らない

## ① レイアウトの選択

```bash
sf data query -q "SELECT DeveloperName, igns__Width__c, igns__Height__c, igns__BoundsJson__c FROM igns__LampBound__mdt WHERE igns__Usage__c = 'Richmenu' ORDER BY igns__Order__c" -o <org>
```

`igns__BoundsJson__c` が領域の配列（`[{x,y,width,height}, …]`）で、**配列の要素数＝設定が必要な領域数**。`igns__Width__c × igns__Height__c` が画像の寸法。
プリセット例: `EQUAL_SPLIT`（2500×843、左右 2 分割）、`MAIN_SIDE_SPLIT`（3 領域）、`GRID_6_EQUAL`（2500×1686、6 分割）、`FULL_BANNER`（1 領域）。ユーザーの要望（ボタン数・大小）に合うものを提示して選んでもらう。

## ② 画像の用意

`lamp-media-upload` スキルの種別 `richmenu` でアップロードし、返った公開 URL を `igns__ImageUrl__c` に入れる（`recordId` と `imageUrlField=igns__ImageUrl__c`、`uuidField=igns__Uuid__c` を渡せば完了アクションが直接書く）。

画像の制約（LINE）: JPEG / PNG、**幅 800〜2500 px・高さ 250 px 以上・幅÷高さ 1.45 以上・1 MB 以下**、かつ選んだプリセットの `Width__c × Height__c` に合わせる。アップロード前に `sips -g pixelWidth -g pixelHeight <file>` と `stat -f %z <file>` で確認する。

## ③ レコードの作成

```bash
cat > /tmp/rm.json <<'EOF'
{ "Name": "メインメニュー",
  "igns__SocialAccount__c": "<socialAccountId>",
  "igns__BoundName__c": "MAIN_SIDE_SPLIT",
  "igns__ChatBarText__c": "メニュー",
  "igns__IsSelected__c": true,
  "igns__ActionType1__c": "uri",      "igns__ActionUrl1__c": "https://example.com/plans",
  "igns__ActionType2__c": "postback", "igns__ActionTemplate2__c": "<templateId>", "igns__ActionMessage2__c": "資料請求",
  "igns__ActionType3__c": "callagent","igns__ActionReply3__c": "<replyId>", "igns__ActionMessage3__c": "相談する" }
EOF
sf api request rest "/services/data/v67.0/sobjects/igns__RichMenu__c" --method POST -b @/tmp/rm.json -o <org>
```

| 項目 | 内容 |
|---|---|
| `igns__SocialAccount__c` | 公式アカウント（必須） |
| `igns__BoundName__c` | ① の `DeveloperName`（必須） |
| `igns__ChatBarText__c` | トーク画面下部に出るバーの文字（14 文字以内。空なら「メニュー」） |
| `igns__IsSelected__c` | `true` なら最初から開いた状態で表示 |
| `igns__ImageUrl__c` | ② の公開 URL（発行時に必須） |

領域 n（1 始まり、レイアウトの領域数ぶん **すべて**設定する。1 つでも欠けると無効）:

| `igns__ActionType{n}__c` | 意味 | 必須の相手項目 | 任意 |
|---|---|---|---|
| `uri` | リンクを開く | `igns__ActionUrl{n}__c`（http / https / line / tel のみ） | |
| `postback` | テンプレート呼出 | `igns__ActionTemplate{n}__c`（`igns__Template__c` の Id） | `igns__ActionMessage{n}__c`（タップ時にトークへ表示する文字）、`igns__ActionOption{n}__c`（`openKeyboard` など）、`igns__ActionFillInText{n}__c` |
| `callagent` | AI エージェント呼出 | `igns__ActionReply{n}__c`（`igns__Reply__c` の Id） | `igns__ActionMessage{n}__c`、`igns__ActionOption{n}__c`、`igns__ActionFillInText{n}__c` |
| `richmenuswitch` | 別のリッチメニューへ切替（タブ） | `igns__ActionRichMenu{n}__c`（切替先の `igns__RichMenu__c` の Id。**切替先も発行済み**であること） | |

Agentforce の自動応答を呼び出す場合は、`lamp-agentforce` で種別 `Agentforce` の自動応答を作成し、その Id を `ActionReply{n}` に設定する。

## ④ 検証ループ

```bash
sf data query -q "SELECT igns__IsValid__c, igns__ValidationErrors__c, igns__IsActive__c, igns__RichMenuId__c, igns__ImageUrl__c FROM igns__RichMenu__c WHERE Id = '<richMenuId>'" -o <org>
```

`igns__IsValid__c=false` なら `igns__ValidationErrors__c` の日本語の理由（「領域2のアクションタイプが設定されていません」「領域1のURIアクションにURLが設定されていません」「指定されたレイアウト名が見つかりません」等）に従って PATCH で直す。保存はブロックされないので、直して保存 → 再確認を繰り返す。

## ⑤ LINE に発行

```bash
cat > /tmp/pub.json <<'EOF'
{ "inputs": [ { "richMenuId": "<richMenuId>" } ] }
EOF
sf api request rest "/services/data/v67.0/actions/custom/apex/igns__LampPublishRichMenuAction" --method POST -b @/tmp/pub.json -o <org>
```

- `mode` を省略すると自動（`igns__RichMenuId__c` が空なら新規発行、あれば差し替え）。明示するなら `"mode": "create"` / `"mode": "update"`
- 成功: `outputValues.success=true`、`lineRichMenuId`（`richmenu-…`）、`isActive=true`。レコードの `igns__RichMenuId__c` / `igns__IsActive__c` も更新される
- 失敗: `success=false`、`message` に理由。設定不備なら `validationErrors` も返る

| `message` | 対処 |
|---|---|
| リッチメニューの設定が無効なため発行できません: … | ④ の理由を直す |
| 画像が設定されていません。… | ② を行い `igns__ImageUrl__c` を設定 |
| このリッチメニューは既に LINE に発行されています… | 差し替えなら `mode=update`（または省略） |
| …HTTP 400: 画像の寸法（W×Hpx）が対応していません… | ② の制約に合わせて作り直して上げ直す |
| …HTTP 400: 画像の容量が1MBを超えています… | 圧縮して上げ直す |
| …HTTP 400: LINEがリッチメニューの設定を受け付けませんでした。… `areas[0].action.data: …` | 示された項目（例: postback の data が長すぎる＝`ActionMessage` を短く）を直す |
| …HTTP 401 / 403 | サーバー認証か公式アカウント接続の問題（`lamp-setup` で確認）。接続直後は最大 5 分待つ |

発行に失敗しても LINE 側に未完成のメニューは残らない（backend が回収する）ので、直してそのまま再発行してよい。

## ⑥ 適用

**デフォルトメニュー（公式アカウントの全友だち）**: 公式アカウントの `igns__DefaultRichMenu__c` に発行済みメニューの Id を入れる。処理は非同期なので `igns__RichMenuStatus__c` をポーリングする（`updating` → `valid` / `error`）。

```bash
sf api request rest "/services/data/v67.0/sobjects/igns__SocialAccount__c/<socialAccountId>" --method PATCH -b '{"igns__DefaultRichMenu__c":"<richMenuId>"}' -o <org>
sf data query -q "SELECT igns__RichMenuStatus__c, igns__RichMenuErrorMessage__c FROM igns__SocialAccount__c WHERE Id = '<socialAccountId>'" -o <org>
```

解除は `igns__DefaultRichMenu__c` を `null` に更新。未発行のメニューは選べない（参照フィルタで弾かれる）。

**友だち個別の割当**: `igns__SocialFriend__c.igns__RichMenu__c` に Id を入れる。同じく `igns__RichMenuStatus__c` をポーリング。解除は `null`。未発行のメニューを割り当てると `error`（「リッチメニューがLINEに発行されていません」）になる。

複数の友だちに一括で割り当てる場合は 1 件ずつ更新し、`valid` を確認してから次へ進む（1 トランザクションで大量更新すると非同期処理の上限に当たる）。

## ⑦ 差し替え・削除

- **内容の変更**: レコードを PATCH（アクション・レイアウト）→ ④ で有効を確認 → ⑤ を `mode=update`。画像だけ変える場合も ② で上げ直して ⑤ を `update`。LINE 側では新しいメニューが作られ、デフォルト設定・友だちの割当は自動で新しいメニューに付け替わる
- **削除**:

```bash
sf api request rest "/services/data/v67.0/actions/custom/apex/igns__LampDeleteRichMenuAction" --method POST -b '{"inputs":[{"richMenuId":"<richMenuId>"}]}' -o <org>
```

LINE 側から削除され、レコードは未発行（`igns__IsActive__c=false`、`igns__RichMenuId__c` 空）に戻る。デフォルトや友だちに割り当て中のメニューを削除すると、その人たちのメニューは消える。先に別メニューへ切り替えるか、ユーザーに影響を伝えて承認を得る。

## トラブルシューティング

| 症状 | 原因と対処 |
|---|---|
| `IsValid__c` が `false` のまま | `ValidationErrors__c` の理由どおり項目を埋める。領域数はレイアウトの `BoundsJson__c` の要素数 |
| 発行は成功したのにスマホで画像が崩れる | 画像の寸法がプリセットの `Width__c × Height__c` と違う。作り直して `update` |
| `RichMenuStatus__c` が `updating` のまま長い | 非同期処理の失敗。`RichMenuErrorMessage__c` を確認し、値を一度 `null` にしてから再設定 |
| `richmenuswitch` で切り替わらない | 切替先が未発行。切替先を先に ⑤ で発行してから、このメニューを `update` |
| 発行で `HTTP 403` | 公式アカウント接続の直後（最大 5 分）か、サーバー認証切れ |
