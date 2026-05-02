"""Shared gRPC channel to the API ``RecruitmentData`` service."""

from __future__ import annotations

from grpc import aio

from settings import settings

_channel: aio.Channel | None = None


def get_grpc_channel() -> aio.Channel:
    global _channel
    if _channel is None:
        _channel = aio.insecure_channel(settings.api_grpc_target)
    return _channel
