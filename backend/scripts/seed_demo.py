"""デモ動画用データ投入（DEMO_MODE=1 のサーバーに対して実行）。
  python scripts/seed_demo.py http://localhost:8000
作られる家族は「デモ用データ」バッジ付き。実在の人物データではありません。

15日分（毎日報告・質問に回答）。親の承認は、最終日の前の14日のうち3日だけ抜いて11日分。
  → 承認前の在庫は calcium / phosphorus / vitd の3個（承認3・6・9日目に付与）、あげたものは0。
  → 最終日（承認前）に承認すると12日目の承認で vitc が付与され、4種類がそろう（全部あげるとピカピカ）。
承認を抜く日も報告は毎日するので、さぼり演出は出ない。"""
import sys
from datetime import datetime, timedelta

import httpx

DAYS = 15
SKIP_APPROVAL = {2, 6, 10}  # 承認しない日（最終日は含めない）
base = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
c = httpx.Client(base_url=base, timeout=30)
start = datetime.now().astimezone().replace(hour=19, minute=0, second=0, microsecond=0) - timedelta(days=DAYS - 1)
fid = c.post("/api/families", headers={"X-Demo": "1", "X-Debug-Now": start.isoformat()}, json={
    "childNickname": "デモこ", "ageBand": "5-6", "buddyName": "もこ", "pin": "1234"}).json()["familyId"]
# 回答（きもち, じぶんから, むずかしさ）。0日目は比較の範囲外。
# 直近7日(8〜14日目)とその前の7日(1〜7日目)に回答のある日が各7日。前の7日は「ふつう・後ろ向き」寄り、直近は「前向き」寄り（承認画面の傾向が出る）
choices = [(1, 1, 2),
           (1, 1, 2), (2, 1, 2), (1, 2, 2), (1, 1, 1), (2, 1, 2), (1, 1, 2), (1, 2, 1),
           (0, 0, 1), (0, 1, 1), (1, 0, 1), (0, 0, 1), (0, 0, 0), (0, 1, 1), (0, 0, 1)]
for i in range(DAYS):
    at = (start + timedelta(days=i)).isoformat()
    h = {"X-Family-Id": fid, "X-Debug-Now": at, "X-Parent-Pin": "1234"}
    c.post("/api/report", headers=h, json={"selfStarted": i not in (3, 4, 5, 9)})
    qs = c.get("/api/questions", headers=h).json()["questions"]
    c.post("/api/answers", headers=h, json={"answers": [{"axis": q["axis"], "choice": ch} for q, ch in zip(qs, choices[i])]})
    if i < DAYS - 1 and i not in SKIP_APPROVAL:  # 最終日は承認前の状態を残す（デモで承認操作を見せるため）
        c.post("/api/parent/approve", headers=h, json={"phrase": "", "edited": False, "watched": i % 2 == 0})
print("familyId:", fid)
print("ブラウザのコンソールで: localStorage.setItem('fid','%s'); location.reload()" % fid)
