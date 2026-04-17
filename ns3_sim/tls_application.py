"""
TLS Application — Simulates TLS handshake and data transfer over NS-3 network

Measures timing and overhead of the triple-hybrid TLS handshake
when running over simulated classical channels.
"""

import time
import hashlib
from typing import Dict, Any, Optional

from ns3_sim.channel_model import ClassicalChannel
from ns3_sim.topology import QKDTopology


class TLSApplication:
    """
    Simulates TLS handshake and encrypted data transfer over
    a classical channel in the QKD network.
    
    Measures:
    - Handshake latency breakdown (ECDH, ML-KEM, QKD phases)
    - Data throughput over encrypted channel
    - Post-quantum crypto overhead
    """
    
    # Approximate message sizes for crypto operations
    ECDH_X25519_PUBKEY_SIZE = 32          # bytes
    MLKEM768_PUBKEY_SIZE = 1184           # bytes
    MLKEM768_CIPHERTEXT_SIZE = 1088       # bytes
    CLIENT_HELLO_OVERHEAD = 100           # header bytes
    SERVER_HELLO_OVERHEAD = 100
    FINISHED_MSG_SIZE = 64                # HMAC
    AES_GCM_OVERHEAD = 28                 # 12-byte nonce + 16-byte tag
    
    def __init__(self, topology: QKDTopology):
        self.topology = topology
        self.results: Dict[str, Any] = {}
    
    def simulate_handshake(
        self,
        link_name: str,
        include_qkd: bool = True,
        qkd_key_size_bytes: int = 32
    ) -> Dict[str, Any]:
        """
        Simulate a TLS handshake over the classical channel.
        
        Measures the time for each phase:
        1. ClientHello transmission (ECDH pub + ML-KEM pub)
        2. ServerHello transmission (ECDH pub + ML-KEM ciphertext)
        3. Finished messages
        4. Key derivation (compute-bound, not network)
        
        Args:
            link_name: Link to simulate handshake over
            include_qkd: Whether to include QKD key injection
            qkd_key_size_bytes: Size of QKD key component
        """
        link = self.topology.links[link_name]
        cc = link.classical_channel
        cc.reset_metrics()
        
        timing = {}
        total_latency = 0
        
        # 1. ClientHello → Server
        client_hello_size = (
            self.CLIENT_HELLO_OVERHEAD +
            self.ECDH_X25519_PUBKEY_SIZE +
            self.MLKEM768_PUBKEY_SIZE
        )
        delivered, latency = cc.transmit_reliable(client_hello_size)
        timing['client_hello_ms'] = round(latency, 4)
        total_latency += latency
        
        # 2. Server computes ECDH + ML-KEM (CPU time)
        ecdh_compute_ms = 0.1     # X25519 is very fast
        mlkem_compute_ms = 2.0    # ML-KEM-768 encapsulation
        qkd_inject_ms = 0.05 if include_qkd else 0
        hkdf_ms = 0.05
        
        server_compute = ecdh_compute_ms + mlkem_compute_ms + qkd_inject_ms + hkdf_ms
        timing['server_compute_ms'] = round(server_compute, 4)
        total_latency += server_compute
        
        # 3. ServerHello → Client
        server_hello_size = (
            self.SERVER_HELLO_OVERHEAD +
            self.ECDH_X25519_PUBKEY_SIZE +
            self.MLKEM768_CIPHERTEXT_SIZE
        )
        delivered, latency = cc.transmit_reliable(server_hello_size)
        timing['server_hello_ms'] = round(latency, 4)
        total_latency += latency
        
        # 4. Client computes ECDH + ML-KEM decapsulation
        client_compute = ecdh_compute_ms + mlkem_compute_ms + qkd_inject_ms + hkdf_ms
        timing['client_compute_ms'] = round(client_compute, 4)
        total_latency += client_compute
        
        # 5. Server Finished → Client
        delivered, latency = cc.transmit_reliable(self.FINISHED_MSG_SIZE)
        timing['server_finished_ms'] = round(latency, 4)
        total_latency += latency
        
        # 6. Client Finished → Server
        delivered, latency = cc.transmit_reliable(self.FINISHED_MSG_SIZE)
        timing['client_finished_ms'] = round(latency, 4)
        total_latency += latency
        
        # Breakdown by component
        kex_type = 'ECDH-X25519 + ML-KEM-768'
        if include_qkd:
            kex_type += ' + QKD'
        
        result = {
            'link': link_name,
            'distance_km': cc.distance_km,
            'kex_type': kex_type,
            'timing_breakdown': timing,
            'total_handshake_ms': round(total_latency, 4),
            'network_latency_ms': round(
                timing['client_hello_ms'] + timing['server_hello_ms'] +
                timing['server_finished_ms'] + timing['client_finished_ms'], 4
            ),
            'compute_latency_ms': round(
                timing['server_compute_ms'] + timing['client_compute_ms'], 4
            ),
            'data_transferred_bytes': client_hello_size + server_hello_size + 2 * self.FINISHED_MSG_SIZE,
            'pq_overhead_bytes': self.MLKEM768_PUBKEY_SIZE + self.MLKEM768_CIPHERTEXT_SIZE,
            'classical_channel_metrics': cc.metrics.to_dict(),
        }
        
        self.results['handshake'] = result
        return result
    
    def simulate_data_transfer(
        self,
        link_name: str,
        data_size_bytes: int = 10000,
        record_size: int = 16384
    ) -> Dict[str, Any]:
        """
        Simulate encrypted data transfer over TLS.
        
        Measures throughput with AES-256-GCM encryption overhead.
        """
        link = self.topology.links[link_name]
        cc = link.classical_channel
        
        # Fragment into TLS records
        num_records = (data_size_bytes + record_size - 1) // record_size
        total_overhead = num_records * self.AES_GCM_OVERHEAD
        total_wire_bytes = data_size_bytes + total_overhead
        
        total_latency = 0
        records_sent = 0
        
        remaining = total_wire_bytes
        while remaining > 0:
            chunk = min(remaining, record_size + self.AES_GCM_OVERHEAD)
            delivered, latency = cc.transmit_reliable(chunk)
            total_latency += latency
            if delivered:
                records_sent += 1
            remaining -= chunk
        
        throughput_bps = (data_size_bytes * 8) / (total_latency / 1000) if total_latency > 0 else 0
        
        result = {
            'link': link_name,
            'data_size_bytes': data_size_bytes,
            'wire_bytes': total_wire_bytes,
            'encryption_overhead_bytes': total_overhead,
            'overhead_ratio': round(total_overhead / max(data_size_bytes, 1), 4),
            'num_records': num_records,
            'records_delivered': records_sent,
            'total_latency_ms': round(total_latency, 4),
            'throughput_mbps': round(throughput_bps / 1e6, 4),
        }
        
        self.results['data_transfer'] = result
        return result
    
    def simulate_full_session(
        self,
        link_name: str,
        include_qkd: bool = True,
        data_size_bytes: int = 10000
    ) -> Dict[str, Any]:
        """
        Simulate a complete TLS session: handshake + data transfer.
        """
        handshake = self.simulate_handshake(link_name, include_qkd=include_qkd)
        transfer = self.simulate_data_transfer(link_name, data_size_bytes)
        
        total_time = handshake['total_handshake_ms'] + transfer['total_latency_ms']
        
        return {
            'handshake': handshake,
            'data_transfer': transfer,
            'total_session_ms': round(total_time, 4),
            'time_to_first_byte_ms': round(handshake['total_handshake_ms'], 4),
        }
