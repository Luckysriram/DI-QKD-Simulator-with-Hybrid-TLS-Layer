"""
TLS Session — Real socket wrapper with encrypted send/recv

Wraps a standard TCP socket with TLS handshake and record-layer encryption.
Supports triple-hybrid key exchange with optional QKD key injection.
"""

import socket
import struct
import hashlib
import logging
from typing import Optional

from tls.hybrid_kex import HybridKeyExchange
from tls.handshake import (
    ClientHello, ServerHello, Finished,
    HandshakeTranscript, MSG_CLIENT_HELLO, MSG_SERVER_HELLO, MSG_FINISHED,
    get_message_length, read_handshake_message
)
from tls.record import RecordLayer, RECORD_TYPE_APPLICATION, parse_record_header
from tls.prf import derive_traffic_keys, derive_finished_key

logger = logging.getLogger(__name__)


class TLSSession:
    """
    Real socket TLS wrapper.
    
    Performs a triple-hybrid handshake (ECDH + ML-KEM + QKD),
    then encrypts all application data via AES-256-GCM.
    
    Usage:
        # Server side
        session = TLSSession(client_sock, is_server=True, qkd_key=qkd_bytes)
        session.handshake()
        data = session.recv()
        session.send(response)
        
        # Client side
        session = TLSSession(sock, is_server=False, qkd_key=qkd_bytes)
        session.handshake()
        session.send(request)
        data = session.recv()
    """
    
    def __init__(
        self,
        sock: socket.socket,
        is_server: bool,
        qkd_key: Optional[bytes] = None
    ):
        """
        Args:
            sock: Connected TCP socket
            is_server: True for server side, False for client side
            qkd_key: Optional QKD-derived key for triple-hybrid KEX
        """
        self.sock = sock
        self.is_server = is_server
        self.qkd_key = qkd_key
        
        self.kex = HybridKeyExchange()
        self.transcript = HandshakeTranscript()
        
        self.send_record: Optional[RecordLayer] = None
        self.recv_record: Optional[RecordLayer] = None
        
        self.shared_secret: Optional[bytes] = None
        self.handshake_done = False
        
        # Handshake info for logging
        self.handshake_info = {}
    
    # ── Socket I/O helpers ───────────────────────────────────────────
    
    def _send_raw(self, data: bytes):
        """Send raw bytes over the socket."""
        total_sent = 0
        while total_sent < len(data):
            sent = self.sock.send(data[total_sent:])
            if sent == 0:
                raise ConnectionError("Socket connection broken")
            total_sent += sent
    
    def _recv_raw(self, length: int) -> bytes:
        """Receive exactly `length` bytes from the socket."""
        chunks = []
        received = 0
        while received < length:
            chunk = self.sock.recv(min(length - received, 65536))
            if not chunk:
                raise ConnectionError("Socket connection closed")
            chunks.append(chunk)
            received += len(chunk)
        return b''.join(chunks)
    
    def _recv_handshake_message(self) -> bytes:
        """
        Read a complete handshake message from the socket.
        First reads the 7-byte header, then the body.
        """
        header = self._recv_raw(7)
        body_len = struct.unpack_from('!I', header, 3)[0]
        body = self._recv_raw(body_len)
        return header + body
    
    # ── Handshake ────────────────────────────────────────────────────
    
    def handshake(self):
        """
        Perform the triple-hybrid TLS handshake.
        
        Flow:
            Client → Server: ClientHello (ECDH pub + ML-KEM pub)
            Server → Client: ServerHello (ECDH pub + ML-KEM ciphertext)
            Server → Client: Finished (HMAC verification)
            Client → Server: Finished (HMAC verification)
        """
        if self.is_server:
            self._server_handshake()
        else:
            self._client_handshake()
        
        self.handshake_done = True
        logger.info("Handshake completed successfully")
    
    def _client_handshake(self):
        """Client-side handshake."""
        logger.info("Client: Starting handshake")
        
        # 1. Generate and send ClientHello
        client_shares = self.kex.generate_client_shares()
        
        client_hello = ClientHello(
            ecdh_public=client_shares['ecdh_public'],
            mlkem_public=client_shares['mlkem_public'],
            has_qkd=self.qkd_key is not None,
        )
        client_hello_bytes = client_hello.serialize()
        self.transcript.add(client_hello_bytes)
        self._send_raw(client_hello_bytes)
        logger.info("Client: Sent ClientHello")
        
        # 2. Receive ServerHello
        server_hello_bytes = self._recv_handshake_message()
        self.transcript.add(server_hello_bytes)
        server_hello = ServerHello.deserialize(server_hello_bytes)
        logger.info("Client: Received ServerHello")
        
        # 3. Derive shared secret
        self.shared_secret = self.kex.client_derive(
            server_ecdh_public=server_hello.ecdh_public,
            mlkem_ciphertext=server_hello.mlkem_ciphertext,
            qkd_key=self.qkd_key,
        )
        logger.info("Client: Derived shared secret")
        
        # 4. Set up record layer
        transcript_hash = self.transcript.get_hash()
        client_key, server_key, client_iv, server_iv = \
            derive_traffic_keys(self.shared_secret, transcript_hash)
        
        self.send_record = RecordLayer(client_key, client_iv)
        self.recv_record = RecordLayer(server_key, server_iv)
        
        # 5. Receive server Finished
        server_finished_bytes = self._recv_handshake_message()
        server_finished = Finished.deserialize(server_finished_bytes)
        
        # Verify server Finished
        finished_key = derive_finished_key(self.shared_secret)
        expected_verify = Finished.compute_verify_data(
            finished_key, transcript_hash
        )
        if server_finished.verify_data != expected_verify:
            raise ValueError("Server Finished verification failed!")
        
        self.transcript.add(server_finished_bytes)
        logger.info("Client: Verified server Finished")
        
        # 6. Send client Finished
        client_transcript_hash = self.transcript.get_hash()
        client_verify = Finished.compute_verify_data(
            finished_key, client_transcript_hash
        )
        client_finished = Finished(verify_data=client_verify)
        client_finished_bytes = client_finished.serialize()
        self.transcript.add(client_finished_bytes)
        self._send_raw(client_finished_bytes)
        logger.info("Client: Sent Finished")
        
        # Store handshake info
        self.handshake_info = {
            'role': 'client',
            'kex': 'ECDH-X25519 + ML-KEM-768' + (' + QKD' if self.qkd_key else ''),
            'cipher': 'AES-256-GCM',
            'kdf': 'HKDF-SHA256',
        }
    
    def _server_handshake(self):
        """Server-side handshake."""
        logger.info("Server: Waiting for ClientHello")
        
        # 1. Receive ClientHello
        client_hello_bytes = self._recv_handshake_message()
        self.transcript.add(client_hello_bytes)
        client_hello = ClientHello.deserialize(client_hello_bytes)
        logger.info("Server: Received ClientHello")
        
        # 2. Perform key exchange
        result = self.kex.server_respond(
            client_ecdh_public=client_hello.ecdh_public,
            client_mlkem_public=client_hello.mlkem_public,
            qkd_key=self.qkd_key,
        )
        self.shared_secret = result['shared_secret']
        logger.info("Server: Computed shared secret")
        
        # 3. Send ServerHello
        server_hello = ServerHello(
            ecdh_public=result['ecdh_public'],
            mlkem_ciphertext=result['mlkem_ciphertext'],
        )
        server_hello_bytes = server_hello.serialize()
        self.transcript.add(server_hello_bytes)
        self._send_raw(server_hello_bytes)
        logger.info("Server: Sent ServerHello")
        
        # 4. Set up record layer
        transcript_hash = self.transcript.get_hash()
        client_key, server_key, client_iv, server_iv = \
            derive_traffic_keys(self.shared_secret, transcript_hash)
        
        self.send_record = RecordLayer(server_key, server_iv)
        self.recv_record = RecordLayer(client_key, client_iv)
        
        # 5. Send server Finished
        finished_key = derive_finished_key(self.shared_secret)
        verify_data = Finished.compute_verify_data(finished_key, transcript_hash)
        server_finished = Finished(verify_data=verify_data)
        server_finished_bytes = server_finished.serialize()
        self.transcript.add(server_finished_bytes)
        self._send_raw(server_finished_bytes)
        logger.info("Server: Sent Finished")
        
        # 6. Receive client Finished
        client_finished_bytes = self._recv_handshake_message()
        client_finished = Finished.deserialize(client_finished_bytes)
        
        # Verify client Finished
        client_transcript_hash = self.transcript.get_hash()
        expected_verify = Finished.compute_verify_data(
            finished_key, client_transcript_hash
        )
        if client_finished.verify_data != expected_verify:
            raise ValueError("Client Finished verification failed!")
        
        self.transcript.add(client_finished_bytes)
        logger.info("Server: Verified client Finished")
        
        # Store handshake info
        self.handshake_info = {
            'role': 'server',
            'kex': 'ECDH-X25519 + ML-KEM-768' + (' + QKD' if self.qkd_key else ''),
            'cipher': 'AES-256-GCM',
            'kdf': 'HKDF-SHA256',
        }
    
    # ── Encrypted data transfer ──────────────────────────────────────
    
    def send(self, data: bytes):
        """
        Send encrypted data over the TLS session.
        
        Args:
            data: Plaintext bytes to send
        """
        if not self.handshake_done:
            raise RuntimeError("Handshake not completed")
        
        record = self.send_record.encrypt(data)
        # Prefix with total record length for easy framing
        length_prefix = struct.pack('!I', len(record))
        self._send_raw(length_prefix + record)
    
    def recv(self) -> bytes:
        """
        Receive and decrypt data from the TLS session.
        
        Returns:
            Decrypted plaintext bytes
        """
        if not self.handshake_done:
            raise RuntimeError("Handshake not completed")
        
        # Read length prefix
        length_bytes = self._recv_raw(4)
        total_length = struct.unpack('!I', length_bytes)[0]
        
        # Read the record
        record_data = self._recv_raw(total_length)
        
        plaintext, _ = self.recv_record.decrypt(record_data)
        return plaintext
    
    def close(self):
        """Close the TLS session and underlying socket."""
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self.sock.close()
        logger.info("TLS session closed")
    
    def get_session_info(self) -> dict:
        """Get information about the current TLS session."""
        return {
            'handshake_completed': self.handshake_done,
            'has_qkd_key': self.qkd_key is not None,
            **self.handshake_info,
        }
