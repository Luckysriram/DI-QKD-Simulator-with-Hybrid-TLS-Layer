"""
TLS Client — CLI and library client for the TLS-wrapped API

Connects to the TLS server, performs the triple-hybrid handshake,
and sends encrypted HTTP requests.
"""

import socket
import json
import logging
import time
from typing import Optional, Dict, Any

from tls.session import TLSSession

logger = logging.getLogger(__name__)


class TLSClient:
    """
    Client for the triple-hybrid TLS server.
    
    Usage:
        client = TLSClient('localhost', 8443, qkd_key=qkd_bytes)
        client.connect()
        response = client.request('POST', '/api/initialize', json={'key_size': 256})
        print(response)
        client.close()
    """
    
    def __init__(
        self,
        host: str = 'localhost',
        port: int = 8443,
        qkd_key: Optional[bytes] = None,
        timeout: float = 30.0
    ):
        """
        Args:
            host: Server hostname
            port: Server port
            qkd_key: Optional QKD-derived key for triple-hybrid KEX
            timeout: Connection timeout in seconds
        """
        self.host = host
        self.port = port
        self.qkd_key = qkd_key
        self.timeout = timeout
        
        self.sock: Optional[socket.socket] = None
        self.session: Optional[TLSSession] = None
        self.connected = False
    
    def connect(self):
        """
        Connect to the TLS server and perform handshake.
        """
        logger.info(f"Connecting to {self.host}:{self.port}")
        
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect((self.host, self.port))
        
        self.session = TLSSession(
            self.sock,
            is_server=False,
            qkd_key=self.qkd_key
        )
        
        start = time.time()
        self.session.handshake()
        handshake_time = time.time() - start
        
        self.connected = True
        info = self.session.get_session_info()
        
        print(f"[✓] Connected to {self.host}:{self.port}")
        print(f"    KEX: {info.get('kex', 'unknown')}")
        print(f"    Cipher: {info.get('cipher', 'unknown')}")
        print(f"    Handshake time: {handshake_time:.3f}s")
        if info.get('has_qkd_key'):
            print(f"    QKD key: injected into handshake")
    
    def request(
        self,
        method: str,
        path: str,
        json_body: Optional[Dict] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Send an HTTP request over the TLS session.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            path: Request path (e.g., '/api/initialize')
            json_body: Optional JSON body for POST requests
            headers: Optional additional headers
        
        Returns:
            Parsed JSON response dict
        """
        if not self.connected:
            raise RuntimeError("Not connected. Call connect() first.")
        
        # Build HTTP request
        body = ''
        if json_body is not None:
            body = json.dumps(json_body)
        
        request_headers = {
            'Host': f'{self.host}:{self.port}',
            'Content-Type': 'application/json',
            'Content-Length': str(len(body)),
            'Connection': 'close',
        }
        if headers:
            request_headers.update(headers)
        
        request = f"{method} {path} HTTP/1.1\r\n"
        for key, value in request_headers.items():
            request += f"{key}: {value}\r\n"
        request += "\r\n"
        request += body
        
        # Send encrypted request
        start = time.time()
        self.session.send(request.encode('utf-8'))
        
        # Receive encrypted response
        response_data = self.session.recv()
        rtt = time.time() - start
        
        # Parse HTTP response
        response_str = response_data.decode('utf-8')
        
        # Split headers and body
        parts = response_str.split('\r\n\r\n', 1)
        header_section = parts[0]
        body_section = parts[1] if len(parts) > 1 else ''
        
        # Parse status line
        status_line = header_section.split('\r\n')[0]
        status_code = int(status_line.split(' ')[1])
        
        # Parse JSON body
        result = {}
        if body_section:
            try:
                result = json.loads(body_section)
            except json.JSONDecodeError:
                result = {'raw': body_section}
        
        result['_status_code'] = status_code
        result['_rtt_ms'] = round(rtt * 1000, 2)
        
        return result
    
    def close(self):
        """Close the TLS session."""
        if self.session:
            self.session.close()
        self.connected = False
        logger.info("TLS client disconnected")
    
    def get_session_info(self) -> dict:
        """Get information about the current TLS session."""
        if self.session:
            return self.session.get_session_info()
        return {'connected': False}


def run_demo():
    """
    Demo: Connect to TLS server and run a full DI-QKD simulation.
    """
    import sys
    sys.path.insert(0, '.')
    
    print("=" * 60)
    print("  DI-QKD TLS Client Demo")
    print("=" * 60)
    
    # Optional: Load QKD key
    qkd_key = None
    try:
        from backend.diqkd_simulator import DIQKDSimulator
        from tls.hybrid_kex import bits_to_bytes
        print("\n[*] Running DI-QKD to generate key...")
        sim = DIQKDSimulator(key_size=256, num_chsh_rounds=500)
        results = sim.run_full_simulation()
        if results.get('combined_key'):
            qkd_key = bits_to_bytes(results['combined_key'])
            print(f"[✓] QKD key: {len(qkd_key)} bytes")
    except Exception as e:
        print(f"[!] QKD key generation skipped: {e}")
    
    # Connect to TLS server
    print(f"\n[*] Connecting to TLS server...")
    client = TLSClient('localhost', 8443, qkd_key=qkd_key)
    
    try:
        client.connect()
        
        # Initialize simulator
        print("\n[*] Initializing simulator...")
        resp = client.request('POST', '/api/initialize', json_body={
            'key_size': 256,
            'chsh_rounds': 500
        })
        print(f"    Status: {resp.get('status')}")
        print(f"    RTT: {resp.get('_rtt_ms')}ms")
        
        # Run full simulation
        print("\n[*] Running full DI-QKD simulation over TLS...")
        resp = client.request('POST', '/api/run_full_simulation', json_body={
            'chsh_state': 'entangled'
        })
        print(f"    Status: {resp.get('status')}")
        
        if resp.get('results'):
            results = resp['results']
            if results.get('security_certification'):
                cert = results['security_certification']
                print(f"    Security: {cert.get('overall_security_level')}")
            if results.get('bb84_results'):
                bb84 = results['bb84_results']
                print(f"    QBER: {bb84.get('qber')}")
            if results.get('chsh_results'):
                chsh = results['chsh_results']
                print(f"    CHSH: {chsh.get('chsh_value')}")
        
        print(f"    RTT: {resp.get('_rtt_ms')}ms")
        
        # Health check
        print("\n[*] Health check...")
        # Need a new connection for another request (single-request server)
        
    except ConnectionRefusedError:
        print("[✗] Could not connect. Is the TLS server running?")
        print("    Start it with: python -m tls.tls_server")
    except Exception as e:
        print(f"[✗] Error: {e}")
    finally:
        client.close()
    
    print("\n" + "=" * 60)
    print("  Demo complete")
    print("=" * 60)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    run_demo()
