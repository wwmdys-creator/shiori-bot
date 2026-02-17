# 📎 栞（Shiori）モジュール間インターフェース契約書

**Version 5.3 対応** — 全20モジュール＋1テキストファイルの公開API仕様

作成日: 2026-02-13  
v5.3更新日: 2026-02-17  
目的: COMMON_MISTAKES §10（クロスモジュール不整合）、§12（リネーム参照漏れ）、§13（sync/async不整合）、§14（データフォーマット変換層欠如）、§15（未実装メソッド呼び出し）、N-01〜N-04（v5.3固有エラー）の再発防止

---

## 0. 本文書の使い方

**コード生成前に必ず確認すること:**
1. 実装するモジュールの「公開API」セクションを読む
2. 「依存先」列のモジュールの公開APIと引数を照合する
3. 「データ変換境界」セクションで内部形式 ↔ 外部API形式の変換ポイントを確認する
4. async/sync の一致を確認する（本文書で `async` と明記されたメソッドは必ず `async def` で実装）

**モジュール変更時:**
- クラス名・メソッド名・引数を変更する場合、本文書の該当セクション＋「依存マトリクス」（§1）を更新
- `grep -rn "from {module} import\|import {module}" *.py` で全呼び出し元を確認

---

## 1. 依存マトリクス

### 1.1 モジュール一覧

```
shiori_bot/
├── bot.py              # Discordイベント処理（メイン）
├── llm.py              # Anthropic Claude API インターフェース
├── trust.py            # 信頼度管理
├── predictions.py      # 予測台帳の記録・検索・差分検出
├── categories.py       # カテゴリ管理
├── timeline.py         # 時間軸解析
├── nudge.py            # 低活動メンバーnudge
├── summarizer.py       # リンク要約（ページ取得＋プロンプト構築）
├── passive_monitor.py  # 受動監視モジュール
├── channel_config.py   # チャンネル別設定
├── rate_limiter.py     # レート制限
├── member_profile.py   # メンバープロファイル管理
├── errors.py           # エラーハンドリング
├── reactions.py        # 絵文字リアクション管理
├── config.py           # 定数・設定値一元管理（★v5.3追加）
├── reaction_handler.py # ハートリアクション＋遅延リアクション（★v5.3追加）
├── response_mode.py    # 記録/自由モード判定（★v5.3追加）
├── trust_level_up.py   # 信頼度レベル昇格検出（★v5.3追加）
├── daily_maintenance.py     # 日次メンテナンスタスク（★v5.3追加）
├── weekly_monologue.py      # 週次独り言タスク（★v5.3追加）
├── prediction_highlighter.py # 予測ハイライト選定（★v5.3追加）
├── discussion_summary.py    # 議論まとめ機能（★v5.3追加）
├── response_generator.py    # 応答生成（★v5.3追加）
├── system_prompt.txt   # キャラクター定義テキスト
└── data/               # Markdownデータファイル
```

### 1.2 import 依存表

行が「呼び出し元」、列が「呼び出し先」。`✅` = import する。

| 呼び出し元 ＼ 先 → | llm | trust | predictions | categories | timeline | nudge | summarizer | passive_monitor | channel_config | rate_limiter | member_profile | errors | reactions | config | reaction_handler | response_mode | trust_level_up | prediction_highlighter | daily_maintenance | weekly_monologue | discussion_summary | response_generator |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **bot.py** | ✅ | ✅ | ✅ | — | — | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **llm.py** | — | — | — | — | — | — | — | — | — | — | ✅ | ✅ | — | — | — | — | — | — | — | — | — | — |
| **trust.py** | — | — | — | — | — | — | — | — | — | — | — | — | — | ✅ | — | — | — | — | — | — | — | — |
| **predictions.py** | ✅ | — | — | ✅ | ✅ | — | — | — | — | — | — | ✅ | — | — | — | — | — | — | — | — | — | — |
| **categories.py** | ✅ | — | — | — | — | — | — | — | — | — | — | ✅ | — | — | — | — | — | — | — | — | — | — |
| **timeline.py** | ✅ | — | — | — | — | — | — | — | — | — | — | ✅ | — | — | — | — | — | — | — | — | — | — |
| **nudge.py** | ✅ | — | — | — | — | — | — | — | — | — | ✅ | ✅ | — | — | — | — | — | — | — | — | — | — |
| **summarizer.py** | ✅ | — | — | — | — | — | — | — | — | — | — | ✅ | — | — | — | — | — | — | — | — | — | — |
| **passive_monitor.py** | ✅ | — | ✅ | ✅ | ✅ | — | — | — | ✅ | — | — | ✅ | — | — | — | — | — | — | — | — | — | — |
| **reactions.py** | — | — | — | — | — | — | — | — | — | — | — | — | — | — | ✅ | — | — | — | — | — | — | — |
| **reaction_handler.py** | — | — | — | — | — | — | — | — | — | — | — | — | — | ✅ | — | — | — | — | — | — | — | — |
| **response_mode.py** | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — |
| **trust_level_up.py** | — | — | — | — | — | — | — | — | — | — | — | — | — | ✅ | ✅ | — | — | — | — | — | — | — |
| **daily_maintenance.py** | — | ✅ | — | — | — | — | — | — | — | — | — | — | — | ✅ | — | — | — | ✅ | — | — | — | — |
| **weekly_monologue.py** | — | — | — | — | — | — | — | — | — | — | — | — | — | ✅ | — | — | — | — | — | — | — | — |
| **prediction_highlighter.py** | — | — | — | — | — | — | — | — | — | — | — | — | — | ✅ | — | — | — | — | — | — | — | — |
| **discussion_summary.py** | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — |
| **config.py** | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — |
| **channel_config.py** | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — |
| **rate_limiter.py** | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — |
| **member_profile.py** | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — |
| **errors.py** | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — |

### 1.3 外部ライブラリ依存

| モジュール | discord.py | anthropic | aiohttp | beautifulsoup4 | python-dotenv |
|---|---|---|---|---|---|
| bot.py | ✅ `discord.Client` | — | — | — | ✅ |
| llm.py | — | ✅ `AsyncAnthropic` | — | — | — |
| summarizer.py | — | — | ✅ `aiohttp.ClientSession` | ✅ `BeautifulSoup` | — |
| その他全モジュール | — | — | — | — | — |

> **COMMON_MISTAKES §13:** llm.pyは必ず `AsyncAnthropic`（非同期クライアント）を使用する。`Anthropic`（同期クライアント）は禁止。bot.py（discord.py）が `await` で呼び出すため。

---

## 2. 各モジュール公開API

### 2.1 bot.py — Discordイベント処理（メイン）

**クラス名:** `ShioriBot`  
**継承:** `discord.Client`  
**全メソッド:** async

```python
class ShioriBot(discord.Client):
    def __init__(self):
        # 初期化するインスタンス変数（v4.1既存）
        self.llm: LLMClient                       # llm.py
        self.trust: TrustManager                   # trust.py
        self.predictions: PredictionLedger         # predictions.py
        self.nudge: NudgeManager                   # nudge.py
        self.summarizer: LinkSummarizer            # summarizer.py
        self.passive_monitor: PassiveMonitor       # passive_monitor.py
        self.channel_config: ChannelConfig         # channel_config.py
        self.rate_limiter: RateLimiter             # rate_limiter.py
        self.member_profile: MemberProfileManager  # member_profile.py
        self.reactions: ReactionManager            # reactions.py

        # ★v5.3 追加インスタンス変数
        self.heart_reactions: ReactionHandler           # reaction_handler.py
        self.response_gen: ResponseGenerator            # response_generator.py
        self.level_up_detector: TrustLevelUpDetector    # trust_level_up.py
        self.prediction_highlighter: PredictionHighlighter  # prediction_highlighter.py
        self.daily_maintenance_task: DailyMaintenanceTask   # daily_maintenance.py
        self.weekly_monologue_task: WeeklyMonologueTask     # weekly_monologue.py
        self.level_up_pending: dict[str, dict] = {}     # 昇格フラグ（§9）

    # --- Discordイベントハンドラ ---

    async def on_ready(self) -> None:
        """Bot起動時処理。データファイルロード＋直近100件取得（Q24: B案）"""

    async def on_message(self, message: discord.Message) -> None:
        """メッセージ受信時の統合ハンドラ"""

    async def on_member_remove(self, member: discord.Member) -> None:
        """メンバー離脱時の匿名化処理（Q26: B案）"""

    # --- 内部処理 ---

    async def _handle_mention(self, message: discord.Message) -> None:
        """メンション/返信トリガー時の応答フロー"""

    async def _handle_passive(self, message: discord.Message) -> None:
        """受動監視フロー（MAIN CHANNELカテゴリ内、メンションなし）"""

    async def _startup_fetch(self) -> None:
        """起動時の直近100件メッセージ取得と予測スキャン"""

    async def validate_data_integrity(self) -> list[str]:
        """起動時のデータファイル間整合性検証。エラーリストを返す"""
```

**コンストラクタの初期化順序:**

```python
def __init__(self):
    super().__init__(intents=intents)
    # 1. 依存なしモジュール（先に初期化）
    self.channel_config = ChannelConfig()
    self.rate_limiter = RateLimiter(cooldown_seconds=30)
    self.member_profile = MemberProfileManager()
    self.trust = TrustManager()
    self.reactions = ReactionManager()
    # 2. LLMクライアント（AsyncAnthropic）
    self.llm = LLMClient()
    # 3. LLMに依存するモジュール
    self.predictions = PredictionLedger(llm=self.llm)
    self.nudge = NudgeManager(llm=self.llm, member_profile=self.member_profile)
    self.summarizer = LinkSummarizer(llm=self.llm)
    self.passive_monitor = PassiveMonitor(
        llm=self.llm,
        predictions=self.predictions,
        channel_config=self.channel_config
    )
```

> **COMMON_MISTAKES §15:** `NudgeManager` のコンストラクタは `llm` と `member_profile` を必須引数として受け取る。`NudgeManager()` と引数なしで呼び出すと `TypeError`。

---

### 2.2 llm.py — Anthropic Claude API インターフェース

**クラス名:** `LLMClient`  
**全メソッド:** async  
**使用クライアント:** `anthropic.AsyncAnthropic`（§13厳守）  
**使用モデル:** `claude-haiku-4-5-20251001`（Q10: B案）

```python
import anthropic

class LLMClient:
    def __init__(self):
        self.client = anthropic.AsyncAnthropic()  # ANTHROPIC_API_KEY は環境変数から自動取得

    async def generate_response(
        self,
        system_prompt: str,
        messages: list[dict],        # Anthropic API形式: [{"role": "user"|"assistant", "content": str}]
        max_tokens: int = 500,
        temperature: float = 0.7
    ) -> str:
        """メイン応答生成。system_prompt.txt + 動的コンテキストで呼び出す。
        戻り値はテキスト文字列。"""

    async def call_template(
        self,
        template_name: str,          # "T1"〜"T8"
        system: str,                 # テンプレート固有のシステムプロンプト
        user: str,                   # テンプレート固有のユーザープロンプト
        max_tokens: int,
        temperature: float
    ) -> dict | None:
        """バックグラウンドテンプレート呼び出し（T1-T8）。
        JSON形式のdictを返す。パース失敗時はNoneを返す。"""

    def build_system_prompt(
        self,
        trust_level: int,            # 1-5
        member_profile: dict | None, # member_profile.py の get_profile() 戻り値
        channel_overrides: dict | None,  # channel_config.py の get_overrides() 戻り値
        community_knowledge: str | None = None  # member_profile.py の get_community_knowledge_text() 戻り値
    ) -> str:
        """system_prompt.txt + 動的コンテキストを結合してシステムプロンプトを構築する。
        同期メソッド（I/O不要のため）。"""

    def convert_context_to_api_format(
        self,
        context_messages: list[dict],  # 内部形式（§2.2.1参照）
        bot_user_id: int
    ) -> list[dict]:
        """内部メッセージ形式 → Anthropic API messages形式に変換する。
        同期メソッド。"""
```

#### 2.2.1 データ変換境界（COMMON_MISTAKES §14 対応）

**内部メッセージ形式（bot.py → llm.py に渡される）:**

```python
# bot.py が収集する直前20件のメッセージ
internal_message = {
    "author_id": int,              # Discord user ID
    "author_display_name": str,    # 表示名
    "content": str,                # メッセージ本文
    "timestamp": str,              # ISO 8601
    "is_bot": bool                 # Bot自身のメッセージか
}
```

**Anthropic API形式（`convert_context_to_api_format()` の出力）:**

```python
# Anthropic Messages API が要求する形式
api_message = {
    "role": "user" | "assistant",  # is_bot=True → "assistant", False → "user"
    "content": str                 # "{author_display_name}: {content}" 形式に結合
}
```

**変換ルール:**
- `is_bot=True` → `role: "assistant"`
- `is_bot=False` → `role: "user"`
- 連続する同一roleのメッセージは結合する（Anthropic APIは交互のroleを要求）
- `content` には発言者名を `"{display_name}: {本文}"` 形式でプレフィックスする

---

### 2.3 trust.py — 信頼度管理

**クラス名:** `TrustManager`  
**全メソッド:** async（ファイルI/Oのため）  
**データファイル:** `data/members.md`

```python
class TrustManager:
    def __init__(self):
        self.members: dict[int, dict] = {}  # user_id → メンバー情報

    async def load(self, filepath: str = "data/members.md") -> None:
        """起動時にメンバー台帳を読み込む"""

    async def record_interaction(
        self,
        user_id: int,
        action: str       # §6.2のアクション名: "mention", "prediction", "answer",
                           #   "self_review", "correction", "summary_request", "explanation"
    ) -> dict:
        """インタラクションを記録し、信頼度を更新する。
        戻り値: {"old_score": int, "new_score": int, "old_level": int, "new_level": int, "delta": int}"""

    async def apply_decay(self, user_id: int) -> None:
        """30日非活動時の-5減衰を適用する（§6.3）"""

    def get_trust_level(self, user_id: int) -> int:
        """現在の信頼度レベル（1-5）を返す。未知ユーザーは1を返す。同期メソッド。"""

    def get_trust_score(self, user_id: int) -> int:
        """現在の信頼度スコア（0-100）を返す。未知ユーザーは0を返す。同期メソッド。"""

    async def anonymize_member(self, user_id: int) -> str:
        """離脱メンバーの匿名化（Q26: B案）。
        戻り値: 匿名化後の名前（'元メンバー#NNN'）"""

    async def save(self) -> None:
        """members.md にメンバー台帳を書き出す"""
```

**スコア変動表（§6.2）:**

| action値 | 変動 |
|----------|------|
| `"mention"` | +3 |
| `"prediction"` | +2 |
| `"answer"` | +5 |
| `"self_review"` | +7 |
| `"correction"` | +5 |
| `"summary_request"` | +2 |
| `"explanation"` | +4 |

**レベル算出（§6.1）:**

```python
def _calculate_level(self, score: int) -> int:
    if score >= 100: return 5
    if score >= 80: return 4
    if score >= 50: return 3
    if score >= 20: return 2
    return 1
```

---

### 2.4 predictions.py — 予測台帳

**クラス名:** `PredictionLedger`  
**全メソッド:** async（ファイルI/O + LLM呼び出し）  
**データファイル:** `data/predictions.md`, `data/index.md`

```python
class PredictionLedger:
    def __init__(self, llm: 'LLMClient'):
        self.llm = llm
        self.predictions: list[dict] = []

    async def load(self, filepath: str = "data/predictions.md") -> None:
        """起動時に予測台帳を読み込む"""

    async def record_prediction(
        self,
        message: dict,            # {"user_id": int, "display_name": str,
                                   #  "content": str, "timestamp": str, "channel": str}
        prediction_text: str,     # T1出力の prediction_text
        detection_method: str     # "mention" | "passive" | "reply"
    ) -> dict:
        """新規予測を記録する。
        内部で T2（カテゴリ）、T3（時間軸）、T4（差分）を順に呼び出す。
        戻り値: 記録された予測レコード（dict）"""

    async def find_by_user_and_category(
        self,
        user_id: int,
        category: str
    ) -> list[dict]:
        """差分指摘用: 同一ユーザー・同一カテゴリの過去予測を検索する"""

    def get_next_prediction_id(self) -> str:
        """次の予測番号を返す（'#0001'形式）。同期メソッド。"""

    def format_prediction_record(self, prediction: dict) -> str:
        """予測レコードをMarkdown形式の文字列に変換する。同期メソッド。"""

    async def save(self) -> None:
        """predictions.md と index.md に書き出す"""
```

---

### 2.5 categories.py — カテゴリ管理

**クラス名:** `CategoryManager`  
**データファイル:** `data/categories.md`

```python
class CategoryManager:
    def __init__(self, llm: 'LLMClient'):
        self.llm = llm
        self.categories: list[str] = []  # "大分類 / 小分類" 形式

    async def load(self, filepath: str = "data/categories.md") -> None:
        """起動時にカテゴリマスタを読み込む"""

    async def classify(
        self,
        prediction_text: str,
        author_display_name: str
    ) -> dict:
        """T2テンプレートでカテゴリを判定する。
        戻り値: {"categories": list[str], "is_new_category": bool}"""

    def get_existing_categories_list(self) -> str:
        """既存カテゴリの一覧テキストを返す（T2プロンプトに注入用）。同期メソッド。"""

    async def register_new_category(self, category: str) -> None:
        """新規カテゴリをマスタに追加する"""

    async def save(self) -> None:
        """categories.md に書き出す"""
```

> **NOTE:** categories.py は predictions.py の `record_prediction()` 内部から呼び出される。bot.py が直接呼び出すことはない。

---

### 2.6 timeline.py — 時間軸解析

**クラス名:** `TimelineAnalyzer`

```python
class TimelineAnalyzer:
    def __init__(self, llm: 'LLMClient'):
        self.llm = llm

    async def extract(
        self,
        prediction_text: str,
        original_message_content: str
    ) -> dict:
        """T3テンプレートで時間軸を抽出する。
        戻り値: {"timeline_start": str, "timeline_end": str,
                 "timeline_display": str, "confidence": float}"""

    @staticmethod
    def timelines_overlap(
        old_start: str, old_end: str,
        new_start: str, new_end: str
    ) -> bool:
        """2つの時間軸が重複するか判定する。
        '?' を含む場合は True（重複扱い＝指摘しない）を返す。
        同期メソッド・staticmethod。"""
```

---

### 2.7 nudge.py — 低活動メンバーnudge

**クラス名:** `NudgeManager`

```python
class NudgeManager:
    def __init__(self, llm: 'LLMClient', member_profile: 'MemberProfileManager'):
        self.llm = llm
        self.member_profile = member_profile

    async def select_nudge_target(
        self,
        current_topic: str
    ) -> dict | None:
        """ナッジ対象を選定する。
        条件: 30日以上非活動 + 現在の話題に関連する過去発言あり
        戻り値: {"member": dict, "past_message": str} | None"""

    async def build_nudge_hint(
        self,
        current_topic: str,
        target_display_name: str,
        past_relevant_message: str,
        last_active_date: str
    ) -> dict | None:
        """T8テンプレートでナッジ文案を生成する。
        戻り値: {"nudge_text": str, "connection_type": str} | None"""

    def find_relevant_past_message(
        self,
        member: dict,
        current_topic: str
    ) -> str | None:
        """メンバーの過去発言から現在の話題に関連するものを検索する。
        同期メソッド。"""
```

> **COMMON_MISTAKES §15:** bot.py が `self.nudge.build_nudge_hint()` を呼び出す。このメソッドは必ず実装すること。引数は4つ（current_topic, target_display_name, past_relevant_message, last_active_date）。

---

### 2.8 summarizer.py — リンク要約

**クラス名:** `LinkSummarizer`

```python
import aiohttp
from bs4 import BeautifulSoup

class LinkSummarizer:
    def __init__(self, llm: 'LLMClient'):
        self.llm = llm

    async def summarize_url(
        self,
        url: str,
        related_keywords: list[str] | None = None
    ) -> dict | None:
        """URLの内容を取得し、T5テンプレートで要約する。
        戻り値: {"title": str, "domain": str, "points": list[str],
                 "related_prediction_hint": str | None} | None"""

    async def _fetch_page(self, url: str) -> dict | None:
        """ページを取得してタイトルと本文テキストを返す。
        戻り値: {"title": str, "text": str} | None（失敗時）"""

    def format_summary(self, result: dict) -> str:
        """T5結果を栞の応答形式にフォーマットする。同期メソッド。
        戻り値:
        📎 リンク要約
        出典: [title] (domain)
        要点: ①... ②... ③...
        予測台帳との関連: ...
        """
```

---

### 2.9 passive_monitor.py — 受動監視モジュール

**クラス名:** `PassiveMonitor`

```python
class PassiveMonitor:
    def __init__(
        self,
        llm: 'LLMClient',
        predictions: 'PredictionLedger',
        channel_config: 'ChannelConfig'
    ):
        self.llm = llm
        self.predictions = predictions
        self.channel_config = channel_config

    async def check_message(
        self,
        message: dict       # {"user_id": int, "display_name": str,
                             #  "content": str, "timestamp": str, "channel": str,
                             #  "channel_category_id": int}
    ) -> dict | None:
        """メッセージが予測を含むか T1 で判定する。
        MAIN CHANNELカテゴリ外のメッセージは即座にNoneを返す。
        戻り値: T1結果 {"is_prediction": bool, "confidence": float,
                        "prediction_text": str} | None"""

    async def process_prediction(
        self,
        message: dict,
        t1_result: dict
    ) -> dict | None:
        """検出された予測を記録する（predictions.record_prediction() に委譲）。
        detection_method は "passive" を設定する。"""
```

---

### 2.10 channel_config.py — チャンネル別設定

**クラス名:** `ChannelConfig`

```python
class ChannelConfig:
    def __init__(self):
        self.main_channel_category_id: int = int(os.getenv("MAIN_CHANNEL_CATEGORY_ID", "0"))
        self.overrides: dict = CHANNEL_OVERRIDES  # channel_behavior.md §6.2 参照

    def is_main_channel_category(self, category_id: int | None) -> bool:
        """チャンネルがMAIN CHANNELカテゴリに属するか判定する。同期メソッド。"""

    def get_overrides(self, channel_name: str) -> dict | None:
        """チャンネル名からオーバーライド設定を返す。該当なしならNone。同期メソッド。"""

    def is_dm(self, message) -> bool:
        """メッセージがDMかどうか判定する。同期メソッド。"""
```

---

### 2.11 rate_limiter.py — レート制限

**クラス名:** `RateLimiter`

```python
class RateLimiter:
    def __init__(self, cooldown_seconds: int = 30):
        self.cooldown_seconds = cooldown_seconds
        self._last_response: dict[int, float] = {}  # channel_id → timestamp

    def can_respond(self, channel_id: int) -> bool:
        """クールダウン期間が過ぎていればTrueを返す。同期メソッド。"""

    def record_response(self, channel_id: int) -> None:
        """応答したことを記録する。同期メソッド。"""
```

---

### 2.12 member_profile.py — メンバープロファイル管理

**クラス名:** `MemberProfileManager`  
**参照データ:** `data/members_extended.md`, `data/community_lexicon.md`, `data/consensus_tracker.md`

```python
class MemberProfileManager:
    def __init__(self):
        self.profiles: dict[str, dict] = {}       # username → プロファイル
        self.lexicon: dict[str, dict] = {}         # 用語名 → 定義
        self.consensus: dict[str, dict] = {}       # トピック → コンセンサス情報

    async def load(self) -> None:
        """起動時に3ファイルをフルロード"""

    def get_profile(self, user_id: int = None, username: str = None) -> dict | None:
        """メンバープロファイルを返す。user_idまたはusernameで検索。
        同期メソッド。"""

    def get_profile_summary(self, user_id: int) -> str:
        """コンテキスト注入用の要約プロファイルを返す（200字以内）。
        同期メソッド。"""

    def get_tier_ab_summaries(self) -> str:
        """Tier A-Bメンバーの要約プロファイル一覧を返す（常時ロード用）。
        同期メソッド。"""

    def get_community_knowledge_text(self, compact: bool = False) -> str:
        """コミュニティ知識（Tier A-Bメンバー + コンセンサス）をテキスト形式で返す。
        compact=True の場合、コンセンサス情報を省略。
        同期メソッド。"""

    def lookup_term(self, term: str) -> dict | None:
        """community_lexicon.md から用語を検索する。
        戻り値: {"term": str, "definition": str, "proposer": str, ...} | None
        同期メソッド。"""

    def lookup_consensus(self, topic: str) -> dict | None:
        """consensus_tracker.md からトピックのコンセンサスを検索する。
        戻り値: {"topic": str, "majority": str, "dissenters": list, ...} | None
        同期メソッド。"""

    def get_display_name(self, user_id: int) -> str:
        """user_idから表示名を返す。不明な場合は'不明なメンバー'を返す。
        同期メソッド。"""
```

> **COMMON_MISTAKES §10:** 旧名 `profiles.py` → 現名 `member_profile.py`。`from profiles import` とするとImportError。常に `from member_profile import MemberProfileManager` を使用。

> **COMMON_MISTAKES §10:** `get_profile_summary()` の引数は `user_id: int` の1つのみ。`get_profile_summary(name, profiles)` のような2引数シグネチャは廃止済み。

---

### 2.13 errors.py — エラーハンドリング

**関数ベース（クラスなし）**

```python
def format_error_message(error_type: str) -> str:
    """エラー種別に応じたキャラクター口調のエラーメッセージを返す（Q23: B案）。
    同期関数。

    error_type:
      "link_fetch_failed" → リンク取得失敗メッセージ
      "timeout"           → タイムアウトメッセージ
      "api_limit"         → API制限メッセージ
      "unknown"           → 汎用エラーメッセージ

    戻り値: str（栞のキャラクター口調のエラー文）"""
```

---

### 2.14 reactions.py — 絵文字リアクション管理

**クラス名:** `ReactionManager`

```python
class ReactionManager:
    # 使用する絵文字定数（Q25: C案改。✅は廃止）
    CLIP = "📎"          # 予測記録時
    NOTEBOOK = "📓"      # 議論まとめ・週報時
    QUESTION = "❓"      # プレモーテム質問時
    BOOK = "📖"          # 高信頼度メンバー（Lv4以上）への特別反応

    async def add_reaction(
        self,
        message: 'discord.Message',   # discord.py の Message オブジェクト
        reaction_type: str             # "prediction" | "discussion" | "premortem" | "high_trust"
    ) -> None:
        """メッセージに適切な絵文字リアクションを追加する（20秒遅延）
        v5.3変更: §10.3 — schedule_delayed_reaction() 経由で遅延付与
        """
```

> **v4.1変更:** ✅（`CHECKMARK`）定数は存在しない。Q27凍結に伴い削除済み。
> **v5.3変更:** `add_reaction()` 内部で `schedule_delayed_reaction()` を使用。即座の `message.add_reaction()` は行わない。

---

### 2.15 config.py — 定数・設定値一元管理 ★v5.3追加

```python
# バージョン管理
BOT_VERSION: str = "5.3"

# 好感度2倍化（§2）
TRUST_GAIN_MULTIPLIER: int = 2

# ハートカラー閾値（§4, §9 共有）
HEART_THRESHOLDS: dict[int, tuple[int, int]] = {
    1: (0, 19),    # newbie → 🧡
    2: (20, 49),   # low    → 💛
    3: (50, 79),   # high   → 💗
    4: (80, 100),  # max    → ❤️
}

# リアクション遅延（§10）
REACTION_DELAY_SECONDS: int = 20

# 日次メンテナンス（§5）
DAILY_MAINTENANCE_HOUR: int = 18   # JST

# 週次独り言（§8）
MONOLOGUE_DAY: int = 6             # calendar.SUNDAY
MONOLOGUE_HOUR: int = 21           # JST

# 予測ハイライト（§5.7）
APPROACHING_MONTHS: int = 6
MAX_HIGHLIGHTS: int = 2

# 議論まとめ（§7）
MEMBER_SUMMARY_FETCH_LIMIT: int = 100
```

> **⚠️ COMMON_MISTAKES N-04:** `HEART_THRESHOLDS` はこの `config.py` が唯一の定義元。`trust.py`, `reaction_handler.py`, `trust_level_up.py` は全て `from config import HEART_THRESHOLDS` で参照すること。

---

### 2.16 reaction_handler.py — ハートリアクション＋遅延リアクション ★v5.3追加

**クラス名:** `ReactionHandler`
**モジュール関数:** `delayed_add_reaction()`, `schedule_delayed_reaction()`

```python
class ReactionHandler:
    def should_heart_react(
        self,
        message_content: str,         # [必須] メッセージ内容
        is_reply_to_shiori: bool,     # [必須] 栞への返信か
        is_mention_to_shiori: bool,   # [必須] 栞へのメンションか（★v5.3追加）
    ) -> bool:
        """ハートリアクション付与判定（§1, §12.6.1）"""

    def get_heart_emoji(self, trust_score: int) -> str:
        """好感度スコア別ハートカラー（§4）
        Returns: "🧡" | "💛" | "💗" | "❤️"
        """

    async def handle_reaction(
        self,
        message: discord.Message,     # [必須]
        trust_score: int,             # [必須]
        is_reply_to_shiori: bool,     # [必須]
        is_mention_to_shiori: bool,   # [必須]（★v5.3追加）
    ) -> None:
        """リアクション統合フロー（§4.5, §12.6.2）"""


async def delayed_add_reaction(
    message: discord.Message,         # [必須]
    emoji: str,                       # [必須]
    delay: int = REACTION_DELAY_SECONDS,  # [任意]
) -> bool:
    """遅延付きリアクション付与（§10, §12.5.2）
    ⚠️ asyncio.create_task() で呼び出すこと（await直接禁止 — N-01）
    """

def schedule_delayed_reaction(
    message: discord.Message,         # [必須]
    emoji: str,                       # [必須]
) -> None:
    """遅延リアクションの安全ラッパー（§10.10.2）
    create_task() 呼び出しを try/except で囲む。
    全リアクション付与箇所はこの関数経由で呼び出すこと。
    """
```

> **⚠️ COMMON_MISTAKES N-01:** `await delayed_add_reaction(...)` は禁止。必ず `schedule_delayed_reaction()` または `asyncio.create_task()` 経由。

---

### 2.17 response_mode.py — 記録/自由モード判定 ★v5.3追加

```python
def determine_response_mode(message_content: str) -> str:
    """メッセージから応答モードを判定（§3）
    Returns: "record" | "free"
    """
```

---

### 2.18 trust_level_up.py — 信頼度レベル昇格検出 ★v5.3追加

**クラス名:** `TrustLevelUpDetector`

```python
class TrustLevelUpDetector:
    def check_level_up(
        self,
        user_id: str,       # [必須]
        old_score: int,     # [必須]
        new_score: int,     # [必須]
    ) -> dict | None:
        """昇格を検出（§9, sync）
        Returns:
            {"old_level": int, "new_level": int, "new_heart": str} | None
        """
```

> **⚠️ COMMON_MISTAKES N-03:** 昇格フラグの消費は `level_up_pending.pop()` で行うこと。`.get()` は禁止。

---

### 2.19 daily_maintenance.py — 日次メンテナンス ★v5.3追加

**クラス名:** `DailyMaintenanceTask`
**コンストラクタ:** `DailyMaintenanceTask(bot)`（コンストラクタ注入, §12.9）

```python
class DailyMaintenanceTask:
    def __init__(self, bot: ShioriBot): ...

    async def run_daily_maintenance(self) -> dict:
        """日次メンテナンス実行（§5, async）
        Returns: {"total_messages": int, "new_predictions": int, ...}
        """
```

---

### 2.20 weekly_monologue.py — 週次独り言 ★v5.3追加

**クラス名:** `WeeklyMonologueTask`
**コンストラクタ:** `WeeklyMonologueTask(bot)`（コンストラクタ注入, §12.9）

```python
class WeeklyMonologueTask:
    def __init__(self, bot: ShioriBot): ...

    async def weekly_monologue_loop(self) -> None:
        """週次独り言ループ（§8, async）"""
```

---

### 2.21 prediction_highlighter.py — 予測ハイライト選定 ★v5.3追加

**クラス名:** `PredictionHighlighter`

```python
class PredictionHighlighter:
    def select_highlights(
        self,
        predictions: list[dict],   # [必須]
        current_date: str,         # [必須]
    ) -> list[dict]:
        """予測ハイライト選定（§5.7, sync, LLM呼び出しなし）
        Returns: 最大 MAX_HIGHLIGHTS 件のリスト
        """
```

---

### 2.22 discussion_summary.py — 議論まとめ ★v5.3追加

```python
def detect_summary_request(message_content: str) -> dict | None:
    """要約依頼検出（§7, sync）
    Returns: {"type": "general"} | {"type": "member", "members": [...]} | None
    """

async def handle_member_summary(
    channel: discord.TextChannel,
    members: list[str],
    fetch_limit: int = MEMBER_SUMMARY_FETCH_LIMIT,
) -> str:
    """メンバー指定要約（§7, async — Sonnet API呼び出し）"""
```

---

### 2.23 response_generator.py — 応答生成 ★v5.3追加

**クラス名:** `ResponseGenerator`

```python
class ResponseGenerator:
    async def generate(
        self,
        message: discord.Message,         # [必須]
        config: dict,                     # [必須]
        context: str | None = None,       # [任意]
        level_up_hint: str | None = None, # [任意] ★v5.3追加
        response_mode: str = "free",      # [任意] ★v5.3追加
        *,
        system_prompt: str | None = None, # [任意]
        api_messages: list | None = None, # [任意]
    ) -> str:
        """応答生成（§12.6.3, async）"""
```

---

## 3. データ変換境界の一覧

COMMON_MISTAKES §14が指摘する「データフォーマット変換層の欠如」を防止するため、全変換ポイントを一覧化する。

| 変換ポイント | 変換元（内部形式） | 変換先（外部形式） | 責任モジュール | メソッド |
|---|---|---|---|---|
| チャットコンテキスト | `internal_message` (§2.2.1) | Anthropic API `messages` | `llm.py` | `convert_context_to_api_format()` |
| 予測レコード→Markdown | prediction dict | Markdown文字列 | `predictions.py` | `format_prediction_record()` |
| T5結果→応答テキスト | T5 JSON dict | 栞の応答形式テキスト | `summarizer.py` | `format_summary()` |
| T7結果→応答テキスト | T7 JSON dict | 議論まとめ形式テキスト | `llm.py` | `format_discussion_summary()` |
| members_extended.md→注入文 | Markdown → dict | システムプロンプト内テキスト | `member_profile.py` | `get_profile_summary()` / `get_tier_ab_summaries()` |
| チャンネル設定→プロンプト | override dict | プロンプト制約テキスト | `llm.py` | `build_system_prompt()` |

---

## 4. メッセージ処理フロー（概要版）

`event_flow.md`（次のドキュメント）で詳細化するが、本文書でも概要を示す。

### 4.1 メンション/返信受信時

```
bot.py: on_message()
  ├── DM? → channel_config.is_dm() → Q19定型応答
  ├── Bot自身? → skip
  ├── rate_limiter.can_respond()? → No → skip
  ├── メンション/返信?
  │     ├── Yes → _handle_mention()
  │     │     ├── trust.record_interaction(user_id, "mention")
  │     │     ├── channel_config.get_overrides(channel_name)
  │     │     ├── passive_monitor.check_message() → 予測検出
  │     │     ├── [予測あり] predictions.record_prediction()
  │     │     │     ├── categories.classify() ← T2
  │     │     │     ├── timeline.extract() ← T3
  │     │     │     └── [過去予測あり] call_template("T4") ← T4
  │     │     ├── [楽観的予測] llm.call_template("T6") ← プレモーテム
  │     │     ├── [条件一致] nudge.build_nudge_hint() ← T8
  │     │     ├── llm.build_system_prompt(trust_level, profile, overrides)
  │     │     ├── llm.convert_context_to_api_format(context, bot_id)
  │     │     ├── llm.generate_response(system, messages)
  │     │     ├── reactions.add_reaction(message, type)
  │     │     └── rate_limiter.record_response(channel_id)
  │     └── No → _handle_passive()（MAIN CHANNELカテゴリのみ）
  │           ├── channel_config.is_main_channel_category()? → No → skip
  │           ├── passive_monitor.check_message() ← T1
  │           └── [予測あり] passive_monitor.process_prediction()
```

---

## 5. async/sync 一覧表

**COMMON_MISTAKES §13 対応:** 全メソッドの async/sync を明示する。`await` で呼ぶメソッドは必ず `async def`。

| モジュール | メソッド | async/sync | 理由 |
|---|---|---|---|
| **llm.py** | `generate_response()` | **async** | Anthropic API呼び出し |
| | `call_template()` | **async** | Anthropic API呼び出し |
| | `build_system_prompt()` | sync | テキスト組み立てのみ |
| | `convert_context_to_api_format()` | sync | データ変換のみ |
| **trust.py** | `load()` | **async** | ファイル読み込み |
| | `record_interaction()` | **async** | ファイル書き込み |
| | `apply_decay()` | **async** | ファイル書き込み |
| | `get_trust_level()` | sync | メモリ参照のみ |
| | `get_trust_score()` | sync | メモリ参照のみ |
| | `anonymize_member()` | **async** | ファイル書き込み |
| | `save()` | **async** | ファイル書き込み |
| **predictions.py** | `load()` | **async** | ファイル読み込み |
| | `record_prediction()` | **async** | LLM呼び出し + ファイル書き込み |
| | `find_by_user_and_category()` | **async** | ファイル検索 |
| | `get_next_prediction_id()` | sync | メモリ参照のみ |
| | `format_prediction_record()` | sync | テキスト組み立てのみ |
| | `save()` | **async** | ファイル書き込み |
| **categories.py** | `load()` | **async** | ファイル読み込み |
| | `classify()` | **async** | LLM呼び出し |
| | `get_existing_categories_list()` | sync | メモリ参照のみ |
| | `register_new_category()` | **async** | ファイル書き込み |
| | `save()` | **async** | ファイル書き込み |
| **timeline.py** | `extract()` | **async** | LLM呼び出し |
| | `timelines_overlap()` | sync (static) | 計算のみ |
| **nudge.py** | `select_nudge_target()` | **async** | 検索処理 |
| | `build_nudge_hint()` | **async** | LLM呼び出し |
| | `find_relevant_past_message()` | sync | メモリ検索のみ |
| **summarizer.py** | `summarize_url()` | **async** | HTTP + LLM呼び出し |
| | `_fetch_page()` | **async** | HTTP取得 |
| | `format_summary()` | sync | テキスト組み立てのみ |
| **passive_monitor.py** | `check_message()` | **async** | LLM呼び出し |
| | `process_prediction()` | **async** | predictions.py 委譲 |
| **channel_config.py** | 全メソッド | sync | 設定参照のみ |
| **rate_limiter.py** | 全メソッド | sync | メモリ参照のみ |
| **member_profile.py** | `load()` | **async** | ファイル読み込み |
| | その他全メソッド | sync | メモリ参照のみ |
| **errors.py** | `format_error_message()` | sync | テキスト生成のみ |
| **reactions.py** | `add_reaction()` | **async** | Discord API呼び出し（内部でschedule_delayed_reaction経由） |
| **config.py** | 全定数 | — | 定数定義のみ |
| **reaction_handler.py** | `should_heart_react()` | sync | 正規表現マッチのみ |
| | `get_heart_emoji()` | sync | 条件分岐のみ |
| | `handle_reaction()` | **async** | リアクション統合フロー |
| | `delayed_add_reaction()` | **async** | asyncio.sleep + Discord API |
| | `schedule_delayed_reaction()` | sync | create_task呼び出し（安全ラッパー） |
| **response_mode.py** | `determine_response_mode()` | sync | 正規表現マッチのみ |
| **trust_level_up.py** | `check_level_up()` | sync | 条件分岐のみ |
| **daily_maintenance.py** | `run_daily_maintenance()` | **async** | LLM + ファイル書き込み |
| **weekly_monologue.py** | `weekly_monologue_loop()` | **async** | LLM + Discord送信 |
| **prediction_highlighter.py** | `select_highlights()` | sync | 計算のみ（LLM不使用） |
| **discussion_summary.py** | `detect_summary_request()` | sync | 正規表現マッチのみ |
| | `handle_member_summary()` | **async** | LLM呼び出し |
| **response_generator.py** | `generate()` | **async** | Anthropic API呼び出し |

---

## 6. 過去エラーの防止チェックリスト

本文書の実効性を確保するため、COMMON_MISTAKESの各エラーが本文書のどの箇所で防止されるかを対応づける。

| COMMON_MISTAKES | エラー内容 | 本文書での防止策 |
|---|---|---|
| §10 | `PredictionManager` vs `PredictionLedger` | §2.4 でクラス名 `PredictionLedger` を明記 |
| §10 | `generate_response()` vs `generate()` | §2.2 でメソッド名 `generate_response()` を明記 |
| §10 | `get_profile_summary(name, profiles)` 2引数 | §2.12 で引数 `user_id: int` の1引数を明記 |
| §10 | `NudgeManager()` 引数なしコンストラクタ | §2.7 + §2.1 で `NudgeManager(llm, member_profile)` を明記 |
| §12 | `from profiles import` → `from member_profile import` | §1.2 + §2.12 の注記で旧名を警告 |
| §13 | 同期 `Anthropic` の誤使用 | §2.2 + §1.3 で `AsyncAnthropic` を必須指定 |
| §14 | 内部形式を直接Anthropic APIに渡す | §2.2.1 + §3 でデータ変換境界を明示 |
| §15 | `build_nudge_hint()` 未実装 | §2.7 でメソッド仕様を明記。§4.1フローで呼び出し箇所を明示 |
| §15 | `record_interaction()` 未実装 | §2.3 でメソッド仕様を明記 |

---

## 7. 変更履歴

| 日付 | 変更内容 |
|------|----------|
| 2026-02-13 | 初版作成。v4.1仕様書に基づき全14モジュールのインターフェースを定義 |
| 2026-02-14 | `llm.py` の `build_system_prompt()` に `community_knowledge: str | None` パラメータを追加 |
| 2026-02-17 | **v5.3対応:** §2.15〜§2.23 追加（config, reaction_handler, response_mode, trust_level_up, daily_maintenance, weekly_monologue, prediction_highlighter, discussion_summary, response_generator）。依存マトリクス更新。async/sync表にv5.3メソッド追加。reactions.py遅延化（§10.3）反映。bot.py インスタンス変数にv5.3モジュール追加 |

---

*本文書は COMMON_MISTAKES.md §10, §12, §13, §14, §15, N-01〜N-04 の再発防止を目的として作成されました。*  
*Source: Shiori_Requirements_v4_1.md, Shiori_v5_3_Detailed_Spec §1〜§13, data_schema.md, prompt_templates.md, channel_behavior.md §6*
