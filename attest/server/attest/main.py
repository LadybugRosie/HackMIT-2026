from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .attestors import server_attestors
from .issuer import Issuer
from .routers import attestation, certificate, ingest, session, verify
from .settings import Settings, settings as default_settings
from .storage import MemoryStore, SqliteStore


# Create storage for the app
def make_store(cfg: Settings):
    if cfg.STORE == "memory":
        return MemoryStore()
    if cfg.STORE == "sqlite":
        return SqliteStore(cfg.SQLITE_PATH)
    raise ValueError(f"unknown ATTEST_STORE={cfg.STORE}")


def configure_attestation(app: FastAPI, cfg: Settings) -> None:
    """Stage 3: authoritative verifiers for device signatures (keys looked up in the store) and
    trusted timestamps. Shared by the engine app and the classroom app."""
    app.state.attest_settings = cfg
    app.state.issuer = Issuer.load_or_create(cfg.ISSUER_KEY_PATH)
    app.state.attestors = server_attestors(cfg.WEBAUTHN_RP_ID, cfg.WEBAUTHN_ORIGINS, app.state.store.get_credential,
                                           cfg.TSA_TRUSTED_FINGERPRINTS)


# Create app with Cross-Origin Resource Sharing to allow frotend access
def create_app(cfg: Settings = default_settings) -> FastAPI:
    app = FastAPI(title="attest", version=__version__)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cfg.CORS_ORIGINS,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.store = make_store(cfg)
    configure_attestation(app, cfg)
    app.include_router(session.router)
    app.include_router(ingest.router)
    app.include_router(certificate.router)
    app.include_router(attestation.router)
    app.include_router(verify.router)

    @app.get("/healthz")
    def healthz() -> dict:
        return {"ok": True, "version": __version__, "store": cfg.STORE, "issuer_key_id": app.state.issuer.key_id}

    @app.get("/v1/issuer")
    def issuer_info() -> dict:
        """The public half of the server's certificate-signing key — what an offline verifier pins."""
        return app.state.issuer.public_info()

    return app


app = create_app()
