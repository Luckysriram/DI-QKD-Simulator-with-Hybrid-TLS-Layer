"""
TLS Record Layer — AES-256-GCM encryption/decryption

Handles encryption and decryption of application data with:
- AES-256-GCM authenticated encryption
- 12-byte nonce (4-byte fixed IV + 8-byte counter)
- Authenticated Additional Data (AAD) for integrity
- Record fragmentation for large payloads
"""

import struct
from typing import Tuple

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


# TLS record types
RECORD_TYPE_HANDSHAKE = 0x16
RECORD_TYPE_APPLICATION = 0x17
RECORD_TYPE_ALERT = 0x15
RECORD_TYPE_CHANGE_CIPHER = 0x14

# Maximum record payload (TLS 1.3)
MAX_RECORD_PAYLOAD = 16384  # 16 KiB
GCM_TAG_LENGTH = 16  # 128-bit GCM tag


class RecordLayer:
    """
    TLS Record Layer using AES-256-GCM.
    
    Each record is:
        [type (1 byte)] [length (2 bytes)] [encrypted_payload] [GCM_tag (16 bytes)]
    
    Nonce construction:
        nonce = fixed_iv XOR counter (12 bytes total)
    """
    
    def __init__(self, key: bytes, iv: bytes):
        """
        Initialize the record layer.
        
        Args:
            key: AES-256 key (32 bytes)
            iv: Fixed IV (12 bytes)
        """
        if len(key) != 32:
            raise ValueError(f"Key must be 32 bytes, got {len(key)}")
        if len(iv) != 12:
            raise ValueError(f"IV must be 12 bytes, got {len(iv)}")
        
        self.aesgcm = AESGCM(key)
        self.fixed_iv = iv
        self.sequence_number = 0
    
    def _make_nonce(self) -> bytes:
        """
        Construct per-record nonce by XOR-ing fixed IV with sequence number.
        
        Returns:
            12-byte nonce
        """
        seq_bytes = self.sequence_number.to_bytes(12, 'big')
        nonce = bytes(a ^ b for a, b in zip(self.fixed_iv, seq_bytes))
        self.sequence_number += 1
        return nonce
    
    def _make_aad(self, record_type: int, payload_length: int) -> bytes:
        """
        Construct Authenticated Additional Data.
        
        Format: record_type (1 byte) + payload_length (2 bytes)
        """
        return struct.pack('!BH', record_type, payload_length)
    
    def encrypt(self, plaintext: bytes, record_type: int = RECORD_TYPE_APPLICATION) -> bytes:
        """
        Encrypt a plaintext payload into a TLS record.
        
        Args:
            plaintext: Data to encrypt
            record_type: TLS record type
        
        Returns:
            Complete TLS record: [type][length][ciphertext+tag]
        """
        records = []
        
        # Fragment if necessary
        offset = 0
        while offset < len(plaintext):
            chunk = plaintext[offset:offset + MAX_RECORD_PAYLOAD]
            offset += len(chunk)
            
            nonce = self._make_nonce()
            aad = self._make_aad(record_type, len(chunk))
            
            ciphertext = self.aesgcm.encrypt(nonce, chunk, aad)
            # ciphertext includes the GCM tag (16 bytes appended)
            
            # Build record header
            total_len = len(ciphertext)
            header = struct.pack('!BH', record_type, total_len)
            
            records.append(header + ciphertext)
        
        return b''.join(records)
    
    def decrypt(self, record_data: bytes) -> Tuple[bytes, int]:
        """
        Decrypt a single TLS record.
        
        Args:
            record_data: Raw record bytes [type][length][ciphertext+tag]
        
        Returns:
            (plaintext, record_type)
        
        Raises:
            ValueError: If authentication fails (tampered data)
        """
        if len(record_data) < 3:
            raise ValueError("Record too short")
        
        record_type = record_data[0]
        payload_length = struct.unpack('!H', record_data[1:3])[0]
        ciphertext = record_data[3:3 + payload_length]
        
        if len(ciphertext) != payload_length:
            raise ValueError(
                f"Record payload length mismatch: expected {payload_length}, "
                f"got {len(ciphertext)}"
            )
        
        # Reconstruct AAD (using original plaintext length)
        plaintext_length = payload_length - GCM_TAG_LENGTH
        aad = self._make_aad(record_type, plaintext_length)
        nonce = self._make_nonce()
        
        try:
            plaintext = self.aesgcm.decrypt(nonce, ciphertext, aad)
        except Exception as e:
            raise ValueError(f"Record authentication failed: {e}")
        
        return plaintext, record_type
    
    def reset_sequence(self):
        """Reset the sequence number counter."""
        self.sequence_number = 0


def parse_record_header(data: bytes) -> Tuple[int, int]:
    """
    Parse a TLS record header to get the type and payload length.
    
    Args:
        data: At least 3 bytes of record header
    
    Returns:
        (record_type, payload_length)
    """
    if len(data) < 3:
        raise ValueError("Need at least 3 bytes for record header")
    record_type = data[0]
    payload_length = struct.unpack('!H', data[1:3])[0]
    return record_type, payload_length
