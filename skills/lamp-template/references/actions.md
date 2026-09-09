# アクションの接続と項目代入

固定案内・選択肢・Agentforce起動をつなぐときに読む。受付一式は `lamp-bot` の [設定例](../../lamp-bot/references/intake-routing.md) を使う。

## 保存先と添字

以下の `ActionType`、`ActionTemplate`、`ActionReply`、`ActionLabel` 等には `igns__` と `__c` を付ける。

| 押す場所 | 保存先 | 添字 | 選べる種類 |
|---|---|---|---|
| テンプレート末尾の返信ボタン | `igns__Template__c` | 1〜13 | uri / message / postback / callagent / camera / cameraRoll / location |
| 設問2択 | `igns__TemplateMessage__c` | 11 / 12 | uri / message / postback / callagent |
| カードnのボタンm | 同上 | nm（n=1〜9、m=1〜3） | 同上 |
| カードnの画像・タイトル・本文の領域 | 同上 | n | 同上。ただし現行のApexは1枚カードをbuttonsに変換するとき、この領域のアクションを出力しない。1枚の場合は明示的なボタンを使う |
| 画像のみカードn | 同上 | n（1〜9） | 同上。項目代入は下記の制限を確認 |
| リンク付き画像の領域n | 同上 | n（選択したレイアウトの領域数） | uri / message のみ |
| リッチメニューの領域n | `igns__RichMenu__c` | n（全領域） | uri / postback / callagent / richmenuswitch |
| Flexのボタン・タップ領域 | `Json__c` 内のLINEアクション | ビルダーの生成順 | ビルダーのリンク・メッセージ・テンプレート呼出・エージェント呼出・電話。通常の `ActionType{n}` 項目は使わない |

## 種類を選ぶ

| 種類 | 必須の接続先 | 動作と注意 |
|---|---|---|
| `uri` | `ActionUrl` | URLを開く。応答や項目代入は起きない |
| `message` | `ActionMessage` | ユーザーのテキスト受信として処理される。AI会話中は現在のエージェントへ渡る。Botのキーワード起動にも使える |
| `postback` | `ActionTemplate` = 呼出先テンプレートId | そのテンプレートを返信する。自動応答のIdを入れない。現在のAI会話はこの操作だけでは終了しない |
| `callagent` | `ActionReply` = 自動応答Id | 有効な自動応答を起動する。本手順では `Type=Agentforce` / `Condition=CALLOUT` を接続。既存会話があれば終了し、新規会話を作る |
| `richmenuswitch` | `ActionRichMenu` = 同じ公式アカウントの発行済みリッチメニューId | タブ切替。返信テンプレート・AI会話の起動とは別 |
| camera / cameraRoll / location | 接続先不要、ラベル必須 | 返信ボタンから撮影・写真選択・位置情報送信を開く |

`callagent` の接続先にAgentforce API参照名やセッションIdを入れない。自動応答レコードの `AgentforceAgentApiName__c` にAPI参照名を設定する。

`postback` / `callagent` の `ActionMessage` はタップ時の表示用で、通常テキストの受信やAgentforceの最初の質問とは異なる。開始テンプレートの後に質問を送る設計にする。

`ActionOption` はpostback系の入力動作。`openKeyboard` の場合に `ActionFillInText` を組み合わせられる。下書きが入るだけで自動送信されない。選択肢は保存先のdescribeで確認する（テンプレートの返信ボタンには `openRichMenu` がない）。種類を変更するときは不要になった旧接続先も空にする。

## Flexから呼び出す

ビジュアルエディタではアクション「テンプレート呼出」「AIエージェント呼出」で既存レコードを選ぶ。`FlexEditorData__c` がある既存デザインはビルダーで編集して保存し、デザインと `Json__c` の食い違いを作らない。

ヘッドレスでFlex JSONを直接作る場合、LINE側の種別はどちらも `postback`。`data` はLAMPの形式とする:

```text
recordId=<送信元TemplateMessageId>&actionId=<このメッセージ内の一意な番号>&type=template&templateId=<呼出先TemplateId>
recordId=<送信元TemplateMessageId>&actionId=<このメッセージ内の一意な番号>&type=template&replyId=<Agentforce自動応答Id>
```

表示文を付けるなら `displayText` と、dataの `message=<UTF-8でURLエンコードした表示文>` を揃える。実在するメッセージIdを得てから最終JSONをPATCHする。`type:"callagent"` というLINEアクションを作らない。部品の `action` に設定し、通常の `ActionType{n}` を書いてもFlex内のボタンには反映されない。

## ボタン別の項目代入

`TemplateFieldSetting__c.Template__c` は **呼び出し先（送られる）テンプレート**。`SourcedRecordId__c` / `SourcedActionId__c` は **押した側**を指す。この向きを取り違えない。

例: 受付カード2枚目のボタン1から、案内テンプレートを送り、友だちの既存項目へ分類を保存する:

```json
{
  "igns__Template__c": "<呼出先の案内TemplateId>",
  "Name": "<describeで確認した友だち項目API名>",
  "igns__Condition__c": "EQ",
  "igns__Value__c": "操作相談",
  "igns__SourcedRecordId__c": "<押したカードのTemplateMessageId>",
  "igns__SourcedActionId__c": "21"
}
```

これを `POST /services/data/v67.0/sobjects/igns__TemplateFieldSetting__c` で保存する。押したボタンは `postback` + 上記の呼出先TemplateIdに設定する。

- 返信ボタンのSourcedRecordIdは押した側のTemplateId、リッチメニューならRichMenuId。番号はそのボタン／領域の添字。
- Sourcedの2項目を両方空にすると共通設定。呼出先テンプレートの処理で、共通設定を先に適用し、その後に一致するボタン別設定を上書き適用する。
- 同じ項目に複数の共通設定、または同じボタンに同一項目の設定を重複作成しない。中間の順序を利用した計算はしない。
- `EQ` は項目型へ変換して置換、`BLANK` はnullへクリア。数式項目や編集不可項目は指定しない。`ADD` は文字列のカンマ連結であり、数値加算ではない。現行返信処理では既存値を事前取得しないため、既存の保存値への追記が保証されるとは案内しない。
- **callagentは呼出元のrecordId/actionIdを開始テンプレート処理へ引き継がない。ボタン別代入を前提にしない。** 開始テンプレートの共通設定は使えるが、回答生成より前の同期更新としては扱わない。分類が必要なら担当ごとに開始テンプレートを分けるか、先にpostbackで分類を保存し、次の操作で起動する。
- **画像のみカードは、送信時のApexが全カードのactionIdを `1` にする。** カード2以降に別々の番号で代入設定を作る構成は使わない。通常のカードにするか、異なる呼出先テンプレートと共通設定を組み合わせる。
- 項目代入と配送成功は別に検証する。現行返信ジョブでは配送APIが非200でも項目更新へ進み得るため、フラグが立ったことはLINE到着の証拠にはならない。

## 接続後の検証

テンプレートの各メッセージ、返信ボタン、リッチメニューを別々に確認する。メッセージの `IsValid=true` は返信ボタンの正しさや接続先の有効化を保証しない。返信ボタンは必須値不足で省略される場合がある。

呼出先の有効なメッセージ数、Agentforceの有効化・同じ公式アカウント・開始テンプレート、全ボタンの遷移先、項目代入を確認する。公開済みリッチメニューの変更は再発行が必要。既存メッセージのボタンを押し直した場合や連打でも同じ業務処理を繰り返してよいかを確認する。
