"""Rate limiting middleware using slowapi."""

from slowapi import Limiter
from slowapi.util import get_remote_address

# Create limiter with default rate limits
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["100/minute"],
)
