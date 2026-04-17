"""
TLS Flask Server — Serves the Flask API over custom TLS

Wraps the Flask application with the triple-hybrid TLS layer,
accepting real TCP connections, performing the handshake, then
proxying decrypted HTTP requests to/from Flask.
"""

import socket
import threading
import json
import logging
import time
from typing import Optional
from io import BytesIO

from tls.session import TLSSession

logger = logging.getLogger(__name__)


class TLSFlaskServer:
    """
    Serves a Flask application over the custom triple-hybrid TLS layer.
    
    Each incoming connection:
    1. Accepts TCP connection
    2. Performs TLS handshake (ECDH + ML-KEM + optional QKD)
    3. Reads encrypted HTTP request
    4. Passes to Flask WSGI app
    5. Encrypts and returns HTTP response
    
    Usage:
        from backend.api import app
        server = TLSFlaskServer(app, host='0.0.0.0', port=8443)
        server.start()  # Blocking
    """
    
    def __init__(
        self,
        flask_app,
        host: str = '0.0.0.0',
        port: int = 8443,
        qkd_key: Optional[bytes] = None,
        max_connections: int = 10
    ):
        """
        Args:
            flask_app: Flask application instance
            host: Bind address
            port: Bind port
            qkd_key: Optional QKD-derived key for triple-hybrid KEX
            max_connections: Max simultaneous connections
        """
        self.app = flask_app
        self.host = host
        self.port = port
        self.qkd_key = qkd_key
        self.max_connections = max_connections
        
        self.server_socket: Optional[socket.socket] = None
        self.running = False
        self._connections = []
    
    def start(self):
        """Start the TLS server (blocking)."""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(self.max_connections)
        self.server_socket.settimeout(1.0)  # Allow clean shutdown
        self.running = True
        
        kex_type = 'ECDH-X25519 + ML-KEM-768'
        if self.qkd_key:
            kex_type += ' + QKD'
        
        print(f"╔══════════════════════════════════════════════════════╗")
        print(f"║  DI-QKD TLS Server                                  ║")
        print(f"║  Listening on {self.host}:{self.port:<28}║")
        print(f"║  KEX: {kex_type:<45}║")
        print(f"║  Cipher: AES-256-GCM                                ║")
        print(f"║  KDF: HKDF-SHA256                                   ║")
        print(f"╚══════════════════════════════════════════════════════╝")
        
        try:
            while self.running:
                try:
                    client_sock, addr = self.server_socket.accept()
                    logger.info(f"Connection from {addr}")
                    print(f"[+] Connection from {addr[0]}:{addr[1]}")
                    
                    thread = threading.Thread(
                        target=self._handle_connection,
                        args=(client_sock, addr),
                        daemon=True
                    )
                    thread.start()
                    self._connections.append(thread)
                    
                except socket.timeout:
                    continue
                except OSError:
                    break
        except KeyboardInterrupt:
            print("\n[*] Server shutting down...")
        finally:
            self.stop()
    
    def start_background(self) -> threading.Thread:
        """Start the TLS server in a background thread."""
        thread = threading.Thread(target=self.start, daemon=True)
        thread.start()
        time.sleep(0.5)  # Wait for socket to bind
        return thread
    
    def stop(self):
        """Stop the TLS server."""
        self.running = False
        if self.server_socket:
            try:
                self.server_socket.close()
            except OSError:
                pass
        logger.info("TLS server stopped")
    
    def _handle_connection(self, client_sock: socket.socket, addr: tuple):
        """Handle a single client connection."""
        tls_session = None
        try:
            # 1. TLS handshake
            tls_session = TLSSession(
                client_sock,
                is_server=True,
                qkd_key=self.qkd_key
            )
            tls_session.handshake()
            print(f"[✓] TLS handshake complete with {addr[0]}:{addr[1]}")
            print(f"    KEX: {tls_session.handshake_info.get('kex', 'unknown')}")
            
            # 2. Read encrypted HTTP request
            request_data = tls_session.recv()
            
            # 3. Parse HTTP request and dispatch to Flask
            response_data = self._dispatch_to_flask(request_data)
            
            # 4. Send encrypted HTTP response
            tls_session.send(response_data)
            
        except Exception as e:
            logger.error(f"Connection error from {addr}: {e}")
            print(f"[✗] Error with {addr[0]}:{addr[1]}: {e}")
        finally:
            if tls_session:
                tls_session.close()
    
    def _dispatch_to_flask(self, request_data: bytes) -> bytes:
        """
        Dispatch a raw HTTP request to the Flask WSGI application.
        
        Parses the request, creates a WSGI environ, and calls the Flask app.
        """
        try:
            request_str = request_data.decode('utf-8')
            lines = request_str.split('\r\n')
            
            if not lines:
                return self._make_error_response(400, "Empty request")
            
            # Parse request line
            request_line = lines[0].split(' ')
            if len(request_line) < 2:
                return self._make_error_response(400, "Malformed request line")
            
            method = request_line[0]
            path = request_line[1]
            
            # Parse headers
            headers = {}
            body_start = 0
            for i, line in enumerate(lines[1:], 1):
                if line == '':
                    body_start = i + 1
                    break
                if ':' in line:
                    key, value = line.split(':', 1)
                    headers[key.strip()] = value.strip()
            
            # Get body
            body = '\r\n'.join(lines[body_start:]) if body_start < len(lines) else ''
            
            # Create WSGI environ
            environ = {
                'REQUEST_METHOD': method,
                'PATH_INFO': path,
                'SERVER_NAME': self.host,
                'SERVER_PORT': str(self.port),
                'HTTP_HOST': f'{self.host}:{self.port}',
                'wsgi.input': BytesIO(body.encode('utf-8')),
                'wsgi.errors': BytesIO(),
                'wsgi.url_scheme': 'https',
                'CONTENT_TYPE': headers.get('Content-Type', 'application/json'),
                'CONTENT_LENGTH': str(len(body)),
                'SERVER_PROTOCOL': 'HTTP/1.1',
                'SCRIPT_NAME': '',
                'QUERY_STRING': '',
            }
            
            # Add HTTP headers to environ
            for key, value in headers.items():
                env_key = 'HTTP_' + key.upper().replace('-', '_')
                environ[env_key] = value
            
            # Parse query string if present
            if '?' in path:
                path_part, query = path.split('?', 1)
                environ['PATH_INFO'] = path_part
                environ['QUERY_STRING'] = query
            
            # Call Flask WSGI app
            response_body = []
            response_headers = []
            response_status = ['200 OK']
            
            def start_response(status, headers):
                response_status[0] = status
                response_headers.extend(headers)
            
            result = self.app(environ, start_response)
            for chunk in result:
                response_body.append(chunk)
            
            body_bytes = b''.join(response_body)
            
            # Build HTTP response
            response = f"HTTP/1.1 {response_status[0]}\r\n"
            for key, value in response_headers:
                response += f"{key}: {value}\r\n"
            response += f"Content-Length: {len(body_bytes)}\r\n"
            response += f"Connection: close\r\n"
            response += "\r\n"
            
            return response.encode('utf-8') + body_bytes
            
        except Exception as e:
            return self._make_error_response(500, str(e))
    
    @staticmethod
    def _make_error_response(status_code: int, message: str) -> bytes:
        """Create an HTTP error response."""
        body = json.dumps({
            'status': 'error',
            'message': message
        }).encode('utf-8')
        
        status_text = {400: 'Bad Request', 500: 'Internal Server Error'}
        response = f"HTTP/1.1 {status_code} {status_text.get(status_code, 'Error')}\r\n"
        response += f"Content-Type: application/json\r\n"
        response += f"Content-Length: {len(body)}\r\n"
        response += "\r\n"
        return response.encode('utf-8') + body


if __name__ == '__main__':
    import sys
    sys.path.insert(0, '.')
    from backend.api import app
    
    logging.basicConfig(level=logging.INFO)
    
    # Optional: Load QKD key from simulation
    qkd_key = None
    try:
        from backend.diqkd_simulator import DIQKDSimulator
        print("[*] Running DI-QKD to generate key for TLS...")
        sim = DIQKDSimulator(key_size=256, num_chsh_rounds=500)
        results = sim.run_full_simulation()
        if results.get('combined_key'):
            from tls.hybrid_kex import bits_to_bytes
            qkd_key = bits_to_bytes(results['combined_key'])
            print(f"[✓] QKD key generated: {len(qkd_key)} bytes")
    except Exception as e:
        print(f"[!] QKD key generation skipped: {e}")
    
    server = TLSFlaskServer(app, host='0.0.0.0', port=8443, qkd_key=qkd_key)
    server.start()
