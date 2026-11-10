"""環境変数による設定。値は呼び出し時に読むので、テストで差し替えやすい。"""
import os


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def storage_kind() -> str:
    # memory | firestore
    return env("STORAGE", "memory")


def data_file() -> str:
    # memory ストアの保存先。空なら保存しない（再起動で消える）
    return env("DATA_FILE", "")


def demo_mode() -> bool:
    # 1 のときだけ X-Debug-Now ヘッダで「今」を差し替えられる（デモデータ用）
    return env("DEMO_MODE", "0") == "1"


def gemini_enabled() -> bool:
    return env("GEMINI_ENABLED", "0") == "1"


def gemini_model() -> str:
    return env("GEMINI_MODEL", "gemini-3.8-flash")


def gemini_timeout_ms() -> int:
    return int(env("GEMINI_TIMEOUT_MS", "20000"))


def question_timeout_ms() -> int:
    """子への質問の生成だけは短く待つ（他の生成は gemini_timeout_ms）"""
    return int(env("QUESTION_TIMEOUT_MS", "5000"))


def gcp_project() -> str:
    return env("GOOGLE_CLOUD_PROJECT", "")


def gcp_location() -> str:
    return env("GOOGLE_CLOUD_LOCATION", "global")


def admin_key() -> str:
    return env("ADMIN_KEY", "")


def static_dir() -> str:
    return env("STATIC_DIR", "")
