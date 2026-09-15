---
name: lamp-setup
description: LAMP/BRAINの初期設定を自動実行する。パッケージインストール後の設定アシスタント（権限セットグループ作成・権限割当・サーバー認証・パス有効化）をSalesforce CLIとLAMPの設定アクションで進め、LAMPでは続けて最初のLINE公式アカウント接続（lamp-social-account-setup）まで通す。「LAMPをセットアップして」「LAMPの初期設定」「BRAINの初期設定」などで使用。公式アカウントの追加だけなら lamp-social-account-setup を使う。
---

# LAMP 初期セットアップ

LAMP/BRAINパッケージ（バージョン1.153以降）をインストールしたSalesforce組織の初期設定を自動で進める。
ユーザーにしかできない操作（ブラウザでの認証承認、LINE Developersコンソールの設定、スマホでのQR読み取り）だけを明確に依頼し、それ以外はすべてこのスキルが実行する。

流れは設定アシスタントと同じ: Step 1〜4 がSalesforce側の設定（BRAINだけを使う組織はここまで）、Step 5 が最初のLINE公式アカウント接続。**運用中の組織に公式アカウントを追加するだけなら、このスキルではなく `lamp-social-account-setup` を使う**（Step 1〜4 は不要）。

## 前提条件

- Salesforce CLI（`sf`）がインストールされ、対象組織に接続済みであること（`sf org list` で確認。未接続なら `sf org login web -a <別名>` を案内）
- 対象組織にLAMPパッケージ（namespace `igns`）1.153以降がインストール済みであること
- 実行ユーザーがシステム管理者であること

以降のコマンドの `<org>` は対象組織の別名に置き換える。**必ず最初に対象組織をユーザーに確認する**（顧客の本番組織を扱うため、組織の取り違えは重大事故になる）。

## Step 1: 初期セットアップの実行

パッケージのインストールでは組織のメタデータは変更されない（バージョン 1.157 以降）。権限セットグループ 6 件・ローカル権限セット・スケジュールジョブ 3 件（日次 2 件・配信終了処理の毎時 1 件）は、次のアクションで管理者の権限で作成する（冪等・何度実行しても安全。既に揃っている組織では何も作らず `executed: false` を返す）:

```bash
sf api request rest "/services/data/v67.0/actions/custom/apex/igns__LampAutoSetupAction" --method POST -b '{"inputs":[{}]}' -o <org>
```

実行後に結果を確認する:

```bash
sf data query -q "SELECT DeveloperName, Status FROM PermissionSetGroup WHERE DeveloperName LIKE 'LAMP_%' OR DeveloperName LIKE 'BRAIN_%'" -o <org>
sf data query -q "SELECT CronJobDetail.Name FROM CronTrigger WHERE CronJobDetail.Name LIKE 'LAMP - %'" -o <org>
```

- 権限セットグループ6件（LAMP_SystemAdministrator_Group / LAMP_User_Group / LAMP_MarketingAdministrator_Group / LAMP_MarketingUser_Group / BRAIN_Administrator_Group / BRAIN_User_Group）とスケジュールジョブ3件（`LAMP - ReplyHistoryScheduler Daily Job` / `LAMP - AggregationUpdateBatch Daily Job` / `LAMP - Broadcast End Sweeper Hourly Job`）が揃っていれば完了。1.153〜1.156 では毎時ジョブが無く2件で正常
- `Status` が `Updated` でないグループは再計算中。数分待って再確認する
- 1.153〜1.156 でインストールした組織では一部がインストール時に自動作成されているが、同じアクションを実行して問題ない（不足分だけ作られる）

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
sf api request rest "/services/data/v67.0/actions/custom/apex/igns__LampPathAssistantAction" --method POST -b '{"inputs":[{}]}' -o <org>
```

`status` が `enabled` / `disabled` なら認証済み → Step 4へ。`unauthenticated` なら以下を実行:

1. **契約IDとアクセスキーを持っているかユーザーに確認する**。持っていれば両方入力してもらう（片方だけは不可）。持っていなければ空のままトライアルとして開始する
2. 認証を開始する:

```bash
# トライアルの場合（契約なし）
sf api request rest "/services/data/v67.0/actions/custom/apex/igns__LampStartServerAuthAction" --method POST -b '{"inputs":[{}]}' -o <org>
# 契約がある場合
sf api request rest "/services/data/v67.0/actions/custom/apex/igns__LampStartServerAuthAction" --method POST -b '{"inputs":[{"contractId":"<契約ID>","accessKey":"<アクセスキー>"}]}' -o <org>
```

3. 結果の `prepared` が `true` の場合は資格情報の初期化だけが行われた状態。**同じコマンドをもう一度実行**すると `authUrl` が返る
4. `authUrl` をユーザーに提示し、**ブラウザで開いて認証を承認してもらう**（ここだけは人の操作が必要）。承認が完了するとAPIキーは自動で組織に保存される
5. 完了を確認する: 手順冒頭の状態確認を10秒間隔で繰り返し、`status` が `unauthenticated` 以外になったら完了（最大5分。超えたらユーザーのブラウザ側でエラーが出ていないか確認する）

## Step 4: パスの有効化

```bash
sf api request rest "/services/data/v67.0/actions/custom/apex/igns__LampPathAssistantAction" --method POST -b '{"inputs":[{"enable":true}]}' -o <org>
```

`status: enabled` になれば完了。

## Step 5: 最初のLINE公式アカウントの接続（LAMPのみ）

BRAINだけを利用する組織はここで**セットアップ完了**。LAMPを使う組織は、続けて公式アカウントを接続する。

手順は `lamp-social-account-setup` スキル（[SKILL.md](../lamp-social-account-setup/SKILL.md)）の Step 0〜5 をそのまま実行する。初回接続でも追加接続でも同じ手順で、Messaging APIチャネルの接続 → LINEログインチャネルからのLIFF自動作成と公式アカウントレコード作成 → LINEコンソールでの仕上げ（ユーザー操作）→ 連携項目（任意）→ 疎通確認、の順に進む。Step 0 の認証状態確認は、Step 3〜4 を終えた直後なら結果だけ確認して進んでよい。

公式アカウントレコードが作成されると、設定アシスタントの「公式アカウントの設定」は次に設定タブを開いたときに自動で完了扱いになる。疎通確認まで終わったら**セットアップ完了**。

## トラブルシューティング

- アクション呼び出しが404（`The requested resource does not exist`）→ パッケージが1.153未満。アップグレードが必要
- Step 3の認証URLが `no_contract` エラーページに飛ぶ → 契約IDまたはアクセスキーが誤り。ユーザーに再確認
- 公式アカウント接続（Step 5）の問題 → `lamp-social-account-setup` のトラブルシューティングを参照
