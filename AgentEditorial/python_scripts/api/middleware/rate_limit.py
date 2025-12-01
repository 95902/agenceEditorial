"""Rate limiting middleware using slowapi."""

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from python_scripts.config.settings import settings

# Initialize limiter
limiter = Limiter(key_func=get_remote_address)

__all__ = ["limiter", "setup_rate_limiting"]


def setup_rate_limiting(app: any) -> None:
    """Setup rate limiting for FastAPI app."""
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

