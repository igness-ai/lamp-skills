---
name: lamp-setup
description: LAMP/BRAINの初期設定を自動実行する。パッケージインストール後の設定アシスタント（権限割当・サーバー認証・パス有効化）とLINE公式アカウント接続を、Salesforce CLIとLAMPの設定アクションで進める。「LAMPをセットアップして」「LAMPの初期設定」「公式アカウントを接続して」などで使用。
---

# LAMP 初期セットアップ

LAMP/BRAINパッケージ（バージョン1.153以降）をインストールしたSalesforce組織の初期設定を自動で進める。
ユーザーにしかできない操作（ブラウザでの認証承認、LINE Developersコンソールの設定、スマホでのQR読み取り）だけを明確に依頼し、それ以外はすべてこのスキルが実行する。

## 前提条件

- Salesforce CLI（`sf`）がインストールされ、対象組織に接続済みであること（`sf org list` で確認。未接続なら `sf org login web -a <別名>` を案内）
- 対象組織にLAMPパッケージ（namespace `igns`）1.153以降がインストール済みであること
- 実行ユーザーがシステム管理者であること

以降のコマンドの `<org>` は対象組織の別名に置き換える。**必ず最初に対象組織をユーザーに確認する**（顧客の本番組織を扱うため、組織の取り違えは重大事故になる）。

## Step 1: インストール時自動セットアップの確認

パッケージのインストール時に、権限セットグループの作成とスケジューラーの登録は自動実行されている。まず結果を確認する:

```bash
sf data query -q "SELECT DeveloperName, Status FROM PermissionSetGroup WHERE DeveloperName LIKE 'LAMP_%' OR DeveloperName LIKE 'BRAIN_%'" -o <org>
sf data query -q "SELECT CronJobDetail.Name FROM CronTrigger WHERE CronJobDetail.Name LIKE 'LAMP - %'" -o <org>
```

- 権限セットグループ6件（LAMP_SystemAdministrator_Group / LAMP_User_Group / LAMP_MarketingAdministrator_Group / LAMP_MarketingUser_Group / BRAIN_Administrator_Group / BRAIN_User_Group）とスケジュールジョブ2件（ReplyHistoryScheduler / AggregationUpdateBatch）があればOK
- `Status` が `Updated` でないグループは再計算中。数分待って再確認する
- 欠けている場合は、以下で不足分を自動作成できる（冪等・何度実行しても安全）:

```bash
sf api request rest "/services/data/v66.0/actions/custom/apex/igns__LampAutoSetupAction" --method POST -b '{"inputs":[{}]}' -o <org>
```

実行後、最初のクエリで作成されたことを再確認する

## Step 2: ユーザーへの権限セットグループ割当

どのユーザーにどのロールを割り当てるかをユーザーに確認してから実行する。管理者には `LAMP_SystemAdministrator_Group`、一般利用者には `LAMP_User_Group` が基本。

```bash
# 割当済み確認（重複割当はエラーになるため必ず先に確認）
sf data query -q "SELECT AssigneeId, PermissionSetGroupId FROM PermissionSetAssignment WHERE PermissionSetGroup.DeveloperName = 'LAMP_User_Group'" -o <org>
# 割当（IDはそれぞれ SELECT Id FROM User / PermissionSetGroup で取得）
sf data create record -s PermissionSetAssignment -v "AssigneeId=<userId> PermissionSetGroupId=<groupId>" -o <org>
```

自動化ユーザーへの割当（設定アシスタントStep相当）:

```bash
sf data query -q "SELECT Id FROM User WHERE Username LIKE '%autoproc%'" -o <org>
sf data query -q "SELECT Id FROM PermissionSet WHERE Name = 'LAMP_AutomatedProcessUser'" -o <org>
sf data create record -s PermissionSetAssignment -v "AssigneeId=<autoprocUserId> PermissionSetId=<permsetId>" -o <org>
```

## Step 3: サーバーとの認証設定

まず現在の認証状態を確認する:

```bash
sf api request rest "/services/data/v66.0/actions/custom/apex/igns__LampPathAssistantAction" --method POST -b '{"inputs":[{}]}' -o <org>
```

`status` が `enabled` / `disabled` なら認証済み → Step 4へ。`unauthenticated` なら以下を実行:

1. **契約IDとアクセスキーを持っているかユーザーに確認する**。持っていれば両方入力してもらう（片方だけは不可）。持っていなければ空のままトライアルとして開始する
2. 認証を開始する:

```bash
# トライアルの場合（契約なし）
sf api request rest "/services/data/v66.0/actions/custom/apex/igns__LampStartServerAuthAction" --method POST -b '{"inputs":[{}]}' -o <org>
# 契約がある場合
sf api request rest "/services/data/v66.0/actions/custom/apex/igns__LampStartServerAuthAction" --method POST -b '{"inputs":[{"contractId":"<契約ID>","accessKey":"<アクセスキー>"}]}' -o <org>
```

3. 結果の `prepared` が `true` の場合は資格情報の初期化だけが行われた状態。**同じコマンドをもう一度実行**すると `authUrl` が返る
4. `authUrl` をユーザーに提示し、**ブラウザで開いて認証を承認してもらう**（ここだけは人の操作が必要）。承認が完了するとAPIキーは自動で組織に保存される
5. 完了を確認する: 手順冒頭の状態確認を10秒間隔で繰り返し、`status` が `unauthenticated` 以外になったら完了（最大5分。超えたらユーザーのブラウザ側でエラーが出ていないか確認する）

## Step 4: パスの有効化

```bash
sf api request rest "/services/data/v66.0/actions/custom/apex/igns__LampPathAssistantAction" --method POST -b '{"inputs":[{"enable":true}]}' -o <org>
```

`status: enabled` になれば完了。

## Step 5: LINE公式アカウントの接続

### 5-1. チャネル接続の開始

ユーザーに **LINE DevelopersのMessaging APIチャネルのチャネルIDとチャネルシークレット** を確認する（LINE Developers → 対象チャネル → チャネル基本設定）。アカウント名は接続時にLINE側から自動取得されるため**ユーザーには聞かない**。

```bash
sf api request rest "/services/data/v66.0/actions/custom/apex/igns__LampStartChannelConnectionAction" --method POST \
  -b '{"inputs":[{"channelId":"<チャネルID>","channelSecret":"<チャネルシークレット>"}]}' -o <org>
```

- 成功時: `lampId` と `botDisplayName`（公式アカウントの表示名）を控える。トークン発行・Webhook自動登録まで完了している
- `errorCode: CHANNEL_IN_USE`: このチャネルは別の組織に接続済み。**この組織に切り替えてよいかユーザーに確認し**、承諾されたら入力に `"confirmTakeover":true` を追加して再実行（旧組織の接続は切れる）
- `errorCode: CHANNEL_ALREADY_CONNECTED`: この組織で接続済み。`existingRecordId` のレコードを案内して終了

### 5-2. LINEログインチャネルとLIFFの設定

ユーザーに **LINEログインチャネルのチャネルIDとチャネルシークレット** を確認する（未作成の場合はLINE Developersで「LINEログイン」チャネルを新規作成してもらう）。

```bash
sf api request rest "/services/data/v66.0/actions/custom/apex/igns__LampCompleteChannelConnectionAction" --method POST \
  -b '{"inputs":[{"lampId":"<5-1で取得したlampId>","name":"<5-1のbotDisplayName>","loginChannelId":"<ログインチャネルID>","loginChannelSecret":"<ログインチャネルシークレット>"}]}' -o <org>
```

成功すると LIFFアプリの自動作成と `公式アカウント（SocialAccount）` レコードの作成まで完了する。`recordId` を控える。

### 5-3. LINEコンソールでの仕上げ（ユーザー操作が必要）

以下の2つはLINE側にAPIがないため、ユーザーに依頼する（完了の報告を待ってから次へ進む）:

1. **LINEログインチャネルの公開設定**: LINE Developers → ログインチャネル → チャネル基本設定で「リンクされたLINE公式アカウント」に対象の公式アカウントを設定し、チャネルを「開発中」から「公開」に変更
2. **応答設定**: [LINE Official Account Manager](https://manager.line.biz) → 設定 → 応答設定で「応答メッセージ」をオフ（あいさつメッセージもLAMPで送る場合はオフ）

### 5-4. リード・取引先責任者との連携（任意）

リード/取引先責任者と友だちを紐付ける場合のみ:

```bash
sf api request rest "/services/data/v66.0/actions/custom/apex/igns__LampSetupRelationshipFieldsAction" --method POST \
  -b '{"inputs":[{"socialAccountId":"<5-2で取得したrecordId>"}]}' -o <org>
```

### 5-5. 疎通確認

```bash
# 疎通確認用の流入経路を作成（既にあれば再利用）
sf data query -q "SELECT Id, igns__URL__c FROM igns__Source__c WHERE Name = '疎通確認' AND igns__SocialAccount__c = '<recordId>'" -o <org>
sf data create record -s igns__Source__c -v "Name='疎通確認' igns__SocialAccount__c=<recordId>" -o <org>
```

作成後に `igns__URL__c` を取得し、`https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=<URLエンコードしたigns__URL__c>` をQRコードとしてユーザーに提示。**スマホのLINEで読み取って友だち追加してもらう**。その後:

```bash
sf data query -q "SELECT Id, Name, LastModifiedDate FROM igns__SocialFriend__c ORDER BY LastModifiedDate DESC LIMIT 3" -o <org>
```

友だちレコードが作成されていれば、SalesforceとLINEの連携は正常に動作している。**セットアップ完了**。

## トラブルシューティング

- アクション呼び出しが404（`The requested resource does not exist`）→ パッケージが1.153未満。アップグレードが必要
- Step 3の認証URLが `no_contract` エラーページに飛ぶ → 契約IDまたはアクセスキーが誤り。ユーザーに再確認
- Step 5-1で `400` / `invalid client_id` 相当のメッセージ → チャネルID/シークレットの入力ミス
- 疎通確認で友だちレコードが増えない → 5-3の応答設定・Webhook設定を再確認。公式アカウント（SocialAccount）レコードのページにWebhook URLが表示されるので、LINE DevelopersのMessaging API設定のWebhook URLと一致しているか確認する
