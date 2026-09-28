---
name: lamp-richmenu
description: Igness LAMP のリッチメニュー（LINE トーク画面下部のメニュー）を Salesforce CLI でヘッドレスに作成・検証・LINE に発行し、タブ切り替え・自由配置の領域・デフォルト設定・友だち個別の割当・差し替え・削除、LINE 統計（表示回数・領域ごとのタップ数）の読み取りまで行う。「LAMPでリッチメニューを作って」「タブ付きのリッチメニューにしたい」「リッチメニューを有効化して」「メニューの画像を差し替えて」「この友だちにメニューを割り当てて」「リッチメニューのクリック数を見たい」などで使う。
---

# LAMP リッチメニュー（ヘッドレス）

リッチメニューは **`igns__RichMenu__c`** レコードで定義する。レイアウト（領域の分割）はプリセットから選ぶか座標で自由に指定し、領域ごとにタップ時のアクションを設定し、画像を付けて **LINE に発行**すると使えるようになる。発行するたびに **バージョン**（`igns__RichMenuVersion__c`）が1件でき、LINE 統計はバージョンごとに読める。

```
① レイアウト選択   igns__LampBound__mdt のプリセット（領域数・画像サイズ）
② 画像の用意       lamp-media-upload（種別 richmenu）でアップロード → ImageUrl__c
③ レコード作成     igns__RichMenu__c（領域ごとの ActionType{n} …）
④ 検証ループ       IsValid__c / ValidationErrors__c を読んで修正
⑤ LINE に発行      Actions API igns__LampPublishRichMenuAction
⑥ 適用             デフォルトメニュー（公式アカウント全体）/ 友だち個別の割当
⑦ 差し替え・削除   update モードで再発行 / igns__LampDeleteRichMenuAction
⑧ 分析             igns__LampGetRichMenuInsightsAction（LINE 統計をバージョン単位で）
```

タブ切り替えは「タブの数だけリッチメニューを作り、タブ部分の領域を `richmenuswitch` で互いにつなぐ」（→「タブ付きメニュー」）。

## 前提条件

- LAMP 基本パッケージ **1.157 以降**（発行・削除アクション、有効化エラー項目）。タブ付きレイアウト（`TAB*`）・自由配置（`igns__AreasJson__c`）・12 領域・バージョンと分析（`igns__RichMenuVersion__c` / `igns__LampGetRichMenuInsightsAction`）は **リッチメニュービルダー対応版以降**。項目やアクションが無く `No such column` / 404 になる org では、それらを使わず従来の範囲で行う
- `sf` CLI で対象 org に認証済み（以下 `<org>`）。API バージョン v67.0 以上
- 実行ユーザーに `LAMP_SystemAdministrator` または `LAMP_MarketingAdministrator` 権限セットグループ
- 公式アカウント（`igns__SocialAccount__c`）が接続済み
- **必ず最初に対象 org をユーザーに確認する**（顧客の本番 org を扱うため）

## 守ること

- **発行・デフォルト設定・削除は顧客の LINE 友だちの画面を即座に変える。** 実行前にユーザーの明示の承認を得る
- `igns__Json__c` / `igns__IsValid__c` / `igns__ValidationErrors__c` / `igns__RichMenuId__c` は書かない（トリガーと発行処理が管理する）
- 発行済みメニューの内容を変えたら、必ず ⑤ を `mode=update` で再発行する（レコードを変えただけでは LINE 側は変わらない。`igns__IsNeedUpdate__c=true` が「未反映」の印）
- 記録した Id は会話に残し、同じメニューを二重に作らない

## ① レイアウトの選択

```bash
sf data query -q "SELECT DeveloperName, igns__Width__c, igns__Height__c, igns__BoundsJson__c FROM igns__LampBound__mdt WHERE igns__Usage__c = 'Richmenu' ORDER BY igns__Order__c" -o <org>
```

`igns__BoundsJson__c` が領域の配列（`[{x,y,width,height}, …]`）で、配列の順が領域 A, B, C…（＝項目の番号 1, 2, 3…）。`igns__Width__c × igns__Height__c` が画像の寸法。
プリセット例: `EQUAL_SPLIT`（2500×843、左右 2 分割）、`MAIN_SIDE_SPLIT`（3 領域）、`GRID_6_EQUAL`（2500×1686、6 分割）、`FULL_BANNER`（1 領域）。

**タブ付きレイアウト**（`DeveloperName` が `TAB` で始まる）: 上端 220px がタブ見出しで、先頭の領域がタブ（左から A, B, C）、続いて本体。

| DeveloperName | サイズ | タブ | 本体 | 領域数 |
|---|---|---|---|---|
| `TAB2_FULL` / `TAB3_FULL` | 2500×1686 | 2 / 3 | 1枚 | 3 / 4 |
| `TAB2_GRID_3` / `TAB3_GRID_3` | 2500×1686 | 2 / 3 | 3列×1段 | 5 / 6 |
| `TAB2_GRID_6` / `TAB3_GRID_6` | 2500×1686 | 2 / 3 | 3列×2段 | 8 / 9 |
| `TAB3_GRID_9` | 2500×1686 | 3 | 3列×3段 | 12 |
| `TAB2_TRIPLE` / `TAB3_TRIPLE` | 2500×843 | 2 / 3 | 3列×1段 | 5 / 6 |

**自由配置**: プリセットに無い配置は、`igns__BoundName__c` を `CUSTOM` にし、`igns__AreasJson__c` に座標の配列（`[{"x":0,"y":0,"width":1250,"height":843}, …]`、整数・最大 12 個）、`igns__ImageWidth__c` / `igns__ImageHeight__c` に画像サイズ（2500×1686 か 2500×843）を入れる。各領域は画像の範囲内に収める。`igns__AreasJson__c` が入っていればプリセットより優先される。

ユーザーの要望（ボタン数・大小・タブの有無）に合うものを提示して選んでもらう。

## ② 画像の用意

`lamp-media-upload` スキルの種別 `richmenu` でアップロードし、返った公開 URL を `igns__ImageUrl__c` に入れる（`recordId` と `imageUrlField=igns__ImageUrl__c`、`uuidField=igns__Uuid__c` を渡せば完了アクションが直接書く）。

画像の制約（LINE）: JPEG / PNG、**幅 800〜2500 px・高さ 250 px 以上・幅÷高さ 1.45 以上・1 MB 以下**、かつ選んだプリセットの `Width__c × Height__c` に合わせる。アップロード前に `sips -g pixelWidth -g pixelHeight <file>` と `stat -f %z <file>` で確認する。

## ③ レコードの作成

```bash
cat > /tmp/rm.json <<'EOF'
{ "Name": "メインメニュー",
  "igns__SocialAccount__c": "<socialAccountId>",
  "igns__BoundName__c": "MAIN_SIDE_SPLIT",
  "igns__ChatBarText__c": "メニュー",
  "igns__IsSelected__c": true,
  "igns__ActionType1__c": "uri",      "igns__ActionUrl1__c": "https://example.com/plans",
  "igns__ActionType2__c": "postback", "igns__ActionTemplate2__c": "<templateId>", "igns__ActionMessage2__c": "資料請求",
  "igns__ActionType3__c": "callagent","igns__ActionReply3__c": "<replyId>", "igns__ActionMessage3__c": "相談する" }
EOF
sf api request rest "/services/data/v67.0/sobjects/igns__RichMenu__c" --method POST -b @/tmp/rm.json -o <org>
```

| 項目 | 内容 |
|---|---|
| `igns__SocialAccount__c` | 公式アカウント（必須） |
| `igns__BoundName__c` | ① の `DeveloperName`（必須） |
| `igns__ChatBarText__c` | トーク画面下部に出るバーの文字（14 文字以内。空なら「メニュー」） |
| `igns__IsSelected__c` | `true` なら最初から開いた状態で表示 |
| `igns__ImageUrl__c` | ② の公開 URL（発行時に必須） |

領域 n（1 始まり・最大 12。**アクションを設定しない領域はタップ領域にならない**（タブの「表示中のタブ」など）。ただしアクションが 1 つも無いメニューは無効）:

| `igns__ActionType{n}__c` | 意味 | 必須の相手項目 | 任意 |
|---|---|---|---|
| `uri` | リンクを開く | `igns__ActionUrl{n}__c`（http / https / line / tel のみ） | |
| `postback` | テンプレート呼出 | `igns__ActionTemplate{n}__c`（`igns__Template__c` の Id） | `igns__ActionMessage{n}__c`（タップ時にトークへ表示する文字）、`igns__ActionOption{n}__c`（`openKeyboard` など）、`igns__ActionFillInText{n}__c` |
| `callagent` | AI エージェント呼出 | `igns__ActionReply{n}__c`（`igns__Reply__c` の Id） | `igns__ActionMessage{n}__c`、`igns__ActionOption{n}__c`、`igns__ActionFillInText{n}__c` |
| `richmenuswitch` | 別のリッチメニューへ切替（タブ） | `igns__ActionRichMenu{n}__c`（切替先の `igns__RichMenu__c` の Id。**同じ公式アカウント**のメニュー。未発行でも設定・発行できるが、切替先を発行するまでタップしても切り替わらない） | |

Agentforce の自動応答を呼び出す場合は、`lamp-agentforce` で種別 `Agentforce` の自動応答を作成し、その Id を `ActionReply{n}` に設定する。

Botの受付メニューを開くなら `postback` で受付テンプレートを指定する。一式の構成は `lamp-bot`、固定案内とエージェント起動の違い・項目代入の保存先・現在会話への影響は [アクションの接続](../lamp-template/references/actions.md) を参照する。リッチメニューに `message` やimagemap専用の領域設定を混ぜない。

## タブ付きメニュー

LINE にタブの機能は無く、**タブの数だけリッチメニューを作り、タブの領域で互いに切り替える**（LINE の `richmenuswitch` とエイリアス）。

1. タブの数だけ `igns__RichMenu__c` を作る（例: 「ホーム」「学科紹介」「アクセス」）。すべて同じタブ付きレイアウト（例: `TAB3_GRID_6`）
2. 画像はタブごとに 1 枚。**タブ見出しも画像に描き、そのメニューのタブを「選択中」の見た目**にする（見出しの高さは 220px、横は均等割り）
3. 各メニューのタブ領域: 自分のタブは **アクションなし**、他のタブは `richmenuswitch` で対応するメニューを指定（例: ホームの A=なし・B=学科紹介・C=アクセス）
4. 本体の領域に通常のアクションを設定
5. ④ で全部 `IsValid__c=true` を確認 → ⑤ で **全部**発行（順番は問わない）
6. ⑥ でデフォルト（または友だちへの割当）には **最初に見せるタブ**（例: ホーム）だけを設定する。タップで切り替えたあとの表示は LINE が友だちごとに覚える

どれか 1 つを削除（⑦）すると、そのタブへの切り替えだけが効かなくなる。変更したメニューはそれだけ `update` で再発行すればよい（切り替え先の指定は変わらない）。

## ④ 検証ループ

```bash
sf data query -q "SELECT igns__IsValid__c, igns__ValidationErrors__c, igns__IsActive__c, igns__RichMenuId__c, igns__ImageUrl__c FROM igns__RichMenu__c WHERE Id = '<richMenuId>'" -o <org>
```

`igns__IsValid__c=false` なら `igns__ValidationErrors__c` の日本語の理由（「アクションが設定されていません。少なくとも1つの領域に…」「領域1のURIアクションにURLが設定されていません」「指定されたレイアウト名が見つかりません」「領域2が画像（2500×843px）の範囲からはみ出しています」「タップ領域は12個までです」等）に従って PATCH で直す。保存はブロックされないので、直して保存 → 再確認を繰り返す。

## ⑤ LINE に発行

```bash
cat > /tmp/pub.json <<'EOF'
{ "inputs": [ { "richMenuId": "<richMenuId>" } ] }
EOF
sf api request rest "/services/data/v67.0/actions/custom/apex/igns__LampPublishRichMenuAction" --method POST -b @/tmp/pub.json -o <org>
```

- `mode` を省略すると自動（`igns__RichMenuId__c` が空なら新規発行、あれば差し替え）。明示するなら `"mode": "create"` / `"mode": "update"`
- 成功: `outputValues.success=true`、`lineRichMenuId`（`richmenu-…`）、`isActive=true`。レコードの `igns__RichMenuId__c` / `igns__IsActive__c` も更新される
- 失敗: `success=false`、`message` に理由。設定不備なら `validationErrors` も返る

| `message` | 対処 |
|---|---|
| リッチメニューの設定が無効なため発行できません: … | ④ の理由を直す |
| 画像が設定されていません。… | ② を行い `igns__ImageUrl__c` を設定 |
| このリッチメニューは既に LINE に発行されています… | 差し替えなら `mode=update`（または省略） |
| …HTTP 400: 画像の寸法（W×Hpx）が対応していません… | ② の制約に合わせて作り直して上げ直す |
| …HTTP 400: 画像の容量が1MBを超えています… | 圧縮して上げ直す |
| …HTTP 400: LINEがリッチメニューの設定を受け付けませんでした。… `areas[0].action.data: …` | 示された項目（例: postback の data が長すぎる＝`ActionMessage` を短く）を直す |
| …HTTP 401 / 403 | サーバー認証（`lamp-setup`）か公式アカウント接続（`lamp-social-account-setup`）の問題。接続直後は最大 10 分待つ |

発行に失敗しても LINE 側に未完成のメニューは残らない（backend が回収する）ので、直してそのまま再発行してよい。

## ⑥ 適用

**デフォルトメニュー（公式アカウントの全友だち）**: 公式アカウントの `igns__DefaultRichMenu__c` に発行済みメニューの Id を入れる。処理は非同期なので `igns__RichMenuStatus__c` をポーリングする（`updating` → `valid` / `error`）。

```bash
sf api request rest "/services/data/v67.0/sobjects/igns__SocialAccount__c/<socialAccountId>" --method PATCH -b '{"igns__DefaultRichMenu__c":"<richMenuId>"}' -o <org>
sf data query -q "SELECT igns__RichMenuStatus__c, igns__RichMenuErrorMessage__c FROM igns__SocialAccount__c WHERE Id = '<socialAccountId>'" -o <org>
```

解除は `igns__DefaultRichMenu__c` を `null` に更新。未発行のメニューは選べない（参照フィルタで弾かれる）。

**友だち個別の割当**: `igns__SocialFriend__c.igns__RichMenu__c` に Id を入れる。同じく `igns__RichMenuStatus__c` をポーリング。解除は `null`。未発行のメニューを割り当てると `error`（「リッチメニューがLINEに発行されていません」）になる。

複数の友だちに一括で割り当てる場合は 1 件ずつ更新し、`valid` を確認してから次へ進む（1 トランザクションで大量更新すると非同期処理の上限に当たる）。

## ⑦ 差し替え・削除

- **内容の変更**: レコードを PATCH（アクション・レイアウト）→ ④ で有効を確認 → ⑤ を `mode=update`。画像だけ変える場合も ② で上げ直して ⑤ を `update`。LINE 側では新しいメニューが作られ、デフォルト設定・友だちの割当は自動で新しいメニューに付け替わる
- **削除**:

```bash
sf api request rest "/services/data/v67.0/actions/custom/apex/igns__LampDeleteRichMenuAction" --method POST -b '{"inputs":[{"richMenuId":"<richMenuId>"}]}' -o <org>
```

LINE 側から削除され、レコードは未発行（`igns__IsActive__c=false`、`igns__RichMenuId__c` 空）に戻る。デフォルトや友だちに割り当て中のメニューを削除すると、その人たちのメニューは消える。先に別メニューへ切り替えるか、ユーザーに影響を伝えて承認を得る。

## ⑧ 分析（LINE 統計）

LINE の統計（表示回数・表示人数・領域ごとのタップ数とタップした人数）を、バージョン単位で読む。LAMP のサーバーが毎日 LINE から取得したものを返すだけなので、何度呼んでも LINE の上限は使わない。

```bash
echo '{"inputs":[{"richMenuId":"<richMenuId>","includeDaily":false}]}' > /tmp/ins.json
sf api request rest "/services/data/v67.0/actions/custom/apex/igns__LampGetRichMenuInsightsAction" --method POST -b @/tmp/ins.json -o <org>
```

- 入力: `richMenuId`（必須）、`versionNumber`（省略時は使用中のバージョン）、`fromDate` / `toDate`（`YYYY-MM-DD`、日別の範囲）、`includeDaily`
- 出力: `status`（`ok` / `below_threshold`＝期間中にタップした人が 20 人未満で数値なし / `not_ready`＝発行の翌日から / `not_collected`）、`impressionCount`（表示回数）、`impressionUsers`（表示人数）、`clickCount`（全領域のタップ数）、`period`、`areasJson`（`[{letter, type, label, targetName, count, uniqueUsers, clickRate}]`、`clickRate`＝タップした人数÷表示人数）、`dailyJson`
- バージョンの一覧（数値は毎日 11 時に更新。レポートにも使える）:

```bash
sf data query -q "SELECT Name, igns__VersionNumber__c, igns__IsCurrent__c, igns__PublishedAt__c, igns__RetiredAt__c, igns__ImpressionCount__c, igns__ImpressionUsers__c, igns__ClickCount__c, igns__StatsStatus__c FROM igns__RichMenuVersion__c WHERE igns__RichMenu__c = '<richMenuId>' ORDER BY igns__VersionNumber__c DESC" -o <org>
```

読み方の注意:
- 数値は LINE の推定値（1% 前後の差）。統計は発行の翌日から。**`uniqueUsers`（人数）は日やバージョンをまたいで足さない**（重複する）。回数は足してよい
- **メニュー全体の「タップした人数」と「全体のクリック率」は LINE の API に無い**ので出せない（領域ごとの人数を足しても全体の人数にならない）
- 画面（リッチメニューの「分析」タブ）では、任意の期間・日別グラフ・CSV（LINE 公式アカウントマネージャーと同じ列）が使える

## トラブルシューティング

| 症状 | 原因と対処 |
|---|---|
| `IsValid__c` が `false` のまま | `ValidationErrors__c` の理由どおり項目を埋める。領域数はレイアウトの `BoundsJson__c` の要素数 |
| 発行は成功したのにスマホで画像が崩れる | 画像の寸法がプリセットの `Width__c × Height__c` と違う。作り直して `update` |
| `RichMenuStatus__c` が `updating` のまま長い | 非同期処理の失敗。`RichMenuErrorMessage__c` を確認し、値を一度 `null` にしてから再設定 |
| `richmenuswitch` で切り替わらない | 切替先が未発行（切替先を ⑤ で発行すれば、このメニューを再発行しなくても切り替わる）か、別の公式アカウントのメニューを指定している |
| 自由配置が無効（`IsValid__c=false`） | `AreasJson__c` の値が整数でない・画像の範囲外・13 個以上、または `ImageWidth__c` / `ImageHeight__c` が空 |
| 分析が `below_threshold` のまま | 期間中にタップした人が 20 人未満（LINE の仕様）。期間を広げると出ることがある |
| 発行で `HTTP 403` | 公式アカウント接続の直後（最大 10 分）か、サーバー認証切れ |
