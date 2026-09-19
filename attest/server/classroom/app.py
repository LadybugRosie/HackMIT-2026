"""One FastAPI app: the attest ledger engine routers plus the classroom product routers, sharing
one SQLite file. Run with `uvicorn classroom.app:app --port 8090 --reload`."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from attest import __version__ as attest_version
from attest.main import make_store
from attest.routers import certificate as attest_certificate
from attest.routers import ingest as attest_ingest
from attest.routers import session as attest_session
from attest.routers import verify as attest_verify
from attest.settings import Settings as AttestSettings

from . import __version__
from .db import Db
from .routers import auth
from .settings import ClassroomSettings, settings as default_settings


def create_app(cfg: ClassroomSettings = default_settings) -> FastAPI:
    app = FastAPI(title="attest classroom", version=__version__)
    app.add_middleware(CORSMiddleware, allow_origins=cfg.CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])

    app.state.settings = cfg
    app.state.db = Db(cfg.DB_PATH)  # creates the data directory; the store opens the same file next
    app.state.store = make_store(AttestSettings(STORE="sqlite", SQLITE_PATH=cfg.DB_PATH, CORS_ORIGINS=cfg.CORS_ORIGINS))

    app.include_router(attest_session.router)
    app.include_router(attest_ingest.router)
    app.include_router(attest_certificate.router)
    app.include_router(attest_verify.router)

    app.include_router(auth.router)

    @app.get("/healthz")
    def healthz() -> dict:
        return {"ok": True, "classroom": __version__, "attest": attest_version, "db": cfg.DB_PATH}

    return app


app = create_app()
