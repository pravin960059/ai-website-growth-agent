from fastapi import Header, HTTPException

from .settings import get_settings


def get_actor(x_actor_id: str | None = Header(default=None)) -> str:
    """Use a local identity during development and fail closed in production.

    OIDC verification is intentionally not faked. Production deployment must
    replace this dependency with an issuer/audience-validated JWT dependency.
    """

    settings = get_settings()
    if settings.app_env.lower() == "production":
        raise HTTPException(status_code=503, detail="Configure OIDC authentication before production use")
    return x_actor_id or "local-developer"
