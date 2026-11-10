"""固定の質問・声かけ・傾向文（Gemini が使えない／出力が不適切な時の代替）。

選択肢は「楽・前向き → 大変」の順に固定する（index 0 が最も前向き）。
集計はこの順序に依存するため、Gemini が言い換える時も順序を変えさせない。
"""
AXES = ["feeling", "self", "difficulty"]

# 軸ごとの固定質問（週番号でローテーション。Gemini なしでも毎週変わる）
QUESTION_BANK = {
    "feeling": [
        {"text": "きょうの はみがき、きもちは どうだった？", "choices": ["たのしかった", "ふつう", "ちょっと いや"]},
        {"text": "はみがきの とき、どんな きもち？", "choices": ["いいきもち", "ふつう", "めんどう"]},
        {"text": "はみがき、すきだった？", "choices": ["すき", "まあまあ", "あまり"]},
    ],
    "self": [
        {"text": "だれかに いわれる まえに はじめた？", "choices": ["じぶんから", "まあまあ", "いわれて"]},
        {"text": "はみがき、じぶんで はじめた？", "choices": ["うん", "すこし", "いわれた"]},
        {"text": "「はみがきしよう」って じぶんで おもった？", "choices": ["おもった", "ちょっとだけ", "おもわなかった"]},
    ],
    "difficulty": [
        {"text": "はみがき、むずかしかった？", "choices": ["かんたん", "ふつう", "むずかしい"]},
        {"text": "はみがき、がんばった？", "choices": ["すごく", "ふつう", "ちょっと"]},
        {"text": "さいごまで できた？", "choices": ["かんたんに", "なんとか", "たいへんだった"]},
    ],
}

AXIS_LABEL = {"feeling": "きもち", "self": "じぶんから", "difficulty": "むずかしさ"}


def fixed_questions(week_number: int) -> list[dict]:
    out = []
    for ax in AXES:
        bank = QUESTION_BANK[ax]
        q = bank[week_number % len(bank)]
        out.append({"axis": ax, "text": q["text"], "choices": list(q["choices"])})
    return out


def fallback_phrases(f: dict) -> list[str]:
    """声かけ3案（固定）。評価（えらい子）ではなく行動を認める文にする。"""
    first = "今日も磨いたこと、ちゃんと気づいたよ。"
    if f.get("selfStreak", 0) >= 2:
        first = f"{f['selfStreak']}日続けて、自分から磨いたね。"
    elif f.get("streak", 0) >= 2:
        first = f"{f['streak']}日続けて磨いたこと、見てたよ。"
    return [first, "磨いてくれて、うれしいな。", "一緒に見られて、よかった。"]


_PRAISE_TREND_FIXED = {
    ("feeling", "up"): "はみがきの気持ちが、前向きになってきている様子が見られます。",
    ("self", "up"): "自分から始めることが、増えてきている様子が見られます。",
    ("difficulty", "up"): "はみがきを、やさしく感じる日が増えている様子が見られます。",
    ("difficulty", "less_hard"): "はみがきを、むずかしく感じる日が減ってきている様子が見られます。",
}


def fallback_praise_trend(trend: dict) -> str:
    """傾向の一文（固定）。事実の種類から作る。"""
    return _PRAISE_TREND_FIXED.get((trend["axis"], trend["kind"]), "気持ちが前向きになってきている様子が見られます。")


def fallback_trend(w: dict) -> str:
    """傾向文（固定）。断定せず、集計を言葉にするだけ。"""
    parts = [f"今週は{w['doneDays']}日できました（自分から始めた日：{w['selfDays']}日）。"]
    c = w["answerCounts"]
    if c["difficulty"][2] >= 2 or c["feeling"][2] >= 2:
        parts.append("「むずかしい」「いや」と答えた日もありましたが、続けられている傾向が見られます。")
    elif c["self"][0] >= 2:
        parts.append("自分から始められた日が複数あった傾向が見られます。")
    else:
        parts.append("気持ちや取り組み方は日によって違う様子が見られます。")
    return "".join(parts)
