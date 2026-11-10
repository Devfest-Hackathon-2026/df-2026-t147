"""Gemini(Vertex AI)疎通確認。デプロイ前にローカルで実行する。
  gcloud auth application-default login
  $env:GOOGLE_CLOUD_PROJECT="あなたのプロジェクトID"; $env:GEMINI_ENABLED="1"
  python scripts/check_gemini.py
3つとも「OK(gemini)」になれば連携成功。NGなら理由の目安を表示する。"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("GEMINI_ENABLED", "1")

from app import config, content, guard, prompts, rules  # noqa: E402
from app.llm import get_llm  # noqa: E402

if not config.gcp_project():
    sys.exit("GOOGLE_CLOUD_PROJECT が未設定です")
print(f"project={config.gcp_project()} location={config.gcp_location()} model={config.gemini_model()}")
llm = get_llm()
fails = 0


def timed(prompt):
    t = time.perf_counter()
    d = llm.generate_json(prompt)
    return d, time.perf_counter() - t

# 1) 声かけ3案
f = rules.today_facts({"2026-11-09": {"selfStarted": True}}, rules.date(2026, 11, 9))
d, sec = timed(prompts.phrases_prompt("たろう", rules.fact_lines(f)))
ph = (d or {}).get("phrases")
ok = guard.valid_phrases(ph)
print("声かけ:", f"({sec:.1f}秒)", "OK(gemini)" if ok else "NG", ph if ok else d); fails += not ok

# 2) 週の質問
base = content.fixed_questions(46)
d, sec = timed(prompts.questions_prompt(base))
ok = guard.valid_questions((d or {}).get("questions"), content.AXES)
print("質問:", f"({sec:.1f}秒)", "OK(gemini)" if ok else "NG", d if not ok else ""); fails += not ok

# 3) 傾向文
w = {"weekId": "2026-W46", "weekStart": "2026-11-09", "doneDays": 5, "selfDays": 3, "longestStreak": 3,
     "prevDoneDays": 4, "prevSelfDays": 1, "answerCount": 15, "answerDays": 5,
     "answerCounts": {"feeling": [3, 1, 1], "self": [2, 2, 1], "difficulty": [1, 3, 1]}, "trendAvailable": True}
d, sec = timed(prompts.trend_prompt("たろう", w))
txt = (d or {}).get("text")
ok = guard.valid_trend(txt)
print("傾向文:", f"({sec:.1f}秒)", "OK(gemini)" if ok else "NG", txt if ok else d); fails += not ok

if fails:
    print("\nNGの主な原因: ①gcloud auth application-default login 未実施 ②Vertex AI API未有効化(aiplatform.googleapis.com)"
          " ③プロジェクトIDの誤り ④モデル名/リージョン(GEMINI_MODEL, GOOGLE_CLOUD_LOCATION)")
sys.exit(1 if fails else 0)
