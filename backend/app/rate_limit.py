"""
Shared rate-limiter instance (slowapi, backed by an in-process memory store).

Kept in its own module so both `main.py` (registers the limiter + its
exception handler on the app) and individual routers (apply `@limiter.limit`
to specific endpoints) can import it without a circular import.

Limits are intentionally generous: Nigerian users very commonly share a
single public IP behind school/cybercafe NAT, so an aggressive per-IP limit
would lock out legitimate students, not just attackers. These thresholds
target credential-stuffing/brute-force speed, not normal multi-user traffic.

NOTE: in-memory storage means limits reset on every process restart and are
NOT shared across multiple backend instances/workers. Acelume currently
runs as a single Render service instance, so this is fine for now -- if the
API is ever scaled to multiple instances, switch slowapi to a Redis storage
backend (`storage_uri="redis://..."`) so limits are shared, otherwise each
instance enforces its own separate quota and the effective limit multiplies
by instance count.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
