"""
AURA OS — IPC Protocol & Message Schemas
Standardized JSON-based request/response and event notifications over UDS.
"""

from __future__ import annotations

import time
import uuid
from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class ErrorCode(str, Enum):
    INVALID_REQUEST = "INVALID_REQUEST"
    METHOD_NOT_FOUND = "METHOD_NOT_FOUND"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    PAYLOAD_TOO_LARGE = "PAYLOAD_TOO_LARGE"
    UNAUTHORIZED = "UNAUTHORIZED"


class IPCRequest(BaseModel):
    """Client request sent to aurad daemon."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    method: str = Field(..., description="RPC method identifier (e.g. 'core.ping')")
    params: Dict[str, Any] = Field(default_factory=dict)
    timestamp: float = Field(default_factory=time.time)

    def to_bytes(self) -> bytes:
        """Serialize request to newline-delimited UTF-8 bytes."""
        return self.model_dump_json().encode("utf-8") + b"\n"


class IPCResponse(BaseModel):
    """Server response returned from aurad daemon."""
    id: str
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    error_code: Optional[ErrorCode] = None
    timestamp: float = Field(default_factory=time.time)

    @classmethod
    def ok(cls, request_id: str, data: Any = None) -> IPCResponse:
        return cls(id=request_id, success=True, data=data)

    @classmethod
    def fail(cls, request_id: str, error: str, code: ErrorCode = ErrorCode.INTERNAL_ERROR) -> IPCResponse:
        return cls(id=request_id, success=False, error=error, error_code=code)

    def to_bytes(self) -> bytes:
        """Serialize response to newline-delimited UTF-8 bytes."""
        return self.model_dump_json().encode("utf-8") + b"\n"


class IPCEvent(BaseModel):
    """Unsolicited broadcast event emitted by aurad daemon."""
    event: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    timestamp: float = Field(default_factory=time.time)

    def to_bytes(self) -> bytes:
        return self.model_dump_json().encode("utf-8") + b"\n"
