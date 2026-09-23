---
name: lamp-data360-setup
description: Igness LAMP の会話（メッセージングアプリの送受信）を、お客様の Salesforce Data 360（旧 Data Cloud）へ取り込むための初期設定を行う。拡張パッケージの確認、Data Kit の展開、コネクタ権限の付与、着信の確認まで。「LAMPの会話をData 360に入れたい」「Data Cloudで友だちと会話をつなげたい」「Data 360連携を設定して」などで使う。
---

<!-- 下書き（2026-09-20）。拡張パッケージは未リリース（ベータ 0.2.0.1）。公開前に: インストールURLと、対象の基本パッケージ版を確定する。 -->

# LAMP Data 360連携の初期設定

会話は Igness のサーバーからお客様の Data 360 へ送られ、友だち・自動応答・配信は Salesforce の中で Data 360 に同期される。Data 360 の中で、会話は `lampId:userId` をキーに友だちへ、送信元のIDで自動応答・配信・ユーザーへ結ばれる。

このスキルが行うのは、お客様の org の中の設定だけ。**連携そのものの有効化（オプション契約）は Igness 側で行う**。有効化されていない契約では、設定が済んでいても会話は送られない。取り込み方式（標準＝定期／即時）と、過去の会話の送信は、契約の管理者が Igness のアカウント画面（LAMP のページ）で操作する。

## 前提の確認

- 対象 org に `sf` で接続済みであること（以下 `<org>`）。実行ユーザーは Data 360 の管理者権限（Data Cloud 管理者）を持つこと。
- Data 360 が有効であること。次が `FUNCTIONALITY_NOT_ENABLED` を返す org では設定できない。Data 360 の有効化はお客様の Salesforce 契約の範囲なので、このスキルでは行わない。

```bash
sf api request rest "/services/data/v67.0/ssot/data-streams" -o <org>
```

- LAMP 基本パッケージと、拡張パッケージ「Igness LAMP - Data 360 Extension Package」が入っていること。

```bash
sf package installed list -o <org> --json | jq -r '.result[] | select(.SubscriberPackageName | test("Igness LAMP|Standard Data Model")) | "\(.SubscriberPackageName)\t\(.SubscriberPackageVersionNumber)"'
```

「Salesforce Standard Data Model」が無い org は Data 360 のセットアップが終わっていない。拡張パッケージが無ければ、Igness から案内されたインストールURLで入れてから続ける。

- `lamp-setup` によるサーバー認証が済んでいること。多くの org は基本パッケージを Data 360 対応版へ上げるだけで足りる。接続の方式によっては、設定アシスタントの「認証」を1回やり直す必要がある（会話を Data 360 へ送るための権限が、認証し直したときに付く）。必要かどうかは Igness 側で検知できるので、Igness から案内があった場合だけやり直す。

## 1. 既に展開済みでないかを確かめる

```bash
sf api request rest "/services/data/v67.0/ssot/data-streams" -o <org> | jq -r '.dataStreams[] | "\(.name)\t\(.dataStreamStatus)"'
```

`Igness_LAMP_Timeline_…`・`igns_SocialFriend_c_Home`・`igns_Reply_c_Home`・`igns_Broadcast_c_Home` の4本が `ACTIVE` なら展開済み。手順3へ進む。一部だけある場合は、重ねて展開せず、まず状況を利用者に伝える。

## 2. Data Kit を展開する

インストール直後は定義が届いているだけで、データストリームもデータモデルも無い。次の1回で、取り込みAPIの接続「Igness_LAMP」、データストリーム4本、データモデル、リレーションが作られる（約3分）。

```bash
ORG_ID=$(sf org display -o <org> --json | jq -r '.result.id' | cut -c1-15)
cat > /tmp/lamp-data360-deploy.json <<EOF
{"components":[
 {"type":"DataStreamBundle","config":{"connectorType":"CRM","bundleName":"igns__LAMP_Friend","bundleConfig":{"orgId":"${ORG_ID}"}}},
 {"type":"DataStreamBundle","config":{"connectorType":"INGESTAPI","bundleName":"igns__LAMP_Timeline","bundleConfig":{"connectorName":"Igness_LAMP"}}}
]}
EOF
sf api request rest "/services/data/v67.0/ssot/data-kits/igns__LAMP_Data_Kit?asyncMode=true&dataspace=default" \
  --method POST --body @/tmp/lamp-data360-deploy.json -o <org>
```

- **org の ID は15桁で渡す。** 18桁のままだと `No CRM Connection exists for externalRecordId` で失敗する（接続が無いという意味ではない）。
- `connectorName` は `Igness_LAMP` のまま変えない。Igness のサーバーはこの名前を宛先にして送る。
- 応答の `jobId` で結果を確かめる。`Successful` になるまで待つ。失敗時は同じレコードにエラーの全文が入る。

```bash
sf data query -q "SELECT FIELDS(ALL) FROM DataKitDeploymentLog WHERE JobIdentifier = '<jobId>' ORDER BY CreatedDate LIMIT 20" -o <org>
```

画面で行う場合は、［設定］のデータキットの画面ではなく、**Data Cloud アプリの［データストリーム］→［新規］から、2回に分けて**作る（［設定］のデータキット詳細には展開のボタンが無い）。

1. 友だち・自動応答・配信:「Salesforce CRM」→［次へ］→ 一覧の一番下「カスタムバンドル」の `LAMP_Friend` →［次へ］→［次へ］→［リリース］（入力なし）
2. 会話:「インストール済みデータキットおよびパッケージ」→［次へ］→「Igness LAMP Data Kit」→ `LAMP_Timeline` にチェック →［次へ］→［新規コネクタ］→ **コネクタ名に `Igness_LAMP` と入力**（既定値は無い。ここを誤ると会話が届かない）→［保存］→［次へ］→［次へ］→［リリース］

画面つきの手順はヘルプの「Data 360連携を設定したい」を案内する。

## 3. コネクタの読み取り権限を確かめる

Data 360 の Salesforce CRM コネクタは、権限セット `sfdc_a360_sfcrm_data_extract` の権限でレコードを読む。**LAMP を先に入れ、後から Data 360 を有効にした org では、LAMP のオブジェクトへの読み取りが付いていない**ことがある（その場合、ストリームは成功と表示されたまま0件になる）。

```bash
sf data query -q "SELECT SobjectType, PermissionsRead, PermissionsViewAllRecords FROM ObjectPermissions WHERE Parent.Name = 'sfdc_a360_sfcrm_data_extract' AND SobjectType IN ('igns__SocialFriend__c','igns__Reply__c','igns__Broadcast__c')" -o <org>
```

3件とも `PermissionsRead` と `PermissionsViewAllRecords` が `true` であること。足りないオブジェクトがあれば、利用者に確認のうえ、権限セット「Data Cloud Salesforce Connector」（日本語の画面でも英語表記。API参照名 `sfdc_a360_sfcrm_data_extract`）に「参照」と「すべてのレコードの参照」、および取り込む項目の参照権限を付ける（［設定］→［権限セット］）。お客様の権限設定を変える操作なので、無断で行わない。

## 4. 着信を確かめる

友だち・自動応答・配信は、展開の直後と、その後おおむね15分ごとに同期される。

```bash
sf api request rest "/services/data/v67.0/ssot/data-streams" -o <org> | jq -r '.dataStreams[] | "\(.name)\t\(.lastRunStatus)\t\(.lastRefreshDate)"'
```

会話は、Igness 側で連携が有効になった後に送受信したものから入る（即時で数分、標準では設定した間隔の後）。

```bash
cat > /tmp/lamp-data360-count.json <<'EOF'
{"sql":"SELECT igns__direction__c, COUNT(*) FROM igns__LAMP_Timeline__dlm GROUP BY igns__direction__c"}
EOF
sf api request rest "/services/data/v67.0/ssot/queryv2" --method POST --body @/tmp/lamp-data360-count.json -o <org>
```

会話が0件のままなら、①手順2が `Successful` か、②契約で連携が有効か、認証のやり直しが必要でないか（どちらも Igness へ確認。送信が止まっている理由は Igness 側で把握している）の順に確かめる。過去の会話は自動では入らない。必要なら、契約の管理者が Igness のアカウント画面で「過去の会話をData 360に送信」を実行する。

## 取り込まれるもの

| データモデル | 内容 |
|---|---|
| Igness LAMP Timeline | 会話1件ごと。向き、種類、本文、日時、メッセージの構造（Flex など）、メディアURL、配信ID、AI自動返信かどうか、送信取消の印、送信元の種別とID |
| Igness LAMP Friend | 友だち。取引先責任者・リードへの参照を含む |
| Igness LAMP Reply / Igness LAMP Broadcast | 自動応答・配信 |

- 送信が取り消されたメッセージは、行を残したまま本文・構造・メディアURLを空にし、取消済みの印を付ける。
- 自動応答の「APIキー」項目は Data 360 へ取り込まない。
- 画像・動画・ファイルは原本を取り込まない。URLも、誰でも開ける公開URLは送らず、LAMP の非公開の参照（`https://files.mylp.jp/…`）だけを入れる。この参照は Data 360 の画面からは開けない。見るときは、友だちのレコードから Salesforce のチャット画面を開く。非公開ファイルの保存を有効にしていない org では、ファイルのURLは空で入る（種類は `messageType` で分かる）。
- 担当者が送った会話の `sourceUserId` は、Data 360 の標準の User データモデルに結ばれる。ユーザーの取り込みはこのキットに含まれない（下の節）。

## 担当者（ユーザー）まで結びたい場合

会話からユーザーへのリレーションはパッケージに入っているが、**org でユーザーが Data 360 に取り込まれていない間は現れない**（展開は成功し、他の3本は立つ。会話側にはユーザーIDの値が入る）。ユーザーの取り込みは、Data Kit の展開の前でも後でもよい。**後から取り込んだ場合も、ユーザーのデータストリームを作った時点でリレーションが自動で有効になる。Data Kit の再展開は要らない。**

既にユーザーを取り込んでいる org（Sales Cloud のデータバンドル等）では、何もしなくてよい。取り込んでいない org では、利用者に確認のうえ次を案内する（画面操作・6クリック・入力なし）。

1. ［データストリーム］→［新規］→「Salesforce CRM」→［次へ］
2. 標準バンドル **AgenticDataStreamUser** を選ぶ（オブジェクトの一覧に User は出ない。バンドル側にだけある）→［次へ］→ 既定のまま［次へ］→［リリース］
3. 作成直後はデータが空なので、ストリームの［今すぐ更新］を1回実行する。数分で入る。

確認:

```bash
sf api request rest "/services/data/v67.0/ssot/metadata?entityType=DataModelObject&entityName=igns__LAMP_Timeline__dlm" -o <org> \
  | jq -r '.metadata[0].relationships[] | "\(.fromEntityAttribute) -> \(.toEntity)"'
```

`igns__sourceUserId__c -> ssot__User__dlm` を含む4本が出ること。ユーザーの既定の取り込み項目は多い（185項目中79項目）ので、絞りたい場合は作成時の項目選択で外す。リレーションに必要なのは User Id だけ。
