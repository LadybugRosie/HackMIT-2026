from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .routers import certificate, ingest, session, verify
from .settings import Settings, settings as default_settings
from .storage import MemoryStore, SqliteStore


def make_store(cfg: Settings):
    if cfg.STORE == "memory":
        return MemoryStore()
    if cfg.STORE == "sqlite":
        return SqliteStore(cfg.SQLITE_PATH)
    raise ValueError(f"unknown ATTEST_STORE={cfg.STORE}")


def create_app(cfg: Settings = default_settings) -> FastAPI:
    app = FastAPI(title="attest", version=__version__)
    app.add_middleware(
        CORSMiddleware, allow_origins=cfg.CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"]
    )
    app.state.store = make_store(cfg)
    app.include_router(session.router)
    app.include_router(ingest.router)
    app.include_router(certificate.router)
    app.include_router(verify.router)

    @app.get("/healthz")
    def healthz() -> dict:
        return {"ok": True, "version": __version__, "store": cfg.STORE}

    return app


app = create_app()
