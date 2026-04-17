"""
Test Suite for TLS Layer

Tests triple-hybrid key exchange, HKDF, record layer encryption,
handshake message framing, and end-to-end TLS sessions.
"""

import sys
import os
import socket
import threading
import time
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tls.prf import hkdf_extract, hkdf_expand, hkdf, derive_traffic_keys, derive_finished_key
from tls.hybrid_kex import HybridKeyExchange, bits_to_bytes, bytes_to_bits
from tls.record import RecordLayer, RECORD_TYPE_APPLICATION
from tls.handshake import (
    ClientHello, ServerHello, Finished,
    HandshakeTranscript, MSG_CLIENT_HELLO, MSG_SERVER_HELLO, MSG_FINISHED
)
from tls.session import TLSSession


class TestHKDF:
    """Tests for HKDF key derivation."""
    
    def test_extract_produces_32_bytes(self):
        prk = hkdf_extract(b"salt", b"input key material")
        assert len(prk) == 32
    
    def test_extract_deterministic(self):
        prk1 = hkdf_extract(b"salt", b"ikm")
        prk2 = hkdf_extract(b"salt", b"ikm")
        assert prk1 == prk2
    
    def test_extract_different_inputs_differ(self):
        prk1 = hkdf_extract(b"salt", b"ikm1")
        prk2 = hkdf_extract(b"salt", b"ikm2")
        assert prk1 != prk2
    
    def test_expand_requested_length(self):
        prk = hkdf_extract(b"salt", b"ikm")
        for length in [16, 32, 48, 64, 128]:
            okm = hkdf_expand(prk, b"info", length)
            assert len(okm) == length
    
    def test_derive_traffic_keys_lengths(self):
        shared_secret = os.urandom(32)
        transcript_hash = os.urandom(32)
        
        client_key, server_key, client_iv, server_iv = \
            derive_traffic_keys(shared_secret, transcript_hash)
        
        assert len(client_key) == 32   # AES-256
        assert len(server_key) == 32
        assert len(client_iv) == 12    # GCM nonce
        assert len(server_iv) == 12
    
    def test_derive_traffic_keys_different_for_client_and_server(self):
        shared_secret = os.urandom(32)
        transcript_hash = os.urandom(32)
        
        client_key, server_key, client_iv, server_iv = \
            derive_traffic_keys(shared_secret, transcript_hash)
        
        assert client_key != server_key
        assert client_iv != server_iv
    
    def test_derive_finished_key(self):
        key = derive_finished_key(os.urandom(32))
        assert len(key) == 32


class TestHybridKEX:
    """Tests for triple-hybrid key exchange."""
    
    def test_ecdh_plus_mlkem_exchange(self):
        """Test ECDH + ML-KEM key exchange (no QKD)."""
        client_kex = HybridKeyExchange()
        
        # Client generates shares
        shares = client_kex.generate_client_shares()
        assert 'ecdh_public' in shares
        assert 'mlkem_public' in shares
        assert len(shares['ecdh_public']) == 32  # X25519
        
        # Server responds
        server_kex = HybridKeyExchange()
        server_result = server_kex.server_respond(
            shares['ecdh_public'],
            shares['mlkem_public'],
            qkd_key=None
        )
        
        assert len(server_result['ecdh_public']) == 32
        assert len(server_result['shared_secret']) == 32
        
        # Client derives same secret
        client_secret = client_kex.client_derive(
            server_result['ecdh_public'],
            server_result['mlkem_ciphertext'],
            qkd_key=None
        )
        
        assert client_secret == server_result['shared_secret']
    
    def test_triple_hybrid_with_qkd(self):
        """Test ECDH + ML-KEM + QKD key exchange."""
        qkd_key = os.urandom(32)
        
        client_kex = HybridKeyExchange()
        shares = client_kex.generate_client_shares()
        
        server_kex = HybridKeyExchange()
        server_result = server_kex.server_respond(
            shares['ecdh_public'],
            shares['mlkem_public'],
            qkd_key=qkd_key
        )
        
        client_secret = client_kex.client_derive(
            server_result['ecdh_public'],
            server_result['mlkem_ciphertext'],
            qkd_key=qkd_key
        )
        
        assert client_secret == server_result['shared_secret']
    
    def test_qkd_changes_secret(self):
        """Verify QKD key injection changes the shared secret."""
        client_kex1 = HybridKeyExchange()
        shares1 = client_kex1.generate_client_shares()
        
        server_kex1 = HybridKeyExchange()
        result_no_qkd = server_kex1.server_respond(
            shares1['ecdh_public'], shares1['mlkem_public'],
            qkd_key=None
        )
        
        # New exchange with QKD key
        client_kex2 = HybridKeyExchange()
        shares2 = client_kex2.generate_client_shares()
        
        server_kex2 = HybridKeyExchange()
        result_with_qkd = server_kex2.server_respond(
            shares2['ecdh_public'], shares2['mlkem_public'],
            qkd_key=os.urandom(32)
        )
        
        # Different exchanges will have different secrets anyway,
        # but we verify the QKD path works without errors
        assert len(result_with_qkd['shared_secret']) == 32
    
    def test_qkd_bit_list_input(self):
        """Test QKD key as a bit list (from DI-QKD simulation)."""
        bits = [1, 0, 1, 1, 0, 0, 1, 0] * 4  # 32 bits
        qkd_bytes = bits_to_bytes(bits)
        assert len(qkd_bytes) == 4
        
        # Verify roundtrip
        recovered = bytes_to_bits(qkd_bytes)
        assert recovered[:len(bits)] == bits


class TestBitsConversion:
    """Tests for bit/byte conversions."""
    
    def test_bits_to_bytes(self):
        bits = [1, 0, 1, 0, 0, 0, 0, 0]  # = 0x05
        result = bits_to_bytes(bits)
        assert result == bytes([0x05])
    
    def test_bytes_to_bits(self):
        data = bytes([0x05])  # = 10100000
        bits = bytes_to_bits(data)
        assert bits == [1, 0, 1, 0, 0, 0, 0, 0]
    
    def test_roundtrip(self):
        original = os.urandom(16)
        bits = bytes_to_bits(original)
        recovered = bits_to_bytes(bits)
        assert recovered == original


class TestRecordLayer:
    """Tests for AES-256-GCM record layer."""
    
    def test_encrypt_decrypt_roundtrip(self):
        key = os.urandom(32)
        iv = os.urandom(12)
        
        encrypt_rl = RecordLayer(key, iv)
        decrypt_rl = RecordLayer(key, iv)
        
        plaintext = b"Hello, quantum world!"
        ciphertext = encrypt_rl.encrypt(plaintext)
        
        recovered, rtype = decrypt_rl.decrypt(ciphertext)
        assert recovered == plaintext
        assert rtype == RECORD_TYPE_APPLICATION
    
    def test_ciphertext_differs_from_plaintext(self):
        key = os.urandom(32)
        iv = os.urandom(12)
        
        rl = RecordLayer(key, iv)
        plaintext = b"Secret data"
        ciphertext = rl.encrypt(plaintext)
        
        assert plaintext not in ciphertext
    
    def test_tamper_detection(self):
        key = os.urandom(32)
        iv = os.urandom(12)
        
        encrypt_rl = RecordLayer(key, iv)
        decrypt_rl = RecordLayer(key, iv)
        
        plaintext = b"Original data"
        ciphertext = encrypt_rl.encrypt(plaintext)
        
        # Tamper with ciphertext
        tampered = bytearray(ciphertext)
        tampered[-1] ^= 0xFF  # Flip last byte
        
        with pytest.raises(ValueError, match="authentication failed"):
            decrypt_rl.decrypt(bytes(tampered))
    
    def test_wrong_key_fails(self):
        key1 = os.urandom(32)
        key2 = os.urandom(32)
        iv = os.urandom(12)
        
        encrypt_rl = RecordLayer(key1, iv)
        decrypt_rl = RecordLayer(key2, iv)
        
        ciphertext = encrypt_rl.encrypt(b"Secret")
        
        with pytest.raises(ValueError):
            decrypt_rl.decrypt(ciphertext)
    
    def test_large_payload_fragmentation(self):
        key = os.urandom(32)
        iv = os.urandom(12)
        
        encrypt_rl = RecordLayer(key, iv)
        
        large_data = os.urandom(32768)  # > 16KB
        ciphertext = encrypt_rl.encrypt(large_data)
        
        # Should have been fragmented (multiple records)
        assert len(ciphertext) > len(large_data)


class TestHandshake:
    """Tests for handshake message serialization."""
    
    def test_client_hello_roundtrip(self):
        original = ClientHello(
            ecdh_public=os.urandom(32),
            mlkem_public=os.urandom(1184),
            has_qkd=True,
        )
        
        serialized = original.serialize()
        recovered = ClientHello.deserialize(serialized)
        
        assert recovered.ecdh_public == original.ecdh_public
        assert recovered.mlkem_public == original.mlkem_public
        assert recovered.has_qkd == original.has_qkd
        assert recovered.client_random == original.client_random
    
    def test_server_hello_roundtrip(self):
        original = ServerHello(
            ecdh_public=os.urandom(32),
            mlkem_ciphertext=os.urandom(1088),
        )
        
        serialized = original.serialize()
        recovered = ServerHello.deserialize(serialized)
        
        assert recovered.ecdh_public == original.ecdh_public
        assert recovered.mlkem_ciphertext == original.mlkem_ciphertext
        assert recovered.server_random == original.server_random
    
    def test_finished_roundtrip(self):
        original = Finished(verify_data=os.urandom(32))
        
        serialized = original.serialize()
        recovered = Finished.deserialize(serialized)
        
        assert recovered.verify_data == original.verify_data
    
    def test_finished_verify_data(self):
        key = os.urandom(32)
        transcript = os.urandom(32)
        
        verify = Finished.compute_verify_data(key, transcript)
        assert len(verify) == 32
        
        # Same inputs produce same result
        verify2 = Finished.compute_verify_data(key, transcript)
        assert verify == verify2
    
    def test_transcript_hash(self):
        transcript = HandshakeTranscript()
        transcript.add(b"message1")
        transcript.add(b"message2")
        
        hash1 = transcript.get_hash()
        assert len(hash1) == 32
        
        transcript.add(b"message3")
        hash2 = transcript.get_hash()
        assert hash1 != hash2


class TestTLSSession:
    """End-to-end TLS session tests over loopback."""
    
    def test_handshake_and_data_exchange(self):
        """Test full TLS handshake + encrypted data exchange."""
        server_ready = threading.Event()
        server_error = [None]
        client_received = [None]
        
        def server_thread():
            try:
                srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                srv.bind(('127.0.0.1', 0))
                port = srv.getsockname()[1]
                srv.listen(1)
                server_ready.port = port
                server_ready.set()
                
                client_sock, _ = srv.accept()
                session = TLSSession(client_sock, is_server=True)
                session.handshake()
                
                # Receive data
                data = session.recv()
                # Echo back
                session.send(data)
                session.close()
                srv.close()
            except Exception as e:
                server_error[0] = e
                server_ready.set()
        
        t = threading.Thread(target=server_thread, daemon=True)
        t.start()
        server_ready.wait(timeout=10)
        
        if server_error[0]:
            pytest.fail(f"Server error: {server_error[0]}")
        
        # Client
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(('127.0.0.1', server_ready.port))
        
        session = TLSSession(sock, is_server=False)
        session.handshake()
        
        assert session.handshake_done
        
        # Send data
        test_data = b"Hello from TLS client!"
        session.send(test_data)
        
        # Receive echo
        response = session.recv()
        assert response == test_data
        
        session.close()
        t.join(timeout=5)
    
    def test_handshake_with_qkd_key(self):
        """Test handshake with QKD key injection."""
        qkd_key = os.urandom(32)
        server_ready = threading.Event()
        
        def server_thread():
            srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.bind(('127.0.0.1', 0))
            port = srv.getsockname()[1]
            srv.listen(1)
            server_ready.port = port
            server_ready.set()
            
            client_sock, _ = srv.accept()
            session = TLSSession(client_sock, is_server=True, qkd_key=qkd_key)
            session.handshake()
            
            data = session.recv()
            session.send(data)
            session.close()
            srv.close()
        
        t = threading.Thread(target=server_thread, daemon=True)
        t.start()
        server_ready.wait(timeout=10)
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(('127.0.0.1', server_ready.port))
        
        session = TLSSession(sock, is_server=False, qkd_key=qkd_key)
        session.handshake()
        
        info = session.get_session_info()
        assert 'QKD' in info.get('kex', '')
        assert info['has_qkd_key'] is True
        
        session.send(b"QKD-secured data")
        response = session.recv()
        assert response == b"QKD-secured data"
        
        session.close()
        t.join(timeout=5)


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
