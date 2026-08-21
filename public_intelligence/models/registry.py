"""Model-kind dispatch with no implicit fallback implementation."""

from __future__ import annotations

from typing import Callable

from .anomaly_detection import train_anomaly_detector
from .common import TrainingOutput
from .contracts import CanonicalDataset, TrainingRefusal
from .funding_forecast import train_funding_forecast
from .observed_signal_proxy import train_observed_signal_proxy
from .research_impact import train_research_impact_quantiles
from .sbir_transition import train_sbir_transition
from .technology_classifier import train_technology_classifier


TRAINERS: dict[str, Callable[[CanonicalDataset], TrainingOutput]] = {
    "funding_forecast": train_funding_forecast,
    "sbir_transition": train_sbir_transition,
    "technology_classifier": train_technology_classifier,
    "research_impact_quantiles": train_research_impact_quantiles,
    "anomaly_detection": train_anomaly_detector,
    "observed_signal_proxy": train_observed_signal_proxy,
}


def train_dataset(dataset: CanonicalDataset) -> TrainingOutput:
    trainer = TRAINERS.get(dataset.model_kind)
    if trainer is None:
        raise TrainingRefusal(
            "unsupported_model", f"no trainer exists for {dataset.model_kind!r}"
        )
    return trainer(dataset)
