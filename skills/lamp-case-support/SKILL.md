---
name: lamp-case-support
description: Igness LAMP で、LINE のボタン（リッチメニュー・テンプレートのボタンなど）を押すとケースが開き、ケースがクローズすると友だちの「対応中ケース」が空になる仕組みを Salesforce CLI でヘッドレスに組む。項目3つ・レコードトリガーフロー2本・ケース起動テンプレートを顧客 org に入れる。「LINEの問い合わせをケースで管理したい」「ボタンを押したらケースを作りたい」「友だちとケースを紐付けたい」などで使う。
---

# LAMP ケース起動（ヘッドレス）

LINE のボタンを押すと、LAMP がケース起動用テンプレートを返信し、その**項目設定**で友だちの「ケース起動」スイッチをオンにする。スイッチを見てフローがケースを作り、友だちの「対応中ケース」にセットしてスイッチを戻す。ケースがクローズすると、別のフローが友だちの「対応中ケース」を空にする。

```
ボタンを押す（リッチメニュー／テンプレートのボタン）
  → LAMP がケース起動テンプレートを返信し、項目設定で IsCreateCase__c = true
  → フロー①: 対応中ケースが空ならケースを作成 → CurrentCase__c にセット → スイッチを戻す
                （対応中ケースがあれば作成せずスイッチだけ戻す）
ケースがクローズ（IsClosed = true）
  → フロー②: その友だちの CurrentCase__c を空にする（ケース側の SocialFriend__c は残す）
```

AI 自動応答（Agentforce / BRAIN）、Slack 通知、チャットの配置、満足度アンケートはこのスキルの範囲外。AI 応答は `lamp-agentforce`、チャット配置は `lamp-chat` を使う。

## 作られるもの

| 種類 | API名 | 内容 |
|---|---|---|
| 項目（友だち `igns__SocialFriend__c`） | `IsCreateCase__c`「ケース起動」 | チェックボックス（初期値オフ）。ボタンでオンになり、フローがオフに戻す |
| 項目（友だち） | `CurrentCase__c`「対応中ケース」 | ケースへの参照。ケース削除時は空になる。クローズで空になる |
| 項目（ケース） | `SocialFriend__c`「友だち」 | 友だちへの参照。クローズ後も残す。友だち画面の関連リスト名は「ケース」 |
| フロー | `LAMP_Case_OpenOnSwitch`「LAMP ケース起動」 | 友だち更新時（`IsCreateCase__c` がオンになったとき）にケースを作成 |
| フロー | `LAMP_Case_ReleaseFriendOnClose` | ケース更新時（クローズになったとき）に友だちの `CurrentCase__c` を空にする |
| テンプレート | 例「お問い合わせ受付」 | 返信メッセージ＋共通の項目設定 `IsCreateCase__c = true` |
| 選択肢（任意） | ケース「発生源」に `LINE` | 無い場合だけ、ユーザーの了承を得て追加 |
| 項目権限 | 上記3項目の参照・編集 | **ユーザーが指定した既存の権限セット／プロファイル**に追加する。権限セットを新規作成しない |

ケースは次の値で作る:

| 項目 | 値 |
|---|---|
| 件名 | 既定「【LAMP】LINE問い合わせ」（ユーザー指定可） |
| 状況 | org の「新規」にあたる値（ユーザーに確認） |
| 発生源 | `LINE`（または既存の値） |
| 友だち | 起動した友だち |
| 取引先責任者 | 友だちの `igns__Contact__c`（空なら空） |
| 所有者 | ユーザーが指定したキューまたはユーザー（**必須**） |

## 前提条件

- LAMP 基本パッケージがインストール済みで、公式アカウントが接続済み（`lamp-setup`、`lamp-social-account-setup`）
- `sf` CLI で対象 org に認証済み（以下 `<org>`）。実行ユーザーはシステム管理者
- **必ず最初に対象 org をユーザーに確認する**（顧客の本番 org を扱うため）

## 守ること

- 顧客 org への変更（項目・フロー・選択肢・権限・テンプレート）は、手順2でユーザーに内容を見せて了承を得てから行う
- 権限セットを新規作成しない。項目権限を足す先は必ずユーザーに聞く
- ケース起動テンプレートは**一斉配信・プッシュ送信に使わない**。項目設定は配信経路でも適用されるため、受信者全員のケースが開く。返信（ボタン）専用にする
- 既存の同名項目・同じ役割のフローがあれば、上書きせずユーザーに確認する
- 日本語・JSON を含む値は `sf api request rest` + JSON ファイルで書く

## 手順1: 事前診断（読み取りのみ）

```bash
# 既存項目の衝突（同名があれば型と参照先を確認し、流用するか聞く）
sf sobject describe -s igns__SocialFriend__c -o <org> --json > /tmp/lcs-friend.json
sf sobject describe -s Case -o <org> --json > /tmp/lcs-case.json
python3 - <<'EOF'
import json
for obj, names in [('friend', ['IsCreateCase__c', 'CurrentCase__c', 'igns__Contact__c']), ('case', ['SocialFriend__c', 'Status', 'Origin'])]:
    f = {x['name']: x for x in json.load(open(f'/tmp/lcs-{obj}.json'))['result']['fields']}
    for n in names:
        x = f.get(n)
        if not x: print(obj, n, '→ なし'); continue
        vals = [(v['value'], v['defaultValue']) for v in x.get('picklistValues', []) if v['active']]
        print(obj, n, x['type'], x.get('referenceTo'), vals or '')
EOF

# ケースの状況: 「新規」にあたる値と、クローズ扱いの値
sf data query -q "SELECT MasterLabel, ApiName, IsClosed, IsDefault FROM CaseStatus ORDER BY SortOrder" -o <org>

# 所有者候補のキュー（ケースを扱えるもの）
sf data query -q "SELECT Queue.Id, Queue.Name, Queue.DeveloperName FROM QueueSobject WHERE SobjectType = 'Case'" -o <org>

# 友だち・ケースで動く既存フロー（役割の重複・干渉を確認）
sf data query -q "SELECT ApiName, Label, TriggerType, IsActive FROM FlowDefinitionView WHERE TriggerObjectOrEvent.QualifiedApiName IN ('Case','igns__SocialFriend__c') AND IsActive = true" -o <org>

# LAMP 受信処理の実行ユーザー（行が無ければ既定の Automated Process ユーザー）
sf data query -q "SELECT DeveloperName, UserId, PlatformEventConsumerId FROM PlatformEventSubscriberConfig" --use-tooling-api -o <org>
```

判定:

| 結果 | 対応 |
|---|---|
| `IsCreateCase__c` / `CurrentCase__c` / `SocialFriend__c` が既にある | 型・参照先が同じなら流用してよいかユーザーに聞く。違えば別名を相談する（フロー内の参照も合わせて置換） |
| 友だち・ケースに同じ役割のフロー（ケース作成・対応中ケースの同期）がある | 二重にケースが作られる。どちらを残すかユーザーに聞く |
| 発生源に `LINE` が無い | 手順3-2で追加するか、既存の値を使うか聞く |
| ケース用のキューが無い | 所有者を特定ユーザーにするか、ユーザー側でキューを用意してもらう |
| `PlatformEventSubscriberConfig` に行が無い | 受信処理は Automated Process ユーザーで動く。このユーザーは項目権限を足さなくても `IsCreateCase__c` を書き込める（検証済み） |
| 行があり、別ユーザーを指定している | そのユーザーに `IsCreateCase__c` の編集権限が必要。無いと LAMP は**友だちの更新をまるごと黙ってスキップする**（ケースが開かないうえ、最終送信日時も更新されない）。手順3-3の追加先に含める |

## 手順2: ユーザーに確認する

次をまとめて聞き、決まった内容を一覧で見せて了承を得る。

1. **所有者**: キュー（上で取得した一覧から）か、特定ユーザーか。指定しないとケースの所有者が Automated Process ユーザーになり、誰にも見えない状態になるため必須
2. **状況の初期値**: `CaseStatus` の一覧から「新規」にあたる値。クローズの判定は `IsClosed` を使うので、クローズ側の値は聞かなくてよい
3. **件名**（既定「【LAMP】LINE問い合わせ」）と**発生源**（`LINE` を追加するか、既存の値を使うか）
4. **項目権限の追加先**: 3項目を見る・編集する人（ケース担当者・管理者）が使っている**既存の権限セットまたはプロファイル**。複数可。候補の出し方:
   ```bash
   # 自社作成の権限セット（権限セットグループの集約用や管理パッケージのものは出ない）
   sf data query -q "SELECT Id, Name, Label FROM PermissionSet WHERE NamespacePrefix = null AND Type = 'Regular' ORDER BY Label" -o <org>
   # 有効ユーザーがいるプロファイルと人数
   sf data query -q "SELECT Profile.Name, COUNT(Id) FROM User WHERE IsActive = true AND UserType = 'Standard' GROUP BY Profile.Name" -o <org>
   # 選ばれたプロファイルの権限セットId（手順3-3で使う）
   sf data query -q "SELECT Id, Profile.Name FROM PermissionSet WHERE IsOwnedByProfile = true AND Profile.Name IN ('<プロファイル名>')" -o <org>
   ```
   受信処理の実行ユーザーが Automated Process 以外なら、そのユーザーに割り当て済みの権限セットも候補に入れる。管理パッケージの権限セット（`igns` など）は編集できないので候補にしない
5. **ページレイアウト**: 友だち画面に「対応中ケース」、ケース画面に「友だち」を表示するか。表示する場合はどのレイアウトか
6. **ボタンの場所**: リッチメニューのどの領域か、既存テンプレートのボタンか。ケース起動テンプレートの返信文

## 手順3: 反映

### 3-1. 項目とフロー

このスキルの [metadata](references/metadata/) を作業ディレクトリへコピーし、フロー①のプレースホルダーを置き換えてからデプロイする。

```bash
cp -R <このスキルのディレクトリ>/references/metadata /tmp/lamp-case-support && cd /tmp/lamp-case-support
F=force-app/main/default/flows/LAMP_Case_OpenOnSwitch.flow-meta.xml
# {{OWNER_ID}}=キューまたはユーザーのId / {{SUBJECT}} / {{STATUS_NEW}}=状況のAPI値 / {{ORIGIN}}=発生源のAPI値
python3 - "$F" '<ownerId>' '<件名>' '<状況>' '<発生源>' <<'EOF'
import sys
from xml.sax.saxutils import escape
p, owner, subject, status, origin = sys.argv[1:]
s = open(p, encoding='utf-8').read()
for k, v in {'{{OWNER_ID}}': owner, '{{SUBJECT}}': subject, '{{STATUS_NEW}}': status, '{{ORIGIN}}': origin}.items():
    s = s.replace(k, escape(v))
assert '{{' not in s, 'プレースホルダーが残っている'
open(p, 'w', encoding='utf-8').write(s)
EOF
sf project deploy start -d force-app -o <org> --dry-run --wait 10   # 先に検証だけ
sf project deploy start -d force-app -o <org> --wait 10
```

- 手順1で既存項目を流用する場合は、その項目ファイルを `force-app` から外してからデプロイする（既存の定義を上書きしない）
- 別名にした場合は、フロー2本の `IsCreateCase__c` / `CurrentCase__c` / `SocialFriend__c` も同じ名前に置換する
- フローは有効（`Active`）でデプロイされる。無効で入れたい場合は `<status>Draft</status>` に変える

### 3-2. 発生源に LINE を追加（了承した場合のみ）

標準選択リストは値の一覧ごと置き換わるので、取得 → 1件追記 → デプロイの順で行い、前後で値が減っていないことを確認する。

```bash
cd /tmp/lamp-case-support
sf project retrieve start -m StandardValueSet:CaseOrigin -o <org>
# force-app/main/default/standardValueSets/CaseOrigin.standardValueSet-meta.xml の末尾（</StandardValueSet> の前）に追記:
#   <standardValue><fullName>LINE</fullName><default>false</default><label>LINE</label></standardValue>
sf project deploy start -m StandardValueSet:CaseOrigin -o <org> --wait 10
```

レコードタイプを使っている org では、そのレコードタイプの発生源の選択肢にも `LINE` を追加する必要がある（ユーザーに確認）。

### 3-3. 項目権限（指定された既存の権限セット／プロファイル）

プロファイルの場合は、そのプロファイルに紐づく権限セット（`IsOwnedByProfile = true`）の Id を使う。既に行があるものは作らずに更新する。

```bash
# 既存の行を確認
sf data query -q "SELECT Id, ParentId, Field, PermissionsRead, PermissionsEdit FROM FieldPermissions WHERE ParentId IN ('<psId1>','<psId2>') AND Field IN ('igns__SocialFriend__c.IsCreateCase__c','igns__SocialFriend__c.CurrentCase__c','Case.SocialFriend__c')" -o <org>

# 無いものだけ作成（例: 1つの権限セットに3項目）
cat > /tmp/lcs-fp.json <<'EOF'
{ "records": [
  { "attributes": {"type": "FieldPermissions", "referenceId": "f1"}, "ParentId": "<psId>", "SobjectType": "igns__SocialFriend__c", "Field": "igns__SocialFriend__c.IsCreateCase__c", "PermissionsRead": true, "PermissionsEdit": true },
  { "attributes": {"type": "FieldPermissions", "referenceId": "f2"}, "ParentId": "<psId>", "SobjectType": "igns__SocialFriend__c", "Field": "igns__SocialFriend__c.CurrentCase__c", "PermissionsRead": true, "PermissionsEdit": true },
  { "attributes": {"type": "FieldPermissions", "referenceId": "f3"}, "ParentId": "<psId>", "SobjectType": "Case", "Field": "Case.SocialFriend__c", "PermissionsRead": true, "PermissionsEdit": true }
] }
EOF
sf api request rest "/services/data/v67.0/composite/tree/FieldPermissions" --method POST -b @/tmp/lcs-fp.json -o <org>
```

参照だけでよい相手（例: 閲覧のみのユーザー）は `PermissionsEdit: false` にする。フローはシステム権限で動くため、フローのための権限追加は不要。

### 3-4. ページレイアウト（希望した場合のみ）

```bash
sf project retrieve start -m "Layout:igns__SocialFriend__c-<レイアウト名>" -m "Layout:Case-<レイアウト名>" -o <org>
```

取得した XML の適当なセクションに `<layoutItems><behavior>Edit</behavior><field>CurrentCase__c</field></layoutItems>`（ケース側は `SocialFriend__c`）を追加して `sf project deploy start -m ...` で戻す。Lightning ページが Dynamic Forms の場合はレイアウトではなく FlexiPage 側の変更になるので、ユーザーに画面から追加してもらう。

## 手順4: ボタンをつなぐ

### 4-1. ケース起動テンプレート

テンプレートとメッセージの作り方は `lamp-template` に従う。ここでは返信文1件と、**共通の項目設定**（押した場所を問わず適用）を作る。

```bash
cat > /tmp/lcs-tpl.json <<'EOF'
{ "Name": "お問い合わせ受付" }
EOF
sf api request rest "/services/data/v67.0/sobjects/igns__Template__c" --method POST -b @/tmp/lcs-tpl.json -o <org>

cat > /tmp/lcs-msg.json <<'EOF'
{ "igns__Template__c": "<templateId>", "igns__Type__c": "text", "igns__Sort__c": 1,
  "igns__Text__c": "お問い合わせを受け付けました。担当者からご連絡します。" }
EOF
sf api request rest "/services/data/v67.0/sobjects/igns__TemplateMessage__c" --method POST -b @/tmp/lcs-msg.json -o <org>

cat > /tmp/lcs-tfs.json <<'EOF'
{ "igns__Template__c": "<templateId>", "Name": "IsCreateCase__c", "igns__Condition__c": "EQ", "igns__Value__c": "true" }
EOF
sf api request rest "/services/data/v67.0/sobjects/igns__TemplateFieldSetting__c" --method POST -b @/tmp/lcs-tfs.json -o <org>
```

- `SourcedRecordId__c` / `SourcedActionId__c` は空のままにする（共通設定）。どのボタンから呼んでもケースが開く
- 返信文のメッセージが `IsValid__c = true` になっていることを確認する（`lamp-template` の検証ループ）

### 4-2. ボタン

- **リッチメニュー**: `lamp-richmenu` で対象領域を `postback`、`igns__ActionTemplate{n}__c` = ケース起動テンプレートの Id にする。発行済みのメニューを変えた場合は再発行する
- **テンプレートのボタン**: `lamp-template` の返信ボタン・カードのボタンを `postback` + 同じテンプレート Id にする
- AI 応答の起動（`callagent`）と組み合わせる場合は、その自動応答の開始テンプレートに同じ共通設定を付ければケースも開く（`callagent` はボタン別の項目設定を引き継がないが、共通設定は効く）

## 手順5: 確認

### 5-1. フロー単体（LINE を送らない）

テスト用の友だち（`igns__IsTest__c = true` など、ユーザーが指定した友だち）で、管理者としてスイッチを直接オンにする。

```bash
echo '{"IsCreateCase__c": true}' > /tmp/lcs-on.json
sf api request rest "/services/data/v67.0/sobjects/igns__SocialFriend__c/<friendId>" --method PATCH -b @/tmp/lcs-on.json -o <org>
sf data query -q "SELECT IsCreateCase__c, CurrentCase__c FROM igns__SocialFriend__c WHERE Id = '<friendId>'" -o <org>
sf data query -q "SELECT Id, Subject, Status, Origin, Owner.Name, ContactId, SocialFriend__c FROM Case WHERE SocialFriend__c = '<friendId>' ORDER BY CreatedDate DESC" -o <org>
```

| 操作 | 期待する結果 |
|---|---|
| スイッチをオン | ケースが1件でき、`CurrentCase__c` にその Id、`IsCreateCase__c = false` |
| もう一度オン（ケースは開いたまま） | ケースは増えない。スイッチはオフに戻る |
| ケースをクローズ | 友だちの `CurrentCase__c` が空。ケースの `SocialFriend__c` は残る |
| もう一度オン | 新しいケースが1件でき、`CurrentCase__c` が新しいケースになる |
| クローズ済みケースを開き直す | 友だちの `CurrentCase__c` は変わらない（仕様） |

確認で作ったケースは、ユーザーに消すか残すかを聞く。

### 5-2. 実際のボタン

ユーザーのスマートフォンでボタンを押してもらい、ケース起動テンプレートが届くこと、ケースが開くことを確認する。ケースが開かない場合は次を順に見る:

```bash
# 返信ジョブ（LampReplyMessageJob）が動いたか・実行ユーザー
sf data query -q "SELECT Status, ExtendedStatus, CreatedBy.Name, CompletedDate FROM AsyncApexJob WHERE ApexClass.Name = 'LampReplyMessageJob' ORDER BY CreatedDate DESC LIMIT 3" -o <org>
# 項目設定が付いているか
sf data query -q "SELECT Name, igns__Condition__c, igns__Value__c, igns__SourcedRecordId__c, igns__SourcedActionId__c FROM igns__TemplateFieldSetting__c WHERE igns__Template__c = '<templateId>'" -o <org>
```

## トラブルシューティング

| 症状 | 原因と対処 |
|---|---|
| テンプレートは届くがケースが開かない。友だちの最終送信日時も更新されない | 受信処理の実行ユーザーに `IsCreateCase__c` の編集権限が無く、LAMP が友だちの更新をスキップしている。`PlatformEventSubscriberConfig` の実行ユーザーを確認し、ユーザーが指定した権限セットに権限を足す |
| テンプレートは届き、スイッチもオフのまま、ケースが無い | 項目設定の `Name` が `IsCreateCase__c` になっていない、または Sourced 項目に値が入っていてボタンと一致していない |
| スイッチがオンのまま残る | フロー①が無効、またはケース作成でエラー（所有者のキューがケース非対応、状況・発生源の値が存在しない等）。フローのエラーメールか「フローの実行時エラー」を確認 |
| ケースが二重に作られる | 同じ役割の既存フロー（顧客独自のケース作成）が動いている。手順1の既存フロー一覧を見直す |
| 配信したら大量にケースが開いた | ケース起動テンプレートを一斉配信・プッシュ送信に使った。配信には別のテンプレートを使う |
| クローズしても対応中ケースが残る | フロー②が無効、またはクローズに使った状況の `IsClosed` が false |

## 元に戻す

フロー2本を無効化（`<status>Obsolete</status>` で再デプロイ、または画面から無効化）すると動作は止まる。項目の削除はデータも消えるため、ユーザーの明示的な指示がある場合だけ行う。

```bash
# 無効化（有効なフローはこのままでは削除できない）
sf data query -q "SELECT Id FROM FlowDefinition WHERE DeveloperName = '<フローAPI名>'" --use-tooling-api -o <org>
echo '{"Metadata":{"activeVersionNumber":0}}' > /tmp/fd-off.json
sf api request rest "/services/data/v67.0/tooling/sobjects/FlowDefinition/<FlowDefinitionId>" --method PATCH -b @/tmp/fd-off.json -o <org>
# 削除する場合（ユーザーの指示があるときだけ）: バージョンごとに消す
sf data query -q "SELECT Id, VersionNumber, Status FROM Flow WHERE Definition.DeveloperName = '<フローAPI名>'" --use-tooling-api -o <org>
sf data delete record -s Flow -i <FlowのバージョンId> --use-tooling-api -o <org>
```
