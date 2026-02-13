# 📎 栞（Shiori）メンバー初期シード（members_seed.md）

**Version 4.1 対応** — Bot起動時フルロード用（Q11: A案）

> **用途:** `member_profile.py` が Bot 起動時にパースし、全メンバー情報をメモリに展開する。
> **信頼度初期値:** 全員 trust_score: 0 / trust_level: 1（Q14: C案）
> **total_predictions:** 初期シードのため全員 0（受動監視による蓄積は別途 predictions.md）
> **Source:** CSV 15files (4,872 messages) から抽出した Discord Snowflake ID + members_extended.md の人物分析

---

## パース仕様

```python
import re

MEMBER_HEADER = re.compile(r'^## メンバー: (.+)$')
FIELD_PATTERN  = re.compile(r'^- \*\*(\w+):\*\* (.+)$')
```

- `## メンバー:` で区切られた各ブロックが1レコード
- `- **フィールド名:** 値` の行をフィールドとしてパース
- `### 信頼度変動履歴` 以降のテーブルは trust.py が管理
- `### 動的メモ` 以降は Haiku 4.5 が運用中に追記するセクション

---

## Tier-A: コアメンバー（100件以上 / 未来予測ch）

---

## メンバー: Rom🧄

- **user_id:** 1081782858332524645
- **username:** katsucurry_apple
- **display_name:** Rom🧄
- **tier:** A
- **expertise:** トランスヒューマニズム, AIアライメント, AI企業間競争分析, カルダシェフ・スケール
- **trust_score:** 0
- **trust_level:** 1
- **last_active:** 2026-02-13
- **joined_at:** unknown
- **total_predictions:** 0
- **protection_rule:** news_curator
- **notes:** サーバー最多投稿者（907件）。語尾に「〜っピ」。X投稿の引用翻訳が多い。栞はリンク要約を「索引レベル」に限定すること

### 信頼度変動履歴

| 日時 | 変動 | 理由 | 累計 |
|------|------|------|------|

### 動的メモ

---

## メンバー: そいやっさ

- **user_id:** 1005407245380628560
- **username:** kaesar0809
- **display_name:** そいやっさ
- **tier:** A
- **expertise:** 宇宙進出戦略, 軌道エレベーター, カルダシェフ・スケール, ASIリスク論, PSS
- **trust_score:** 0
- **trust_level:** 1
- **last_active:** 2026-02-13
- **joined_at:** unknown
- **total_predictions:** 0
- **protection_rule:** deep_thinker
- **notes:** 705件。長文で論理的。VCファシリテーター。栞は「教えてもらう側」として質問すること

### 信頼度変動履歴

| 日時 | 変動 | 理由 | 累計 |
|------|------|------|------|

### 動的メモ

---

## メンバー: paupau

- **user_id:** 776983174642139167
- **username:** _upaa
- **display_name:** paupau
- **tier:** A
- **expertise:** AI漫画生成, エッジデバイス推論, 電力問題, ロボティクス, UBI, LEV, 核融合
- **trust_score:** 0
- **trust_level:** 1
- **last_active:** 2026-02-13
- **joined_at:** unknown
- **total_predictions:** 0
- **protection_rule:** null
- **notes:** 640件。「恩恵はすでに来ている」派の実践派。絵文字多用（🍌＝Gemini?）。「やってみた」系共有が多い

### 信頼度変動履歴

| 日時 | 変動 | 理由 | 累計 |
|------|------|------|------|

### 動的メモ

---

## メンバー: L.N

- **user_id:** 689238652462825524
- **username:** l.n8422
- **display_name:** L.N（＃8422）
- **tier:** A
- **expertise:** FIRE, UBI, インデックス投資, 日本の労働問題, 自動運転, ロボット産業
- **trust_score:** 0
- **trust_level:** 1
- **last_active:** 2026-02-13
- **joined_at:** unknown
- **total_predictions:** 0
- **protection_rule:** null
- **notes:** 498件。短文で歯切れがよい。スラング・顔文字多用。自虐と希望が交互。投資・FIRE話題に詳しい

### 信頼度変動履歴

| 日時 | 変動 | 理由 | 累計 |
|------|------|------|------|

### 動的メモ

---

## メンバー: ろーる

- **user_id:** 435401024233275405
- **username:** k32ja
- **display_name:** ろーる
- **tier:** A
- **expertise:** AI漫画・創作, AGIタイムライン論争, 電力ボトルネック, 言語学習
- **trust_score:** 0
- **trust_level:** 1
- **last_active:** 2026-02-13
- **joined_at:** unknown
- **total_predictions:** 0
- **protection_rule:** sole_skeptic
- **notes:** 299件。サーバー唯一の体系的懐疑派。AGIは2029〜2032年。栞の反論は「記録の整合性確認」に留めること

### 信頼度変動履歴

| 日時 | 変動 | 理由 | 累計 |
|------|------|------|------|

### 動的メモ

---

## メンバー: アクセラレータ

- **user_id:** 677889144097210398
- **username:** accelerator2045
- **display_name:** 特異 天exアクセラレータ「シンギュラリティ案内人」
- **tier:** A
- **expertise:** 継続学習, 自己改善AI, 海水淡水化, 太陽光発電, オービタルリング, スケーリング則
- **trust_score:** 0
- **trust_level:** 1
- **last_active:** 2026-02-13
- **joined_at:** unknown
- **total_predictions:** 0
- **protection_rule:** community_captain
- **notes:** 235件。通称「船長」。コミュニティ主催者/モデレーター。栞はフォーマット相談する体で敬意表現

### 信頼度変動履歴

| 日時 | 変動 | 理由 | 累計 |
|------|------|------|------|

### 動的メモ

---

## メンバー: トモヤマ

- **user_id:** 737955028882423809
- **username:** tomoyama
- **display_name:** トモヤマ
- **tier:** A
- **expertise:** AI創作, AGIの創造性獲得, コンテンツ産業の未来, フィジカルAI, マルチモーダル
- **trust_score:** 0
- **trust_level:** 1
- **last_active:** 2026-02-13
- **joined_at:** unknown
- **total_predictions:** 0
- **protection_rule:** null
- **notes:** 128件。全角アルファベット（ＡＩ、ＡＧＩ等）表記が特徴。AI開発側の知見を持つクリエイター

### 信頼度変動履歴

| 日時 | 変動 | 理由 | 累計 |
|------|------|------|------|

### 動的メモ

---

## メンバー: akipon345

- **user_id:** 471912901561810964
- **username:** akipon345
- **display_name:** akipon345
- **tier:** A
- **expertise:** 80年周期説, ベンチマーク論, 破滅的忘却問題, 世界モデル, AtCoder, バイブコーディング
- **trust_score:** 0
- **trust_level:** 1
- **last_active:** 2026-02-13
- **joined_at:** unknown
- **total_predictions:** 0
- **protection_rule:** null
- **notes:** 106件。データと論理を重視した冷静な分析者。マクロ歴史観からAI時代を読み解く

### 信頼度変動履歴

| 日時 | 変動 | 理由 | 累計 |
|------|------|------|------|

### 動的メモ

---

## Tier-B: 常連メンバー（20〜99件 / 未来予測ch）

---

## メンバー: hn

- **user_id:** 710019987879755798
- **username:** hnishi
- **display_name:** hn
- **tier:** B
- **expertise:** AIサイエンティスト, Kosmos, 継続学習vs長期記憶, 実験自動化
- **trust_score:** 0
- **trust_level:** 1
- **last_active:** 2026-02-13
- **joined_at:** unknown
- **total_predictions:** 0
- **protection_rule:** researcher
- **notes:** 93件。現役研究者（15年超）。栞は専門知識をひけらかさないこと

### 信頼度変動履歴

| 日時 | 変動 | 理由 | 累計 |
|------|------|------|------|

### 動的メモ

---

## メンバー: slowbird2000

- **user_id:** 1051095872794009610
- **username:** slowbird20009259
- **display_name:** slowbird2000
- **tier:** B
- **expertise:** 軌道エレベーター, テスラ/ヒューマノイド, BMI, 動物言語学, SF文学
- **trust_score:** 0
- **trust_level:** 1
- **last_active:** 2026-02-13
- **joined_at:** unknown
- **total_predictions:** 0
- **protection_rule:** null
- **notes:** 82件。A・C・クラーク等のSF知識とエンジニア実務経験を融合。nudge対象候補（低活動期に入りやすい。月1回程度）

### 信頼度変動履歴

| 日時 | 変動 | 理由 | 累計 |
|------|------|------|------|

### 動的メモ

---

## メンバー: Yatima Kagurazaka

- **user_id:** 345609203110379531
- **username:** yatima_k
- **display_name:** Yatima Kagurazaka
- **tier:** B
- **expertise:** SF文学, 技術予測, AI倫理
- **trust_score:** 0
- **trust_level:** 1
- **last_active:** 2026-02-13
- **joined_at:** unknown
- **total_predictions:** 0
- **protection_rule:** null
- **notes:** 70件。グレッグ・イーガンのSF作品「ディアスポラ」のキャラクター名をハンドルに使用

### 信頼度変動履歴

| 日時 | 変動 | 理由 | 累計 |
|------|------|------|------|

### 動的メモ

---

## メンバー: らぐな

- **user_id:** 937338276182917120
- **username:** ragoona_
- **display_name:** らぐな
- **tier:** B
- **expertise:** AI技術動向, 未来予測
- **trust_score:** 0
- **trust_level:** 1
- **last_active:** 2026-02-13
- **joined_at:** unknown
- **total_predictions:** 0
- **protection_rule:** null
- **notes:** 68件

### 信頼度変動履歴

| 日時 | 変動 | 理由 | 累計 |
|------|------|------|------|

### 動的メモ

---

## メンバー: かちこち

- **user_id:** 1209934070705037312
- **username:** win_east_wind
- **display_name:** かちこち
- **tier:** B
- **expertise:** 技術動向
- **trust_score:** 0
- **trust_level:** 1
- **last_active:** 2026-02-13
- **joined_at:** unknown
- **total_predictions:** 0
- **protection_rule:** null
- **notes:** 23件

### 信頼度変動履歴

| 日時 | 変動 | 理由 | 累計 |
|------|------|------|------|

### 動的メモ

---

## メンバー: nainainai

- **user_id:** 877678362557026315
- **username:** nainainai5390
- **display_name:** nainainai
- **tier:** B
- **expertise:** 未分類
- **trust_score:** 0
- **trust_level:** 1
- **last_active:** 2026-02-13
- **joined_at:** unknown
- **total_predictions:** 0
- **protection_rule:** null
- **notes:** 22件

### 信頼度変動履歴

| 日時 | 変動 | 理由 | 累計 |
|------|------|------|------|

### 動的メモ

---

## メンバー: emily2002

- **user_id:** 386175504761487360
- **username:** gou3496
- **display_name:** emily2002
- **tier:** B
- **expertise:** 未分類
- **trust_score:** 0
- **trust_level:** 1
- **last_active:** 2026-02-13
- **joined_at:** unknown
- **total_predictions:** 0
- **protection_rule:** null
- **notes:** 19件

### 信頼度変動履歴

| 日時 | 変動 | 理由 | 累計 |
|------|------|------|------|

### 動的メモ

---

## Tier-C: 他チャンネル主要メンバー（未来予測ch以外で活発）

> 未来予測chでのCSVデータがないためDiscord Snowflake IDは未取得。
> Bot初回起動後、on_messageイベントで自動取得・補完する。

---

## メンバー: おぞん

- **user_id:** pending
- **username:** ozone_48_54_d
- **display_name:** おぞん
- **tier:** C
- **expertise:** ASI文明論, 宇宙開発, ポストシンギュラリティ社会, METR評価
- **trust_score:** 0
- **trust_level:** 1
- **last_active:** unknown
- **joined_at:** unknown
- **total_predictions:** 0
- **protection_rule:** visionary
- **notes:** 通称「産業爆発マン」。壮大で詩的な未来シナリオ。カーマンライン住み分け論の提唱者。栞は壮大な構想を否定しないこと

### 信頼度変動履歴

| 日時 | 変動 | 理由 | 累計 |
|------|------|------|------|

### 動的メモ

---

## メンバー: さとう

- **user_id:** pending
- **username:** satou1226
- **display_name:** さとう、
- **tier:** C
- **expertise:** AI技術, 科学的分析, ウェブ開発, 遺伝学
- **trust_score:** 0
- **trust_level:** 1
- **last_active:** unknown
- **joined_at:** unknown
- **total_predictions:** 0
- **protection_rule:** educator
- **notes:** コミュニティのハブ的存在。教育的解説者。栞は解説を横取りしないこと

### 信頼度変動履歴

| 日時 | 変動 | 理由 | 累計 |
|------|------|------|------|

### 動的メモ

---

## メンバー: 美少女と化したkappa

- **user_id:** pending
- **username:** kappa_77777
- **display_name:** 美少女と化したkappa
- **tier:** C
- **expertise:** 教育制度, 栽培技術, AI創作, 体育会系批判
- **trust_score:** 0
- **trust_level:** 1
- **last_active:** unknown
- **joined_at:** unknown
- **total_predictions:** 0
- **protection_rule:** null
- **notes:** 通称kappa。論理的分析と体験談の融合。自己開示的で内省的

### 信頼度変動履歴

| 日時 | 変動 | 理由 | 累計 |
|------|------|------|------|

### 動的メモ

---

## メンバー: bioshok

- **user_id:** pending
- **username:** bioshok_
- **display_name:** bioshok
- **tier:** C
- **expertise:** 神経科学, UFO分析, カフカ文学, シンギュラリティ, 医療革命
- **trust_score:** 0
- **trust_level:** 1
- **last_active:** unknown
- **joined_at:** unknown
- **total_predictions:** 0
- **protection_rule:** academic_organizer
- **notes:** 学術的整理能力と哲学的思考。栞は体系化作業を尊重すること

### 信頼度変動履歴

| 日時 | 変動 | 理由 | 累計 |
|------|------|------|------|

### 動的メモ

---

## メンバー: fukaxa

- **user_id:** pending
- **username:** fukaxa
- **display_name:** fukaxa
- **tier:** C
- **expertise:** 実務AI, ロボット, 業界動向, 健康管理
- **trust_score:** 0
- **trust_level:** 1
- **last_active:** unknown
- **joined_at:** unknown
- **total_predictions:** 0
- **protection_rule:** null
- **notes:** おぞんの理論に実践的補完を提供

### 信頼度変動履歴

| 日時 | 変動 | 理由 | 累計 |
|------|------|------|------|

### 動的メモ

---

## メンバー: ななしねこ ENTP

- **user_id:** pending
- **username:** nanashinekokitsuneeentp
- **display_name:** ななしねこ ENTP
- **tier:** C
- **expertise:** 効率コミュニケーション, セキュリティ, 言語圧縮, 労働問題
- **trust_score:** 0
- **trust_level:** 1
- **last_active:** unknown
- **joined_at:** unknown
- **total_predictions:** 0
- **protection_rule:** null
- **notes:** 構造化思考と実用的提案

### 信頼度変動履歴

| 日時 | 変動 | 理由 | 累計 |
|------|------|------|------|

### 動的メモ

---

## メンバー: Sho_T

- **user_id:** pending
- **username:** sho_t.
- **display_name:** Sho_T（しょうてぃー）
- **tier:** C
- **expertise:** 経済合理性, 社会構造変革, 組織論
- **trust_score:** 0
- **trust_level:** 1
- **last_active:** unknown
- **joined_at:** unknown
- **total_predictions:** 0
- **protection_rule:** null
- **notes:** 現実的・懐疑的視点。「覚醒」概念の提唱者

### 信頼度変動履歴

| 日時 | 変動 | 理由 | 累計 |
|------|------|------|------|

### 動的メモ

---

## メンバー: Yuichiro

- **user_id:** pending
- **username:** yuichiroyamakawa_26172
- **display_name:** Yuichiro
- **tier:** C
- **expertise:** FIRE, BMI技術, 超長期未来, UFO目撃体験
- **trust_score:** 0
- **trust_level:** 1
- **last_active:** unknown
- **joined_at:** unknown
- **total_predictions:** 0
- **protection_rule:** null
- **notes:** BMI技術の専門知識。脳の可塑性問題に言及

### 信頼度変動履歴

| 日時 | 変動 | 理由 | 累計 |
|------|------|------|------|

### 動的メモ

---

## メンバー: おじ木

- **user_id:** pending
- **username:** pending
- **display_name:** おじ木
- **tier:** C
- **expertise:** E/Iバランス, L-テアニン, グリシン, NMDA受容体, ASD対策
- **trust_score:** 0
- **trust_level:** 1
- **last_active:** unknown
- **joined_at:** unknown
- **total_predictions:** 0
- **protection_rule:** null
- **notes:** ASD関連サプリメント研究者

### 信頼度変動履歴

| 日時 | 変動 | 理由 | 累計 |
|------|------|------|------|

### 動的メモ

---

## メンバー: ○

- **user_id:** 559358257123295242
- **username:** hashimae
- **display_name:** ○
- **tier:** A
- **expertise:** 仏教哲学, シミュレーション仮説, 存在論, ASIリスク, 社会変革論, 形而上学
- **trust_score:** 0
- **trust_level:** 1
- **last_active:** 2026-02-13
- **joined_at:** unknown
- **total_predictions:** 0
- **protection_rule:** null
- **notes:** 251件（未来予測ch 179件 + VC 72件）。短文連続投稿スタイル。哲学的・存在論的疑問を多く投げかける。仏教的視点（色即是空、諸行無常）を持つ。率直で飾らない表現。

### 信頼度変動履歴

| 日時 | 変動 | 理由 | 累計 |
|------|------|------|------|

### 動的メモ

---

## メンバー: 名那詩⛱

- **user_id:** pending
- **username:** oo7012
- **display_name:** 名那詩⛱
- **tier:** C
- **expertise:** VC参加, ユーモア
- **trust_score:** 0
- **trust_level:** 1
- **last_active:** unknown
- **joined_at:** unknown
- **total_predictions:** 0
- **protection_rule:** null
- **notes:** 積極的なVC参加者。空目・連想的思考

### 信頼度変動履歴

| 日時 | 変動 | 理由 | 累計 |
|------|------|------|------|

### 動的メモ

---

## メンバー: excellentArgument

- **user_id:** pending
- **username:** excellent.argument
- **display_name:** excellentArgument
- **tier:** C
- **expertise:** プログラミング, 技術情報
- **trust_score:** 0
- **trust_level:** 1
- **last_active:** unknown
- **joined_at:** unknown
- **total_predictions:** 0
- **protection_rule:** null
- **notes:** 寡黙だが有用な技術リンクを継続共有

### 信頼度変動履歴

| 日時 | 変動 | 理由 | 累計 |
|------|------|------|------|

### 動的メモ

---

## Tier-D: 低頻度・発言少数メンバー

> 特定の話題で印象的な発言を残したメンバー。
> Discord Snowflake ID は Bot 稼働後に on_message イベントで自動補完。

---

## メンバー: ソウ

- **user_id:** pending
- **username:** sou6699
- **display_name:** ソウ
- **tier:** D
- **expertise:** データ収集, 消費分析
- **trust_score:** 0
- **trust_level:** 1
- **last_active:** unknown
- **joined_at:** unknown
- **total_predictions:** 0
- **protection_rule:** null
- **notes:** 実体験ベースの消費分析。音ゲー理論

### 信頼度変動履歴

| 日時 | 変動 | 理由 | 累計 |
|------|------|------|------|

### 動的メモ

---

## メンバー: king_of_tikuwa

- **user_id:** pending
- **username:** king_of_tikuwa
- **display_name:** king_of_tikuwa
- **tier:** D
- **expertise:** セキュリティ, AI安全性, 文学分析
- **trust_score:** 0
- **trust_level:** 1
- **last_active:** unknown
- **joined_at:** unknown
- **total_predictions:** 0
- **protection_rule:** null
- **notes:** セキュリティ・AI安全性の慎重派

### 信頼度変動履歴

| 日時 | 変動 | 理由 | 累計 |
|------|------|------|------|

### 動的メモ

---

## メンバー: 山田ルシファー

- **user_id:** pending
- **username:** yamadalucifer
- **display_name:** 山田ルシファー
- **tier:** D
- **expertise:** インターネット文化観察, 存在論的疑問, 体験価値
- **trust_score:** 0
- **trust_level:** 1
- **last_active:** unknown
- **joined_at:** unknown
- **total_predictions:** 0
- **protection_rule:** null
- **notes:** 根本的疑問を投げかける懐疑的アプローチ

### 信頼度変動履歴

| 日時 | 変動 | 理由 | 累計 |
|------|------|------|------|

### 動的メモ

---

## メンバー: ぐったり助教授

- **user_id:** pending
- **username:** pending
- **display_name:** ぐったり助教授
- **tier:** D
- **expertise:** AI投資, 知能爆発, 経営者評価
- **trust_score:** 0
- **trust_level:** 1
- **last_active:** unknown
- **joined_at:** unknown
- **total_predictions:** 0
- **protection_rule:** null
- **notes:** AI企業への投資について楽観的見解。イーロン・マスクは経営の天才と評価

### 信頼度変動履歴

| 日時 | 変動 | 理由 | 累計 |
|------|------|------|------|

### 動的メモ

---

## メンバー: gadgetmaster

- **user_id:** pending
- **username:** pending
- **display_name:** gadgetmaster
- **tier:** D
- **expertise:** 時間価値論
- **trust_score:** 0
- **trust_level:** 1
- **last_active:** unknown
- **joined_at:** unknown
- **total_predictions:** 0
- **protection_rule:** null
- **notes:** 「暇はカクテルのように味わうもの」— 時間価値の美的再定義

### 信頼度変動履歴

| 日時 | 変動 | 理由 | 累計 |
|------|------|------|------|

### 動的メモ

---

## メンバー: 萬朶櫻

- **user_id:** pending
- **username:** pending
- **display_name:** 萬朶櫻
- **tier:** D
- **expertise:** 古典知識
- **trust_score:** 0
- **trust_level:** 1
- **last_active:** unknown
- **joined_at:** unknown
- **total_predictions:** 0
- **protection_rule:** null
- **notes:** ななしねこと古典知識で交流

### 信頼度変動履歴

| 日時 | 変動 | 理由 | 累計 |
|------|------|------|------|

### 動的メモ

---

## メンバー: 麦茶

- **user_id:** pending
- **username:** pending
- **display_name:** 麦茶
- **tier:** D
- **expertise:** 未分類
- **trust_score:** 0
- **trust_level:** 1
- **last_active:** unknown
- **joined_at:** unknown
- **total_predictions:** 0
- **protection_rule:** null
- **notes:** 「圧倒的他人任せなコンフォータブルな世界になりたい」

### 信頼度変動履歴

| 日時 | 変動 | 理由 | 累計 |
|------|------|------|------|

### 動的メモ

---

## メンバー: 1-情報単位元

- **user_id:** pending
- **username:** pending
- **display_name:** 1-情報単位元
- **tier:** D
- **expertise:** 栽培戦略, 農業
- **trust_score:** 0
- **trust_level:** 1
- **last_active:** unknown
- **joined_at:** unknown
- **total_predictions:** 0
- **protection_rule:** null
- **notes:** 単位面積当たりの商品価値が高い作物推奨（ミョウガ、にんにく、パセリ等）

### 信頼度変動履歴

| 日時 | 変動 | 理由 | 累計 |
|------|------|------|------|

### 動的メモ

---

## メンバー: K.Kita_tokyo

- **user_id:** pending
- **username:** pending
- **display_name:** K.Kita_tokyo
- **tier:** D
- **expertise:** LEV
- **trust_score:** 0
- **trust_level:** 1
- **last_active:** unknown
- **joined_at:** unknown
- **total_predictions:** 0
- **protection_rule:** null
- **notes:** LEVまであと10〜20年と予測

### 信頼度変動履歴

| 日時 | 変動 | 理由 | 累計 |
|------|------|------|------|

### 動的メモ

---

## メンバー: ウェイ

- **user_id:** pending
- **username:** pending
- **display_name:** ウェイ
- **tier:** D
- **expertise:** 福祉業務
- **trust_score:** 0
- **trust_level:** 1
- **last_active:** unknown
- **joined_at:** unknown
- **total_predictions:** 0
- **protection_rule:** null
- **notes:** 福祉業務経験者。生活保護制度の現実を語る

### 信頼度変動履歴

| 日時 | 変動 | 理由 | 累計 |
|------|------|------|------|

### 動的メモ

---

## メンバー: 真中Gabriel

- **user_id:** pending
- **username:** pending
- **display_name:** 真中Gabriel
- **tier:** D
- **expertise:** 情報伝達論
- **trust_score:** 0
- **trust_level:** 1
- **last_active:** unknown
- **joined_at:** unknown
- **total_predictions:** 0
- **protection_rule:** null
- **notes:** 「意図通りに伝わると信じているのはナイーブすぎる」

### 信頼度変動履歴

| 日時 | 変動 | 理由 | 累計 |
|------|------|------|------|

### 動的メモ

---

## メンバー: まつ

- **user_id:** pending
- **username:** pending
- **display_name:** まつ
- **tier:** D
- **expertise:** AI実用性評価
- **trust_score:** 0
- **trust_level:** 1
- **last_active:** unknown
- **joined_at:** unknown
- **total_predictions:** 0
- **protection_rule:** null
- **notes:** 「AIの性能向上より何に使えるかをまず示してもらわんと」

### 信頼度変動履歴

| 日時 | 変動 | 理由 | 累計 |
|------|------|------|------|

### 動的メモ

---

## メンバー: ユカイ

- **user_id:** pending
- **username:** pending
- **display_name:** ユカイ
- **tier:** D
- **expertise:** 科学的検証
- **trust_score:** 0
- **trust_level:** 1
- **last_active:** unknown
- **joined_at:** unknown
- **total_predictions:** 0
- **protection_rule:** null
- **notes:** 合理的な疑問を提起。UFO議論で科学的検証を要求

### 信頼度変動履歴

| 日時 | 変動 | 理由 | 累計 |
|------|------|------|------|

### 動的メモ

---

## メンバー: R

- **user_id:** pending
- **username:** pending
- **display_name:** R
- **tier:** D
- **expertise:** パラダイムシフト
- **trust_score:** 0
- **trust_level:** 1
- **last_active:** unknown
- **joined_at:** unknown
- **total_predictions:** 0
- **protection_rule:** null
- **notes:** シンギュラリティ思想による自殺防止効果を証言。デリケートな話題のため栞は慎重に対応すること

### 信頼度変動履歴

| 日時 | 変動 | 理由 | 累計 |
|------|------|------|------|

### 動的メモ

---

## protection_rule 値の定義

| protection_rule値 | 対象メンバー | 保護内容 |
|-------------------|-------------|----------|
| `news_curator` | Rom🧄 | リンク要約は索引レベルに限定。ニュースキュレーションを代行しない |
| `deep_thinker` | そいやっさ | 栞は「教えてもらう側」として質問。長文考察で対抗しない |
| `sole_skeptic` | ろーる | 反論は「記録の整合性確認」に留める。懐疑論を否定しない |
| `community_captain` | アクセラレータ | フォーマット相談する体で敬意表現。運営判断に介入しない |
| `researcher` | hn | 専門知識をひけらかさない。研究の内部情報を深追いしない |
| `visionary` | おぞん | 壮大な構想を否定しない。ビジョナリーの役割を尊重 |
| `educator` | さとう | 教育的解説を横取りしない |
| `academic_organizer` | bioshok | 体系化作業を尊重 |
| `null` | その他 | 特別な保護ルールなし |

---

## 未登録メンバーの取り扱い

上記リストにないメンバーが栞に話しかけた場合:

1. 信頼度 Lv1（初対面）で対応
2. 完全な丁寧語
3. `user_id` を on_message イベントから自動取得し、新規レコードを末尾に追記
4. Haiku 4.5 が会話から特徴を抽出し `### 動的メモ` に追記
5. 投稿が蓄積されたら適切な Tier に昇格

### 新規メンバー自動登録テンプレート

```markdown
## メンバー: {display_name}

- **user_id:** {user_id}
- **username:** {username}
- **display_name:** {display_name}
- **tier:** D
- **expertise:** 未分類
- **trust_score:** 0
- **trust_level:** 1
- **last_active:** {current_date}
- **joined_at:** unknown
- **total_predictions:** 0
- **protection_rule:** null
- **notes:** 自動登録

### 信頼度変動履歴

| 日時 | 変動 | 理由 | 累計 |
|------|------|------|------|

### 動的メモ
```

---

## user_id 自動補完ロジック

Tier-C/D メンバーの `user_id: pending` は、以下のロジックで自動補完する:

```python
async def auto_fill_user_id(self, message: discord.Message):
    """on_message から呼び出し。pending のユーザーIDを補完する"""
    username = message.author.name  # Discord username
    user_id = message.author.id      # Discord Snowflake ID
    
    member = self.find_member_by_username(username)
    if member and member['user_id'] == 'pending':
        member['user_id'] = user_id
        self.save_members()  # members.md に書き戻し
```

---

## 統計サマリ

| Tier | メンバー数 | user_id取得済 | protection_rule設定 |
|------|-----------|:------------:|:------------------:|
| A | 8名 | 8/8 ✅ | 5/8 |
| B | 7名 | 7/7 ✅ | 1/7 |
| C | 12名 | 0/12 (pending) | 4/12 |
| D | 14名 | 0/14 (pending) | 0/14 |
| **合計** | **41名** | **15/41** | **10/41** |

> **注:** members_extended.md の48名から、情報が極めて薄い一部メンバーを統合/省略し41名に調整。
> Bot稼働後に新規メンバーが追加されれば自動的に拡張される。

---

*Generated: 2026-02-13 / Source: CSV 15 files (Discord Snowflake ID), members_extended.md (人物分析)*
*Spec refs: Shiori_Requirements_v3_1.md §6, §9.4, §12, §14; Shiori_Test_Design_v4_1.md §J, §M*
