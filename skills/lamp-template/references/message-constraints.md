# テンプレート種別ごとの設定・制約

新規作成・種別変更・有効化エラー対応では対象種別の行と補足を読む。LAMPの基本パッケージ1.157時点の保存・生成処理と、[LINEのメッセージ仕様](https://developers.line.biz/en/reference/messaging-api/#message-objects) を区別する。`IsValid=true` はLAMP内の検証結果で、LINE側の全制約や宛先ごとの差し込み結果まで保証しない。

## 対応する9種別

| 種別 | 必須設定・個数 | 長さ・画像・アクションの条件 |
|---|---|---|
| text | `Text__c` | 5,000文字以内。差し込み後も上限内にする。本文そのものにボタンはなく、テンプレート側の返信ボタンを併用 |
| image | `OriginalContentUrl__c` / `PreviewImageUrl__c` | `lamp-media-upload` のimage。元画像とプレビューの公開URLを両方設定。画像自体からテンプレートやAgentforceを呼ぶ設定はなく、imagemap・カード・返信ボタン等を選ぶ |
| video | 動画URL / JPEG・PNGのプレビューURL | `lamp-media-upload` のvideo + video_thumbnail。同じcustomId、動画と同じ縦横比。mp4、200MB以下 |
| imagemap | 拡張子なしbase URL / `BoundName__c` / `AltText__c` / 1領域以上の有効なアクション | 選んだ領域数・画像寸法に一致。領域はuri/messageのみ。別テンプレートやAgentforceを直接指定できない。messageでキーワードを送る場合は通常受信の条件判定になる |
| carousel | 1〜9枚、各 `Text{n}`、各1〜3ボタン | タイトル40文字、ボタンラベル20文字。画像またはタイトルありの本文60文字。画像・タイトルの有無とボタン数を全カードで揃える |
| confirm | `Text1`、ボタン11・12の両方 | 質問240文字、各ラベル20文字。1択・3択は不可 |
| image_carousel | 1〜9枚、各画像URLとアクション | ラベル任意・12文字以内。LAMPの項目は20文字だが送信時に12文字へ切り詰める。正方形画像を用意。カード別代入の制限は [actions.md](actions.md) |
| coupon | 発行済み `Coupon__c` | 同じ公式アカウントで利用するクーポンの `CouponId__c`、期限・終了状態を確認。SalesforceのIdだけではLINEへ送れない。詳細は `lamp-coupon` |
| flex | `Json__c` に `type=flex` / `contents` | `AltText__c`、JSON内altText、既定値の順で補完。LAMPの検証はJSON形式と外側の構造が中心。内部のレイアウト・アクション・サイズはLINE仕様で確認 |

`buttons` / `sticker` / `location` / `audio` は現行Type選択肢で非アクティブ。項目が残っていても新規テンプレートで利用可能とは判断しない。1枚カードは `carousel` を使う。返信ボタンの `location` は「位置情報を送ってもらう」機能で、位置情報メッセージ種別とは別。

## カードの細部

- 画像とタイトルを全カードで揃える制約は、LAMPの有効化チェックが完全には検出しない。カードの一部にだけ画像・タイトルを残さない。
- 本文はSalesforceの `Text{n}__c` に240文字保存できるが、LINEの制限は別。画像・タイトルともなしの複数カードは120文字、1枚カード（buttonsに変換）は160文字まで。画像またはタイトルがあれば60文字。差し込み後の長さも確認する。
- 画像比率は `ImageAspectRatio1__c` が全カードに適用される（rectangle / square）。現行生成は背景白、複数カードは `imageSize=cover`。背景色やcontainを架空の項目に保存しない。必要ならFlexを選ぶ。
- 1枚のcarouselはLINEのbuttonsへ変換されるが、LAMPの設定項目は最大3ボタンのまま。画像タップ用defaultActionはこの変換時に出力されないので、操作はボタンで用意する。
- 種別変更やカード削除では旧カード・旧アクションの値を整理する。作りかけのカードも有効化チェックの対象になる。カードの番号は1から順に詰める。

## 差し込み・URL・Flex

- `{!Name}` / `{!igns__SomeField__c}` は友だち自身の項目をdescribeで確認して使う。関連先パスをそのまま書いても現行の項目取得では解決されない。必要な値は友だち上の既存数式項目等を確認する。
- `{!insert_1}` 以降はCSV／レポートの2列目以降に対応する。通常のBot返信で自動的にその値が用意されるわけではない。配信・自動応答で共用する場合は変数の供給元を揃える。
- URL項目の保存可能長、HTTPS・公開アクセス、画像形式・容量は `lamp-media-upload` と対象orgのdescribeで確認する。メディアを保存しただけでLINEから取得できるとは判断しない。
- Flexはメッセージオブジェクト全体を保存し、`contents` だけや配列を渡さない。ビジュアル編集用 `FlexEditorData__c` とJSONを混同しない。LAMP生成項目を持たないLINEの機能が必要なら、Flexで表現可能かを確認する。
- Flex内のテンプレート／Agentforce呼出は [actions.md](actions.md) の形式に従う。外側の `ActionType{n}` はFlex内部を変更しない。

## 保存後の確認

1. 対象orgの選択肢・項目長、必須値、存在する接続先を確認する。
2. 全メッセージの `IsValid__c` / `ValidationErrors__c` を取得し、無効なものを残さない。意図した有効メッセージが1〜5件かを数える。
3. 上表のうちサーバーが検証しきれない長さ、画像・タイトルの統一、Flex内部、返信ボタンを確認する。プレビューと生成済みJSONは補助情報として使い、非FlexのJsonキャッシュを修正して直さない。
4. 承認されたテスト宛先で、差し込み後の文面、画像、各アクション、呼出先、項目更新を確認する。保存成功・ジョブ完了・LINE到着は区別する。

原因不明のまま保存・送信を繰り返さない。欠落項目を補っても解消しなければ、パッケージ版・権限・生成結果と該当するLINE仕様を確認し、未対応の組合せを使えると説明しない。
