# 栞（Shiori）Discord Bot v4.1

2045年から来た時間遡行研究者「栞」として、未来予測コミュニティの記録係を務めるDiscord Botです。

## セットアップ

### 1. 環境変数の設定

`.env.example` を `.env` にコピーして編集：

```bash
cp .env.example .env
```

必須の環境変数：
- `DISCORD_TOKEN`: Discord Bot Token
- `ANTHROPIC_API_KEY`: Anthropic API Key

オプション：
- `MAIN_CHANNEL_CATEGORY_ID`: 監視対象のチャンネルカテゴリID（未設定時は全チャンネル）

### 2. 依存パッケージのインストール

```bash
pip install -r requirements.txt
```

### 3. 起動

```bash
python bot.py
```

## ファイル構成

```
shiori_v41/
├── bot.py                 # メインBotモジュール
├── llm.py                 # Claude API クライアント
├── trust.py               # 信頼度管理
├── predictions.py         # 予測台帳
├── categories.py          # カテゴリ分類
├── timeline.py            # 時間軸解析
├── nudge.py               # 低活動メンバーnudge
├── summarizer.py          # リンク要約
├── passive_monitor.py     # 受動監視
├── channel_config.py      # チャンネル別設定
├── rate_limiter.py        # レート制限
├── member_profile.py      # メンバープロファイル
├── errors.py              # エラーハンドリング
├── reactions.py           # 絵文字リアクション
├── system_prompt.txt      # キャラクター設定
├── requirements.txt       # 依存パッケージ
├── Procfile               # Railway用
├── .env.example           # 環境変数サンプル
└── data/
    ├── members.md             # メンバー台帳
    ├── members_extended.md    # 拡張プロファイル
    ├── predictions.md         # 予測台帳
    ├── categories.md          # カテゴリマスタ
    ├── index.md               # 予測インデックス
    ├── community_lexicon.md   # コミュニティ用語
    └── consensus_tracker.md   # コンセンサス情報
```

## 主要機能

1. **予測記録** - メンバーの未来予測を自動検出・記録
2. **差分指摘** - 過去予測との変化を指摘
3. **プレモーテム質問** - 楽観的予測へのリスク質問
4. **リンク要約** - URLの内容を索引レベルで要約
5. **議論まとめ** - 複数人の議論を公平に整理
6. **信頼度システム** - メンバーの活動に応じた5段階レベル

## Railway デプロイ

1. GitHubにリポジトリを作成してプッシュ
2. Railwayで新規プロジェクト作成
3. GitHubリポジトリを接続
4. 環境変数を設定
5. デプロイ

## ライセンス

Private - All Rights Reserved
