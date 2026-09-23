"""Versioned Windows DPAPI file support; no secrets in diagnostics or on disk."""

import base64
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path


MAX_FILE_BYTES = 65536
ERROR_MESSAGE = "Attaché Bridge service secrets are unavailable or invalid."


class ServiceSecretsError(RuntimeError):
    pass


class _DataBlob(ctypes.Structure):
    _fields_ = [("size", wintypes.DWORD), ("data", ctypes.POINTER(ctypes.c_ubyte))]


def _decrypt_dpapi(ciphertext):
    if os.name != "nt":
        raise ServiceSecretsError(ERROR_MESSAGE) from None
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    unprotect = crypt32.CryptUnprotectData
    unprotect.argtypes = [
        ctypes.POINTER(_DataBlob), ctypes.c_void_p, ctypes.c_void_p,
        ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(_DataBlob),
    ]
    unprotect.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    buffer = (ctypes.c_ubyte * len(ciphertext)).from_buffer_copy(ciphertext)
    source = _DataBlob(len(ciphertext), buffer)
    result = _DataBlob()
    try:
        # CRYPTPROTECT_UI_FORBIDDEN: a service must never display a decrypt prompt.
        if not unprotect(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(result)):
            raise ServiceSecretsError(ERROR_MESSAGE)
        if not result.data or not 0 < result.size <= MAX_FILE_BYTES:
            raise ServiceSecretsError(ERROR_MESSAGE)
        return ctypes.string_at(result.data, result.size)
    finally:
        if result.data:
            ctypes.memset(result.data, 0, result.size)
            kernel32.LocalFree(result.data)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate field")
        result[key] = value
    return result


def load_service_secrets(path, *, decrypt=None):
    """Fail closed with a fixed diagnostic; decrypt is injectable for fake tests."""
    try:
        file_path = Path(path)
        if not file_path.is_absolute():
            raise ValueError("Absolute path required")
        with file_path.open("rb") as handle:
            raw = handle.read(MAX_FILE_BYTES + 1)
        if len(raw) > MAX_FILE_BYTES:
            raise ValueError("Oversized envelope")
        envelope = json.loads(raw, object_pairs_hook=_unique_object)
        if (set(envelope) != {"version", "scope", "ciphertext"}
                or type(envelope["version"]) is not int or envelope["version"] != 1
                or envelope["scope"] != "LocalMachine"):
            raise ValueError("Unsupported envelope")
        ciphertext = base64.b64decode(envelope["ciphertext"], validate=True)
        if not ciphertext:
            raise ValueError("Empty ciphertext")
        plaintext = (decrypt or _decrypt_dpapi)(ciphertext)
        if len(plaintext) > MAX_FILE_BYTES:
            raise ValueError("Oversized payload")
        payload = json.loads(plaintext, object_pairs_hook=_unique_object)
        if (set(payload) != {"version", "scope", "connection_string", "api_token"}
                or type(payload["version"]) is not int or payload["version"] != 1
                or payload["scope"] != "LocalMachine"):
            raise ValueError("Unsupported payload")
        values = {}
        for key in ("connection_string", "api_token"):
            value = payload[key]
            if not isinstance(value, str) or not value.strip() or any(c in value for c in "\r\n\x00"):
                raise ValueError("Missing or invalid value")
            values[key] = value.strip()
        return values
    except Exception:
        # Do not include paths, JSON, OS errors, or decrypted values in diagnostics.
        raise ServiceSecretsError(ERROR_MESSAGE) from None
