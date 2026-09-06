---
name: lamp-coupon
description: Igness LAMP の LINE クーポンを Salesforce CLI でヘッドレスに作成・検証・LINE に発行し、テンプレートメッセージへの組み込み、内容変更（複製→再発行）、終了まで行う。「LAMPでクーポンを作って」「クーポンを発行して」「クーポンの割引率を変えたい」「クーポンを終了して」などで使う。
---

# LAMP クーポン（ヘッドレス）

クーポンは **`igns__Coupon__c`** レコードで定義し、**LINE に発行**すると LINE 側にクーポンが作られて `igns__CouponId__c` が入る。発行済みクーポンはテンプレートメッセージ（クーポンタイプ）に組み込んで配信する。

```
① レコード作成     igns__Coupon__c（リワード種別ごとの必須項目）
② 画像（任意）     lamp-media-upload（種別 coupon）→ ImageUrl__c / BarcodeUrl__c
③ LINE に発行      Actions API igns__LampIssueCouponAction
④ 配信に組み込む   igns__TemplateMessage__c（Type=coupon）→ lamp-template / lamp-broadcast
⑤ 内容を変える     igns__LampCloneCouponAction で複製 → 修正 → ③ で発行 →（必要なら）旧クーポンを終了
⑥ 終了             igns__LampCloseCouponAction（confirmClose=true、不可逆）
```

## 前提条件

- LAMP 基本パッケージ **1.157 以降**（発行・終了・複製アクション）
- `sf` CLI で対象 org に認証済み（以下 `<org>`）。API バージョン v66.0 以上
- 実行ユーザーに `LAMP_SystemAdministrator` または `LAMP_MarketingAdministrator` 権限セットグループ
- 公式アカウント（`igns__SocialAccount__c`）が接続済み
- **必ず最初に対象 org をユーザーに確認する**（顧客の本番 org を扱うため）

## 守ること（LINE のクーポンの性質）

- **発行したクーポンは変更できない。** 内容を変えるときは「複製 → 修正 → 発行」で新しいクーポンを作る（⑤）
- **終了は取り消せず、既に受け取った人も使えなくなる。** 終了アクションは `confirmClose=true` が無いと実行されない。実行前に影響をユーザーに伝えて承認を得る
- 発行はユーザーの承認を得てから行う（LINE 側に実体が作られる）
- 取得数・使用数は LINE API で提供されないため取れない。効果を見たい場合は、クーポンを送った配信の既読数・クリック数（`lamp-broadcast` スキル）を使う
- `igns__CouponId__c` / `igns__IsActive__c` は書かない（発行・終了処理が管理する）

## ① レコードの作成

```bash
cat > /tmp/cp.json <<'EOF'
{ "Name": "秋の温泉20%OFF",
  "igns__SocialAccount__c": "<socialAccountId>",
  "igns__Description__c": "箱根・草津・別府の秋の温泉プランが20%OFF",
  "igns__RewardType__c": "discount",
  "igns__PriceInfoDiscountType__c": "percentage",
  "igns__PriceInfoDiscountPercentage__c": 20,
  "igns__StartDateTime__c": "2026-09-10T00:00:00.000Z",
  "igns__EndDateTime__c": "2026-11-30T14:59:59.000Z",
  "igns__Timezone__c": "ASIA_TOKYO",
  "igns__MaxUseCountPerTicket__c": "1",
  "igns__ConditionType__c": "normal",
  "igns__Visibility__c": "UNLISTED",
  "igns__UsageCondition__c": "他の割引との併用不可" }
EOF
sf api request rest "/services/data/v66.0/sobjects/igns__Coupon__c" --method POST -b @/tmp/cp.json -o <org>
```

| 項目 | 必須 | 内容 |
|---|---|---|
| `Name` | ✔ | クーポン名（60 文字以内。入力規則で保存時に検証） |
| `igns__SocialAccount__c` | ✔ | 公式アカウント |
| `igns__RewardType__c` | ✔ | `discount`（割引）/ `free`（無料）/ `gift`（プレゼント）/ `cashBack` / `others` |
| `igns__StartDateTime__c` / `igns__EndDateTime__c` | ✔ | 有効期間（終了 > 開始）。UTC で書く |
| `igns__MaxUseCountPerTicket__c` | ✔ | `"1"`（1 回）または `"-1"`（無制限）。**文字列** |
| `igns__Timezone__c` | 任意 | 既定 `ASIA_TOKYO` |
| `igns__Visibility__c` | 任意 | `UNLISTED`（メッセージで受け取った人だけ。既定）/ `PUBLIC`（公式アカウントのクーポン一覧にも出る） |
| `igns__ConditionType__c` | 任意 | `normal`（既定）/ `lottery`（抽選。`igns__LotteryProbability__c` 1〜99 と `igns__MaxAcquireCount__c`（-1=上限なし、または 1〜999999）が必須） |
| `igns__Description__c` / `igns__UsageCondition__c` | 任意 | 説明 / 利用条件 |
| `igns__ImageUrl__c` / `igns__BarcodeUrl__c` | 任意 | ② の公開 URL（https 必須） |
| `igns__CouponCode__c` / `igns__CouponCodeVisibility__c` | 任意 | クーポンコードと表示方法（`クーポンコードを表示する` / `バーコードを表示する` / `両方表示する`） |

リワード種別ごとの必須項目:

| `igns__RewardType__c` | 追加項目 |
|---|---|
| `discount` | `igns__PriceInfoDiscountType__c`: `fixed`（`igns__PriceInfoDiscountFixedAmount__c` > 0）/ `percentage`（`igns__PriceInfoDiscountPercentage__c` 1〜99）/ `explicit`（`igns__PriceInfoOriginalPrice__c` > 0、`igns__PriceInfoPriceAfterDiscount__c` ≥ 0 かつ元価格より小さい） |
| `cashBack` | `igns__PriceInfoCashbackType__c`: `fixed`（`igns__PriceInfoFixedAmountCashback__c` > 0）/ `percentage`（`igns__PriceInfoPercentageCashback__c` 1〜99） |
| `free` / `gift` / `others` | 追加なし |

保存後の `igns__Status__c`（数式）は `有効期間前` / `有効` / `期限切れ` / `無効`（未発行または終了済み）。

## ② 画像（任意）

`lamp-media-upload` スキルの種別 `coupon` でアップロードし、`recordId` と `imageUrlField=igns__ImageUrl__c`（バーコードは `igns__BarcodeUrl__c`）、`uuidField=igns__ImageUuid__c`（同 `igns__BarcodeUuid__c`）を渡す。トーク画面では横長（1.51 : 1）に切り抜かれて表示される。

## ③ LINE に発行

発行前に、名前・リワード・有効期間・公開範囲をユーザーに提示して承認を得る。

```bash
sf api request rest "/services/data/v66.0/actions/custom/apex/igns__LampIssueCouponAction" --method POST -b '{"inputs":[{"couponId":"<couponId>"}]}' -o <org>
```

- 成功: `outputValues.success=true`、`lineCouponId`、`isActive=true`。レコードの `igns__CouponId__c` が入る
- 失敗: `message` に理由

| `message` | 対処 |
|---|---|
| リワードタイプは必須です / 固定金額は正の数値… / パーセンテージは1-99… / 終了日時は開始日時より後… / 抽選確率は1-99… | ① の必須・範囲を直す（LINE を呼ぶ前の検証） |
| このクーポンは既に LINE に発行されています… | 変更したいなら ⑤ |
| クーポンの作成に失敗しました: HTTP 400: imageUrl is invalid… | 画像 URL が http や外部の URL。② でコンテンツ配信基盤に上げ直す |
| クーポンの作成に失敗しました: HTTP 400: … | LINE の検証で拒否。`message` の項目を直す |
| HTTP 401 / 403 | サーバー認証か公式アカウント接続の問題（`lamp-setup`）。接続直後は最大 5 分待つ |

発行後は `Name`・期間・リワード・画像・コード等を変更できない（入力規則「一度有効化したクーポンは編集できません」）。

## ④ 配信に組み込む

テンプレートメッセージをクーポンタイプで作る（詳細は `lamp-template`）:

```bash
cat > /tmp/msg.json <<'EOF'
{ "igns__Template__c": "<templateId>", "igns__Type__c": "coupon", "igns__Coupon__c": "<couponId>", "igns__Sort__c": 1 }
EOF
sf api request rest "/services/data/v66.0/sobjects/igns__TemplateMessage__c" --method POST -b @/tmp/msg.json -o <org>
```

未発行（`igns__CouponId__c` 空）や終了済みのクーポンを参照するメッセージは、送信時に黙って除外される。配信前に `igns__CouponId__c` があり `igns__IsActive__c=true` であることを確認する。

## ⑤ 内容を変える（複製 → 修正 → 発行）

```bash
sf api request rest "/services/data/v66.0/actions/custom/apex/igns__LampCloneCouponAction" --method POST -b '{"inputs":[{"sourceCouponId":"<couponId>","newName":"秋の温泉30%OFF"}]}' -o <org>
```

- `newCouponId` に未発行の複製が返る（発行結果は複製しない）。`newName` 省略時は「（コピー）」付き
- `referencingTemplateMessageIds`（カンマ区切り）に、複製元を参照しているテンプレートメッセージが返る。**自動では差し替えない。** 新クーポンに切り替えるかをユーザーに確認し、切り替える場合は該当メッセージの `igns__Coupon__c` を PATCH する（配信予約中のテンプレートを黙って書き換えないため）
- 複製を PATCH で修正 → ③ で発行 → 旧クーポンを終了するかはユーザーの判断（終了すると受け取り済みの人も使えなくなる。有効期限まで残す選択も正しい）

## ⑥ 終了

1 回目は `confirmClose` なしで呼び、影響（参照しているテンプレートメッセージ数など）を確認する:

```bash
sf api request rest "/services/data/v66.0/actions/custom/apex/igns__LampCloseCouponAction" --method POST -b '{"inputs":[{"couponId":"<couponId>"}]}' -o <org>
# → needsConfirmation=true, message に影響の説明, referencingTemplateMessages=件数
```

ユーザーの承認を得てから実行:

```bash
sf api request rest "/services/data/v66.0/actions/custom/apex/igns__LampCloseCouponAction" --method POST -b '{"inputs":[{"couponId":"<couponId>","confirmClose":true}]}' -o <org>
```

成功すると LINE 側で終了（CLOSED）し、`igns__IsActive__c=false` になる。終了は取り消せない。

## トラブルシューティング

| 症状 | 原因と対処 |
|---|---|
| 保存が `FIELD_CUSTOM_VALIDATION_EXCEPTION`「クーポン名は60文字以内…」 | 名前を短くする |
| 保存が「一度有効化したクーポンは編集できません」 | 発行済み。⑤ の複製で新しく作る |
| `bad value for restricted picklist` | `RewardType__c` / 価格情報タイプ / `Visibility__c` / `ConditionType__c` の値を上表どおりに |
| `MaxUseCountPerTicket__c` の型エラー | 文字列 `"1"` / `"-1"` |
| 配信したのにクーポンが届かない | 未発行か終了済み。`igns__CouponId__c` と `igns__IsActive__c` を確認 |
| 取得数・使用数を知りたい | LINE API に無い。配信の既読数・クリック数で代替 |
