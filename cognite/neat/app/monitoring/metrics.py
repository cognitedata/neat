from collections.abc import Iterable

from prometheus_client import REGISTRY, Counter, Gauge, Metric

from cognite.client import CogniteClient


class NeatMetricsCollector:
    def __init__(self, name: str, cdf_client: CogniteClient = None) -> None:
        self.name = name
        self.metrics: dict[str, Gauge | Counter] = {}

    def register_metric(
        self,
        metric_name: str,
        metric_description: str = "",
        m_type: str = "gauge",
        metric_labels: list[str] | None = None,
    ) -> Gauge | Counter:
        """Register metric in prometheus"""
        metric_labels = [] if metric_labels is None else metric_labels

        metric_name = f"neat_workflow_{self.name}_{metric_name}"
        if metric_name in REGISTRY._names_to_collectors:
            self.metrics[metric_name] = REGISTRY._names_to_collectors[metric_name]
            return self.metrics[metric_name]

        metric = None
        if m_type == "gauge":
            metric = Gauge(metric_name, metric_description, metric_labels)
        elif m_type == "counter":
            metric = Counter(metric_name, metric_description, metric_labels)

        if metric:
            self.metrics[metric_name] = metric
            return metric

    def get(self, metric_name: str, labels: dict[str, str] | None = None) -> Gauge | Counter:
        """Return metric by name"""
        labels = {} if labels is None else labels
        metric_name = f"neat_workflow_{self.name}_{metric_name}"
        return self.metrics.get(metric_name).labels(**labels)

    def report_metric_value(
        self,
        metric_name: str,
        metric_description: str = "",
        m_type: str = "gauge",
        labels: dict[str, str] | None = None,
    ) -> Gauge | Counter:
        metric = self.register_metric(metric_name, metric_description, m_type, [k for k, v in labels.items()])
        return metric.labels(**labels)

    def collect(self) -> Iterable[Metric]:
        pass

    def report_to_cdf():
        pass
