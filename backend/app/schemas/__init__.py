"""Pydantic request/response schemas.

Separated from the ORM models on purpose: what the database stores and what the
API exposes are different contracts, and keeping them apart is what stops
internal columns leaking into responses.
"""
