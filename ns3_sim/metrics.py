"""
Metrics Collector — Records and aggregates simulation data

Collects time-series metrics during QKD and TLS simulations
for analysis and visualization.
"""

import csv
import json
import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class MetricPoint:
    """A single data point."""
    timestamp: float
    name: str
    value: float
    labels: Dict[str, str] = field(default_factory=dict)


class MetricsCollector:
    """
    Collects and aggregates simulation metrics.
    
    Usage:
        mc = MetricsCollector()
        mc.record("key_rate", 0.0012, distance_km=10)
        mc.record("qber", 0.03, distance_km=10)
        
        summary = mc.summary()
        mc.to_csv("metrics.csv")
    """
    
    def __init__(self, scenario_name: str = "default"):
        self.scenario_name = scenario_name
        self.start_time = time.time()
        self._points: List[MetricPoint] = []
    
    def record(self, name: str, value: float, **labels):
        """
        Record a metric value.
        
        Args:
            name: Metric name (e.g., "key_rate", "qber", "handshake_ms")
            value: Metric value
            **labels: Additional labels (e.g., distance_km=10)
        """
        self._points.append(MetricPoint(
            timestamp=time.time() - self.start_time,
            name=name,
            value=value,
            labels={k: str(v) for k, v in labels.items()},
        ))
    
    def get_metric(self, name: str) -> List[Dict[str, Any]]:
        """Get all data points for a specific metric."""
        return [
            {
                'timestamp': p.timestamp,
                'value': p.value,
                **p.labels,
            }
            for p in self._points if p.name == name
        ]
    
    def get_metric_values(self, name: str) -> List[float]:
        """Get just the values for a metric."""
        return [p.value for p in self._points if p.name == name]
    
    def get_metric_by_label(
        self,
        name: str,
        label_key: str
    ) -> Dict[str, List[float]]:
        """
        Group metric values by a label.
        
        Returns:
            dict mapping label values to lists of metric values
        """
        groups: Dict[str, List[float]] = {}
        for p in self._points:
            if p.name == name and label_key in p.labels:
                key = p.labels[label_key]
                if key not in groups:
                    groups[key] = []
                groups[key].append(p.value)
        return groups
    
    def summary(self) -> Dict[str, Any]:
        """
        Get aggregated summary of all metrics.
        
        Returns:
            dict with min/max/avg/count for each metric
        """
        metric_names = set(p.name for p in self._points)
        result = {
            'scenario': self.scenario_name,
            'total_points': len(self._points),
            'duration_s': round(time.time() - self.start_time, 4),
            'metrics': {},
        }
        
        for name in sorted(metric_names):
            values = self.get_metric_values(name)
            if values:
                result['metrics'][name] = {
                    'count': len(values),
                    'min': round(min(values), 8),
                    'max': round(max(values), 8),
                    'avg': round(sum(values) / len(values), 8),
                    'sum': round(sum(values), 8),
                }
        
        return result
    
    def to_csv(self, filename: str):
        """Export all metrics to CSV."""
        if not self._points:
            return
        
        # Collect all label keys
        all_labels = set()
        for p in self._points:
            all_labels.update(p.labels.keys())
        all_labels = sorted(all_labels)
        
        with open(filename, 'w', newline='') as f:
            writer = csv.writer(f)
            header = ['timestamp', 'metric', 'value'] + list(all_labels)
            writer.writerow(header)
            
            for p in self._points:
                row = [
                    round(p.timestamp, 6),
                    p.name,
                    round(p.value, 8),
                ]
                for label in all_labels:
                    row.append(p.labels.get(label, ''))
                writer.writerow(row)
    
    def to_json(self, filename: str):
        """Export all metrics to JSON."""
        data = {
            'scenario': self.scenario_name,
            'timestamp': datetime.now().isoformat(),
            'summary': self.summary(),
            'data_points': [
                {
                    'timestamp': round(p.timestamp, 6),
                    'metric': p.name,
                    'value': round(p.value, 8),
                    'labels': p.labels,
                }
                for p in self._points
            ],
        }
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
    
    def reset(self):
        """Clear all collected metrics."""
        self._points = []
        self.start_time = time.time()
    
    def __len__(self):
        return len(self._points)
    
    def __repr__(self):
        return (
            f"MetricsCollector(scenario='{self.scenario_name}', "
            f"points={len(self._points)})"
        )
