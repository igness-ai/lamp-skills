# Bot受付からAgentforceへつなぐ設定例

「初回の問い合わせに選択肢を返し、内容ごとのAgentforceで対応する」を一つの依頼で構成する。固有の企業名・既存顧客のId・業務項目をコピーせず、以下の役割を対象orgの設定に対応づける。

## 完成する流れ

```text
通常メッセージ受信 → Botの条件一致 → 受付カードを返信
                                       ├ 契約の相談 → callagent → 契約担当の開始案内 → 次の質問からAgentforce
                                       ├ 操作の相談 → callagent → 操作担当の開始案内 → 次の質問からAgentforce
                                       └ 固定の案内 → postback → 案内テンプレート
リッチメニュー「お問い合わせ」 → postback → 同じ受付カード
```

「対応中の案件がない」等の入口条件が必要なら、対象orgの実在する友だち項目を使う。ケース作成・担当者割当・Slack通知等はこの構成で自動的には実装されない。既存Flowを利用する場合は、起動条件と入力項目を確認し、依頼に含まれる部分だけ接続する。

## 作成順

1. 公式アカウント、条件に使う友だち項目、AgentforceのAPI参照名2つ、担当ごとの開始案内、送信元、リッチメニューの公開範囲を確定する。対象orgのdescribe・既存レコード・有効なFlowを確認する。
2. `lamp-template` で契約担当・操作担当の開始テンプレート、固定の案内テンプレートを作る。
3. `lamp-agentforce` で2つの `Reply__c` を下書き作成する。各々 `Type=Agentforce`、`Condition=CALLOUT`、その担当のAPI参照名と開始テンプレートを設定する。
4. 受付用 `Template__c` を作り、下の3枚カードを接続する。画像を付ける場合は全カードに同じ形式で設定する。
5. `lamp-bot` の手順で `Type=Bot` の入口を下書き作成し、受付テンプレートを指定する。初回受付だけなら「対応中案件の参照が空」等の実在する条件を設定。一般の受付ならキーワード条件、常時案内なら最後の `NONE` とする。テスト中は `AND` + `IsTest=true` で絞る。
6. `lamp-richmenu` で「お問い合わせ」領域を `postback`、呼出先を受付テンプレートに設定する。1領域だけ差し替えるときも他領域を保持し、発行前に全領域を検証する。
7. 条件・ID参照・有効メッセージ数・送信元・公開範囲を検証する。承認範囲で接続先Agentforceを有効化してから、Botを有効化し、メニューを発行・適用する。

作成・再利用したIdは `contractStartTemplateId`、`contractReplyId`、`intakeTemplateId` 等の役割別にローカルで保持する。途中で失敗したら保存済みのIdから再開し、同名のBotやテンプレートを丸ごと重複作成しない。個別の作成は成功しても一式が完成したとは限らない。

## 受付カードの設定例

```bash
cat > /tmp/lamp-intake-cards.json <<'EOF'
{
  "igns__Template__c": "<intakeTemplateId>",
  "igns__Type__c": "carousel",
  "igns__Sort__c": 1,
  "igns__AltText__c": "お問い合わせ内容をお選びください",
  "igns__Title1__c": "契約の相談",
  "igns__Text1__c": "契約内容についてはこちら",
  "igns__ActionType11__c": "callagent",
  "igns__ActionLabel11__c": "相談する",
  "igns__ActionReply11__c": "<contractReplyId>",
  "igns__ActionMessage11__c": "契約について相談する",
  "igns__Title2__c": "操作の相談",
  "igns__Text2__c": "使い方についてはこちら",
  "igns__ActionType21__c": "callagent",
  "igns__ActionLabel21__c": "相談する",
  "igns__ActionReply21__c": "<supportReplyId>",
  "igns__ActionMessage21__c": "操作について相談する",
  "igns__Title3__c": "ご利用案内",
  "igns__Text3__c": "窓口と受付時間をご案内します",
  "igns__ActionType31__c": "postback",
  "igns__ActionLabel31__c": "案内を見る",
  "igns__ActionTemplate31__c": "<guidanceTemplateId>"
}
EOF
sf api request rest '/services/data/v67.0/sobjects/igns__TemplateMessage__c' --method POST -b @/tmp/lamp-intake-cards.json -o <org>
```

`ActionReply11/21` は自動応答のId。AgentforceのAPI参照名を直接入れない。`ActionMessage` は表示用で、最初のAIへの質問にはならない。開始案内を返した後、ユーザーが送る次のメッセージから回答する。

## 一式の確認

| 操作・状態 | 確認する結果 |
|---|---|
| AI会話なし、Bot条件一致 | 受付カードが1回届く |
| 条件不一致 | このBotが応答せず、設定された後続ルールの動作になる |
| カード1・2を選び、次の質問を送る | 対応するAgentforceが開始・継続する |
| カード3を選ぶ | 固定の案内だけが届く |
| リッチメニューを押す | 同じ受付カードが届く。すでにAI会話中なら、このpostbackだけでは会話を終了しない |
| 別の担当のcallagentを押す | 現在会話を終了して新規会話を開始する。連打による繰り返し起動も確認する |
| 友だち項目の更新を併用 | 呼出先・共通／ボタン別の区分・実際の更新値を確認する。callagentのボタン別代入は対応すると仮定しない |

受付カードが届いた段階、Agentforceが開始した段階、次の質問へ回答した段階を分けて報告する。組織固有の案件作成まで検証していなければ、その業務が自動化できたとは説明しない。
