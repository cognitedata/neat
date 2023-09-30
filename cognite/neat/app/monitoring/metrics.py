from collections.abc import Iterable
from typing import cast

from cognite.client import CogniteClient
from prometheus_client import REGISTRY, Counter, Gauge, Metric


class NeatMetricsCollector:
    def __init__(self, name: str, cdf_client: CogniteClient | None = None) -> None:
        self.name = name
        self.metrics: dict[str, Gauge | Counter] = {}

    def register_metric(
        self,
        metric_name: str,
        metric_description: str = "",
        m_type: str = "gauge",
        metric_labels: list[str] | None = None,
    ) -> Gauge | Counter | None:
        """Register metric in prometheus"""
        metric_name = self.sanitize_metric_name(metric_name)
        metric_labels = [] if metric_labels is None else metric_labels

        metric_name = f"neat_workflow_{self.sanitize_metric_name(self.name)}_{metric_name}"
        if metric_name in REGISTRY._names_to_collectors:
            self.metrics[metric_name] = cast(Gauge | Counter, REGISTRY._names_to_collectors[metric_name])
            return self.metrics[metric_name]

        metric: Gauge | Counter | None = None
        if m_type == "gauge":
            metric = Gauge(metric_name, metric_description, metric_labels)
        elif m_type == "counter":
            metric = Counter(metric_name, metric_description, metric_labels)

        if metric:
            self.metrics[metric_name] = metric
            return metric
        return None

    def get(self, metric_name: str, labels: dict[str, str] | None = None) -> Gauge | Counter | None:
        """Return metric by name"""
        metric_name = self.sanitize_metric_name(metric_name)
        labels = {} if labels is None else labels
        metric_name = f"neat_workflow_{self.sanitize_metric_name(self.name)}_{metric_name}"
        if metric_name in self.metrics:
            return self.metrics[metric_name].labels(**(labels or {}))
        return None

    def report_metric_value(
        self,
        metric_name: str,
        metric_description: str = "",
        m_type: str = "gauge",
        labels: dict[str, str] | None = None,
    ) -> Gauge | Counter | None:
        self.sanitize_metric_name(metric_name)
        metric = self.register_metric(metric_name, metric_description, m_type, [k for k, v in (labels or {}).items()])
        if metric:
            return metric.labels(**(labels or {}))
        return None

    def sanitize_metric_name(self, metric_name: str) -> str:
        return metric_name.replace("-", "_").replace(" ", "_").replace(".", "_").replace(":", "_").lower()

    def collect(self) -> Iterable[Metric]:
        return cast(Iterable[Metric], self.metrics.values())

    def report_to_cdf(self):
        pass
