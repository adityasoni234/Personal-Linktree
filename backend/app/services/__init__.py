"""Service layer.

Business rules and authorization live here, not in the routers. Routers parse
and shape; services decide. That keeps every rule reachable from tests and
background jobs, not only from an HTTP request.
"""
