"""One FastAPI app: the attest ledger engine routers plus the classroom product routers, sharing
one SQLite file. Run with `uvicorn classroom.app:app --port 8090 --reload`."""
from __future__ import annotations

from fastapi import Depends, FastAPI
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
from .deps import guard_ingest_body, guard_session_path
from .factcheck import CachedResolver, HttpResolver
from .routers import assignments, auth, classes, dashboard, factcheck, review, similarity, submissions
from .settings import ClassroomSettings, settings as default_settings


def create_app(cfg: ClassroomSettings = default_settings) -> FastAPI:
    app = FastAPI(title="attest classroom", version=__version__)
    app.add_middleware(CORSMiddleware, allow_origins=cfg.CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])

    app.state.settings = cfg
    app.state.db = Db(cfg.DB_PATH)  # creates the data directory; the store opens the same file next
    app.state.store = make_store(AttestSettings(STORE="sqlite", SQLITE_PATH=cfg.DB_PATH, CORS_ORIGINS=cfg.CORS_ORIGINS))
    # Tests swap this for a fake; production resolves against Crossref/doi.org with a 7-day cache.
    app.state.resolver = CachedResolver(HttpResolver(cfg.HTTP_TIMEOUT_S, cfg.CROSSREF_MAILTO), app.state.db)

    # Engine routes: sessions bound to a submission are guarded; unbound demo sessions stay public.
    app.include_router(attest_session.router, dependencies=[Depends(guard_session_path)])
    app.include_router(attest_certificate.router, dependencies=[Depends(guard_session_path)])
    app.include_router(attest_ingest.router, dependencies=[Depends(guard_ingest_body)])
    app.include_router(attest_verify.router)  # pure; nothing to protect

    for r in (auth, dashboard, classes, assignments, submissions, review, factcheck, similarity):
        app.include_router(r.router)

    @app.get("/healthz")
    def healthz() -> dict:
        return {"ok": True, "classroom": __version__, "attest": attest_version, "db": cfg.DB_PATH}

    return app


app = create_app()
