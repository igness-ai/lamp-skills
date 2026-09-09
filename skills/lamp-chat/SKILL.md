---
name: lamp-chat
description: Igness LAMP のチャットコンポーネント（LAMP Chat Component / LampMessageComponent）の配置・高さ・QuickText・送信元を設定し、Prompt Builderで作成した返信ドラフト用プロンプトテンプレートを接続する。「チャットの高さを変えたい」「QuickTextのフォルダを使いたい」「返信ドラフトをコンポーネントに入れたい」「担当者名義で送りたい」などで使う。
---

# LAMP チャットコンポーネントの設定

Salesforce のレコードページに置く **LAMP Chat Component** の設定を扱う。会話で「LampMessageComponent」と呼ばれるものは、現行のコンポーネント名 **`lampFriendChatComponent`** に対応する。
**Prompt Builder で作った返信ドラフトは、このコンポーネントの「文面提案エージェントID／テンプレート」に API 参照名を入れて使う。** 自動応答の種別 `Agentforce` の設定は `lamp-agentforce` を使う。

## 対象と変更箇所を確認する

- 本スキルは LAMP 基本パッケージ **1.157 以降**を対象にする。対象 org、アプリ、オブジェクト、実際に割り当てられているLightningレコードページを特定する。
- 友だち・公式アカウントの接続は `lamp-setup` で完了済みとする。ページ編集は管理者、動作確認は実際の利用者の権限で行う。
- ページを依頼の範囲で変更し、既存の他コンポーネントやアプリ・プロファイル・レコードタイプ別のページ割当を保持する。同じページに複数のチャットがある場合は、変更するインスタンスを特定する。
- 返信ドラフトの生成・採用だけで LINE には送られない。動作確認では入力欄まで確認できる。実送信は依頼で承認された宛先・内容で行う。

## 1. 設定する場所と各プロパティ

対象レコードを開き、歯車の **「編集ページ」** から Lightning App Builder に入る。既存の **LAMP Chat Component** を選ぶ（未配置なら配置）と、右側のプロパティで設定できる。保存後は、そのページが対象アプリ・ユーザーに割り当てられているか確認する。有効化・割当変更が必要な場合も対象範囲を広げない。

| 画面の設定名 | API 名 | 設定する値 |
|---|---|---|
| Component Height | `height` | **単位なしの数値文字列**。例 `600`。現行コードは末尾に `px` を付けるため `600px` や `50%` を入れない。未設定時は履歴表示部400px。ヘッダー・入力欄は別に高さを持つ |
| Social Friend Record ID Field | `socialFriendRecordIdField` | 友だちページなら `Id`。Lead / Contact / その他のページなら、そのレコードから友だちを参照する項目のAPI名（org固有の実在する参照項目） |
| クイックテキストのチャネル名 | `quickTextChannel` | QuickTextの **Channelの値**。フォルダ名ではない。空ならチャネルで絞り込まない |
| 表示名とアイコンのカスタマイズを許可 | `allowSenderCustomize` | 担当者・部署などの送信元を選べるようにするとき `true`。既定 `false`。候補となる送信元レコードも必要 |
| 文面提案エージェントID／テンプレート | `suggestAgentId` | Prompt Builderで作成・有効化した返信ドラフト用テンプレートの **API参照名**。例 `My_LINE_Reply_Draft`。空なら文面提案機能は非表示 |

`height` の設定画面の説明には単位付きの例があるが、現行の描画処理に合わせて `600` のように指定する。
友だち参照項目は名前を推測しない。Lead / Contact なら公式アカウントの連携設定にある `LeadField__c` / `ContactField__c` と、対象オブジェクトのdescribeで確認する。項目が存在してもレコードの値が空ならチャットの相手を解決できない。

Experience Builderで配置する場合も同じプロパティを使い、追加で `recordId={!recordId}` と `objectApiName={!objectApiName}` が対象ページから渡ることを確認する。

### CLIでページ設定を変更する場合

既存ページのメタデータを取得し、該当コンポーネントの `componentInstanceProperties` だけを編集する。namespace表記・配置・identifierは取得した内容を保持する。

```bash
sf project retrieve start --metadata "FlexiPage:<対象ページAPI名>" -o <org>
```

該当インスタンス内のプロパティ例（ページ全体をこの断片で置き換えない）:

```xml
<componentInstanceProperties>
    <name>height</name>
    <value>600</value>
</componentInstanceProperties>
<componentInstanceProperties>
    <name>suggestAgentId</name>
    <value>My_LINE_Reply_Draft</value>
</componentInstanceProperties>
```

変更差分と対象ページを確認し、反映が依頼の承認範囲に含まれる場合に、取得したそのファイルだけを配備する:

```bash
sf project deploy start --source-dir <対象ページのflexipage-meta.xmlのパス> -o <org>
```

ページ保存・配備の成功と、そのページの利用者への割当は別に確認する。編集できないパッケージ管理のページは、App Builderで編集可能なコピーを作り、必要な割当だけを設定する。

## 2. Prompt Builder の返信ドラフトを接続する

### テンプレートの入力構成

Salesforce の設定 → **Prompt Builder** で返信ドラフト用の **Flex型** プロンプトテンプレートを用意する。LAMP は次の名前で値を渡すので、独自テンプレートでもAPI名・型を揃える。

| 入力API名 | 入力の型 | LAMPが渡す内容 |
|---|---|---|
| `conversationHistory` | 自由テキスト / String | 直近のLINE会話から取得したテキスト、最大20件を古い順に並べたもの |
| `draft` | 自由テキスト / String | 担当者の入力中の文面、またはブラッシュアップ対象の前回の提案。空欄を許可する |
| `instruction` | 自由テキスト / String | 「短く」「丁寧に」などの指示。空欄を許可する |
| `socialFriend` | レコード / `igns__SocialFriend__c` | 表示中の友だちレコード。必須にせず、解決できた場合に使う |

`socialFriend` の項目・関連先を参照する場合は、実行ユーザーのアクセス権も確認する。LAMPが自動で渡すのは上記4入力であり、独自の必須入力を追加しても値は自動では渡らない。

本文の例（入力名は上表と一致させる）:

```text
次の会話を踏まえ、お客さまへの返信本文だけを作成してください。
下書きがあればその意図を尊重し、修正指示を反映してください。
確認できない事実は断定せず、前置きや説明は出力しないでください。

会話履歴:
{!$Input:conversationHistory}
下書き:
{!$Input:draft}
修正指示:
{!$Input:instruction}
```

保存・プレビュー後に有効化し、**テンプレートのAPI参照名**を控える。Flexテンプレートと自由テキスト入力の作成方法は [SalesforceのPrompt Builder手順](https://developer.salesforce.com/docs/ai/automate-resume-processing/guide/aes-create-prompt-template.html) を参照できる。LAMPの入力構成は上表を使う。

標準テンプレート `igns__LAMP_Reply_Draft` は **Agentforce Extension Package** 側の同梱物。対象orgにそのテンプレートが存在することを確認してから指定する。基本パッケージだけで存在すると決めつけない。独自テンプレートを利用する場合は、そのAPI参照名を使う。

### コンポーネントへの指定と利用

1. Lightning App Builderで対象のLAMP Chat Componentを選択する。
2. **文面提案エージェントID／テンプレート**（`suggestAgentId`）に上で控えたAPI参照名を入力する。表示ラベルやテンプレートのレコードIdは使わない。
3. 保存し、実際に割り当てられたページを利用者として開き直す。
4. チャット入力欄のAI文面提案を開き、下書き・指示を入れて生成する。必要なら再生成やブラッシュアップを行う。
5. **採用**するとチャット入力欄に文面が入る。担当者が本文・宛先・送信元を確認して送信する。

生成は画面を操作している利用者の権限で行われる。Prompt Builderでの有効化、利用者のテンプレート実行権限（例 `Prompt Template User`）、友だちへの参照権限、LAMPサーバー認証を確認する。履歴取得に失敗しても「会話履歴はありません」として生成を続ける場合があるので、文章が生成できたことだけで会話履歴の取得成功を判断しない。

## 3. QuickTextのチャネルとフォルダ

LAMPの候補表示は、利用者が参照できるQuickTextのうち **`IsInsertable=true`** を対象とし、`quickTextChannel` があれば **`Channel INCLUDES ('指定値')`** で絞る。名前順で最大200件。チャネル未設定時もアクセス権の範囲は変わらない。

設定手順:

1. Salesforce の **クイックテキスト** で定型文を作成・編集し、利用したいチャネルを選ぶ。チャネルの実在する値は対象orgで確認する。
2. 定型文を用途別のフォルダに整理し、利用者・グループへ参照できるよう共有する。フォルダ共有の設定状況も確認する。手順は [SalesforceのQuickText共有](https://help.salesforce.com/s/articleView?id=quick_text_share.htm&language=en_US) を参照する。
3. LAMP Chat Componentの **クイックテキストのチャネル名** に、1で使用したチャネルの値を入れる。
4. 実際の利用者でページを開き直し、クイックテキストの選択画面から検索・挿入できるか確認する。

**フォルダ名をコンポーネントへ指定して絞る機能は現行LAMPにはない。** フォルダはSalesforce側での整理・共有、コンポーネント側はチャネルでの絞り込みを担当する。「このフォルダだけ」と依頼された場合、この違いを説明し、既存の共有範囲とチャネル設定で意図を満たせるか確認する。複数フォルダに同じチャネルの定型文があり利用者が参照できれば、どちらも候補になる。

## 4. 誰の名義で送るか（送信元）

送信チャネルは友だちに紐づくLINE公式アカウントで、**送信元（`igns__Sender__c`）はトーク上の表示名・アイコンを指定する**。担当者名、窓口名、部署名などを送信元レコードとして作る。

| 項目 | 用途 |
|---|---|
| `Name` | LINEで表示する送信元の名前 |
| `OwnerId` | この送信元を所有するSalesforceユーザー。個人用の初期選択にも使う |
| `igns__PictureUrl__c` | アイコンの公開URL。`lamp-media-upload` の `profile` 種別で設定できる |
| `igns__IsPublic__c` | 「他ユーザーの使用を許可」。チーム共通の送信元なら `true`、個人用なら `false` |
| `igns__VisibleInChatComponent__c` | 「チャットコンポーネントで表示」。チャットの候補に出すには `true` |

既存の送信元を確認してから、必要なものだけ作成する。管理者が個人用を代理作成するときは `OwnerId` を実際に使う担当者にする:

```bash
sf data query -q "SELECT Id, Name, OwnerId, igns__IsPublic__c, igns__VisibleInChatComponent__c FROM igns__Sender__c ORDER BY Name" -o <org>

cat > /tmp/lamp-sender.json <<'EOF'
{
  "Name": "サポート窓口",
  "OwnerId": "<ownerUserId>",
  "igns__IsPublic__c": true,
  "igns__VisibleInChatComponent__c": true
}
EOF
sf api request rest "/services/data/v67.0/sobjects/igns__Sender__c" --method POST -b @/tmp/lamp-sender.json -o <org>
```

アイコンは `lamp-media-upload` に `contentType=profile`、作成したレコードId、`imageUrlField=igns__PictureUrl__c`、`uuidField=igns__UUID__c` を渡して設定する。

コンポーネントの **表示名とアイコンのカスタマイズを許可** をONにすると、利用可能な送信元がある場合にチャットの **送信元の変更** が表示される。そこでチェックを入れて送信元を選ぶ。チェックを外すと送信元の上書きを行わず、公式アカウントの表示を使う。

候補・初期選択の規則:

- 候補は `VisibleInChatComponent=true` かつ「自分が所有」または「他ユーザーの使用を許可」。オブジェクトへの読み取り権限も必要。
- 自分が所有する **非公開** の送信元のうち、チャット表示がONで **最も古く作成された1件** が初期選択され、「送信元の変更」もONになる。
- そのような個人用の送信元がなければ、初期状態は公式アカウント名義。共有の窓口レコードがあるだけでは自動で選ばれない。
- `allowSenderCustomize=false` では送信元の候補を読み込まない。担当者ごとの表示にしたい場合は、プロパティと個人用レコードの両方を設定する。

この設定の適用先は個別チャット。テンプレートメッセージの送信元は `TemplateMessage__c.Sender__c`、Agentforce自動応答の送信元は `Reply__c.Sender__c` で指定する。チャットで選んだ名前が自動応答・配信にも一律で適用されるとは案内しない。

## 反映後の確認・トラブルシューティング

実際の利用者で、対象友だちの表示、高さ、QuickText候補・挿入、ドラフト生成・採用、送信元の初期選択／切替を確認する。実送信を行う場合は、承認済みのテスト相手のLINEで名前・アイコン・本文まで確認する。

| 症状 | 確認すること |
|---|---|
| 設定を変えても反映されない | 編集したページ・コンポーネントのインスタンスが、現在のアプリ・プロファイル・レコードタイプで使われているか。ページを開き直したか |
| 高さが効かない | `600px` 等を入れていないか。現行コードは `600` のような単位なしの値を使う |
| 友だち・履歴が出ない | `socialFriendRecordIdField`、対象レコードの参照値、項目・レコード権限、公式アカウントの接続を確認 |
| QuickTextが見えない | オブジェクト・フォルダの参照権限、挿入可能な状態、Channelの一致、200件の上限。フォルダ名を `quickTextChannel` に入れていないか |
| AI文面提案が出ない／生成できない | `suggestAgentId` の空欄・API参照名の誤り、テンプレートの有効化、入力名と型、利用者の実行権限を確認 |
| 標準の返信ドラフトが見つからない | Agentforce Extension Packageのテンプレートが対象orgに存在するか。独自テンプレートならそのAPI参照名を使う |
| AI提案が会話の文脈を使わない | 友だちを解決できたか、利用者のアクセス権とLAMPサーバー認証を確認。履歴なしでも生成は続く場合がある |
| 送信元の選択欄がない | `allowSenderCustomize=true` と利用可能な送信元の存在を確認。`VisibleInChatComponent`、Owner、IsPublic、権限を確認 |
| 担当者名が初期選択されない | 自分所有・非公開・チャット表示ONのレコードがあるか。複数あれば最古の1件が選ばれる |

最終報告では、変更したページ・設定値、使用するテンプレートAPI名、QuickTextのチャネル／共有範囲、送信元の選択規則、利用者としての確認結果を簡潔に伝える。未実施の画面確認・実送信は完了としない。
