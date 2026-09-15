---
name: lamp-bot
description: Igness LAMP のBot自動応答を作成し、キーワード・友だち項目での分岐、受付テンプレート、カードやリッチメニューからのAgentforce起動をまとめて設定する。「Bot応答を作って」「問い合わせの種類を選んでエージェントへつなぎたい」「受付メニューを一式設定して」などで使う。
---

# LAMP Bot応答と受付メニュー

`igns__Reply__c` の `igns__Type__c="Bot"` は、条件に一致した受信に対して固定のテンプレートを返す自動応答。AIによる回答生成やAI会話の作成はしない。Botで選択肢を提示し、選んだボタンからAgentforceへつなぐ構成も作れる。

受付全体を頼まれたら、[受付からAgentforceへつなぐ設定例](references/intake-routing.md) を読み、必要なレコードを依存順に作成・接続・検証する。個々のスキルをユーザーに順番に依頼し直してもらう必要はない。

## 1. 対象・既存設定を確認する

- LAMP基本パッケージ1.157以降を対象とする。対象org（以下 `<org>`）、公式アカウント、返す内容、開始条件、優先順を依頼内容から特定する。不明なものだけ確認する。
- `lamp-setup` によるサーバー認証・受信処理の実行ユーザーへの権限付与と、`lamp-social-account-setup` による公式アカウント接続が必要。LINE Official Account Managerの応答メッセージとの重複にも注意する。
- Salesforceの自動応答タブで設定するか、以下のRESTで保存する。組織・項目・有効な選択肢・権限は対象orgのdescribeで確認する。

```bash
sf sobject describe -s igns__Reply__c -o <org> --json > /tmp/lamp-bot-reply-describe.json
sf sobject describe -s igns__AutoKeyword__c -o <org> --json > /tmp/lamp-bot-condition-describe.json
sf sobject describe -s igns__SocialFriend__c -o <org> --json > /tmp/lamp-bot-friend-describe.json
sf data query -q "SELECT Id, Name, igns__Type__c, igns__Status__c, igns__Condition__c, igns__Sort__c, igns__Template__c FROM igns__Reply__c WHERE igns__SocialAccount__c = '<socialAccountId>' ORDER BY igns__Sort__c ASC" -o <org> --json > /tmp/lamp-bot-existing.json
```

有効な応答を同じ公式アカウント内で `Sort__c ASC` に評価し、**最初の一致だけ**を返す。BotとAgentforceで優先順位の列は共通。同順位・空値を避け、具体的な条件を先、汎用案内を後にする。既存の同用途レコードは再利用する。

友だちの項目で分岐する場合は、その項目が存在し、判定したい意味の値が入ることを確認する。`CurrentCase__c` 等の業務項目は標準装備ではない。Lead / Contactとの関連は [友だち参照項目の確認](../lamp-setup/references/social-friend-fields.md) に従う。

## 2. 開始条件を選ぶ

| `Condition__c` | Botの動作 |
|---|---|
| `AND` | すべての条件に一致するとテンプレートを返す |
| `OR` | いずれかの条件に一致するとテンプレートを返す |
| `NONE` | 条件を見ずにテンプレートを返す。通常は最後の案内として使う |
| `CALLOUT` | 通常のキーワード判定では起動しない。固定テンプレートをボタンで返す用途は `postback` + `ActionTemplate` を使う |

AI会話中の友だちは、通常受信ではその会話を継続し、Botの条件を評価しない。Botの条件に `IsAIReply=false` を追加するだけで既存の会話が停止することもない。画像・動画にも受信経路はあるが、テキストのキーワード一致を期待せず、実際に使う種別で確認する。

## 3. Botと条件を下書きで作る

返すテンプレートは `lamp-template` で先に用意する。有効なメッセージ1〜5件、送信元は各 `TemplateMessage__c.Sender__c` で指定する。Botの `Reply__c.Sender__c` を設定しても固定テンプレートの送信元にはならない。

```bash
cat > /tmp/lamp-bot-reply.json <<'EOF'
{
  "Name": "お問い合わせ受付",
  "igns__SocialAccount__c": "<socialAccountId>",
  "igns__Type__c": "Bot",
  "igns__Condition__c": "AND",
  "igns__Sort__c": 100,
  "igns__Template__c": "<intakeTemplateId>",
  "igns__Status__c": "draft"
}
EOF
sf api request rest '/services/data/v67.0/sobjects/igns__Reply__c' --method POST -b @/tmp/lamp-bot-reply.json -o <org>

cat > /tmp/lamp-bot-keyword.json <<'EOF'
{
  "igns__Reply__c": "<botReplyId>",
  "igns__ConditionType__c": "Keyword",
  "Name": "問い合わせ,相談",
  "igns__Condition__c": "EQ"
}
EOF
sf api request rest '/services/data/v67.0/sobjects/igns__AutoKeyword__c' --method POST -b @/tmp/lamp-bot-keyword.json -o <org>
```

変更は作成済みIdへPATCHする。条件は `AutoKeyword__c` に1行ずつ保存する:

| `ConditionType__c` | `Name` | `Condition__c` | `Value__c` |
|---|---|---|---|
| `Keyword` | キーワード。カンマ区切りはその1行の中で「いずれか」 | `EQ` / `CONTAINS` | 不要 |
| `FriendField` | 友だちの実在する項目API名 | `EQ` / `CONTAINS` / `BLANK` / `NOT_BLANK` | 比較文字列。チェックボックスなら `"true"` / `"false"`。空白判定は不要 |

`AND` / `OR` は条件0件では起動しない。関連先をたどる `igns__Contact__r.SomeField__c` はこの条件の対象外で、友だち自身の項目を使う。関連情報で判定したい場合は、既存の数式項目・同期項目を確認する。項目追加が必要なら別の変更として対象と更新方法を具体化する。

`Regex__c` はトリガーが生成するので直接書かない。キーワードの `.`・`+`・`(` 等は正規表現として扱われるため、記号を含む語は実際の一致まで確認する。非推奨の日本語の旧選択肢は使わない。

テスト用の友だちだけに絞るときは `AND` に次を追加する。`OR` では一般の友だちも他の条件だけで一致し、`NONE` / ボタン起動ではこの制限は効かない。

```json
{
  "igns__Reply__c": "<botReplyId>",
  "igns__ConditionType__c": "FriendField",
  "Name": "igns__IsTest__c",
  "igns__Condition__c": "EQ",
  "igns__Value__c": "true"
}
```

## 4. ボタン・リッチメニューを接続する

- 固定案内や次の選択肢を返す: `postback` + `ActionTemplate{n}` に呼出先テンプレートId。
- Agentforceを開始する: `callagent` + `ActionReply{n}` に `lamp-agentforce` で作成した自動応答Id。ボタン起動には `Condition=CALLOUT`、有効な開始テンプレートを用意する。
- キーワードとして受信させる: `message`。普通の受信なので、AI会話中なら現在のエージェントへ渡る。常に同じメニューを開きたいなら `postback` を使う。

保存先・添字・項目代入・制限は [アクションの接続と項目代入](../lamp-template/references/actions.md) を読む。リッチメニューの画像・発行・適用は `lamp-richmenu` で行う。

## 5. 有効化・確認・停止

条件・優先順・本文・公開先を確認し、依頼の承認範囲で `Status__c="valid"` にする。既に承認された一式設定なら承認を取り直さない。下書きだけの依頼なら有効化しない。

```bash
sf api request rest '/services/data/v67.0/sobjects/igns__Reply__c/<botReplyId>' --method PATCH -b '{"igns__Status__c":"valid"}' -o <org>
```

条件一致・不一致の両方、Botからの各ボタン、Agentforce開始後の次の質問まで確認する。`IsTest__c` がtrueでも実LINEへ送られる。ジョブ完了だけで着信成功とせず、対象時刻の受信・返信履歴とLINE表示を確認する。

停止は対象Botを `draft` に戻す。Bot自体はAI会話を作らないため終了する会話はない。接続先のAgentforceですでに始まった会話は別途 `lamp-agentforce` の停止手順に従う。既に送られたテンプレートのボタンや公開リッチメニューからの起動も、必要な範囲で接続先を停止する。
