---
name: lamp-social-account-setup
description: LAMPにLINE公式アカウントを接続する（初回・2つ目以降の追加どちらも）。Messaging APIチャネルの接続、LINEログインチャネルからのLIFF自動作成、公式アカウントレコード作成、連携項目、疎通確認までをLAMPの設定アクションで進め、接続済みアカウントの一覧確認・再認証・解除と、公式アカウントの設定（レコード推定・リンク計測・Webhook転送）の確認・変更も行う。「公式アカウントを接続して」「公式アカウントを追加して」「2つ目のLINE公式アカウントをつなげて」「別の公式アカウントも使いたい」「メッセージのレコード推定をオンにして」「リンク計測を止めたい」「計測しないドメインを追加して」「Webhook転送を設定して」「転送先URLを変えて」などで使用。
---

# LINE公式アカウントの接続（追加）

LAMP（バージョン1.153以降）を導入済みのSalesforce組織に、LINE公式アカウントを接続する。1つの組織には複数の公式アカウントを接続でき、このスキルは**初回の接続にも、運用中の組織への追加にも**同じ手順で使う。初回セットアップの一部として `lamp-setup` から呼ばれる場合は、Step 0 の確認を済ませてから Step 1 に進む。

ユーザーにしかできない操作（LINE Developersコンソールの設定、LINE Official Account Managerの応答設定、スマホでのQR読み取り）だけを明確に依頼し、それ以外はすべてこのスキルが実行する。

## 前提条件

- Salesforce CLI（`sf`）がインストールされ、対象組織に接続済みであること（`sf org list` で確認。未接続なら `sf org login web -a <別名>` を案内）
- 対象組織にLAMPパッケージ（namespace `igns`）1.153以降がインストール済みで、**サーバーとの認証が完了していること**（Step 0 で確認する。未完了なら `lamp-setup` の Step 1〜4 を先に実行する）
- 実行ユーザーがシステム管理者であること
- LINE側で用意するもの:
  - 接続する **LINE公式アカウント**（未開設なら [公式アカウントの開設](https://help.igness.ai/lamp/getting-started/step-2-1-open-line-account) を案内する）
  - その公式アカウントに紐づく **Messaging APIチャネル**（LINE Developersコンソール → プロバイダー → 対象チャネル → チャネル基本設定）
  - **LINEログインチャネル**（同じプロバイダー内に、公式アカウントごとに1つ。Step 2 で作成を依頼する）

以降のコマンドの `<org>` は対象組織の別名に置き換える。**必ず最初に対象組織をユーザーに確認する**（顧客の本番組織を扱うため、組織の取り違えは重大事故になる）。

## 認証情報の扱い

チャネルシークレットはリクエストボディをファイルに書いて `-b @ファイル` で渡し、実行後に削除する（コマンド履歴に残さない）。ユーザーが会話に貼りたくない場合は、ファイルの作成だけをユーザーに依頼し、内容は聞かない。

## Step 0: 現状確認

1. サーバー認証の状態を確認する:

```bash
sf api request rest "/services/data/v67.0/actions/custom/apex/igns__LampPathAssistantAction" --method POST -b '{"inputs":[{}]}' -o <org>
```

`status` が `enabled` / `disabled` なら認証済み。`unauthenticated` なら **`lamp-setup` の Step 3〜4 を先に完了**してから戻る。404（`The requested resource does not exist`）ならパッケージが1.153未満で、アップグレードが必要。

2. 接続済みの公式アカウントを取得し、ユーザーに提示する:

```bash
sf data query -q "SELECT Id, Name, igns__LampId__c, igns__LiffId__c, igns__LeadField__c, igns__ContactField__c, igns__DefaultRichMenu__c, CreatedDate FROM igns__SocialAccount__c ORDER BY CreatedDate" -o <org>
```

- 接続したい公式アカウントが既に一覧にある場合は、追加ではなく既存レコードを案内して終了する（迷う場合は Step 1 の `CHANNEL_ALREADY_CONNECTED` で確定できる）
- 0件なら初回接続、1件以上なら追加接続。手順は同じだが、Step 2 と Step 4 の注意点が追加接続で効いてくる

3. ユーザーに **Messaging APIチャネルのチャネルID（数字）とチャネルシークレット（32桁の英数字）** を確認する。公式アカウント名は接続時にLINE側から自動取得されるため**ユーザーには聞かない**。

## Step 1: チャネル接続の開始

```bash
cat > /tmp/lamp-channel.json <<'JSON'
{"inputs":[{"channelId":"<チャネルID>","channelSecret":"<チャネルシークレット>"}]}
JSON
sf api request rest "/services/data/v67.0/actions/custom/apex/igns__LampStartChannelConnectionAction" --method POST -b @/tmp/lamp-channel.json -o <org>
rm -f /tmp/lamp-channel.json
```

結果の見方:

| 結果 | 対応 |
|---|---|
| `success: true` | `lampId` と `botDisplayName`（公式アカウントの表示名）、`liffEndpointUrl` を控える。トークン発行・LampID採番は完了。Webhook URLの登録・検証結果は以下のフラグで確認する |
| `webhookSet: false` | Webhook URLの自動登録に失敗。Step 3 で `webhookUrl` の手動登録を依頼する（接続自体は続行できる） |
| `webhookSet: true` かつ `webhookVerified: false` | URLは登録済みだが検証に失敗。Step 3 で登録先URLを照合し、LINE Developersの「検証」で確認する。URL未登録とは扱わない |
| `errorCode: CHANNEL_ALREADY_CONNECTED` | この組織で接続済み。`existingRecordId` のレコードを案内して終了 |
| `errorCode: CHANNEL_IN_USE` | このチャネルは別の組織に接続済み。**この組織に切り替えてよいかユーザーに確認し**、承諾されたら入力に `"confirmTakeover":true` を追加して再実行する。旧組織の接続は切れ、旧組織のレコードは動作しなくなる（自動削除はされない） |
| `LINEアカウントの作成上限に達しました（n/m）` | 契約の公式アカウント数の上限。追加するには契約の見直し（Igness へ連絡）が必要。既存アカウントの解除で枠を空ける場合は「既存アカウントの確認・変更」を参照 |
| `invalid client_id` / 400 相当 | チャネルIDまたはシークレットの入力ミス。Messaging APIチャネルの値か（LINEログインチャネルの値ではないか）を確認する |

Step 1 が成功してから Step 2 が完了するまでの間、このLampIDは仮登録（pending）で、契約の数量には数えられない。2日以内に Step 2 を完了しないと自動で消えるので、その場合は Step 1 からやり直す（同じチャネルなら同じLampIDで再開される）。

## Step 2: LINEログインチャネルとLIFFの設定

友だち登録URL（流入経路）に使うLIFFアプリを、LINEログインチャネルの配下に自動作成する。ユーザーに **LINEログインチャネルのチャネルIDとチャネルシークレット** を確認する。

**追加接続で最も間違えやすい点**: LINEログインチャネルは「リンクされたLINE公式アカウント」を1つしか持てないため、**既に接続済みの公式アカウントのログインチャネルは流用できない**。公式アカウントごとに、Messaging APIチャネルと**同じプロバイダー内**にLINEログインチャネルを新規作成してもらう:

1. LINE Developersコンソールで同じプロバイダーを開き、「新規チャネル作成」→「LINEログイン」
2. チャネル名は公式アカウント名と同じでよい。アプリタイプは「ウェブアプリ」
3. 作成したチャネルの「チャネル基本設定」からチャネルIDとチャネルシークレットを控える（Messaging APIチャネルとは別のIDになる）

```bash
cat > /tmp/lamp-login.json <<'JSON'
{"inputs":[{"lampId":"<Step 1のlampId>","name":"<Step 1のbotDisplayName>","loginChannelId":"<ログインチャネルID>","loginChannelSecret":"<ログインチャネルシークレット>"}]}
JSON
sf api request rest "/services/data/v67.0/actions/custom/apex/igns__LampCompleteChannelConnectionAction" --method POST -b @/tmp/lamp-login.json -o <org>
rm -f /tmp/lamp-login.json
```

- `success: true`: LIFFアプリの自動作成（`liffCreated: true`、`liffId`）と `公式アカウント（igns__SocialAccount__c）` レコードの作成まで完了。`recordId` を控える
- `errorCode: LIFF_SETUP_FAILED`: ログインチャネルの値の誤り、またはLINE側の失敗。値を再確認して再実行する。それでも失敗する場合は手動フォールバック: ユーザーにLINE Developersのログインチャネル →「LIFF」タブでLIFFアプリを作成してもらい（エンドポイントURL = Step 1 の `liffEndpointUrl`、サイズ Full、Scope `openid` と `profile`、友だち追加オプション On (Aggressive)）、`loginChannelId` / `loginChannelSecret` の代わりに `"liffId":"<LIFF ID>"` を渡して再実行する

## Step 3: LINEコンソールでの仕上げ（ユーザー操作が必要）

以下はLINE側の画面で確認・設定する必要があるため、ユーザーに依頼する。**完了の報告を待ってから次へ進む**。すでに設定済みの項目は、現在の状態を確認すればよい。

1. **Webhookの利用と再送**（LINE Developers → Step 1 の **Messaging APIチャネル** →「Messaging API設定」→「Webhook設定」）
   - Step 1 で `webhookSet: false` だった場合は、先に「Webhook URL」に Step 1 の `webhookUrl` を登録して「検証」が成功することを確認してもらう。`webhookVerified: false` の場合も、登録先URLの照合と検証を依頼する
   - **「Webhookの利用」をON**にする。OFFのままだと、URLが正しく登録されていてもLAMPにメッセージが届かない
   - **「Webhookの再送」もON**にする。確認画面が表示されたら内容を確認して有効にする。一時的な通信エラーなどで受信に失敗した場合にLINEが再送する設定で、OFFでも通常の初回配信は行われる
   - 両方のスイッチがON（緑色）であることを確認してもらう。すでにONなら切り替えない
   - `success`・`webhookSet`・`webhookVerified` がすべて `true` でも、この2つがONである証拠にはならない。URL登録・検証の成否と、利用・再送の状態を分けて確認する
   - スクリーンショット付きの手順: [Step.2-4 LINEコンソールでの仕上げ](https://help.igness.ai/lamp/getting-started/step-2-4-finish-line-console)
2. **LINEログインチャネルの公開設定**（LINE Developers → Step 2 のログインチャネル → チャネル基本設定）
   - 「友だち追加オプション」の「リンクされたLINE公式アカウント」で、接続した公式アカウントを選択して「更新」（忘れると友だち登録URLから友だち追加されない）
   - チャネル上部の「開発中」を「公開」に変更（元に戻せない旨を添える）
3. **応答設定**（[LINE Official Account Manager](https://manager.line.biz) → 対象アカウント → 設定 → 応答設定）
   - 「応答メッセージ」をOFF（LAMPの自動応答と二重になるため）
   - 「あいさつメッセージ」も、LAMPで送る場合はOFF

**APIでできる範囲:** 公開Messaging APIの[Webhook URL設定](https://developers.line.biz/ja/reference/messaging-api/nojs/#set-webhook-endpoint-url)で変更できるのはURLのみ。[Webhook設定の取得](https://developers.line.biz/ja/reference/messaging-api/nojs/#get-webhook-endpoint-information)の `active` で「Webhookの利用」の状態は取得できるが、利用・再送をON/OFFにする公開APIは提供されていない。再送の状態はこの取得APIでは分からない。[LINE公式の再送設定手順](https://developers.line.biz/ja/docs/messaging-api/receiving-messages/#enable-webhook-redelivery)に従って画面で確認する。

## Step 4: リード・取引先責任者との連携（任意）

リード/取引先責任者と友だちを紐付ける場合のみ。先に [既存の友だち参照項目を確認](../lamp-setup/references/social-friend-fields.md) する。連携項目は**公式アカウントごとに別の項目**（通常 `SocialFriend_<LampId>__c`）になるため、追加接続では既存アカウントの項目を流用せず、新しいLampID用に作成する。

```bash
sf api request rest "/services/data/v67.0/actions/custom/apex/igns__LampSetupRelationshipFieldsAction" --method POST \
  -b '{"inputs":[{"socialAccountId":"<Step 2のrecordId>"}]}' -o <org>
```

返った `success`、`leadFieldApiName`、`contactFieldApiName` と、公式アカウントの `igns__LeadField__c` / `igns__ContactField__c` を照合し、describeで実在・参照先を確認する。片方が未作成なら両方成功と報告しない。Lead/Contactが利用できない組織では利用可能な側だけが作られる。既存レコードへの値の同期は項目作成とは別の作業として扱う。

## Step 5: 疎通確認

```bash
# 疎通確認用の流入経路（既にあれば再利用）
sf data query -q "SELECT Id, igns__URL__c FROM igns__Source__c WHERE Name = '疎通確認' AND igns__SocialAccount__c = '<recordId>'" -o <org>
sf data create record -s igns__Source__c -v "Name='疎通確認' igns__SocialAccount__c=<recordId>" -o <org>
```

作成後に `igns__URL__c` を取得し、`https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=<URLエンコードしたigns__URL__c>` をQRコードとしてユーザーに提示する。**スマホのLINEで読み取って友だち追加してもらう**。その後、**この公式アカウントに絞って**友だちレコードを確認する（複数アカウントの組織では他アカウントの友だちが混ざるため）:

```bash
sf data query -q "SELECT Id, Name, CreatedDate FROM igns__SocialFriend__c WHERE igns__SocialAccount__c = '<recordId>' ORDER BY CreatedDate DESC LIMIT 3" -o <org>
```

友だちレコードが作成されていれば接続は正常。**接続完了**。

## 完了報告

次をまとめてユーザーに報告する:

- 公式アカウントレコード（`recordId`、名前、LampID）
- Webhook自動登録・LIFF自動作成の結果と、ユーザーに依頼した手動設定の完了状況
- 連携項目のAPI参照名（作成した場合）
- 接続直後の注意: 新しいLampIDに対するAPI呼び出し（テンプレート送信、リッチメニュー発行、クーポン発行など）は**最大10分ほど403になることがある**。時間をおいて再実行する
- 次の作業の案内: テンプレート作成は `lamp-template`、リッチメニューは `lamp-richmenu`、自動応答は `lamp-bot` / `lamp-agentforce`

## 既存アカウントの確認・変更

- **一覧・状態**: Step 0 のSOQL。Webhook URLとLIFF IDは公式アカウントレコードのページに表示される
- **チャネルシークレットを変更した／トークンが失効した／手動トークンで接続した古いアカウントを自動更新に切り替えたい**: チャネル情報の再認証を行う。Messaging APIチャネルの現在のチャネルIDとシークレットをユーザーに確認し、対象レコードを Step 0 の一覧で特定してから実行する（**1.158以降**。それより前のバージョンでは404になるので、Salesforceの公式アカウントレコード → 編集 → 「チャネル情報の再認証」の画面操作を案内する）:

```bash
cat > /tmp/lamp-reauth.json <<'JSON'
{"inputs":[{"socialAccountId":"<公式アカウントレコードID>","channelId":"<チャネルID>","channelSecret":"<チャネルシークレット>"}]}
JSON
sf api request rest "/services/data/v67.0/actions/custom/apex/igns__LampReauthChannelAction" --method POST -b @/tmp/lamp-reauth.json -o <org>
rm -f /tmp/lamp-reauth.json
```

  `success: true` でトークンが再発行され、以後は日次で自動更新される。`botDisplayName` が対象の公式アカウントと一致することを確認して報告する。失敗時の `message` に `invalid client_id` 相当が含まれれば入力ミス、別のチャネルIDを渡した場合は別アカウントに付け替わる恐れがあるため、レコードのLampIDと接続先チャネルの対応をユーザーに再確認する
- **公式アカウントの設定**: 次節「公式アカウントの設定の確認・変更」
- **接続解除**: [接続を解除したい](https://help.igness.ai/lamp/misc/disconnect-line-account) の手順（LINE Developersで「Webhookの利用」をOFF → 公式アカウントレコードを削除）。レコード削除は元に戻せないため、**ユーザーが明示的に依頼し、対象レコードを確認した場合にのみ**実行する

### 公式アカウントの設定の確認・変更

公式アカウントの設定は、保存場所によって操作が分かれる。

| 設定 | 保存場所 | 操作 |
|---|---|---|
| レコード推定（引用のない友だちのメッセージについて、どのレコードのメッセージかを会話から推定して紐づける） | LAMPのサーバー | 公式アカウントの編集画面だけ（手順2） |
| Webhook転送 | LAMPのサーバー | Webhook転送のアクション（次節） |
| リンク計測・クリックの記録・計測除外ドメイン | 公式アカウントレコードの項目 | レコード更新 |
| デフォルトのリッチメニュー | 公式アカウントレコードの項目 | `lamp-richmenu` の適用手順 |

1. Step 0 の一覧から `socialAccountId` を特定し、レコードの項目にある設定を取得する（Webhook転送は次節の取得アクション）。

```bash
sf data query -q "SELECT Id, Name, igns__TrackLinks__c, igns__RecordLinkClicks__c, igns__TrackingExcludeDomains__c FROM igns__SocialAccount__c WHERE Id = '<レコードID>'" -o <org>
```

2. **レコード推定**はアクションでは読み書きできない。ユーザーに、公式アカウントのレコードを開いて編集画面の「友だちからのメッセージのレコードを推定する」を切り替えてもらう（LAMP管理者だけが変更できる）。推定するのは1to1のトークで友だちから届いた引用のないテキストで、直近のやり取りにレコードが紐づいたメッセージがあるときだけ。推定の結果は、LAMPのチャットでメッセージのレコードのアイコン（推定したものは杖のアイコン付き）から確認・付け替えできる。

3. **リンク計測**は公式アカウントレコードの項目を更新する。

| 項目 | 意味 |
|---|---|
| `igns__TrackLinks__c` | オンにすると、LAMPから送るメッセージとリッチメニューのURLを計測用URLに置き換え、友だちごとのクリックとコンバージョンを記録する（既定オン） |
| `igns__RecordLinkClicks__c` | オンにすると、リンクをタップするたびに友だちアクティビティを1件作る。最終クリック日時とクリック回数はオフでも更新される（既定オフ） |
| `igns__TrackingExcludeDomains__c` | 計測用URLに置き換えないドメイン。1行に1つ（例: `example.co.jp`） |

  改行を含む値を渡すため、JSONファイルを作って REST で更新する。指定した項目だけが変わる。変更は次に送るメッセージから効く（送信済みのメッセージのURLは変わらない）。

```bash
cat > /tmp/lamp-tracking.json <<'JSON'
{"igns__TrackLinks__c":true,"igns__RecordLinkClicks__c":false,"igns__TrackingExcludeDomains__c":"example.co.jp\nshop.example.com"}
JSON
sf api request rest "/services/data/v67.0/sobjects/igns__SocialAccount__c/<レコードID>" --method PATCH -b @/tmp/lamp-tracking.json -o <org>
rm -f /tmp/lamp-tracking.json
```

  更新後に手順1のSOQLで値を確認して報告する。除外ドメインを消すときは `"igns__TrackingExcludeDomains__c":null`。

### Webhook転送の取得・変更・接続テスト

Webhook転送アクションは LAMP 1.160 以降のパッケージで使える。既存のLINE受信口（LINE Developersに登録するWebhook URL）と、ここで設定する**外部への転送先URL**を混同しない。

1. Step 0 の一覧から `socialAccountId` を特定し、取得する。取得結果の `url` は秘密を含み得るため、コマンド結果を会話へそのまま出さず、ホスト名・ON/OFF・枠・直近結果だけを報告する。

```bash
sf api request rest "/services/data/v67.0/actions/custom/apex/igns__LampGetWebhookAction" --method POST -b '{"inputs":[{"socialAccountId":"<レコードID>"}]}' -o <org>
```

2. ONにする・URLを変更する場合は、**対象組織、公式アカウント、転送先ホスト名、友だちの会話データがその宛先へ送られること**を示して明示的な了承を得る。今回の依頼ですでにその操作を具体的に了承している場合は重ねて確認しない。URLを推測・補完しない。実行には `LAMP_SystemAdministrator` が必要。
3. 転送先URLはチャネルシークレットと同じように、アクセス制限した一時ファイルにJSONを作り、`-b @ファイル` で渡す。シェル引数・コマンド履歴・報告にURLのパスやクエリを残さない。URL変更・ONにする場合は、保存前に次の接続テストを行う。テスト用ファイルは `{"inputs":[{"socialAccountId":"<レコードID>","url":"<ユーザー指定URL>"}]}`。空eventsを送信し、保存済み設定・契約枠は変更しない。

```bash
sf api request rest "/services/data/v67.0/actions/custom/apex/igns__LampTestWebhookAction" --method POST -b @<テスト用JSONファイル> -o <org>
```

4. テストの `success` がtrueの場合だけ同じURLを保存する。OFFのみ・OFF時のURL削除ではテスト不要。保存用ファイルの構造: `{"inputs":[{"socialAccountId":"<レコードID>","enabled":true,"url":"<ユーザー指定URL>"}]}`。`enabled`・`url` の省略は現状維持、無効時の `url: ""` は保存URLの削除。実行後に一時ファイルを削除する。エラーは `errorCode` で判定し、不明な通信結果で再実行する前には取得アクションで状態を照合する。

```bash
sf api request rest "/services/data/v67.0/actions/custom/apex/igns__LampSetWebhookAction" --method POST -b @<保存用JSONファイル> -o <org>
```

5. 取得アクションで保存状態を再確認し、ホスト名・ON/OFF・枠・接続テスト結果を報告する。2xxはHTTP受信の確認であり、受信側の業務処理成功とは限らない。

| 結果 | 対応 |
|---|---|
| `WEBHOOK_OPTION_REQUIRED` / `WEBHOOK_LIMIT_REACHED` | オプション契約または枠の追加をIgnessへ相談 |
| `INVALID_WEBHOOK_URL` | HTTPS・443番ポート・公開ホストを確認。内部IP・LAMP自身のURLは使えない |
| `BUSY` | 取得で現在値を再確認してから必要な変更だけ再実行 |
| `timeout` | 転送先が1.5秒以内に応答する必要がある |
| アクションが404 | 1.160より前のパッケージ。公式アカウントの編集画面にWebhook転送セクションがあれば画面操作を案内し、なければアップグレードを案内 |

転送は署名の成否によらず原文を1回だけ送る。受信側で `x-line-signature` を検証する。自動再送はなく、LINE側の再送による重複は受信側で除外する。外部ツールが先にReplyするとLAMPがPushへ切り替わり二重返信になり得るため、返信担当は運用で決める。

## トラブルシューティング

| 症状 | 確認・対処 |
|---|---|
| アクション呼び出しが404 | パッケージが1.153未満。アップグレードが必要 |
| Step 1 で `invalid client_id` / 400 | チャネルID・シークレットの入力ミス。LINEログインチャネルの値と取り違えていないか |
| Step 1 で上限エラー | 契約の公式アカウント数上限。Igness へ増枠を相談 |
| Step 2 で `LIFF_SETUP_FAILED` | ログインチャネルの値の誤り、または既存アカウントのログインチャネルの流用。公式アカウントごとに新規作成する |
| 友だち登録URLを開いても友だち追加されない | ログインチャネルの「リンクされたLINE公式アカウント」未設定、または「開発中」のまま |
| 疎通確認で友だちレコードが増えない | 「Webhookの利用」がOFF、Webhook URLの不一致（レコードページの表示と LINE Developers を比較）、応答設定。ユーザーが別の公式アカウントを友だち追加していないか |
| 接続直後のテンプレート送信・発行が403 | 最大10分待って再実行。10分を超えて続くならサーバー認証の状態を Step 0 で確認 |
| 運用中のアカウントで送信が401になる／友だち追加が検知されなくなった | LINE側でチャネルシークレットが再発行された可能性。「既存アカウントの確認・変更」の再認証を実行する |
| 転送先に届かない | `LampGetWebhookAction` のON/OFF・`lastOutcome`を確認し、接続テストと転送先の1.5秒以内の応答を確認する |
