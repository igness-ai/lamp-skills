# 配信レポートの先頭列と宛先を検証する

**先頭の詳細列は必ずSocialFriendId（友だちレコードのId）。** 見出しを「SocialFriendId」に変えるだけでは足りない。LAMPは先頭セルを無条件に宛先へ渡すため、Lead / Contact自身のId、友だちの表示名、LINEのuserIdを置かない。2列目以降は `insert_1` 以降の差し込みになる。

## 列を作る・選ぶ

- 友だち基準の標準レポートなら `CUST_ID` が友だちId。`CUST_ID` はレポートタイプ内の列キーなので、Lead / Contact基準で同じキーが友だちIdになるとは限らない。
- Lead / Contact基準なら、[友だち参照項目の確認](../../lamp-setup/references/social-friend-fields.md) で実在する `SocialFriend_<LampId>__c` 等のLookupを特定する。存在、参照先、権限、実値を確認し、そのLookupまたは関連する友だちのId列を先頭にする。
- Lookup未作成・レポートタイプから参照できない場合は、友だち基準のタイプとLead / Contact関連を検討する。未作成の項目名を推測して保存しない。
- レポートビルダーのアウトラインで先頭の**詳細列**へ移し、表形式で保存する。集計行やグループ見出しは宛先列の代わりにならない。

対象レポートのdescribeとレポートタイプ情報で、先頭列キーの実体を調べる:

```bash
sf api request rest '/services/data/v67.0/analytics/reports/<reportId>/describe' -o <org> > /tmp/lamp-report-describe.json
sf api request rest '/services/data/v67.0/analytics/reportTypes/<describeで取得したタイプキー>' -o <org> > /tmp/lamp-report-type.json
```

`reportMetadata.detailColumns[0]` と `reportTypeMetadata.categories[].columns` / `reportExtendedMetadata.detailColumnInfo` を照合し、列のラベルだけでなく元オブジェクト・項目を確定する。スクリプトへ渡す `--expected-first-column` はこの確認で得たキーであり、現在の先頭列を無条件に指定して合格させない。

## 全行の検証

スケジュールする本人のユーザーでレポートを実行する。結果やIdはローカルのファイルで扱い、チャットへ全行表示しない。以下 `<skill-dir>` はインストールした `lamp-broadcast` ディレクトリ。

```bash
sf api request rest '/services/data/v67.0/analytics/reports/<reportId>?includeDetails=true' -o <org> > /tmp/lamp-report-run.json
sf sobject describe -s igns__SocialFriend__c -o <org> --json > /tmp/lamp-friend-describe.json

# 友だち基準・先頭列CUST_IDの場合。出力SOQLファイルは未使用のパスを指定する
python3 <skill-dir>/scripts/validate_report.py \
  --report /tmp/lamp-report-run.json \
  --friend-describe /tmp/lamp-friend-describe.json \
  --column-describe /tmp/lamp-friend-describe.json --column-field Id \
  --expected-first-column CUST_ID \
  --write-id-query /tmp/lamp-report-friends.soql

sf data query --file /tmp/lamp-report-friends.soql -o <org> --json > /tmp/lamp-report-friends.json

python3 <skill-dir>/scripts/validate_report.py \
  --report /tmp/lamp-report-run.json \
  --friend-describe /tmp/lamp-friend-describe.json \
  --column-describe /tmp/lamp-friend-describe.json --column-field Id \
  --expected-first-column CUST_ID \
  --friends /tmp/lamp-report-friends.json --social-account-id '<socialAccountId>'
```

Lead / ContactのLookupを使う場合、`--column-describe` はそのオブジェクトのdescribe JSON、`--column-field` は解決したLookupのAPI名、`--expected-first-column` はレポートタイプ内の該当列キーに置き換える。文字列・数式でIdを作る列は、このスクリプトではnativeなId／Lookupとして合格させない。友だちId列またはLookupを選ぶ。

スクリプトは表形式・列順・全件取得・2,000行以内・全行の非空Id・対象orgのkeyPrefix・Lookupの参照先を検証する。2回目はさらに、抽出Idの実在と公式アカウントの一致を検証する。先頭5件だけを見て合格にしない。

- 非0件では `recipientExistenceAndAccountChecked=true` まで確認する。最初の実行、または0件の場合は `false` で、実在する宛先の照合済みとはしない。
- `rows` は行数、`uniqueFriends` は重複を除いた友だち数。既定の重複排除時に人数として伝えるのは後者。`AllowDuplicate=true` なら同じ相手に複数回届くことを別途確認する。
- `allData=false` や2,000行超なら、切れたままスケジュールしない。CSVへ切替またはレポート分割を行う。
- 0行でも列定義の検証はできるが、実際のセル値は検証できていない。将来条件での定期配信ならその状態を報告し、承認済みのテストレコード・同じ列構成のテストレポートで非0件の確認を行う。本番レポートの条件を勝手に緩めない。
- 件数確認と、ブロック・テスト用・業務条件・日付・共有範囲の確認は別。列の妥当性だけで配信対象が業務上正しいとは断定しない。
- 現在0行であることから、過去の配信が正常だったとは推定しない。実行時点の条件・データ・履歴で確認する。
