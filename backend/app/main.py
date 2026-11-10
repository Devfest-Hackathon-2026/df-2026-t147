from __future__ import annotations

import os
from datetime import datetime

from fastapi import BackgroundTasks, Depends, FastAPI, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import config, rules, service
from .service import ApiError

app = FastAPI(title="AI生活習慣支援RPG API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.exception_handler(ApiError)
async def _api_error(_: Request, e: ApiError):
    return JSONResponse(status_code=e.status, content={"detail": e.msg})


def now_jst(x_debug_now: str | None) -> datetime:
    # デモデータ作成用。DEMO_MODE=1 の時だけ有効
    if x_debug_now and config.demo_mode():
        return datetime.fromisoformat(x_debug_now).astimezone(rules.JST)
    return datetime.now(rules.JST)


def ctx(x_family_id: str | None = Header(None), x_debug_now: str | None = Header(None)):
    return x_family_id, rules.effective_date(now_jst(x_debug_now))


def parent_ctx(x_parent_pin: str | None = Header(None), c=Depends(ctx)):
    fid, today = c
    service.check_pin(fid, x_parent_pin)
    return fid, today


# ---------- models ----------
class FamilyIn(BaseModel):
    childNickname: str = Field(max_length=12)
    ageBand: str
    buddyName: str = Field(max_length=12)
    pin: str
    gender: str = "girl"


class ItemIn(BaseModel):
    key: str


class ReportIn(BaseModel):
    selfStarted: bool


class AnswerItem(BaseModel):
    axis: str
    choice: int


class AnswersIn(BaseModel):
    answers: list[AnswerItem]


class ApproveIn(BaseModel):
    phrase: str = Field(default="", max_length=80)  # 空でも承認できる
    edited: bool = False
    watched: bool = False


class PinIn(BaseModel):
    pin: str


# ---------- routes ----------
@app.get("/api/health")
def health():
    return {"ok": True}


@app.post("/api/families")
def create_family(b: FamilyIn, x_demo: str | None = Header(None), x_debug_now: str | None = Header(None)):
    demo = bool(x_demo) and config.demo_mode()
    return {"familyId": service.create_family(b.childNickname, b.ageBand, b.buddyName, b.pin, demo, b.gender,
                                              rules.effective_date(now_jst(x_debug_now)))}


@app.get("/api/state")
def get_state(c=Depends(ctx)):
    return service.state(*c)


@app.post("/api/report")
def post_report(b: ReportIn, bg: BackgroundTasks, c=Depends(ctx)):
    out = service.report(c[0], c[1], b.selfStarted)
    bg.add_task(service.prefetch_questions, c[0], c[1])  # 質問を裏で先に作る
    return out


@app.get("/api/questions")
def get_questions(c=Depends(ctx)):
    service.require_family(c[0])
    return {"questions": service.questions(c[0], c[1])}


@app.post("/api/answers")
def post_answers(b: AnswersIn, c=Depends(ctx)):
    return service.answer(c[0], c[1], [a.model_dump() for a in b.answers])


@app.post("/api/items/give")
def items_give(b: ItemIn, c=Depends(ctx)):
    return service.give_item(c[0], c[1], b.key)


@app.post("/api/bloom/ack")
def bloom_ack(c=Depends(ctx)):
    service.ack_bloom(c[0])
    return {"ok": True}


@app.post("/api/parent/verify")
def parent_verify(b: PinIn, c=Depends(ctx)):
    service.check_pin(c[0], b.pin)
    return {"ok": True}


@app.get("/api/parent/approval")
def parent_approval(c=Depends(parent_ctx)):
    return service.approval(*c)


@app.get("/api/parent/phrase-hint")
def parent_phrase_hint(c=Depends(parent_ctx)):
    return service.phrase_hint(*c)


@app.post("/api/parent/approve")
def parent_approve(b: ApproveIn, c=Depends(parent_ctx)):
    return service.approve(c[0], c[1], b.phrase, b.edited, b.watched)


@app.get("/api/parent/weekly")
def parent_weekly(c=Depends(parent_ctx)):
    return service.weekly(*c)


@app.delete("/api/family")
def delete_family(c=Depends(parent_ctx)):
    service.delete_family(c[0])
    return {"ok": True}


# ---------- フロント配信（同一コンテナで配信する場合） ----------
_sd = config.static_dir()
if _sd and os.path.isdir(_sd):
    app.mount("/assets", StaticFiles(directory=os.path.join(_sd, "assets")), name="assets")

    @app.get("/{path:path}")
    def spa(path: str):
        if path.startswith(("art/", "assets/", "api/")) and not os.path.isfile(os.path.join(_sd, path)):
            return JSONResponse(status_code=404, content={"detail": "Not Found"})  # 画像が無い時にHTMLを返さない
        f = os.path.join(_sd, path)
        if path and os.path.isfile(f) and ".." not in path:
            return FileResponse(f)
        return FileResponse(os.path.join(_sd, "index.html"))
