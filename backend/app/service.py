"""業務ロジック。事実はルール、文面は Gemini（失敗時は固定文）。"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from datetime import date, timedelta

from . import config

from . import content, guard, prompts, rules
from .llm import get_llm
from .store import get_store

AGE_BANDS = ["3-4", "5-6", "7-8"]
_fail: dict[str, list[float]] = {}


class ApiError(Exception):
    def __init__(self, status: int, msg: str):
        self.status, self.msg = status, msg


# ---------- family / PIN ----------
def _hash_pin(pin: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}:{pin}".encode()).hexdigest()


def create_family(child_nickname: str, age_band: str, buddy_name: str, pin: str, demo: bool = False, gender: str = "girl",
                  created: date | None = None) -> str:
    if not (pin.isdigit() and len(pin) == 4):
        raise ApiError(422, "PINは4桁の数字にしてください")
    if age_band not in AGE_BANDS:
        raise ApiError(422, "年齢帯が正しくありません")
    fid = secrets.token_urlsafe(9)
    salt = secrets.token_hex(8)
    get_store().create_family(fid, {
        "childNickname": child_nickname.strip()[:12] or "こども",
        "ageBand": age_band,
        "buddyName": buddy_name.strip()[:12] or "なかま",
        "salt": salt, "pinHash": _hash_pin(pin, salt),
        "bloomFrom": None, "demo": demo,
        "createdAt": (created or date.today()).isoformat(),
        "gender": gender if gender in ("boy", "girl") else "girl", "given": {},
    })
    return fid


def require_family(fid: str | None) -> dict:
    fam = get_store().get_family(fid) if fid else None
    if not fam:
        raise ApiError(401, "家族コードが正しくありません")
    return fam


def check_pin(fid: str, pin: str | None) -> None:
    fam = require_family(fid)
    now = time.time()
    recent = [t for t in _fail.get(fid, []) if now - t < 30]
    if len(recent) >= 5:
        raise ApiError(429, "30秒あとにもういちど試してください")
    ok = pin is not None and hmac.compare_digest(_hash_pin(pin, fam["salt"]), fam["pinHash"])
    if not ok:
        recent.append(now)
        _fail[fid] = recent
        raise ApiError(403, "PINが違います")
    _fail.pop(fid, None)


# ---------- state ----------
def _snapshot(fid: str, today: date) -> dict:
    st = get_store()
    reports, approvals = st.get_reports(fid), st.get_approvals(fid)
    answers = st.get_answers(fid)
    t = today.isoformat()
    pts = rules.total_points(reports, approvals)
    done = rules.parse_dates(reports.keys())
    total_days = len(done)
    stage = rules.stage_of(total_days)
    fam = st.get_family(fid) or {}
    given = fam.get("given", {})
    earned = rules.earned_items(approvals)  # 親が承認した日の累計で付与
    owned: dict[str, int] = {}
    for e in earned:
        owned[e["key"]] = owned.get(e["key"], 0) + 1
    created = fam.get("createdAt") or (min(done).isoformat() if done else t)  # 古いデータは最初の報告日
    day_no = max(1, (today - date.fromisoformat(created)).days + 1)
    inventory = {k: max(0, owned.get(k, 0) - given.get(k, 0)) for k in rules.ITEM_KEYS}
    item_today = next((e["key"] for e in earned if e["date"] == t), None)
    return {
        "today": t,
        "reportedToday": t in reports,
        "answeredToday": any(a.get("date") == t for a in answers),
        "approvedToday": t in approvals,
        "streak": rules.current_streak(done, today),
        "selfStreak": rules.current_streak(rules.self_dates(reports), today),
        "points": pts, "stage": stage, "stageName": rules.STAGE_NAMES[stage - 1],
        "dayNo": day_no, "totalDays": total_days, "nextStageDays": rules.next_stage_days(total_days),
        "inventory": inventory, "itemToday": item_today,
        "daysToNextItem": rules.days_to_next_item(approvals),
        "sparkly": all(given.get(k, 0) >= 1 for k in rules.ITEM_KEYS),  # 4種ぜんぶ あげたことがある
        "sabori": rules.is_sabori(done, today) and t not in reports,
    }


def state(fid: str, today: date) -> dict:
    fam = require_family(fid)
    s = _snapshot(fid, today)
    s["demoMode"] = config.demo_mode()  # 日付操作パネル用。本番(DEMO_MODE未設定)では false
    bf = fam.get("bloomFrom")
    s["bloom"] = bool(bf and bf < today.isoformat())
    s["family"] = {k: fam[k] for k in ("childNickname", "buddyName", "ageBand")} | {
        "demo": fam.get("demo", False), "gender": fam.get("gender", "girl")}
    return s


def ack_bloom(fid: str) -> None:
    require_family(fid)
    get_store().update_family(fid, {"bloomFrom": None})


def give_item(fid: str, today: date, key: str) -> dict:
    fam = require_family(fid)
    if key not in rules.ITEM_KEYS:
        raise ApiError(422, "アイテムが正しくありません")
    if _snapshot(fid, today)["inventory"][key] <= 0:
        raise ApiError(409, "そのアイテムは持っていません")
    given = dict(fam.get("given", {}))
    given[key] = given.get(key, 0) + 1
    get_store().update_family(fid, {"given": given})
    return state(fid, today)


# ---------- daily flow ----------
def report(fid: str, today: date, self_started: bool) -> dict:
    require_family(fid)
    st = get_store()
    t = today.isoformat()
    if t not in st.get_reports(fid):  # 二重押しは無視（冪等）
        st.put_report(fid, t, {"done": True, "selfStarted": bool(self_started)})
    return state(fid, today)


# 子への質問は「家族ごと・日ごと」に作る。キャッシュキー: qd:{家族ID}:{日付}（source も保存）
_pool = ThreadPoolExecutor(max_workers=4)
_qlocks: dict[str, threading.Lock] = {}
_qlocks_guard = threading.Lock()


def _qkey(fid: str, d: date) -> str:
    return f"qd:{fid}:{d.isoformat()}"


def _qlock(key: str) -> threading.Lock:
    with _qlocks_guard:
        return _qlocks.setdefault(key, threading.Lock())


def _question_facts(fid: str, today: date) -> dict:
    """AIに渡す材料。事実だけ（名前は渡さない）。"""
    st = get_store()
    reports, answers = st.get_reports(fid), st.get_answers(fid)
    done, selfd = rules.parse_dates(reports.keys()), rules.self_dates(reports)
    since = (today - timedelta(days=6)).isoformat()
    counts = {ax: [0, 0, 0] for ax in content.AXES}
    for a in answers:
        if since <= str(a.get("date")) <= today.isoformat() and a.get("axis") in counts and a.get("choice") in (0, 1, 2):
            counts[a["axis"]][a["choice"]] += 1
    before = {d for d in done if d < today}
    return {"連続日数": rules.current_streak(done, today), "自分から始めた連続日数": rules.current_streak(selfd, today),
            "直近7日の回答の件数(軸:[前向き,ふつう,後ろ向き])": counts, "しばらく休んでいた": rules.is_sabori(before, today)}


def _fixed_questions(today: date) -> dict:
    items = content.fixed_questions(today.toordinal())
    return {"source": "fixed", "questions": [
        {"id": f"{today.isoformat()}-{q['axis']}", "axis": q["axis"], "text": q["text"], "choices": q["choices"]} for q in items]}


def ensure_questions(fid: str, today: date) -> dict:
    """その日の質問をキャッシュに用意して返す。二重生成はロックで防ぐ。AIが失敗・不正なら固定の質問。"""
    st = get_store()
    key = _qkey(fid, today)
    with _qlock(key):
        cached = st.get_cache(key)
        if cached:
            return cached
        out = None
        prev = st.get_cache(_qkey(fid, today - timedelta(days=1)))
        prev_texts = [q["text"] for q in (prev or {}).get("questions", [])]
        base = content.fixed_questions(today.toordinal())
        data = get_llm().generate_json(prompts.questions_prompt(_question_facts(fid, today), base, prev_texts),
                                       timeout_ms=config.question_timeout_ms())
        items = (data or {}).get("questions")
        if guard.valid_questions(items, content.AXES):
            by = {q["axis"]: q for q in items}
            out = {"source": "gemini", "questions": [
                {"id": f"{today.isoformat()}-{ax}", "axis": ax, "text": by[ax]["text"], "choices": list(by[ax]["choices"])}
                for ax in content.AXES]}
        out = out or _fixed_questions(today)
        st.put_cache(key, out)
        return out


def prefetch_questions(fid: str, today: date) -> None:
    """「できた」直後にバックグラウンドで呼ぶ。失敗しても体験は止めない。"""
    try:
        ensure_questions(fid, today)
    except Exception:  # noqa: BLE001
        pass


def questions(fid: str, today: date) -> list[dict]:
    """キャッシュがあればそれを返す。なければ最大5秒だけ生成を待ち、間に合わなければ固定の質問。"""
    cached = get_store().get_cache(_qkey(fid, today))
    if cached:
        return cached["questions"]
    try:
        return _pool.submit(ensure_questions, fid, today).result(timeout=config.question_timeout_ms() / 1000)["questions"]
    except (FutureTimeout, Exception):  # noqa: BLE001
        return _fixed_questions(today)["questions"]


def answer(fid: str, today: date, items: list[dict]) -> dict:
    require_family(fid)
    st = get_store()
    t = today.isoformat()
    if t not in st.get_reports(fid):
        raise ApiError(409, "先に「できたよ」を押してください")
    before = _snapshot(fid, today)["points"]
    if not any(a.get("date") == t for a in st.get_answers(fid)):  # 1日1回
        wid = rules.week_id(today)
        valid = [i for i in items if i.get("axis") in content.AXES and i.get("choice") in (0, 1, 2)]
        rows = [{"date": t, "weekId": wid, "axis": i["axis"], "choice": i["choice"],
                 "questionId": f"{wid}-{i['axis']}"} for i in valid]
        if rows:
            st.add_answers(fid, rows)
        st.update_family(fid, {"bloomFrom": t})  # 次に開いた時に開花
    s = state(fid, today)
    return {"pointsGained": s["points"] - before, "state": s}


# ---------- parent ----------
def _praise_trend_text(fid: str, today: date, facts: list[str], trend: dict) -> tuple[str, str]:
    """傾向の一文。キャッシュは 家族ID＋日付＋事実のハッシュ。失敗・検査落ちは固定の文。"""
    st = get_store()
    h = hashlib.sha1("|".join(facts).encode()).hexdigest()[:10]
    key = f"pt:{fid}:{today.isoformat()}:{h}"
    c = st.get_cache(key)
    if c:
        return c["text"], c["source"]
    data = get_llm().generate_json(prompts.praise_trend_prompt(facts), timeout_ms=config.question_timeout_ms())
    txt, src = (data or {}).get("text"), "gemini"
    if not guard.valid_praise_trend(txt, facts):
        txt, src = content.fallback_praise_trend(trend), "fixed"
    st.put_cache(key, {"text": txt, "source": src})
    return txt, src


def approval(fid: str, today: date) -> dict:
    """承認画面の材料。ほめどころ（事実）と、変化があれば傾向の一文だけ。声かけ例は phrase_hint で別に返す。"""
    require_family(fid)
    st = get_store()
    reports = st.get_reports(fid)
    t = today.isoformat()
    if t not in reports:
        return {"canApprove": False, "alreadyApproved": False, "facts": [], "trend": None, "trendSource": None}
    p = rules.praise_points(reports, st.get_answers(fid), today)
    trend, src = None, None
    if p["trend"]:
        trend, src = _praise_trend_text(fid, today, p["facts"], p["trend"])
    return {"canApprove": True, "alreadyApproved": t in st.get_approvals(fid),
            "facts": p["facts"], "trend": trend, "trendSource": src}


def phrase_hint(fid: str, today: date) -> dict:
    """声かけの例（押された時だけ作る）。3件。"""
    fam = require_family(fid)
    st = get_store()
    reports = st.get_reports(fid)
    t = today.isoformat()
    if t not in reports:
        return {"phrases": [], "source": None}
    f = rules.today_facts(reports, today)
    lines = rules.fact_lines(f)
    key = f"phrases:{fid}:{t}:{f['streak']}:{f['selfStreak']}"
    cached = st.get_cache(key)
    if not cached:
        data = get_llm().generate_json(prompts.phrases_prompt(fam["childNickname"], lines))
        ph = (data or {}).get("phrases")
        src = "gemini"
        if not guard.valid_phrases(ph):
            ph, src = content.fallback_phrases(f), "fixed"
        cached = {"phrases": ph, "source": src}
        st.put_cache(key, cached)
    return {"phrases": cached["phrases"], "source": cached["source"]}


def approve(fid: str, today: date, phrase: str, edited: bool, watched: bool) -> dict:
    require_family(fid)
    st = get_store()
    t = today.isoformat()
    if t not in st.get_reports(fid):
        raise ApiError(409, "今日の記録がまだありません")
    fresh = t not in st.get_approvals(fid)
    if fresh:
        st.put_approval(fid, t, {"phraseUsed": (phrase or "")[:80], "edited": bool(edited), "watched": bool(watched)})
    s = state(fid, today)
    # この承認でアイテムが付与された時だけ itemGot を返す（子に見える演出用）
    return {"reaction": "special", "state": s, "itemGot": s["itemToday"] if fresh else None}


def weekly(fid: str, today: date) -> dict:
    fam = require_family(fid)
    st = get_store()
    w = rules.week_facts(st.get_reports(fid), st.get_answers(fid), today)
    out = {k: w[k] for k in ("weekId", "weekStart", "doneDays", "selfDays", "longestStreak",
                              "prevDoneDays", "prevSelfDays", "answerCount", "trendAvailable")}
    out["trendText"] = None
    if w["trendAvailable"]:
        key = f"trend:{fid}:{w['weekId']}:{w['answerCount']}:{w['doneDays']}:{w['selfDays']}"
        c = st.get_cache(key)
        if not c:
            data = get_llm().generate_json(prompts.trend_prompt(fam["childNickname"], w))
            txt = (data or {}).get("text")
            src = "gemini"
            if not guard.valid_trend(txt):
                txt, src = content.fallback_trend(w), "fixed"
            c = {"text": txt, "source": src}
            st.put_cache(key, c)
        out["trendText"], out["trendSource"] = c["text"], c["source"]
    return out


def delete_family(fid: str) -> None:
    require_family(fid)
    get_store().delete_family(fid)
