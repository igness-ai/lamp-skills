---
name: lamp-media-upload
description: Igness LAMP のコンテンツ配信基盤へ画像・動画をヘッドレスでアップロードし、テンプレートメッセージ（画像・動画・リンク付き画像・カルーセル・Flex）、クーポン、リッチメニュー、送信元アイコンに設定する。「LAMPに画像をアップロード」「リンク付き画像の画像を差し替え」「動画メッセージを作りたい」などで使う。sf CLI と curl のみで完結し、ブラウザ操作は不要。
---

# LAMP メディアアップロード（ヘッドレス）

LAMP の画像・動画は S3 上のコンテンツ配信基盤に置き、その公開URLを Salesforce レコードに設定する。
UI の fileUploader と同じ経路を、2つの global アクション（Actions API）で呼び出す。

```
① アップロードURL発行  igns__LampGetUploadUrlAction   → presignedUrl / customId
② ファイル本体を PUT    curl -X PUT（署名付きURLへ直接）
③ アップロード完了      igns__LampCompleteUploadAction → 公開URL（＋レコード更新）
```

## 前提条件

- LAMP 基本パッケージ 1.155 以降がインストール済み、サーバー認証（設定タブ）完了済み
- 実行ユーザーに `LAMP_SystemAdministrator` または `LAMP_MarketingAdministrator` 権限セットグループ
- `sf` CLI で対象 org に認証済み（以下 `<org>`）。API バージョンは v66.0 以上

## 種別（contentType）と保存先

| contentType | 用途 | 拡張子 | 完了後の URL | 設定先レコード / 項目 |
|---|---|---|---|---|
| `image` | テンプレートの画像メッセージ、カルーセル各カードの画像、Flex 内の画像 | png/jpg/jpeg/gif/webp | `.../contents/images/original/<id>.<ext>` | `igns__TemplateMessage__c.igns__OriginalContentUrl__c`（画像）/ `igns__ImageUrl1__c`〜`9`（カルーセル）/ Flex JSON の `url` |
| `imagemap` | リンク付き画像（imagemap） | png/jpg | `.../contents/imagemaps/original/<id>`（**拡張子なし**。LINE が `/1040` 等を付けて取得。240/300/460/700/1040 を自動生成） | `igns__TemplateMessage__c.igns__OriginalContentUrl__c` |
| `video` | 動画メッセージ | mp4 のみ | `.../contents/videos/original/<id>.mp4` | `igns__TemplateMessage__c.igns__OriginalContentUrl__c`（`igns__PreviewImageUrl__c` にサムネが自動設定） |
| `video_thumbnail` | 動画のプレビュー画像 | jpg 固定 | 動画の完了処理で検証 | 単独では完了処理を呼ばない（下記「動画」参照） |
| `coupon` | クーポン画像 | png/jpg | `.../contents/coupon/upload/<id>.<ext>` | `igns__Coupon__c.igns__ImageUrl__c`（UUID: `igns__ImageUuid__c`）。バーコードは `igns__BarcodeUrl__c` / `igns__BarcodeUuid__c` |
| `richmenu` | リッチメニュー画像 | png/jpg（2500×1686 または 2500×843） | `.../contents/templateImages/upload/<id>.<ext>` | `igns__RichMenu__c.igns__ImageUrl__c`（UUID: `igns__Uuid__c`）。LINE への画像登録はリッチメニュー作成時に自動 |
| `profile` | 送信元（Sender）のアイコン | png/jpg | `.../contents/profile/upload/<id>.<ext>` | `igns__Sender__c.igns__PictureUrl__c`（UUID: `igns__UUID__c`） |

`image_coupon` / `image_richmenu` / `image_profile` / `sender` も同じ意味で受け付ける。

## 手順

### ① アップロードURLの発行

```bash
sf api request rest "/services/data/v66.0/actions/custom/apex/igns__LampGetUploadUrlAction" --method POST \
  -b '{"inputs":[{"contentType":"imagemap","fileExtension":"png"}]}' -o <org>
```

返り値の `outputValues`: `presignedUrl`（10分有効）、`customId`（UUID v4。自分で指定する場合もこの形式のみ）、`contentType`、`fileExtension`、`contentTypeHeader`。
`success:false` のときは `message` に理由（種別・拡張子の誤りなど）が入る。

**注意**: `presignedUrl` はそれ自体がアップロード権限なので、ログや会話に貼らない。

### ② ファイル本体の PUT

```bash
curl -sS -o /dev/null -w "%{http_code}\n" -X PUT \
  -H "Content-Type: <contentTypeHeader>" --data-binary @<ローカルファイル> "<presignedUrl>"
```

`200` 以外なら URL 期限切れ（10分）か Content-Type 不一致。①からやり直す。

### ③ アップロード完了（公開URL取得＋レコード更新）

```bash
sf api request rest "/services/data/v66.0/actions/custom/apex/igns__LampCompleteUploadAction" --method POST \
  -b '{"inputs":[{"customId":"<customId>","contentType":"imagemap","fileExtension":"png",
       "recordId":"<TemplateMessage__cのId>","imageUrlField":"igns__OriginalContentUrl__c","uuidField":"igns__UUID__c"}]}' -o <org>
```

- `recordId` を省略すると公開URL（`originalUrl` / `previewUrl`）だけ返す。カルーセルのカード画像や Flex 内画像はこの URL をレコード／JSON に自分で設定する
- `recordId` を渡す場合は `imageUrlField` 必須。`igns__OriginalContentUrl__c` を指定すると `igns__PreviewImageUrl__c` も同時に更新される
- 更新は実行ユーザーの権限（項目レベルセキュリティ）で行われる。権限不足は `message` に出る

## 動画（video）の手順

LINE 仕様でプレビュー画像が必須。動画とサムネは **同じ customId** で組にする。

```
1. ① contentType=video, fileExtension=mp4         → customId=X, presignedUrl(A)
2. ② 動画を A へ PUT
3. ① contentType=video_thumbnail, customId=X       → presignedUrl(B)（拡張子は jpg 固定）
4. ② サムネ(jpg) を B へ PUT
5. ③ contentType=video, customId=X, fileExtension=mp4, recordId=..., imageUrlField=igns__OriginalContentUrl__c
```

サムネ側で③を呼ぶ必要はない（呼ぶとその旨のエラーが返る）。5 でサムネが無いと backend がエラーを返す。
動画とサムネのアスペクト比は一致させる。mp4 は 200MB 以下。

## リンク付き画像（imagemap）の注意

- ③が返す URL は拡張子なし。**`.png` の直リンクを `igns__OriginalContentUrl__c` に入れると LINE で「読み込めませんでした」になる**ため、テンプレートメッセージの検証（`igns__ValidationErrors__c`）でも拒否される
- 画像は 1040px 幅推奨。分割パターン（`igns__BoundName__c`）の比率に合わせる

## 作成後の確認

```bash
sf data query -q "SELECT igns__IsValid__c, igns__ValidationErrors__c, igns__OriginalContentUrl__c FROM igns__TemplateMessage__c WHERE Id='<Id>'" -o <org>
```

`igns__IsValid__c=false` なら `igns__ValidationErrors__c` の理由（日本語）に従って項目を直す。
リンク付き画像は `curl -s -o /dev/null -w "%{http_code}" "<originalUrl>/1040"` が 200 を返すこと。

## トラブルシューティング

| 症状 | 原因と対処 |
|---|---|
| ①で `success:false`「種別（contentType）は…」 | 種別の綴り。上表の値を使う |
| ②で 403 | 署名URLの期限切れ（10分）。①からやり直す |
| ③で「画像処理に失敗しました。ステータスコード: 4xx/5xx」 | ②の PUT が完了していない、customId/拡張子/種別が①と一致していない、動画でサムネ未配置 |
| ③で権限系メッセージ | 実行ユーザーに対象項目の編集権限がない。権限セットグループを確認 |
| LINE で画像が「読み込めませんでした」 | imagemap に `image` 種別の URL（拡張子付き）を使っている。`imagemap` 種別で上げ直す |
