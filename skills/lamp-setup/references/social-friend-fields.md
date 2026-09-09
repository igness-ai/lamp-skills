# Lead / Contactから友だちを参照する項目の確認

チャット配置、配信レポート、友だちとの連携設定では毎回確認する。一般的な作成名は **`SocialFriend_<LampId>__c`** だが、組織の設定・導入手順により別名、未作成、片方のオブジェクトのみの場合がある。名前を組み立てただけで存在すると扱わない。

## 1. 対象公式アカウントの設定を取得する

```bash
sf data query -q "SELECT Id, igns__LampId__c, igns__LeadField__c, igns__ContactField__c FROM igns__SocialAccount__c WHERE Id = '<socialAccountId>'" -o <org> --json > /tmp/lamp-relationship-config.json
sf sobject describe -s igns__SocialFriend__c -o <org> --json > /tmp/lamp-friend-describe.json
sf sobject describe -s Lead -o <org> --json > /tmp/lamp-lead-describe.json
sf sobject describe -s Contact -o <org> --json > /tmp/lamp-contact-describe.json
```

Lead / Contactが利用できない組織なら、そのオブジェクトを前提にした設定を作らない。項目が見えない場合は、実際に未作成なのか、確認ユーザーの権限不足なのかを区別する。

## 2. API名・参照先・値を確認する

| 確認 | 判定 |
|---|---|
| `LeadField__c` / `ContactField__c` | 各オブジェクトでLAMPが使う設定値。空欄・別名もあり得る |
| describeの `fields[].name` | 設定された項目が実在するか。パッケージの項目名と顧客作成項目名を混同しない |
| `type` / `referenceTo` / `relationshipName` | Lookupなら `type=reference`、参照先に `igns__SocialFriend__c` があるか。SOQLで関連をたどる名前はdescribeから取得 |
| オブジェクト・項目権限 | 設定する管理者だけでなく、チャット利用者・レポート実行者・同期処理ユーザーに必要な権限があるか |
| 対象レコードの実値 | 非空か、実在する友だちIdか、対象公式アカウントの友だちか |

片方向だけ設定済みの場合もある。友だちの `igns__Lead__c` / `igns__Contact__c` と、Lead / Contact側の友だち参照項目は別々に確認する。参照項目が存在しても値の同期済みとは限らない。

```bash
# <実在する友だち参照項目API名> は上記で解決した名前を使う
sf data query -q "SELECT Id, <実在する友だち参照項目API名> FROM Contact WHERE Id = '<対象ContactId>'" -o <org> --json > /tmp/lamp-contact-link.json
sf data query -q "SELECT Id, igns__SocialAccount__c, igns__Lead__c, igns__Contact__c FROM igns__SocialFriend__c WHERE Id = '<解決した友だちId>'" -o <org> --json > /tmp/lamp-friend-link.json
```

## 3. 用途に合わせて設定する

- **チャット**: SocialFriendのページでは `socialFriendRecordIdField=Id`。Lead / Contactのページでは確認できた友だち参照項目のAPI名を指定する。
- **配信レポート**: Lead / Contactを基準にする場合は、確認できた友だちLookup、または関連する友だちのIdを先頭の詳細列にする。Lead / Contact自身のIdや友だちの表示名は宛先にならない。レポートタイプの列キーは別途describeで解決する。
- **条件分岐・差し込み**: Bot条件とテンプレート差し込みは友だち自身の項目を使う。Lead / Contactの項目パスがどこでも利用できるとは仮定しない。

参照項目がない場合、配信は友だち基準のレポートからLead / Contactの関連を使えるかを先に検討する。項目作成が必要で、依頼に連携設定が含まれる場合は `lamp-setup` の `LampSetupRelationshipFieldsAction` を使い、返った実際のAPI名・結果とdescribeを再確認する。レポート作成だけの依頼を理由に新規項目を無断追加しない。既存データへの参照値の補完は項目作成とは別の作業である。
