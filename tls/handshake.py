"""
TLS Handshake Messages — ClientHello, ServerHello, Finished

Binary message framing for the hybrid TLS handshake:
  1. ClientHello: ECDH public key + ML-KEM public key + client random
  2. ServerHello: ECDH public key + ML-KEM ciphertext + server random
  3. Finished: HMAC of handshake transcript
"""

import os
import struct
import hashlib
import hmac
from typing import Dict, Optional
from dataclasses import dataclass, field


# Handshake message types
MSG_CLIENT_HELLO = 0x01
MSG_SERVER_HELLO = 0x02
MSG_FINISHED = 0x14

# Protocol version
PROTOCOL_VERSION = 0x0304  # TLS 1.3


@dataclass
class ClientHello:
    """ClientHello message carrying client's key shares."""
    client_random: bytes = field(default_factory=lambda: os.urandom(32))
    ecdh_public: bytes = b''      # 32 bytes X25519 public key
    mlkem_public: bytes = b''     # ML-KEM-768 public key (variable length)
    has_qkd: bool = False         # Whether QKD key is available
    
    def serialize(self) -> bytes:
        """
        Serialize ClientHello to binary.
        
        Format:
            [msg_type: 1B] [version: 2B] [total_length: 4B]
            [client_random: 32B]
            [ecdh_pub_len: 2B] [ecdh_public: NB]
            [mlkem_pub_len: 2B] [mlkem_public: NB]
            [has_qkd: 1B]
        """
        body = b''
        body += self.client_random
        body += struct.pack('!H', len(self.ecdh_public))
        body += self.ecdh_public
        body += struct.pack('!H', len(self.mlkem_public))
        body += self.mlkem_public
        body += struct.pack('!B', 1 if self.has_qkd else 0)
        
        header = struct.pack('!BHI', MSG_CLIENT_HELLO, PROTOCOL_VERSION, len(body))
        return header + body
    
    @classmethod
    def deserialize(cls, data: bytes) -> 'ClientHello':
        """Deserialize ClientHello from binary."""
        offset = 0
        
        msg_type, version, body_len = struct.unpack_from('!BHI', data, offset)
        offset += 7
        
        if msg_type != MSG_CLIENT_HELLO:
            raise ValueError(f"Expected ClientHello (0x01), got 0x{msg_type:02x}")
        
        client_random = data[offset:offset + 32]
        offset += 32
        
        ecdh_len = struct.unpack_from('!H', data, offset)[0]
        offset += 2
        ecdh_public = data[offset:offset + ecdh_len]
        offset += ecdh_len
        
        mlkem_len = struct.unpack_from('!H', data, offset)[0]
        offset += 2
        mlkem_public = data[offset:offset + mlkem_len]
        offset += mlkem_len
        
        has_qkd = struct.unpack_from('!B', data, offset)[0] == 1
        offset += 1
        
        return cls(
            client_random=client_random,
            ecdh_public=ecdh_public,
            mlkem_public=mlkem_public,
            has_qkd=has_qkd,
        )


@dataclass
class ServerHello:
    """ServerHello message carrying server's key shares and ML-KEM ciphertext."""
    server_random: bytes = field(default_factory=lambda: os.urandom(32))
    ecdh_public: bytes = b''       # 32 bytes X25519 public key
    mlkem_ciphertext: bytes = b''  # ML-KEM-768 ciphertext
    
    def serialize(self) -> bytes:
        """
        Serialize ServerHello to binary.
        
        Format:
            [msg_type: 1B] [version: 2B] [total_length: 4B]
            [server_random: 32B]
            [ecdh_pub_len: 2B] [ecdh_public: NB]
            [mlkem_ct_len: 2B] [mlkem_ciphertext: NB]
        """
        body = b''
        body += self.server_random
        body += struct.pack('!H', len(self.ecdh_public))
        body += self.ecdh_public
        body += struct.pack('!H', len(self.mlkem_ciphertext))
        body += self.mlkem_ciphertext
        
        header = struct.pack('!BHI', MSG_SERVER_HELLO, PROTOCOL_VERSION, len(body))
        return header + body
    
    @classmethod
    def deserialize(cls, data: bytes) -> 'ServerHello':
        """Deserialize ServerHello from binary."""
        offset = 0
        
        msg_type, version, body_len = struct.unpack_from('!BHI', data, offset)
        offset += 7
        
        if msg_type != MSG_SERVER_HELLO:
            raise ValueError(f"Expected ServerHello (0x02), got 0x{msg_type:02x}")
        
        server_random = data[offset:offset + 32]
        offset += 32
        
        ecdh_len = struct.unpack_from('!H', data, offset)[0]
        offset += 2
        ecdh_public = data[offset:offset + ecdh_len]
        offset += ecdh_len
        
        mlkem_len = struct.unpack_from('!H', data, offset)[0]
        offset += 2
        mlkem_ciphertext = data[offset:offset + mlkem_len]
        offset += mlkem_len
        
        return cls(
            server_random=server_random,
            ecdh_public=ecdh_public,
            mlkem_ciphertext=mlkem_ciphertext,
        )


@dataclass
class Finished:
    """
    Finished message — HMAC over the handshake transcript.
    Proves both sides derived the same key.
    """
    verify_data: bytes = b''
    
    def serialize(self) -> bytes:
        """Serialize Finished message."""
        body = self.verify_data
        header = struct.pack('!BHI', MSG_FINISHED, PROTOCOL_VERSION, len(body))
        return header + body
    
    @classmethod
    def deserialize(cls, data: bytes) -> 'Finished':
        """Deserialize Finished message."""
        offset = 0
        msg_type, version, body_len = struct.unpack_from('!BHI', data, offset)
        offset += 7
        
        if msg_type != MSG_FINISHED:
            raise ValueError(f"Expected Finished (0x14), got 0x{msg_type:02x}")
        
        verify_data = data[offset:offset + body_len]
        return cls(verify_data=verify_data)
    
    @staticmethod
    def compute_verify_data(finished_key: bytes, transcript_hash: bytes) -> bytes:
        """
        Compute the verify_data for a Finished message.
        
        Args:
            finished_key: Key derived from the shared secret
            transcript_hash: SHA-256 hash of all prior handshake messages
        
        Returns:
            32-byte HMAC
        """
        return hmac.new(finished_key, transcript_hash, hashlib.sha256).digest()


class HandshakeTranscript:
    """
    Tracks the handshake transcript for key derivation and verification.
    Accumulates all handshake messages and provides a running hash.
    """
    
    def __init__(self):
        self._messages = []
        self._hasher = hashlib.sha256()
    
    def add(self, message_bytes: bytes):
        """Add a serialized handshake message to the transcript."""
        self._messages.append(message_bytes)
        self._hasher.update(message_bytes)
    
    def get_hash(self) -> bytes:
        """Get the current transcript hash (SHA-256)."""
        return self._hasher.copy().digest()
    
    def get_messages(self) -> list:
        """Get all recorded messages."""
        return list(self._messages)


def read_handshake_message(data: bytes) -> int:
    """
    Read the message type from a handshake message header.
    
    Returns:
        Message type byte
    """
    if len(data) < 1:
        raise ValueError("Empty handshake message")
    return data[0]


def get_message_length(data: bytes) -> int:
    """
    Get the total length of a handshake message from its header.
    
    Returns:
        Total message length including header (7 bytes header + body)
    """
    if len(data) < 7:
        raise ValueError("Need at least 7 bytes for handshake header")
    _, _, body_len = struct.unpack_from('!BHI', data, 0)
    return 7 + body_len
