# 📎 栞（Shiori）Discord Bot

Discord「シンギュラリティ・サーバー」常駐の未来予測記録係Bot。

2045年の東京大学から時間遡行してきた歴史情報学コースの学生という設定で、メンバーの未来予測を記録・分析し、サーバーの知的活動を支援します。

## ✨ 特徴

- **予測記録**: メンバーの未来予測を自動検出・記録
- **差分指摘**: 同一メンバーの過去予測との変化を指摘
- **的中判定**: 予測の答え合わせを「ついでに」確認
- **リンク要約**: 依頼されたURLの要約を提供
- **議論要約**: 長い議論スレッドの要約
- **信頼度システム**: 活発なメンバーには口調が砕ける（機能品質は全員平等）

## 🏗️ 設計原則

- **受動的**: メンション・返信で呼ばれたときだけ反応
- **非侵害**: 既存メンバーの役割（ニュースキュレーター、論客など）を侵害しない
- **非YESマン**: 楽観的予測にはプレモーテム質問で建設的な疑問を投げかける

## 📦 必要環境

- Python 3.10以上
- Discord Bot Token
- Anthropic API Key

## 🚀 セットアップ

### 1. リポジトリをクローン

```bash
git clone <repository-url>
cd shiori_bot
```

### 2. 仮想環境を作成（推奨）

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

### 3. 依存パッケージをインストール

```bash
pip install -r requirements.txt
```

### 4. 環境変数を設定

```bash
cp .env.example .env
# .envファイルを編集してトークンを設定
```

必須の環境変数：
- `DISCORD_TOKEN`: Discord Developer PortalでBotを作成して取得
- `ANTHROPIC_API_KEY`: Anthropic Consoleで取得

### 5. Discord Botの権限設定

Discord Developer Portalで以下の権限を付与：

**Bot Permissions:**
- Read Messages/View Channels
- Send Messages
- Read Message History
- Add Reactions
- Use Slash Commands（将来の拡張用）

**Privileged Gateway Intents:**
- Message Content Intent（必須）
- Server Members Intent（メンバー離脱検出用）

### 6. Botを起動

```bash
python bot.py
```

## 📁 プロジェクト構造

```
shiori_bot/
├── bot.py              # メインエントリーポイント
├── llm.py              # Claude API連携
├── trust.py            # 信頼度管理
├── predictions.py      # 予測記録・検索
├── categories.py       # カテゴリ管理
├── judgments.py        # 的中判定
├── profiles.py         # ユーザープロファイル
├── summarizer.py       # リンク要約
├── passive_monitor.py  # 受動監視
├── channel_config.py   # チャンネル設定
├── rate_limiter.py     # レート制限
├── reactions.py        # リアクション管理
├── errors.py           # エラーハンドリング
├── system_prompt.txt   # キャラクター定義
├── requirements.txt    # 依存パッケージ
├── .env.example        # 環境変数テンプレート
└── data/               # データファイル（自動生成）
    ├── members.json
    ├── predictions.json
    ├── categories.json
    ├── judgments.json
    └── channel_config.json
```

## 🎮 使い方

### 基本的な呼び方

```
@栞 これどう思う？
@栞 2030年までにAGIが実現すると思う
@栞 このリンク要約して https://example.com/article
@栞 さっきの議論まとめて
```

### 栞が反応するタイミング

| トリガー | 動作 |
|----------|------|
| @メンション | 通常応答 |
| 栞への返信 | 会話継続 |

※📎リアクションによるトリガーは廃止されました（Q2: B案）

### 信頼度の上げ方

| アクション | 変動 |
|------------|------|
| 栞に話しかける | +3 |
| 予測投稿 | +2 |
| 質問に回答 | +5 |
| 過去予測の振り返り | +7 |
| 記録の誤り訂正 | +5 |

## ⚙️ 設定

### チャンネル別振る舞い

`data/channel_config.json`でチャンネルごとの振る舞いを設定できます：

```json
{
  "channels": {
    "1234567890": {
      "type": "prediction",
      "custom_instructions": "予測記録を積極的に実施"
    }
  }
}
```

チャンネルタイプ：
- `prediction`: 予測チャンネル（予測記録を積極化）
- `casual`: 雑談チャンネル（カジュアルトーン）
- `vc`: VC連携（要約重視）
- `technical`: 技術系（専門用語OK）
- `general`: その他（LLM判断）

## 📊 データ形式

### 予測レコード

```json
{
  "prediction_id": "0001",
  "user_id": "123456789",
  "content": "2030年までにAGIが実現する",
  "category": "AI技術",
  "subcategory": "AGI",
  "timeline_start": 2030,
  "timeline_end": 2030,
  "created_at": "2026-02-12T10:00:00",
  "result": "pending"
}
```

### 判定レコード

```json
{
  "judgment_id": "j_0001_20260212",
  "prediction_id": "0001",
  "result": "hit",
  "judged_at": "2026-12-31T23:59:59",
  "notes": "GPT-6発表により的中",
  "confirmed": true
}
```

## 🔧 トラブルシューティング

### Botが反応しない

1. `Message Content Intent`が有効か確認
2. Botがチャンネルを閲覧できる権限があるか確認
3. レート制限中でないか確認（チャンネルごと30秒）

### エラーが発生する

栞はエラーもキャラクター口調で報告します：

```
「あっ、すみません……このリンク、うまく開けませんでした📎💦」
```

詳細なエラーはログファイルを確認してください。

## 📝 設計判断一覧

本Botは27項目の設計判断（Q1-Q27）に基づいて実装されています。詳細は`Shiori_Requirements_v3.1.md`を参照してください。

主要な決定：
- Q1: 自発的投稿なし（依頼ベースのみ）
- Q2: メンション+返信のみ応答
- Q10: Claude Haiku 4.5のみ使用（コスト効率）
- Q14: 全員Lv1スタート
- Q27: 的中判定は「ついでに」確認

## 📜 ライセンス

MIT License

## 🙏 謝辞

このBotは「シンギュラリティ・サーバー」の15ユーザー / 3,895件の投稿分析に基づいて設計されました。サーバーメンバーの皆様の活発な議論に感謝します。

---

*「📎しおり挟みました」— 栞*
