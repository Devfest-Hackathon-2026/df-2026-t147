"""AI出力のガードレール。通らなければ固定文に差し替える。"""
import re

BANNED = [
    "性格", "診断", "病気", "障害", "ダメ", "だめ", "怠", "サボ", "わがまま", "やる気がない",
    "天才", "才能", "向いていない", "どうせ", "しつけ", "問題児", "困った子", "悪い子", "いい子",
]
# 子どもへの質問に使えない言葉（責める・決めつける・比べる・評価に聞こえる語）
Q_BANNED = [
    "なんで", "どうして", "ちゃんと", "いつも", "ぜんぜん", "ぜったい", "また", "まだ", "なのに", "べき", "しなさい",
    "できない", "できなかった", "ほかの", "みんな", "おともだち", "きょうだい", "いもうと", "おとうと", "おにいちゃん", "おねえちゃん",
    "よりも", "えらい", "じょうず", "だめ", "わるい", "さぼ", "なまけ", "はずかしい", "のうりょく", "せいかく", "びょうき",
]
Q_MAX_TEXT = 20
_KANJI = re.compile(r"[一-鿿]")
_SENTENCE_END_ASSERT = re.compile(r"(この子は|うちの子は).{0,12}(です|だ|である)")


def clean_text(t: str, max_len: int) -> bool:
    if not isinstance(t, str) or not t.strip() or len(t) > max_len:
        return False
    if any(b in t for b in BANNED):
        return False
    if _SENTENCE_END_ASSERT.search(t):
        return False
    return True


def is_kana_only(t: str) -> bool:
    """子ども向け画面用。漢字を含まない。"""
    return not _KANJI.search(t)


def valid_phrases(items, max_len: int = 40) -> bool:
    return (
        isinstance(items, list)
        and len(items) == 3
        and all(clean_text(x, max_len) for x in items)
        and len(set(items)) == 3
    )


# 傾向の一文の検査。事実にない数字・断定・責める語を許さない
TREND_BANNED = ["いつも", "ちゃんと", "なんで", "どうして", "ぜんぜん", "ぜったい", "かならず", "きっと", "まだ", "また", "すごい", "えらい"]
TREND_ENDINGS = ("見られます。", "見られます", "ようです。", "ようです", "見えます。", "見えます", "ありそうです。", "ありそうです")
_DIGITS = re.compile(r"[0-9０-９]+")


def valid_praise_trend(t, facts: list[str], min_len: int = 10, max_len: int = 60) -> bool:
    if not clean_text(t, max_len) or len(t) < min_len:
        return False
    if "\n" in t or t.rstrip("。").count("。") > 0:  # 1文だけ
        return False
    if any(b in t for b in TREND_BANNED):
        return False
    if not t.endswith(TREND_ENDINGS):
        return False
    allowed = {n for f in facts for n in _DIGITS.findall(f)}
    return all(n in allowed for n in _DIGITS.findall(t))


def valid_questions(items, axes: list[str]) -> bool:
    """軸がちょうど1問ずつそろい、選択肢が3つ、短く、ひらがな中心で、禁止語を含まない。"""
    if not isinstance(items, list) or len(items) != len(axes):
        return False
    if not all(isinstance(q, dict) for q in items):
        return False
    if sorted(str(q.get("axis")) for q in items) != sorted(axes):
        return False
    for q in items:
        ch = q.get("choices")
        t = q.get("text")
        if not isinstance(ch, list) or len(ch) != 3:
            return False
        if not clean_text(t, Q_MAX_TEXT) or not is_kana_only(t) or "みが" not in t:
            return False
        if any(b in t for b in Q_BANNED):
            return False
        if any((not clean_text(c, 10)) or (not is_kana_only(c)) or any(b in c for b in Q_BANNED) for c in ch):
            return False
        if len(set(ch)) != 3:
            return False
    return True


def valid_trend(t, max_len: int = 140) -> bool:
    return clean_text(t, max_len)
