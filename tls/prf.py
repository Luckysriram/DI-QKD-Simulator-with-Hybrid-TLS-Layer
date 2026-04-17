"""
TLS Key Schedule — HKDF-based key derivation
Derives traffic keys from the triple-hybrid shared secret.

Uses HKDF-SHA256 as per TLS 1.3 (RFC 8446 Section 7.1)
"""

import hashlib
import hmac
from typing import Tuple


def hkdf_extract(salt: bytes, ikm: bytes) -> bytes:
    """
    HKDF-Extract (RFC 5869 Section 2.2)
    
    Args:
        salt: Optional salt (if None, uses zeros)
        ikm: Input keying material
    
    Returns:
        Pseudorandom key (PRK), 32 bytes
    """
    if salt is None or len(salt) == 0:
        salt = b'\x00' * 32
    return hmac.new(salt, ikm, hashlib.sha256).digest()


def hkdf_expand(prk: bytes, info: bytes, length: int) -> bytes:
    """
    HKDF-Expand (RFC 5869 Section 2.3)
    
    Args:
        prk: Pseudorandom key from HKDF-Extract
        info: Context and application-specific information
        length: Output length in bytes (max 255 * 32)
    
    Returns:
        Output keying material (OKM)
    """
    hash_len = 32  # SHA-256 output length
    n = (length + hash_len - 1) // hash_len
    
    if n > 255:
        raise ValueError("Output length too large for HKDF-Expand")
    
    okm = b''
    t = b''
    
    for i in range(1, n + 1):
        t = hmac.new(prk, t + info + bytes([i]), hashlib.sha256).digest()
        okm += t
    
    return okm[:length]


def hkdf(salt: bytes, ikm: bytes, info: bytes, length: int) -> bytes:
    """
    Full HKDF (Extract + Expand)
    
    Args:
        salt: Salt for extraction
        ikm: Input keying material
        info: Context info for expansion
        length: Desired output length
    
    Returns:
        Derived key material
    """
    prk = hkdf_extract(salt, ikm)
    return hkdf_expand(prk, info, length)


def derive_traffic_keys(
    shared_secret: bytes,
    transcript_hash: bytes
) -> Tuple[bytes, bytes, bytes, bytes]:
    """
    Derive TLS 1.3-style traffic keys from the hybrid shared secret.
    
    Produces separate client/server encryption keys and IVs for AES-256-GCM.
    
    Args:
        shared_secret: Combined shared secret from triple-hybrid KEX
        transcript_hash: SHA-256 hash of handshake transcript
    
    Returns:
        (client_key, server_key, client_iv, server_iv)
        - Keys are 32 bytes (AES-256)
        - IVs are 12 bytes (GCM nonce)
    """
    # Extract master secret
    master_secret = hkdf_extract(salt=transcript_hash, ikm=shared_secret)
    
    # Derive client traffic key
    client_key = hkdf_expand(
        master_secret,
        b"tls13_client_key" + transcript_hash,
        32  # AES-256 key length
    )
    
    # Derive server traffic key
    server_key = hkdf_expand(
        master_secret,
        b"tls13_server_key" + transcript_hash,
        32
    )
    
    # Derive client IV
    client_iv = hkdf_expand(
        master_secret,
        b"tls13_client_iv" + transcript_hash,
        12  # GCM nonce length
    )
    
    # Derive server IV
    server_iv = hkdf_expand(
        master_secret,
        b"tls13_server_iv" + transcript_hash,
        12
    )
    
    return client_key, server_key, client_iv, server_iv


def derive_finished_key(base_key: bytes) -> bytes:
    """
    Derive the Finished message key for handshake verification.
    
    Args:
        base_key: The shared secret or master secret
    
    Returns:
        32-byte key for HMAC-based Finished message
    """
    return hkdf_expand(base_key, b"tls13_finished", 32)
