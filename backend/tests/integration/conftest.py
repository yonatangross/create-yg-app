"""Integration test configuration.

Integration tests MAY use real services (Redis, DB, HTTP) when needed.
The autouse fixtures from tests/unit/conftest.py are NOT applied here.
"""



# Integration tests can use real asyncio.sleep for timing-sensitive tests
# No autouse fixture to prevent this
