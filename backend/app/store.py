"""保存層。開発は MemoryStore（任意でJSONに保存）、本番は FirestoreStore。

保存するのはニックネーム・年齢帯・申告・回答・承認のみ。実名や写真は扱わない。
"""
from __future__ import annotations

import json
import os
import threading
from typing import Protocol

from . import config


class Store(Protocol):
    def create_family(self, fid: str, fam: dict) -> None: ...
    def get_family(self, fid: str) -> dict | None: ...
    def update_family(self, fid: str, patch: dict) -> None: ...
    def delete_family(self, fid: str) -> None: ...
    def get_reports(self, fid: str) -> dict: ...
    def put_report(self, fid: str, date_iso: str, data: dict) -> None: ...
    def get_answers(self, fid: str) -> list: ...
    def add_answers(self, fid: str, items: list) -> None: ...
    def get_approvals(self, fid: str) -> dict: ...
    def put_approval(self, fid: str, date_iso: str, data: dict) -> None: ...
    def get_cache(self, key: str) -> dict | None: ...
    def put_cache(self, key: str, val: dict) -> None: ...


class MemoryStore:
    def __init__(self, path: str = "") -> None:
        self._path = path
        self._lock = threading.RLock()
        self.d = {"families": {}, "reports": {}, "answers": {}, "approvals": {}, "cache": {}}
        if path and os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                self.d.update(json.load(f))

    def _save(self) -> None:
        if self._path:
            tmp = self._path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.d, f, ensure_ascii=False)
            os.replace(tmp, self._path)

    def create_family(self, fid, fam):
        with self._lock:
            self.d["families"][fid] = fam
            self._save()

    def get_family(self, fid):
        return self.d["families"].get(fid)

    def update_family(self, fid, patch):
        with self._lock:
            self.d["families"][fid].update(patch)
            self._save()

    def delete_family(self, fid):
        with self._lock:
            for k in ("families", "reports", "answers", "approvals"):
                self.d[k].pop(fid, None)
            for k in [k for k in self.d["cache"] if f":{fid}:" in k]:
                self.d["cache"].pop(k, None)
            self._save()

    def get_reports(self, fid):
        return dict(self.d["reports"].get(fid, {}))

    def put_report(self, fid, date_iso, data):
        with self._lock:
            self.d["reports"].setdefault(fid, {})[date_iso] = data
            self._save()

    def get_answers(self, fid):
        return list(self.d["answers"].get(fid, []))

    def add_answers(self, fid, items):
        with self._lock:
            self.d["answers"].setdefault(fid, []).extend(items)
            self._save()

    def get_approvals(self, fid):
        return dict(self.d["approvals"].get(fid, {}))

    def put_approval(self, fid, date_iso, data):
        with self._lock:
            self.d["approvals"].setdefault(fid, {})[date_iso] = data
            self._save()

    def get_cache(self, key):
        return self.d["cache"].get(key)

    def put_cache(self, key, val):
        with self._lock:
            self.d["cache"][key] = val
            self._save()


class FirestoreStore:
    """Firestore 版。families/{fid}（+ reports / answers / approvals サブコレクション）と cache/{key}。
    ※ 認証情報のある環境でのみ動作確認できる（ローカルテストはMemoryStoreで実施）。"""

    def __init__(self) -> None:
        from google.cloud import firestore

        self.db = firestore.Client(project=config.gcp_project() or None)

    def _fam(self, fid):
        return self.db.collection("families").document(fid)

    def create_family(self, fid, fam):
        self._fam(fid).set(fam)

    def get_family(self, fid):
        s = self._fam(fid).get()
        return s.to_dict() if s.exists else None

    def update_family(self, fid, patch):
        self._fam(fid).update(patch)

    def delete_family(self, fid):
        ref = self._fam(fid)
        for sub in ("reports", "answers", "approvals"):
            for doc in ref.collection(sub).stream():
                doc.reference.delete()
        for doc in self.db.collection("cache").where("fid", "==", fid).stream():
            doc.reference.delete()
        ref.delete()

    def get_reports(self, fid):
        return {d.id: d.to_dict() for d in self._fam(fid).collection("reports").stream()}

    def put_report(self, fid, date_iso, data):
        self._fam(fid).collection("reports").document(date_iso).set(data)

    def get_answers(self, fid):
        return [d.to_dict() for d in self._fam(fid).collection("answers").stream()]

    def add_answers(self, fid, items):
        batch = self.db.batch()
        col = self._fam(fid).collection("answers")
        for it in items:
            batch.set(col.document(), it)
        batch.commit()

    def get_approvals(self, fid):
        return {d.id: d.to_dict() for d in self._fam(fid).collection("approvals").stream()}

    def put_approval(self, fid, date_iso, data):
        self._fam(fid).collection("approvals").document(date_iso).set(data)

    def get_cache(self, key):
        s = self.db.collection("cache").document(key.replace("/", "_")).get()
        return s.to_dict().get("val") if s.exists else None

    def put_cache(self, key, val):
        fid = key.split(":")[1] if key.count(":") >= 2 else ""
        self.db.collection("cache").document(key.replace("/", "_")).set({"val": val, "fid": fid})


_store: Store | None = None


def get_store() -> Store:
    global _store
    if _store is None:
        _store = FirestoreStore() if config.storage_kind() == "firestore" else MemoryStore(config.data_file())
    return _store


def set_store(s: Store | None) -> None:  # テスト用
    global _store
    _store = s
