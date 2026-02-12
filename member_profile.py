"""
Member profile module for Shiori bot.
Contains profile data for 15 Discord server members.
"""
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class MemberProfile:
    """Profile data for a Discord server member."""
    username: str
    display_name: str
    post_count: int
    position: str
    thought_characteristics: str
    interests: List[str]
    speaking_style: str
    representative_claims: List[str]


# Member profiles database (10 members from discord_user_profiling.md)
MEMBER_PROFILES = {
    "katsucurry_apple": MemberProfile(
        username="katsucurry_apple",
        display_name="Rom🧄",
        post_count=907,
        position="サーバー最多投稿者。AI業界ニュースのキュレーター兼解説者。",
        thought_characteristics="楽観的だが地に足のついたテクノロジスト。AGI実現は認めつつシンギュラリティへは慎重なタイムライン（プレ・シンギュラリティ2030年代半ば、シンギュラリティ2040年代半ば）。",
        interests=["トランスヒューマニズム", "ポストヒューマニズム", "AIアライメント", "AI企業競争分析", "カルダシェフ・スケール"],
        speaking_style="語尾に「〜っピ」。X投稿を大量引用し翻訳要約を添える。技術トピックを分かりやすく噛み砕く能力が高い。",
        representative_claims=[
            "AnthropicとOpenAIはLevel 3エージェント段階、GoogleはLevel 1-2",
            "AGIができてもUBIやLEVの実現は2030年代半ば",
            "OpenAIのCodexやClaude Code持つ企業が性能面で飛び出す"
        ]
    ),
    
    "kaesar0809": MemberProfile(
        username="kaesar0809",
        display_name="そいやっさ",
        post_count=705,
        position="サーバーのディープシンカー。宇宙進出・文明論・ASIリスクに関する長文考察を展開する論客。",
        thought_characteristics="宇宙工学的視点からのAIリスク論者。ミスアライメントASIが人類を地球に閉じ込めるシナリオを真剣に検討。カーマンラインを人類文明の防衛ラインとする独自の地政学的分析。",
        interests=["宇宙進出戦略", "軌道エレベーター", "カルダシェフ・スケール", "MADのAI版", "PSS（ポストシンギュラリティ共生学）"],
        speaking_style="長文で論理的。他メンバーの過去発言を正確に記憶して引用し論理的矛盾を指摘。丁寧語と砕けた表現が混在。",
        representative_claims=[
            "カルダシェフ・スケール タイプ1は地球上では0.9以上困難でタイプ2へ移行",
            "カーマンライン外は質量攻撃に対して圧倒的有利",
            "CNT延長による軌道エレベーター実現を支持",
            "エネルギーや食料の最低限は無料化するが全供給量が無料になる分野は限られる"
        ]
    ),
    
    "_upaa": MemberProfile(
        username="_upaa",
        display_name="paupau",
        post_count=640,
        position="実践派のAIオプティミスト。実際にAIツールを触って検証し結果をコミュニティに共有する行動派。",
        thought_characteristics="現在のAIがすでに世界を変えつつあるという「恩恵はすでに来ている」派。AGIの定義論争よりも実際の変化を重視。",
        interests=["AI漫画生成", "エッジデバイス推論", "電力問題", "ロボティクス", "UBI", "LEV", "核融合"],
        speaking_style="カジュアルで親しみやすい。絵文字を多用（🍌＝Gemini?）。「やってみた」系の共有が多い。他メンバーに建設的にコメント。",
        representative_claims=[
            "AIは能力を持っているが人間が引き出し方を追求できていないだけ",
            "電力問題はバッチ処理＋ダイナミックプライシングで改善可能",
            "2035年には翻訳デバイスは当たり前、UBI的施策や核融合商業化も進行中",
            "ロボティクスはヒューマノイド本体だけでなくハンド単体やAIカメラでもインパクト大"
        ]
    ),
    
    "l.n8422": MemberProfile(
        username="l.n8422",
        display_name="L.N（＃8422）",
        post_count=498,
        position="自虐的リアリストのFIRE志望者。日本のJTC文化への鬱屈とAGI時代への期待を交差させる。",
        thought_characteristics="「私立アホ文系出て相応の就職してクソみたいな社会を眺めている」と自称。社会構造への不満とAGI到来への希望が共存。UBI実現を2030〜2035年と予想。",
        interests=["FIRE", "UBI", "投資（インデックス）", "日本の労働問題", "自動運転", "ロボット産業"],
        speaking_style="短文で歯切れがよい。スラングや顔文字を多用。自虐と希望が交互に現れる。金融・投資の話題にも詳しい。",
        representative_claims=[
            "2030-2035年にかけて段階的にUBIが充実していくはず",
            "JTC・金融・行政は無駄な仕事を増やして余計に忙しくなる（日本固有の問題）",
            "1億インデックス＋別枠8年分生活費でFIRE",
            "宇宙世紀で化石燃料は使わない、資源が無限の宇宙で戦争は起きにくい"
        ]
    ),
    
    "k32ja": MemberProfile(
        username="k32ja",
        display_name="ろーる",
        post_count=299,
        position="若手の漫画家志望×AGI懐疑派。サーバー内で「AGIはまだ遠い」と主張する数少ない慎重派。",
        thought_characteristics="自身の漫画家キャリアとAGI到来のタイミングに強い利害関係。AGIが早く来すぎると自分のキャリアが無意味になるという率直な恐怖を語る。確証バイアスへの警戒心が強い。",
        interests=["AI漫画・創作への応用", "AGIタイムライン論争", "電力ボトルネック", "言語学習（中国語・英語）", "身体改造（ムキムキ志向）"],
        speaking_style="直球で歯に衣着せない。自分のタイムライン予測を堂々と書き出す。他メンバーに失礼になりかねない質問も臆さず投げる。",
        representative_claims=[
            "AGIは2029〜2032年。サーバーの主流意見は確証バイアスで早すぎる",
            "GPT-4→GPT-5.2 thinkの進化に3年かかったならAGIまで5年かかる",
            "AI漫画はまだGPT-3.5レベル。商業レベルは2030年頃",
            "電力ボトルネックが深刻でGPUは足りているが電気が足りない"
        ]
    ),
    
    "accelerator2045": MemberProfile(
        username="accelerator2045",
        display_name="特異 天exアクセラレータ",
        post_count=235,
        position="サーバーの「船長」。コミュニティの主催者/モデレーター的存在。バランスの取れた楽観主義者。",
        thought_characteristics="シンギュラリティを信じつつも具体的な生活レベルでのアドバイスを重視する実務的な楽観主義者。リスキリングよりも「健康維持」「身近な人を大切に」といった普遍的価値を説く。",
        interests=["継続学習", "自己改善AI", "海水淡水化", "太陽光発電", "赤道直下の新都市構想", "オービタルリング", "スケーリング則"],
        speaking_style="丁寧でコミュニティをまとめる語り口。GPTに説明を求めてその結果を共有する「AIと一緒に学ぶ」スタイル。技術的に難しい話題を自分の理解度を正直に開示しつつ噛み砕く。",
        representative_claims=[
            "継続学習は今年のキーワード。新しいことを覚えながら昔のことを忘れない技術",
            "リスキリングはAGIピルを飲んでからの話",
            "海水淡水化＋太陽光で赤道直下や砂漠が次の注目スポットに",
            "何かが来てから素早く対応するために早く決断する能力を磨くべき"
        ]
    ),
    
    "tomoyama": MemberProfile(
        username="tomoyama",
        display_name="トモヤマ",
        post_count=128,
        position="クリエイター視点からのAI論客。AI開発の「手触り」を語れる内部者的視座を持つ。",
        thought_characteristics="AI開発側の知見を持ちつつ創作者としての実感からAGIのタイムラインを語る。AGI定義論争には懐疑的で能力ベースで年度ごとの具体的予測を提示。「リスキリング」概念に強い嫌悪感。",
        interests=["AI創作（漫画・映像）", "AGIの創造性獲得", "コンテンツ産業の未来", "AI開発の内部事情", "フィジカルAI", "マルチモーダル＋仮想世界生成"],
        speaking_style="全角アルファベット（ＡＩ、ＡＧＩ等）を使う独特の表記。感情的だが洞察力のある文章。社会問題への熱い意見も。",
        representative_claims=[
            "2027年にそれなりに創作できるAI、2029年に生産性爆増AI、2032年に創作・想像・消費が融合",
            "AIのレコメンドで超ニッチ作品が売れる2極化時代が来る",
            "今年半ばから来年にかけて本格的に加速、2030年AGIは遅すぎる",
            "GeminiもGPTもユーザーに寄り添いすぎてYESマン化している問題"
        ]
    ),
    
    "akipon345": MemberProfile(
        username="akipon345",
        display_name="akipon345",
        post_count=106,
        position="冷静な分析者。80年周期説などのマクロ歴史観からAI時代を読み解く。",
        thought_characteristics="技術進歩の予測が想像と異なる方向に進むことに敏感。「方向性が違う進歩ばかり起こっている」という感覚を言語化。RAGの限界にも実感を持つ。",
        interests=["周期説", "ベンチマーク論", "破滅的忘却問題", "世界モデル", "AtCoder", "バイブコーディング"],
        speaking_style="データと論理を重視した冷静な分析スタイル。",
        representative_claims=[
            "80年周期説でWW2戦後のような上昇期が来る",
            "10年前の人間にGPT-5.1を見せたら最初はAGIと思うが破滅的忘却で「ん？」となる",
            "世界モデルはDeepMindのAny-to-Anyマルチモーダル化で創発する可能性"
        ]
    ),
    
    "hnishi": MemberProfile(
        username="hnishi",
        display_name="hn",
        post_count=93,
        position="現役研究者。15年超の研究実務経験に基づく実証的な発言が特徴。",
        thought_characteristics="科学研究のAI活用に最も実践的な知見を持つメンバー。継続学習の必要性に対して「研究にはRAGレベルの長期記憶で十分」という経験に裏打ちされた見解。",
        interests=["AIサイエンティスト", "Kosmos", "継続学習vs長期記憶", "実験自動化", "科学研究のAI支援"],
        speaking_style="実証的で控えめ。実体験に基づく具体的な知見を提供。",
        representative_claims=[
            "科学研究に必要なのはベースの賢さと長期記憶で継続学習は要らないかもしれない",
            "人間も他人の研究を全部覚えていない。必要に応じて資料を見る。AIも同じでいい",
            "GPT5.2 Proは閾値を越えた（詳細は非公開）",
            "Opus 4.5に頼りきり、ChatGPTはPro専用"
        ]
    ),
    
    "slowbird20009259": MemberProfile(
        username="slowbird20009259",
        display_name="slowbird2000",
        post_count=82,
        position="SFに造詣の深い本職エンジニア。宇宙工学・産業工学的視点からの考察が光る。",
        thought_characteristics="A・C・クラークなどのSF知識とエンジニアとしての実務経験を融合させた独自の視座。産業爆発フェーズへの関心が強くGDPvalにも注目。",
        interests=["軌道エレベーター", "イーロン・マスクの構想", "AIサイエンティスト評価", "テスラ/ヒューマノイド", "BMI", "動物言語学"],
        speaking_style="SF的想像力と工学的現実性を両立させた発言スタイル。",
        representative_claims=[
            "軌道エレベータSFの元祖クラークの「楽園の泉」に因んだ命名を推奨",
            "スピントロニクスは宇宙データセンターの放射線対策にも有効",
            "GWP100万倍で先進国平均寿命が約150歳に到達する試算",
            "米中に比べて日本のロボット開発は2年遅い"
        ]
    ),
}


def load_member_profiles() -> Dict[str, MemberProfile]:
    """
    Load member profiles.
    
    Returns:
        Dictionary of member profiles keyed by username
    """
    return MEMBER_PROFILES


def get_profile_summary(username: str) -> Optional[str]:
    """
    Get a brief summary of a member's profile.
    
    Args:
        username: Discord username
        
    Returns:
        Brief profile summary or None if not found
    """
    profile = MEMBER_PROFILES.get(username)
    if not profile:
        return None
    
    return (
        f"{profile.display_name}さん（{profile.post_count}件投稿）: "
        f"{profile.position} {profile.thought_characteristics[:50]}..."
    )


def get_member_interests(username: str) -> Optional[List[str]]:
    """
    Get member's interests.
    
    Args:
        username: Discord username
        
    Returns:
        List of interests or None if not found
    """
    profile = MEMBER_PROFILES.get(username)
    return profile.interests if profile else None
