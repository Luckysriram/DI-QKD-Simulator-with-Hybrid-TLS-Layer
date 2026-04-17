"""
TLS Layer for DI-QKD Simulator
Triple-hybrid key exchange: ECDH (X25519) + ML-KEM-768 + QKD key injection
Real socket wrapper with AES-256-GCM record encryption
"""

from tls.session import TLSSession
from tls.tls_server import TLSFlaskServer
from tls.tls_client import TLSClient

__version__ = "1.0.0"
__all__ = ["TLSSession", "TLSFlaskServer", "TLSClient"]
