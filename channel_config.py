"""
channel_config.py - チャンネル別振る舞い設定モジュール

Q6: B案 - LLM判断 + 要注意チャンネル個別オーバーライド
基本的にLLMが文脈から適切な振る舞いを判断するが、
要注意チャンネルには個別オーバーライドを設定
"""

import json
import os
from dataclasses import dataclass, field, asdict
from typing import Optional
from pathlib import Path
from enum import Enum


class ChannelType(Enum):
    """チャンネルの種類"""
    PREDICTION = "prediction"      # 未来予測を投稿するch
    GENERAL = "general"            # その他・雑談ch
    VOICE = "voice"                # VC連携
    TECHNICAL = "technical"        # 技術系チャンネル
    DEFAULT = "default"            # その他（LLM判断）


@dataclass
class ChannelBehavior:
    """チャンネル別の振る舞い設定"""
    
    # 基本設定
    channel_type: ChannelType = ChannelType.DEFAULT
    
    # 予測記録の積極度 (0-10)
    # 0: 記録しない, 5: 普通, 10: 積極的に記録
    prediction_recording_level: int = 5
    
    # トーンのカジュアル度 (0-10)
    # 0: 完全フォーマル, 5: 普通, 10: とてもカジュアル
    casual_level: int = 5
    
    # プレモーテム質問の頻度 (0-10)
    # 0: しない, 5: 普通, 10: 積極的に質問
    premortem_frequency: int = 5
    
    # 議論サマリの有効/無効
    enable_discussion_summary: bool = True
    
    # パッシブモニタリングの有効/無効
    enable_passive_monitoring: bool = True
    
    # カスタムプロンプト追加（LLMへの追加指示）
    custom_prompt: str = ""
    
    def to_prompt_instruction(self) -> str:
        """LLMに渡すプロンプト指示を生成"""
        instructions = []
        
        # チャンネルタイプに応じた基本指示
        type_instructions = {
            ChannelType.PREDICTION: "このチャンネルは未来予測専用です。予測の記録を積極的に行い、差分指摘やプレモーテム質問も遠慮なく実施してください。",
            ChannelType.GENERAL: "このチャンネルは雑談チャンネルです。予測記録は控えめに、カジュアルなトーンで会話してください。",
            ChannelType.VOICE: "このチャンネルはVC連携チャンネルです。議論の要約依頼に集中し、短めの応答を心がけてください。",
            ChannelType.TECHNICAL: "このチャンネルは技術系チャンネルです。専門用語を適度に使用し、技術的な議論に対応してください。",
            ChannelType.DEFAULT: "",
        }
        
        if self.channel_type != ChannelType.DEFAULT:
            instructions.append(type_instructions[self.channel_type])
        
        # カジュアル度の調整
        if self.casual_level >= 7:
            instructions.append("普段よりカジュアルなトーンで話してください。")
        elif self.casual_level <= 3:
            instructions.append("より丁寧でフォーマルなトーンを維持してください。")
        
        # 予測記録レベルの調整
        if self.prediction_recording_level >= 8:
            instructions.append("予測と思われる発言は積極的に記録してください。")
        elif self.prediction_recording_level <= 2:
            instructions.append("予測の記録は控えめにしてください。")
        
        # プレモーテム頻度の調整
        if self.premortem_frequency >= 8:
            instructions.append("プレモーテム質問を積極的に投げかけてください。")
        elif self.premortem_frequency <= 2:
            instructions.append("プレモーテム質問は控えてください。")
        
        # カスタムプロンプト
        if self.custom_prompt:
            instructions.append(self.custom_prompt)
        
        return "\n".join(instructions)


# デフォルトのチャンネル設定
DEFAULT_CHANNEL_CONFIGS = {
    # 未来予測チャンネル
    "未来予測": ChannelBehavior(
        channel_type=ChannelType.PREDICTION,
        prediction_recording_level=10,
        casual_level=5,
        premortem_frequency=7,
        enable_discussion_summary=True,
        enable_passive_monitoring=True,
    ),
    # 雑談チャンネル
    "雑談": ChannelBehavior(
        channel_type=ChannelType.GENERAL,
        prediction_recording_level=3,
        casual_level=7,
        premortem_frequency=2,
        enable_discussion_summary=True,
        enable_passive_monitoring=False,
    ),
    # VCチャンネル
    "vc": ChannelBehavior(
        channel_type=ChannelType.VOICE,
        prediction_recording_level=5,
        casual_level=6,
        premortem_frequency=3,
        enable_discussion_summary=True,
        enable_passive_monitoring=False,
    ),
    # シンギュラリティまで生き残ろうch
    "生き残ろう": ChannelBehavior(
        channel_type=ChannelType.GENERAL,
        prediction_recording_level=5,
        casual_level=6,
        premortem_frequency=5,
        enable_discussion_summary=True,
        enable_passive_monitoring=True,
    ),
}


class ChannelConfigManager:
    """チャンネル設定の管理"""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.config_file = self.data_dir / "channel_config.json"
        
        # channel_id -> ChannelBehavior
        self._configs: dict[int, ChannelBehavior] = {}
        
        # channel_name_pattern -> ChannelBehavior (名前ベースのマッチング用)
        self._name_patterns: dict[str, ChannelBehavior] = DEFAULT_CHANNEL_CONFIGS.copy()
        
        self._load()
    
    def _load(self) -> None:
        """設定をファイルから読み込み"""
        if self.config_file.exists():
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    
                    # ID指定の設定を読み込み
                    for channel_id_str, config_dict in data.get("channels", {}).items():
                        channel_id = int(channel_id_str)
                        config_dict["channel_type"] = ChannelType(config_dict.get("channel_type", "default"))
                        self._configs[channel_id] = ChannelBehavior(**config_dict)
                    
                    # 名前パターンの設定を読み込み
                    for pattern, config_dict in data.get("patterns", {}).items():
                        config_dict["channel_type"] = ChannelType(config_dict.get("channel_type", "default"))
                        self._name_patterns[pattern] = ChannelBehavior(**config_dict)
                        
            except (json.JSONDecodeError, IOError, ValueError):
                pass  # 読み込み失敗時はデフォルトを使用
    
    def _save(self) -> None:
        """設定をファイルに保存"""
        data = {
            "channels": {},
            "patterns": {}
        }
        
        for channel_id, config in self._configs.items():
            config_dict = asdict(config)
            config_dict["channel_type"] = config.channel_type.value
            data["channels"][str(channel_id)] = config_dict
        
        for pattern, config in self._name_patterns.items():
            config_dict = asdict(config)
            config_dict["channel_type"] = config.channel_type.value
            data["patterns"][pattern] = config_dict
        
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def get_config(
        self,
        channel_id: int,
        channel_name: Optional[str] = None
    ) -> ChannelBehavior:
        """
        チャンネルの設定を取得
        
        優先順位:
        1. チャンネルID指定の設定
        2. チャンネル名パターンマッチング
        3. デフォルト設定
        
        Args:
            channel_id: チャンネルID
            channel_name: チャンネル名（パターンマッチング用）
        
        Returns:
            チャンネルの振る舞い設定
        """
        # ID指定の設定があれば優先
        if channel_id in self._configs:
            return self._configs[channel_id]
        
        # 名前パターンマッチング
        if channel_name:
            channel_name_lower = channel_name.lower()
            for pattern, config in self._name_patterns.items():
                if pattern.lower() in channel_name_lower:
                    return config
        
        # デフォルト設定
        return ChannelBehavior()
    
    def set_config(
        self,
        channel_id: int,
        config: ChannelBehavior
    ) -> None:
        """
        チャンネルの設定を登録
        
        Args:
            channel_id: チャンネルID
            config: 振る舞い設定
        """
        self._configs[channel_id] = config
        self._save()
    
    def add_pattern(self, pattern: str, config: ChannelBehavior) -> None:
        """
        名前パターンの設定を追加
        
        Args:
            pattern: マッチングパターン（チャンネル名に含まれる文字列）
            config: 振る舞い設定
        """
        self._name_patterns[pattern] = config
        self._save()
    
    def should_monitor(
        self,
        channel_id: int,
        channel_name: Optional[str] = None
    ) -> bool:
        """パッシブモニタリングを有効にすべきかを判定"""
        config = self.get_config(channel_id, channel_name)
        return config.enable_passive_monitoring
    
    def get_prompt_instruction(
        self,
        channel_id: int,
        channel_name: Optional[str] = None
    ) -> str:
        """LLMに渡すチャンネル固有の指示を取得"""
        config = self.get_config(channel_id, channel_name)
        return config.to_prompt_instruction()


# シングルトンインスタンス
_channel_config_manager: Optional[ChannelConfigManager] = None


def get_channel_config_manager(data_dir: str = "data") -> ChannelConfigManager:
    """ChannelConfigManagerのシングルトンインスタンスを取得"""
    global _channel_config_manager
    if _channel_config_manager is None:
        _channel_config_manager = ChannelConfigManager(data_dir)
    return _channel_config_manager
