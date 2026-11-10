from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient

from app import config, guard, rules
from app.llm import set_llm
from app.main import app
from app.store import MemoryStore, set_store


# ---------- rules ----------
def D(s): return date.fromisoformat(s)


def test_day_boundary_4am():
    assert rules.effective_date(datetime(2026, 11, 10, 3, 59, tzinfo=rules.JST)) == D("2026-11-09")
    assert rules.effective_date(datetime(2026, 11, 10, 4, 0, tzinfo=rules.JST)) == D("2026-11-10")


def test_streak_and_grace_until_today():
    ds = {D("2026-11-06"), D("2026-11-07"), D("2026-11-08")}
    assert rules.current_streak(ds, D("2026-11-09")) == 3  # 今日まだでも昨日まで継続
    assert rules.current_streak(ds, D("2026-11-10")) == 0  # 1日空いたら切れる
    assert rules.current_streak(ds | {D("2026-11-09")}, D("2026-11-09")) == 4


def test_points_and_stage():
    reports = {f"2026-11-0{i}": {"selfStarted": i >= 3} for i in range(1, 8)}
    p = rules.total_points(reports, {})
    assert p == 87  # 70 + 連続3日以上(+3)×4日 + 7日目(+5)
    assert rules.total_points(reports, {"2026-11-07": {}}) == p + 20
    assert [rules.stage_of(n) for n in (0, 1, 4, 5, 14, 15, 99)] == [1, 2, 2, 3, 3, 4, 4]  # 通算日数で成長


def test_week_trend_threshold():
    reports = {"2026-11-09": {"selfStarted": True}}
    wid = rules.week_id(D("2026-11-09"))
    ans = [{"date": f"2026-11-{d:02d}", "weekId": wid, "axis": ax, "choice": 0}
           for d in (9, 10, 11) for ax in ("feeling", "self", "difficulty")]
    w = rules.week_facts(reports, ans, D("2026-11-11"))
    assert w["trendAvailable"] is False  # 3日分(9件)では出さない
    ans += [{"date": "2026-11-12", "weekId": wid, "axis": "feeling", "choice": 0}]
    assert rules.week_facts(reports, ans, D("2026-11-12"))["trendAvailable"] is True


def test_items_every_3_approved_days_and_cycle():
    # 連続は不要。承認した日が累計3日たまるごとに1つ。種類は calcium→phosphorus→vitd→vitc の循環
    ap = {f"2026-11-{d:02d}": {} for d in (1, 3, 4, 8, 9, 12, 15)}  # 飛び飛びでもよい
    it = rules.earned_items(ap)
    assert [(e["date"], e["key"]) for e in it] == [("2026-11-04", "calcium"), ("2026-11-12", "phosphorus")]
    assert rules.earned_items({}) == []
    assert [e["key"] for e in rules.earned_items({f"2026-11-{d:02d}": {} for d in range(1, 16)})] == [
        "calcium", "phosphorus", "vitd", "vitc", "calcium"]
    assert rules.days_to_next_item({}) == 3
    assert rules.days_to_next_item({"2026-11-01": {}}) == 2
    assert rules.days_to_next_item({f"2026-11-0{d}": {} for d in (1, 2, 3)}) == 3


def test_sabori_only_after_3_full_missed_days():
    ds = {D("2026-11-01")}
    assert rules.is_sabori(ds, D("2026-11-04")) is False  # 2,3日が空き=2日
    assert rules.is_sabori(ds, D("2026-11-05")) is True   # 2,3,4日が空き=3日
    assert rules.is_sabori(set(), D("2026-11-05")) is False  # 新規は対象外


# ---------- guard ----------
def test_guard():
    assert guard.valid_phrases(["あ", "い", "う"])
    assert not guard.valid_phrases(["あ", "あ", "う"])
    assert not guard.valid_phrases(["あ" * 50, "い", "う"])
    assert not guard.valid_trend("x" * 200)


# ---------- API flow ----------
class FakeLLM:
    def __init__(self, out): self.out, self.calls, self.timeouts = out, 0, []
    def generate_json(self, prompt, timeout_ms=None):
        self.calls += 1; self.timeouts.append(timeout_ms); self.last = prompt
        return self.out


@pytest.fixture()
def client(monkeypatch):
    set_store(MemoryStore())
    set_llm(None)
    monkeypatch.setenv("DEMO_MODE", "1")
    yield TestClient(app)
    set_store(None)
    set_llm(None)


def H(fid, at="2026-11-09T10:00:00+09:00", pin=None):
    h = {"X-Family-Id": fid, "X-Debug-Now": at}
    if pin: h["X-Parent-Pin"] = pin
    return h


def make(client):
    r = client.post("/api/families", json={"childNickname": "たろう", "ageBand": "5-6", "buddyName": "もこ", "pin": "1234"})
    return r.json()["familyId"]


def test_full_flow(client):
    fid = make(client)
    s = client.get("/api/state", headers=H(fid)).json()
    assert s["reportedToday"] is False and s["stage"] == 1
    # 申告前は回答できない
    assert client.post("/api/answers", headers=H(fid), json={"answers": []}).status_code == 409
    s = client.post("/api/report", headers=H(fid), json={"selfStarted": True}).json()
    assert s["reportedToday"] and s["points"] == 10
    # 冪等
    assert client.post("/api/report", headers=H(fid), json={"selfStarted": True}).json()["points"] == 10
    qs = client.get("/api/questions", headers=H(fid)).json()["questions"]
    assert [q["axis"] for q in qs] == ["feeling", "self", "difficulty"]
    r = client.post("/api/answers", headers=H(fid), json={"answers": [{"axis": q["axis"], "choice": 0} for q in qs]}).json()
    assert r["state"]["answeredToday"]
    # 親側: PIN必須
    assert client.get("/api/parent/approval", headers=H(fid)).status_code == 403
    a = client.get("/api/parent/approval", headers=H(fid, pin="1234")).json()
    assert a["canApprove"] and a["facts"] and "phrases" not in a  # 声かけの候補は承認画面のAPIでは作らない
    hint = client.get("/api/parent/phrase-hint", headers=H(fid, pin="1234")).json()
    assert len(hint["phrases"]) == 3
    ap = client.post("/api/parent/approve", headers=H(fid, pin="1234"),
                     json={"phrase": hint["phrases"][0], "edited": False, "watched": True}).json()
    assert ap["state"]["approvedToday"] and ap["state"]["points"] >= 30
    # 翌日: 開花フラグ
    s2 = client.get("/api/state", headers=H(fid, at="2026-11-10T10:00:00+09:00")).json()
    assert s2["bloom"] is True
    client.post("/api/bloom/ack", headers=H(fid, at="2026-11-10T10:00:00+09:00"))
    assert client.get("/api/state", headers=H(fid, at="2026-11-10T10:00:00+09:00")).json()["bloom"] is False


def test_day_no_is_calendar_days_since_signup(client):
    fid = client.post("/api/families", headers={"X-Debug-Now": "2026-11-06T10:00:00+09:00"},
                      json={"childNickname": "たろう", "ageBand": "5-6", "buddyName": "もこ", "pin": "1234"}).json()["familyId"]
    s = client.get("/api/state", headers=H(fid, "2026-11-06T10:00:00+09:00")).json()
    assert s["dayNo"] == 1
    s = client.get("/api/state", headers=H(fid, "2026-11-09T10:00:00+09:00")).json()  # 登録3日後
    assert s["dayNo"] == 4 and s["totalDays"] == 0


def day(client, fid, d, approve=True, self_started=True):
    at = f"2026-11-{d:02d}T10:00:00+09:00"
    client.post("/api/report", headers=H(fid, at), json={"selfStarted": self_started})
    if not approve:
        return None
    return client.post("/api/parent/approve", headers=H(fid, at, pin="1234"),
                       json={"phrase": "", "edited": False, "watched": False}).json()  # 空でも承認できる


def test_item_is_granted_by_approval_not_by_report(client):
    fid = make(client)
    for d in (9, 10, 11):  # 3日連続で報告しても、承認がなければアイテムは無い。成長は報告日数で進む
        day(client, fid, d, approve=False)
    s = client.get("/api/state", headers=H(fid, "2026-11-11T12:00:00+09:00")).json()
    assert s["totalDays"] == 3 and s["stage"] == 2 and s["itemToday"] is None
    assert sum(s["inventory"].values()) == 0 and s["daysToNextItem"] == 3
    # 承認は1・2日目は付与なし、3日目の承認で付与（その承認のレスポンスにだけ itemGot）
    r1 = day(client, fid, 9)
    r2 = day(client, fid, 10)
    assert r1["itemGot"] is None and r2["itemGot"] is None
    assert r2["state"]["daysToNextItem"] == 1
    r3 = day(client, fid, 11)
    assert r3["itemGot"] == "calcium" and r3["state"]["itemToday"] == "calcium"
    assert r3["state"]["inventory"]["calcium"] == 1
    again = client.post("/api/parent/approve", headers=H(fid, "2026-11-11T10:00:00+09:00", pin="1234"),
                        json={"phrase": "x", "edited": False, "watched": False}).json()
    assert again["itemGot"] is None  # 同じ日の再承認では出さない


def test_give_items_and_sparkly(client):
    fid = make(client)
    at = "2026-11-30T10:00:00+09:00"
    for d in range(1, 13):  # 12日承認 → 4種ぜんぶ1つずつ
        day(client, fid, d)
    s = client.get("/api/state", headers=H(fid, at)).json()
    assert all(s["inventory"][k] == 1 for k in rules.ITEM_KEYS) and s["sparkly"] is False
    for n, k in enumerate(rules.ITEM_KEYS, start=1):
        s = client.post("/api/items/give", headers=H(fid, at), json={"key": k}).json()
        assert s["sparkly"] is (n == 4)
    assert s["inventory"]["calcium"] == 0
    assert client.post("/api/items/give", headers=H(fid, at), json={"key": "calcium"}).status_code == 409
    # 丸3日さぼると sabori。成長(通算)は戻らない
    s = client.get("/api/state", headers=H(fid, "2026-12-20T10:00:00+09:00")).json()
    assert s["sabori"] is True and s["stage"] == 3  # 12日 → みならい


def test_pin_lock(client):
    fid = make(client)
    for _ in range(5):
        assert client.post("/api/parent/verify", headers=H(fid), json={"pin": "0000"}).status_code == 403
    assert client.post("/api/parent/verify", headers=H(fid), json={"pin": "1234"}).status_code == 429


def test_phrase_hint_llm_used_and_fallback(client):
    fid = make(client)
    client.post("/api/report", headers=H(fid), json={"selfStarted": False})
    set_llm(FakeLLM({"phrases": ["ひとりではみがけたね", "さいごまでがんばったね", "きょうもえらいね"]}))
    a = client.get("/api/parent/phrase-hint", headers=H(fid, pin="1234")).json()
    assert a["source"] == "gemini" and len(a["phrases"]) == 3
    # 不正出力 → 固定文
    set_store(MemoryStore())
    fid = make(client)
    client.post("/api/report", headers=H(fid), json={"selfStarted": False})
    set_llm(FakeLLM({"phrases": ["ひとつだけ"]}))
    a = client.get("/api/parent/phrase-hint", headers=H(fid, pin="1234")).json()
    assert a["source"] == "fixed" and len(a["phrases"]) == 3
    assert client.get("/api/parent/phrase-hint", headers=H(fid)).status_code == 403  # PIN必須


def test_weekly_needs_answers(client):
    fid = make(client)
    w = client.get("/api/parent/weekly", headers=H(fid, pin="1234")).json()
    assert w["trendText"] is None
    for d in range(9, 13):
        at = f"2026-11-{d:02d}T10:00:00+09:00"
        client.post("/api/report", headers=H(fid, at), json={"selfStarted": True})
        qs = client.get("/api/questions", headers=H(fid, at)).json()["questions"]
        client.post("/api/answers", headers=H(fid, at), json={"answers": [{"axis": q["axis"], "choice": 1} for q in qs]})
    w = client.get("/api/parent/weekly", headers=H(fid, at, pin="1234")).json()
    assert w["trendAvailable"] and w["trendText"]


def test_delete_family(client):
    fid = make(client)
    assert client.delete("/api/family", headers=H(fid, pin="1234")).status_code == 200
    assert client.get("/api/state", headers=H(fid)).status_code == 401


# ---------- 子への質問（家族ごと・日ごと） ----------
GOOD_Q = {"questions": [
    {"axis": "self", "text": "きょうは じぶんから みがけた？", "choices": ["じぶんから", "すこし", "いわれて"]},
    {"axis": "feeling", "text": "はみがき、たのしかった？", "choices": ["たのしい", "ふつう", "いやだった"]},
    {"axis": "difficulty", "text": "はみがき、むずかしかった？", "choices": ["かんたん", "ふつう", "むずかしい"]},
]}


def q_of(client, fid, at="2026-11-09T10:00:00+09:00"):
    client.post("/api/report", headers=H(fid, at), json={"selfStarted": True})
    return client.get("/api/questions", headers=H(fid, at)).json()["questions"]


def test_questions_ai_used_with_axis_order_and_short_timeout(client):
    llm = FakeLLM(GOOD_Q)
    set_llm(llm)
    fid = make(client)
    qs = q_of(client, fid)
    assert [q["axis"] for q in qs] == ["feeling", "self", "difficulty"]  # 返ってきた順に関わらず軸は固定順
    assert qs[1]["text"] == "きょうは じぶんから みがけた？" and all(len(q["choices"]) == 3 for q in qs)
    assert qs[0]["choices"] == ["たのしい", "ふつう", "いやだった"]  # 0=前向き 1=ふつう 2=後ろ向き の並びは保持
    assert llm.timeouts == [5000] and llm.calls == 1  # 質問生成だけ5秒。reportの先読みで1回だけ作る
    assert "たろう" not in llm.last  # 子の名前は渡さない
    q_of(client, fid)  # 2回目はキャッシュ
    assert llm.calls == 1


@pytest.mark.parametrize("bad", [
    None,
    {"questions": GOOD_Q["questions"][:2]},  # 軸が足りない
    {"questions": [GOOD_Q["questions"][0]] * 3},  # 軸が重複
    {"questions": [dict(q, choices=q["choices"][:2]) for q in GOOD_Q["questions"]]},  # 選択肢が2つ
    {"questions": [dict(q, text="きょうの はみがき、なんで いやだったの？") for q in GOOD_Q["questions"]]},  # 禁止語
    {"questions": [dict(q, text="きょうは じぶんから はみがきを はじめられたかな？ ほんとうに？") for q in GOOD_Q["questions"]]},  # 長すぎ
    {"questions": [dict(q, text="今日の歯みがき") for q in GOOD_Q["questions"]]},  # 漢字
])
def test_questions_fallback_to_fixed(client, bad):
    set_llm(FakeLLM(bad))
    fid = make(client)
    qs = q_of(client, fid)
    assert [q["axis"] for q in qs] == ["feeling", "self", "difficulty"] and all(len(q["choices"]) == 3 for q in qs)
    from app.store import get_store
    assert get_store().get_cache(f"qd:{fid}:2026-11-09")["source"] == "fixed"


def test_questions_cache_is_per_family_and_per_day(client):
    from app.store import get_store
    llm = FakeLLM(GOOD_Q)
    set_llm(llm)
    a, b = make(client), make(client)
    q_of(client, a)
    q_of(client, b)
    assert llm.calls == 2  # 家族ごとに作る
    st = get_store()
    assert st.get_cache(f"qd:{a}:2026-11-09")["source"] == "gemini" and st.get_cache(f"qd:{b}:2026-11-09")
    q_of(client, a, "2026-11-10T10:00:00+09:00")
    assert llm.calls == 3  # 日ごとに作る
    assert "きょうは じぶんから みがけた？" in llm.last  # 前日の質問文を渡し、同じ言い回しを避けさせる
    client.delete("/api/family", headers=H(a, pin="1234"))
    assert st.get_cache(f"qd:{a}:2026-11-09") is None and st.get_cache(f"qd:{b}:2026-11-09")


def test_questions_without_llm_are_fixed(client):
    fid = make(client)  # LLM無効(NullLLM)
    qs = client.get("/api/questions", headers=H(fid)).json()["questions"]  # 先読み無しのGETでも固定で返る
    assert [q["axis"] for q in qs] == ["feeling", "self", "difficulty"]


def test_questions_timeout_returns_fixed(client, monkeypatch):
    import time

    class Slow:
        def generate_json(self, prompt, timeout_ms=None):
            time.sleep(0.5)
            return GOOD_Q
    set_llm(Slow())
    monkeypatch.setattr(config, "question_timeout_ms", lambda: 100)
    fid = make(client)
    qs = client.get("/api/questions", headers=H(fid)).json()["questions"]  # 間に合わない → 固定
    assert len(qs) == 3 and qs[0]["text"] != GOOD_Q["questions"][1]["text"]


def test_weekly_counts_by_axis_and_choice_not_wording(client):
    from app.store import get_store
    set_llm(FakeLLM(GOOD_Q))
    fid = make(client)
    for d in range(9, 13):
        at = f"2026-11-{d:02d}T10:00:00+09:00"
        qs = q_of(client, fid, at)
        ch = {"feeling": 0, "self": 1, "difficulty": 2}
        client.post("/api/answers", headers=H(fid, at), json={"answers": [{"axis": q["axis"], "choice": ch[q["axis"]]} for q in qs]})
    w = rules.week_facts(get_store().get_reports(fid), get_store().get_answers(fid), D("2026-11-12"))
    assert w["answerCounts"] == {"feeling": [4, 0, 0], "self": [0, 4, 0], "difficulty": [0, 0, 4]}
    assert w["trendAvailable"] is True


# ---------- 承認画面のほめどころ ----------
def ans(day, axis, choice):
    return {"date": f"2026-11-{day:02d}", "axis": axis, "choice": choice}


def _answers(prev_choice, cur_choice, axis="feeling"):
    """前の7日 11/02-11/08 の中の4日、直近7日 11/09-11/15 の中の4日に回答"""
    return ([ans(d, axis, prev_choice) for d in (2, 3, 4, 5)] + [ans(d, axis, cur_choice) for d in (9, 10, 11, 12)])


def test_praise_points_self_streak_and_limit():
    reports = {f"2026-11-{d:02d}": {"selfStarted": True} for d in range(9, 14)}
    p = rules.praise_points(reports, [], D("2026-11-13"))
    assert "5日続けて、自分から始めました" in p["facts"] and 1 <= len(p["facts"]) <= 3 and p["trend"] is None
    assert "5日連続で、続いています" in p["facts"]


def test_praise_points_fallback_when_no_fact():
    p = rules.praise_points({"2026-11-13": {"selfStarted": False}}, [], D("2026-11-13"))
    assert p["facts"] == [rules.FALLBACK_POINT]


def test_praise_trend_shows_only_improved_axes():
    today = D("2026-11-15")
    # 前向き(0)の割合が増えた → 出す
    t = rules.answer_trend(_answers(2, 0), today)
    assert t and t["axis"] == "feeling" and t["kind"] == "up"
    # 悪化(0 → 2)は出さない
    assert rules.answer_trend(_answers(0, 2), today) is None
    # 変わらない → 出さない
    assert rules.answer_trend(_answers(1, 1), today) is None
    # 悪化した軸と改善した軸が混ざる時は、改善した軸だけ
    mixed = _answers(0, 2, "feeling") + _answers(2, 0, "self")
    t = rules.answer_trend(mixed, today)
    assert t["axis"] == "self" and "きもち" not in t["fact"]
    # 「むずかしい」が減った
    t = rules.answer_trend(_answers(2, 1, "difficulty"), today)
    assert t and t["kind"] == "less_hard" and "減りました" in t["fact"]
    # 悪化した軸は facts にも出ない
    reports = {f"2026-11-{d:02d}": {"selfStarted": False} for d in range(9, 16)}
    p = rules.praise_points(reports, _answers(0, 2), today)
    assert p["trend"] is None and not any("答え" in f for f in p["facts"])


def test_praise_trend_needs_enough_answer_days():
    today = D("2026-11-15")
    few = [ans(d, "feeling", 2) for d in (2, 3, 4)] + [ans(d, "feeling", 0) for d in (9, 10, 11, 12)]  # 前の期間が3日
    assert rules.answer_trend(few, today) is None
    few2 = [ans(d, "feeling", 2) for d in (2, 3, 4, 5)] + [ans(d, "feeling", 0) for d in (9, 10, 11)]  # 直近が3日
    assert rules.answer_trend(few2, today) is None
    assert rules.answer_trend([], today) is None


FACTS = ["「きもち」の質問で、前向きな答えの割合が、前の7日より増えました", "3日連続で、続いています"]


def test_guard_praise_trend():
    ok = "気持ちが前向きになってきている様子が見られます。"
    assert guard.valid_praise_trend(ok, FACTS)
    assert guard.valid_praise_trend("この3日、続けている様子が見られます。", FACTS)
    assert not guard.valid_praise_trend("この5日、続けている様子が見られます。", FACTS)  # 事実にない数字
    assert not guard.valid_praise_trend("気持ちが前向きになりました。", FACTS)  # 断定の語尾
    assert not guard.valid_praise_trend("いつも前向きな様子が見られます。", FACTS)  # 禁止語
    assert not guard.valid_praise_trend("あ" * 70 + "様子が見られます。", FACTS)  # 長すぎ
    assert not guard.valid_praise_trend("見られます。", FACTS)  # 短すぎ
    assert not guard.valid_praise_trend("前向きです。気持ちが変わった様子が見られます。", FACTS)  # 1文ではない


def _trend_family(client):
    fid = make(client)
    from app.store import get_store
    st = get_store()
    for d in range(2, 16):
        st.put_report(fid, f"2026-11-{d:02d}", {"done": True, "selfStarted": False})
    st.add_answers(fid, [dict(a, weekId="x", questionId="x") for a in _answers(2, 0)])
    return fid


AT = "2026-11-15T10:00:00+09:00"


def test_approval_trend_gemini_and_fallback(client):
    from app.store import get_store
    fid = _trend_family(client)
    llm = FakeLLM({"text": "この数日、気持ちが前向きになってきている様子が見られます。"})
    set_llm(llm)
    a = client.get("/api/parent/approval", headers=H(fid, AT, pin="1234")).json()
    assert a["canApprove"] and a["trendSource"] == "gemini" and "見られます" in a["trend"] and len(a["facts"]) <= 3
    assert llm.timeouts == [5000] and "たろう" not in llm.last
    client.get("/api/parent/approval", headers=H(fid, AT, pin="1234"))
    assert llm.calls == 1  # 家族ID＋日付＋事実のハッシュでキャッシュ
    assert any(k.startswith(f"pt:{fid}:2026-11-15:") for k in get_store().d["cache"])
    # 検査に落ちる出力（事実にない数字）→ 固定文
    set_store(MemoryStore())
    fid = _trend_family(client)
    set_llm(FakeLLM({"text": "この9日、前向きな様子が見られます。"}))
    a = client.get("/api/parent/approval", headers=H(fid, AT, pin="1234")).json()
    assert a["trendSource"] == "fixed" and a["trend"].endswith("見られます。")
    # LLMなし → 固定文
    set_store(MemoryStore())
    fid = _trend_family(client)
    set_llm(None)
    a = client.get("/api/parent/approval", headers=H(fid, AT, pin="1234")).json()
    assert a["trendSource"] == "fixed"


def test_approval_without_change_has_no_trend_and_no_llm_call(client):
    fid = make(client)
    client.post("/api/report", headers=H(fid), json={"selfStarted": True})
    llm = FakeLLM({"text": "x"})
    set_llm(llm)  # 質問の先読みが終わってから差し替える
    a = client.get("/api/parent/approval", headers=H(fid, pin="1234")).json()
    assert a["trend"] is None and a["trendSource"] is None and llm.calls == 0


def test_approve_with_empty_or_written_phrase(client):
    fid = make(client)
    client.post("/api/report", headers=H(fid), json={"selfStarted": True})
    r = client.post("/api/parent/approve", headers=H(fid, pin="1234"), json={"edited": False, "watched": False})
    assert r.status_code == 200 and r.json()["state"]["approvedToday"]  # phrase 無しでも承認できる
    fid = make(client)
    client.post("/api/report", headers=H(fid), json={"selfStarted": True})
    r = client.post("/api/parent/approve", headers=H(fid, pin="1234"), json={"phrase": "", "edited": False, "watched": False})
    assert r.status_code == 200 and r.json()["state"]["approvedToday"]
    fid = make(client)
    client.post("/api/report", headers=H(fid), json={"selfStarted": True})
    r = client.post("/api/parent/approve", headers=H(fid, pin="1234"), json={"phrase": "ありがとう", "edited": True, "watched": True})
    assert r.json()["state"]["approvedToday"]


# ---------- デモモード ----------
def test_demo_mode_true_and_debug_now_works(client):
    fid = make(client)
    s = client.get("/api/state", headers=H(fid, "2026-11-09T10:00:00+09:00")).json()
    assert s["demoMode"] is True and s["today"] == "2026-11-09"


def test_production_ignores_debug_now_and_demo_mode_false(client, monkeypatch):
    from datetime import datetime
    monkeypatch.delenv("DEMO_MODE", raising=False)  # 本番相当
    assert config.demo_mode() is False
    fid = make(client)
    s = client.get("/api/state", headers=H(fid, "2020-01-01T10:00:00+09:00")).json()
    assert s["demoMode"] is False
    assert s["today"] == rules.effective_date(datetime.now(rules.JST)).isoformat()  # X-Debug-Now は無視される
    # 家族の登録日も現在時刻で決まる（デバッグ時刻は効かない）
    r = client.post("/api/families", headers={"X-Debug-Now": "2020-01-01T10:00:00+09:00"},
                    json={"childNickname": "たろう", "ageBand": "5-6", "buddyName": "もこ", "pin": "1234"})
    fid2 = r.json()["familyId"]
    assert client.get("/api/state", headers=H(fid2, "2020-01-05T10:00:00+09:00")).json()["dayNo"] == 1


def test_demo_new_family_starts_at_debug_now_day1(client):
    r = client.post("/api/families", headers={"X-Debug-Now": "2026-11-10T19:00:00+09:00"},
                    json={"childNickname": "たろう", "ageBand": "5-6", "buddyName": "もこ", "pin": "1234"})
    fid = r.json()["familyId"]
    s = client.get("/api/state", headers=H(fid, "2026-11-10T19:00:00+09:00")).json()
    assert s["dayNo"] == 1 and s["demoMode"] is True


def test_guard_questions_allow_halfwidth_spaces():
    q = [{"axis": "feeling", "text": "きょうの はみがき どうだった？", "choices": ["たのしい", "ふつう", "いやだった"]}]
    assert guard.valid_questions(q, ["feeling"])
