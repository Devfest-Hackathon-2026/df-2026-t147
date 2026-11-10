"""ルール算出（Gemini を使わない。数値の確定はここだけで行う）。

日付の境界は午前4時（JST）。深夜の歯みがきを前日扱いにするため。
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))  # 日本は夏時間なし。tzdata不要（Windows対策）
DAY_START_HOUR = 4

# ポイント（暫定値。資料の値に合わせた。曖昧な部分は下記コメントの解釈を採用）
PT_REPORT = 10
PT_STREAK3 = 3      # 連続3日以上
PT_STREAK7 = 5      # 連続7日以上（3日以上の+3の代わりに+5。加算ではない）
PT_WATCHED = 5      # 「見てもらえた日は多め」→ +5（暫定）
PT_APPROVED = 20    # 親の承認の特別ボーナス

# 成長は「通算の歯みがき日数」で決める（連続ではない。途切れても戻らない）
STAGE_THRESHOLDS = [1, 5, 15]  # たまご→あかちゃん(1日〜)→みならい(5日〜)→りっぱな大人(15日〜)
STAGE_NAMES = ["たまご", "あかちゃん", "みならい", "りっぱな大人"]

# アイテム: 親が承認した日が累計ITEM_EVERY日ごとに1つ、4種を順番に付与（承認記録から算出。保存不要）
ITEM_KEYS = ["calcium", "phosphorus", "vitd", "vitc"]
ITEM_EVERY = 3
SABORI_MISSED_DAYS = 3  # 丸3日やらなかったときだけ「さぼり」演出（最終手段）

MIN_ANSWERS_FOR_TREND = 4  # これ未満の週は傾向文を出さない


def effective_date(now: datetime) -> date:
    return (now.astimezone(JST) - timedelta(hours=DAY_START_HOUR)).date()


def week_id(d: date) -> str:
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def week_range(d: date) -> tuple[date, date]:
    monday = d - timedelta(days=d.weekday())
    return monday, monday + timedelta(days=6)


def parse_dates(keys) -> set[date]:
    return {date.fromisoformat(k) for k in keys}


def streak_ending(dates: set[date], end: date) -> int:
    """end を含めて遡った連続日数。end が含まれなければ 0。"""
    n, cur = 0, end
    while cur in dates:
        n += 1
        cur -= timedelta(days=1)
    return n


def current_streak(dates: set[date], today: date) -> int:
    """今日がまだ未申告なら昨日までの連続を返す（日が変わるまで途切れ扱いにしない）。"""
    end = today if today in dates else today - timedelta(days=1)
    return streak_ending(dates, end)


def stage_of(total_days: int) -> int:
    """1=たまご 2=あかちゃん 3=みならい 4=りっぱな大人（通算日数で決まる）"""
    s = 1
    for t in STAGE_THRESHOLDS:
        if total_days >= t:
            s += 1
    return s


def next_stage_days(total_days: int) -> int | None:
    for t in STAGE_THRESHOLDS:
        if total_days < t:
            return t
    return None


def earned_items(approvals: dict) -> list[dict]:
    """親が承認した日が累計ITEM_EVERY日たまるごとに1つ付与（連続は不要・古い順）。[{date, key}]"""
    out = []
    for i, d in enumerate(sorted(parse_dates(approvals.keys())), start=1):
        if i % ITEM_EVERY == 0:
            out.append({"date": d.isoformat(), "key": ITEM_KEYS[len(out) % len(ITEM_KEYS)]})
    return out


def days_to_next_item(approvals: dict) -> int:
    """次のアイテムまで、あと何日承認してもらえばよいか。"""
    return ITEM_EVERY - (len(approvals) % ITEM_EVERY)


def is_sabori(dates: set[date], today: date) -> bool:
    """一度でも記録があり、直近の記録から丸3日以上あいた（今日は数えない）"""
    if not dates:
        return False
    return (today - max(dates)).days - 1 >= SABORI_MISSED_DAYS


def total_points(reports: dict, approvals: dict) -> int:
    """reports: {iso: {"selfStarted": bool}}, approvals: {iso: {"watched": bool}}"""
    dates = parse_dates(reports.keys())
    total = 0
    for d in sorted(dates):
        total += PT_REPORT
        s = streak_ending(dates, d)
        if s >= 7:
            total += PT_STREAK7
        elif s >= 3:
            total += PT_STREAK3
        a = approvals.get(d.isoformat())
        if a is not None:
            total += PT_APPROVED
            if a.get("watched"):
                total += PT_WATCHED
    return total


def self_dates(reports: dict) -> set[date]:
    return {date.fromisoformat(k) for k, v in reports.items() if v.get("selfStarted")}


def _in_week(dates: set[date], monday: date, upto: date) -> list[date]:
    sunday = monday + timedelta(days=6)
    return sorted(d for d in dates if monday <= d <= min(sunday, upto))


def longest_run(ds: list[date]) -> int:
    best = run = 0
    prev = None
    for d in ds:
        run = run + 1 if prev and d - prev == timedelta(days=1) else 1
        best = max(best, run)
        prev = d
    return best


def week_facts(reports: dict, answers: list[dict], today: date) -> dict:
    monday, _ = week_range(today)
    wid = week_id(today)
    done = parse_dates(reports.keys())
    selfd = self_dates(reports)
    this_done = _in_week(done, monday, today)
    this_self = _in_week(selfd, monday, today)
    prev_monday = monday - timedelta(days=7)
    prev_done = _in_week(done, prev_monday, prev_monday + timedelta(days=6))
    prev_self = _in_week(selfd, prev_monday, prev_monday + timedelta(days=6))
    # 回答は今週分のみ集計。axis -> [count(choice0), count(choice1), count(choice2)]
    counts = {"feeling": [0, 0, 0], "self": [0, 0, 0], "difficulty": [0, 0, 0]}
    n_answers = 0
    ans_days = set()
    for a in answers:
        if a.get("weekId") != wid:
            continue
        ax, ch = a.get("axis"), a.get("choice")
        if ax in counts and ch in (0, 1, 2):
            counts[ax][ch] += 1
            n_answers += 1
            ans_days.add(a.get("date"))
    return {
        "weekId": wid,
        "weekStart": monday.isoformat(),
        "doneDays": len(this_done),
        "selfDays": len(this_self),
        "longestStreak": longest_run(this_done),
        "prevDoneDays": len(prev_done) if prev_done else None,
        "prevSelfDays": len(prev_self) if prev_done else None,
        "answerCount": n_answers,
        "answerDays": len(ans_days),
        "answerCounts": counts,
        "trendAvailable": len(ans_days) >= MIN_ANSWERS_FOR_TREND,
    }


def today_facts(reports: dict, today: date) -> dict:
    done = parse_dates(reports.keys())
    selfd = self_dates(reports)
    st = current_streak(done, today)
    sst = current_streak(selfd, today)
    monday, _ = week_range(today)
    this_self = len(_in_week(selfd, monday, today))
    prev_monday = monday - timedelta(days=7)
    prev_done = _in_week(done, prev_monday, prev_monday + timedelta(days=6))
    prev_self = len(_in_week(selfd, prev_monday, prev_monday + timedelta(days=6)))
    return {
        "streak": st,
        "selfStreak": sst,
        "selfToday": today in selfd,
        "thisWeekSelf": this_self,
        "prevWeekSelf": prev_self if prev_done else None,
    }


def fact_lines(f: dict) -> list[str]:
    """親に見せる事実（ルール算出）。断定せず、数えられることだけを書く。"""
    lines: list[str] = []
    if f["streak"] >= 2:
        lines.append(f"{f['streak']}日連続で歯みがきをしました")
    else:
        lines.append("今日、歯みがきをしました")
    if f["selfStreak"] >= 2:
        lines.append(f"{f['selfStreak']}日続けて、自分から始めました")
    elif f["selfToday"]:
        lines.append("今日は自分から始めました")
    p = f.get("prevWeekSelf")
    if p is not None and f["thisWeekSelf"] > p:
        lines.append(f"自分から始めた日が先週より増えました（今週{f['thisWeekSelf']}日／先週{p}日）")
    return lines


# ---------- 承認画面の「ほめどころ」（ルールだけで算出。AIは使わない） ----------
MILESTONES = (3, 5, 7, 10, 14, 20, 30, 50, 100)  # きりのよい日数
TREND_MIN_ANSWER_DAYS = 4  # 比べる各期間で、回答のある日がこれ以上ないと変化は出さない
FALLBACK_POINT = "きょうも、できたと伝えにきました"
_AXIS_TREND_LABEL = {"feeling": "きもち", "self": "じぶんから", "difficulty": "むずかしさ"}


def _answers_in(answers: list[dict], start: date, end: date) -> list[dict]:
    s, e = start.isoformat(), end.isoformat()
    return [a for a in answers if s <= str(a.get("date")) <= e and a.get("axis") in _AXIS_TREND_LABEL and a.get("choice") in (0, 1, 2)]


def _share(rows: list[dict], axis: str, choice: int) -> float | None:
    xs = [a for a in rows if a["axis"] == axis]
    return sum(1 for a in xs if a["choice"] == choice) / len(xs) if xs else None


def answer_trend(answers: list[dict], today: date) -> dict | None:
    """直近7日と、その前の7日を比べる。回答のある日が各期間で4日以上ない時は None。
    よくなった軸だけを事実にする（悪化した軸は返さない）。{axis, kind, fact} または None。"""
    cur = _answers_in(answers, today - timedelta(days=6), today)
    prev = _answers_in(answers, today - timedelta(days=13), today - timedelta(days=7))
    if len({a["date"] for a in cur}) < TREND_MIN_ANSWER_DAYS or len({a["date"] for a in prev}) < TREND_MIN_ANSWER_DAYS:
        return None
    best = None  # (増えた幅, axis, kind)
    for ax in _AXIS_TREND_LABEL:
        c0, p0 = _share(cur, ax, 0), _share(prev, ax, 0)
        if c0 is not None and p0 is not None and c0 > p0:
            cand = (c0 - p0, ax, "up")
            best = max(best, cand) if best else cand
        if ax == "difficulty":
            c2, p2 = _share(cur, ax, 2), _share(prev, ax, 2)
            if c2 is not None and p2 is not None and c2 < p2:
                cand = (p2 - c2, ax, "less_hard")
                best = max(best, cand) if best else cand
    if not best:
        return None
    _, ax, kind = best
    label = _AXIS_TREND_LABEL[ax]
    fact = (f"「{label}」の質問で、「むずかしい」と答えた日が、前の7日より減りました" if kind == "less_hard"
            else f"「{label}」の質問で、前向きな答えの割合が、前の7日より増えました")
    return {"axis": ax, "kind": kind, "fact": fact}


def praise_points(reports: dict, answers: list[dict], today: date) -> dict:
    """{facts: 最大3件の事実の文, trend: answer_trend の結果 or None}"""
    done, selfd = parse_dates(reports.keys()), self_dates(reports)
    facts: list[str] = []
    sst = current_streak(selfd, today)
    if sst >= 2:
        facts.append(f"{sst}日続けて、自分から始めました")
    week_self = len([d for d in selfd if today - timedelta(days=6) <= d <= today])
    if week_self >= 2 and week_self != sst:
        facts.append(f"この7日で、自分から始めた日が{week_self}日ありました")
    st, total = current_streak(done, today), len(done)
    if st in MILESTONES:
        facts.append(f"{st}日連続で、続いています")
    elif total in MILESTONES:
        facts.append(f"通算{total}日、続いています")
    trend = answer_trend(answers, today)
    if trend:
        facts = facts[:2] + [trend["fact"]]
    facts = facts[:3] or [FALLBACK_POINT]
    return {"facts": facts, "trend": trend}
