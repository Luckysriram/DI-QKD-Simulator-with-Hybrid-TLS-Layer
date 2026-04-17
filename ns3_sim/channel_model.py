"""
Channel Models for QKD Network Simulation

Models realistic quantum and classical communication channels with:
- Quantum channel: fiber loss, depolarization noise, detector efficiency
- Classical channel: latency, jitter, packet loss, bandwidth
- Eavesdropper channel: intercept-resend attack model
"""

import math
import random
import time
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Any


@dataclass
class ChannelMetrics:
    """Metrics collected from channel transmission."""
    total_sent: int = 0
    total_received: int = 0
    total_lost: int = 0
    total_errors: int = 0
    latencies_ms: List[float] = field(default_factory=list)
    
    @property
    def loss_rate(self) -> float:
        return self.total_lost / max(self.total_sent, 1)
    
    @property
    def error_rate(self) -> float:
        return self.total_errors / max(self.total_received, 1)
    
    @property
    def avg_latency_ms(self) -> float:
        return sum(self.latencies_ms) / max(len(self.latencies_ms), 1)
    
    @property
    def throughput_bps(self) -> float:
        total_time = sum(self.latencies_ms) / 1000.0
        if total_time == 0:
            return 0
        return self.total_received * 8 / total_time
    
    def to_dict(self) -> dict:
        return {
            'total_sent': self.total_sent,
            'total_received': self.total_received,
            'total_lost': self.total_lost,
            'total_errors': self.total_errors,
            'loss_rate': round(self.loss_rate, 6),
            'error_rate': round(self.error_rate, 6),
            'avg_latency_ms': round(self.avg_latency_ms, 4),
            'throughput_bps': round(self.throughput_bps, 2),
        }


class QuantumChannel:
    """
    Simulates a quantum optical fiber channel.
    
    Models:
    - Fiber attenuation (0.2 dB/km typical for telecom fiber)
    - Depolarization noise (reduces quantum correlations)
    - Dark count rate (false detections)
    - Detector efficiency
    - Distance-dependent QBER increase
    """
    
    # Standard parameters for telecom fiber
    DEFAULT_ATTENUATION = 0.2      # dB/km
    DEFAULT_DARK_COUNT = 1e-6      # per pulse
    DEFAULT_DETECTOR_EFF = 0.1     # 10% efficiency (APD)
    DEFAULT_DEPOLAR_RATE = 0.01    # per km
    SPEED_OF_LIGHT_FIBER = 2e8     # m/s (c / 1.5 refractive index)
    
    def __init__(
        self,
        distance_km: float = 10.0,
        attenuation_db_per_km: float = DEFAULT_ATTENUATION,
        dark_count_rate: float = DEFAULT_DARK_COUNT,
        detector_efficiency: float = DEFAULT_DETECTOR_EFF,
        depolarization_rate: float = DEFAULT_DEPOLAR_RATE
    ):
        self.distance_km = distance_km
        self.attenuation = attenuation_db_per_km
        self.dark_count_rate = dark_count_rate
        self.detector_efficiency = detector_efficiency
        self.depolarization_rate = depolarization_rate
        
        self.metrics = ChannelMetrics()
        
        # Derived quantities
        self._total_loss_db = self.attenuation * self.distance_km
        self._transmission_prob = 10 ** (-self._total_loss_db / 10)
        self._propagation_delay_ms = (self.distance_km * 1000) / self.SPEED_OF_LIGHT_FIBER * 1000
        self._depolar_prob = 1 - math.exp(-self.depolarization_rate * self.distance_km)
    
    @property
    def transmission_probability(self) -> float:
        """Probability that a photon arrives at the detector."""
        return self._transmission_prob * self.detector_efficiency
    
    @property
    def expected_qber(self) -> float:
        """Expected QBER due to channel noise."""
        # QBER from depolarization
        depolar_qber = self._depolar_prob / 2  # Depolarization causes 50% errors
        
        # QBER from dark counts (false positives)
        signal_rate = self._transmission_prob * self.detector_efficiency
        dark_rate = self.dark_count_rate
        if signal_rate + dark_rate > 0:
            dark_qber = 0.5 * dark_rate / (signal_rate + dark_rate)
        else:
            dark_qber = 0
        
        total_qber = depolar_qber + dark_qber - depolar_qber * dark_qber
        return min(total_qber, 0.5)
    
    @property
    def key_rate_per_pulse(self) -> float:
        """
        Estimated secure key rate per pulse (bits/pulse).
        
        Uses the simplified BB84 key rate formula:
            R = q * Q * (1 - 2*h(e))
        where:
            q = 0.5 (sifting efficiency)
            Q = detection probability
            e = QBER
            h(x) = -x*log2(x) - (1-x)*log2(1-x) (binary entropy)
        """
        q = 0.5
        Q = self.transmission_probability
        e = self.expected_qber
        
        if Q <= 0 or e >= 0.11:  # QBER threshold
            return 0.0
        
        if e <= 0 or e >= 1:
            h_e = 0
        else:
            h_e = -e * math.log2(e) - (1 - e) * math.log2(1 - e)
        
        rate = q * Q * max(0, 1 - 2 * h_e)
        return rate
    
    def transmit_photon(self) -> Tuple[bool, bool, float]:
        """
        Simulate transmission of a single photon through the channel.
        
        Returns:
            (detected, error, latency_ms)
            - detected: True if photon was detected
            - error: True if the detected photon had a bit flip
            - latency_ms: Propagation delay
        """
        self.metrics.total_sent += 1
        
        latency = self._propagation_delay_ms
        # Add jitter
        latency += random.gauss(0, 0.01 * latency) if latency > 0 else 0
        
        # Check if photon survives fiber loss
        if random.random() > self._transmission_prob:
            # Check dark count
            if random.random() < self.dark_count_rate:
                # Dark count — random bit, 50% error
                self.metrics.total_received += 1
                error = random.random() < 0.5
                if error:
                    self.metrics.total_errors += 1
                self.metrics.latencies_ms.append(latency)
                return True, error, latency
            
            self.metrics.total_lost += 1
            return False, False, latency
        
        # Check detector efficiency
        if random.random() > self.detector_efficiency:
            self.metrics.total_lost += 1
            return False, False, latency
        
        # Photon detected — check depolarization
        error = random.random() < self._depolar_prob / 2
        if error:
            self.metrics.total_errors += 1
        
        self.metrics.total_received += 1
        self.metrics.latencies_ms.append(latency)
        return True, error, latency
    
    def transmit_batch(self, num_photons: int) -> Dict[str, Any]:
        """
        Simulate batch transmission of photons.
        
        Returns:
            dict with transmission results and statistics
        """
        detected = 0
        errors = 0
        total_latency = 0
        
        for _ in range(num_photons):
            det, err, lat = self.transmit_photon()
            if det:
                detected += 1
                total_latency += lat
                if err:
                    errors += 1
        
        return {
            'sent': num_photons,
            'detected': detected,
            'lost': num_photons - detected,
            'errors': errors,
            'detection_rate': detected / max(num_photons, 1),
            'qber': errors / max(detected, 1),
            'avg_latency_ms': total_latency / max(detected, 1),
            'key_rate': self.key_rate_per_pulse,
        }
    
    def get_info(self) -> dict:
        """Get channel parameters and metrics."""
        return {
            'type': 'quantum',
            'distance_km': self.distance_km,
            'attenuation_db_per_km': self.attenuation,
            'total_loss_db': self._total_loss_db,
            'transmission_probability': round(self.transmission_probability, 8),
            'expected_qber': round(self.expected_qber, 6),
            'key_rate_per_pulse': round(self.key_rate_per_pulse, 8),
            'propagation_delay_ms': round(self._propagation_delay_ms, 4),
            'metrics': self.metrics.to_dict(),
        }
    
    def reset_metrics(self):
        """Reset channel metrics."""
        self.metrics = ChannelMetrics()


class ClassicalChannel:
    """
    Simulates a classical TCP/IP communication channel.
    
    Models:
    - Propagation delay (distance-based)
    - Jitter (Gaussian)
    - Packet loss rate
    - Bandwidth limit
    """
    
    SPEED_OF_LIGHT_FIBER = 2e8  # m/s
    
    def __init__(
        self,
        distance_km: float = 10.0,
        base_latency_ms: Optional[float] = None,
        jitter_ms: float = 1.0,
        packet_loss_rate: float = 0.001,
        bandwidth_mbps: float = 1000.0
    ):
        self.distance_km = distance_km
        
        # Auto-calculate latency from distance if not specified
        if base_latency_ms is None:
            self.base_latency_ms = (distance_km * 1000) / self.SPEED_OF_LIGHT_FIBER * 1000
        else:
            self.base_latency_ms = base_latency_ms
        
        self.jitter_ms = jitter_ms
        self.packet_loss_rate = packet_loss_rate
        self.bandwidth_mbps = bandwidth_mbps
        
        self.metrics = ChannelMetrics()
    
    def transmit(self, data_size_bytes: int) -> Tuple[bool, float]:
        """
        Simulate transmission of a data packet.
        
        Args:
            data_size_bytes: Size of the packet
        
        Returns:
            (delivered, latency_ms)
        """
        self.metrics.total_sent += 1
        
        # Calculate latency
        propagation = self.base_latency_ms
        jitter = max(0, random.gauss(0, self.jitter_ms))
        transmission_delay = (data_size_bytes * 8) / (self.bandwidth_mbps * 1e6) * 1000
        total_latency = propagation + jitter + transmission_delay
        
        # Check packet loss
        if random.random() < self.packet_loss_rate:
            self.metrics.total_lost += 1
            return False, total_latency
        
        self.metrics.total_received += 1
        self.metrics.latencies_ms.append(total_latency)
        return True, total_latency
    
    def transmit_reliable(self, data_size_bytes: int, max_retries: int = 3) -> Tuple[bool, float]:
        """
        Simulate reliable (TCP-like) transmission with retransmission.
        
        Returns:
            (delivered, total_latency_ms)
        """
        total_latency = 0
        for attempt in range(max_retries + 1):
            delivered, latency = self.transmit(data_size_bytes)
            total_latency += latency
            if delivered:
                return True, total_latency
            # Wait for timeout before retry
            total_latency += self.base_latency_ms * 2  # RTT timeout
        
        return False, total_latency
    
    def get_info(self) -> dict:
        return {
            'type': 'classical',
            'distance_km': self.distance_km,
            'base_latency_ms': round(self.base_latency_ms, 4),
            'jitter_ms': self.jitter_ms,
            'packet_loss_rate': self.packet_loss_rate,
            'bandwidth_mbps': self.bandwidth_mbps,
            'metrics': self.metrics.to_dict(),
        }
    
    def reset_metrics(self):
        self.metrics = ChannelMetrics()


class EavesdropperChannel(QuantumChannel):
    """
    Extends QuantumChannel with an eavesdropper (Eve).
    
    Eve performs an intercept-resend attack:
    - Intercepts a fraction of photons
    - Measures them in a random basis
    - Resends a new photon based on her measurement
    - This introduces ~25% additional QBER when Eve intercepts
    """
    
    def __init__(
        self,
        distance_km: float = 10.0,
        eve_position_km: float = 5.0,
        intercept_rate: float = 0.5,
        **kwargs
    ):
        """
        Args:
            distance_km: Total channel distance
            eve_position_km: Eve's position along the fiber
            intercept_rate: Fraction of photons Eve intercepts (0 to 1)
        """
        super().__init__(distance_km=distance_km, **kwargs)
        
        self.eve_position_km = min(eve_position_km, distance_km)
        self.intercept_rate = intercept_rate
        
        self.eve_metrics = {
            'intercepted': 0,
            'correct_guesses': 0,
            'induced_errors': 0,
        }
    
    def transmit_photon(self) -> Tuple[bool, bool, float]:
        """Simulate transmission with possible eavesdropping."""
        self.metrics.total_sent += 1
        
        latency = self._propagation_delay_ms
        latency += random.gauss(0, 0.01 * latency) if latency > 0 else 0
        
        error = False
        
        # Eve intercepts?
        if random.random() < self.intercept_rate:
            self.eve_metrics['intercepted'] += 1
            
            # Eve measures in random basis — 50% chance of wrong basis
            if random.random() < 0.5:
                # Wrong basis — introduces 25% error (50% * 50%)
                if random.random() < 0.5:
                    error = True
                    self.eve_metrics['induced_errors'] += 1
                else:
                    self.eve_metrics['correct_guesses'] += 1
            else:
                # Correct basis — no error from Eve
                self.eve_metrics['correct_guesses'] += 1
        
        # Normal channel effects still apply
        if random.random() > self._transmission_prob:
            if random.random() < self.dark_count_rate:
                self.metrics.total_received += 1
                if random.random() < 0.5:
                    error = True
                    self.metrics.total_errors += 1
                self.metrics.latencies_ms.append(latency)
                return True, error, latency
            
            self.metrics.total_lost += 1
            return False, False, latency
        
        if random.random() > self.detector_efficiency:
            self.metrics.total_lost += 1
            return False, False, latency
        
        # Channel depolarization (on top of Eve's disturbance)
        if not error and random.random() < self._depolar_prob / 2:
            error = True
        
        if error:
            self.metrics.total_errors += 1
        
        self.metrics.total_received += 1
        self.metrics.latencies_ms.append(latency)
        return True, error, latency
    
    @property
    def expected_qber(self) -> float:
        """QBER including Eve's interference."""
        base_qber = super().expected_qber
        eve_qber = self.intercept_rate * 0.25  # Intercept-resend adds ~25% QBER
        total = base_qber + eve_qber - base_qber * eve_qber
        return min(total, 0.5)
    
    def get_info(self) -> dict:
        info = super().get_info()
        info['type'] = 'eavesdropper'
        info['eve_position_km'] = self.eve_position_km
        info['intercept_rate'] = self.intercept_rate
        info['eve_metrics'] = dict(self.eve_metrics)
        info['expected_qber'] = round(self.expected_qber, 6)
        return info
    
    def reset_metrics(self):
        super().reset_metrics()
        self.eve_metrics = {
            'intercepted': 0,
            'correct_guesses': 0,
            'induced_errors': 0,
        }
