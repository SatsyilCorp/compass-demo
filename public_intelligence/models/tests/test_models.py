from __future__ import annotations

import unittest

import numpy as np

from public_intelligence.models.anomaly_detection import train_anomaly_detector
from public_intelligence.models.common import tabular_feature_names, tabular_matrix
from public_intelligence.models.contracts import TrainingRefusal
from public_intelligence.models.funding_forecast import train_funding_forecast
from public_intelligence.models.observed_signal_proxy import train_observed_signal_proxy
from public_intelligence.models.research_impact import train_research_impact_quantiles
from public_intelligence.models.sbir_transition import (
    train_sbir_transition,
    transition_feature_names,
    transition_matrix,
)
from public_intelligence.models.technology_classifier import train_technology_classifier

from .synthetic_fixtures import (
    anomaly_fixture,
    funding_fixture,
    impact_fixture,
    observed_signal_fixture,
    sbir_fixture,
    technology_fixture,
)


class PublicModelAlgorithmTests(unittest.TestCase):
    def test_funding_forecast_is_deterministic_and_intervals_are_ordered(self):
        data = funding_fixture()
        first = train_funding_forecast(data)
        second = train_funding_forecast(data)
        numeric, categorical = tabular_feature_names(data)
        X = tabular_matrix(data.rows[-5:], numeric, categorical)
        first_point = first.estimator.predict(X)
        second_point = second.estimator.predict(X)
        intervals = first.estimator.predict_interval(X)
        np.testing.assert_allclose(first_point, second_point)
        self.assertTrue(np.all(intervals[:, 0] <= first_point))
        self.assertTrue(np.all(first_point <= intervals[:, 1]))
        self.assertEqual(
            len(first.model_card["evaluation"]["holdout"]["rolling_backtests"]),
            3,
        )

    def test_sbir_transition_is_calibrated_and_group_split_is_recorded(self):
        data = sbir_fixture()
        output = train_sbir_transition(data)
        numeric, categorical, text_field = transition_feature_names(data)
        probabilities = output.estimator.predict_proba(
            transition_matrix(data.rows[-8:], numeric, categorical, text_field)
        )[:, 1]
        self.assertTrue(np.all(probabilities >= 0.0))
        self.assertTrue(np.all(probabilities <= 1.0))
        split = output.model_card["split_evidence"]
        self.assertGreater(split["fit"]["groups"], 0)
        self.assertGreater(split["calibration"]["groups"], 0)
        self.assertGreater(split["test"]["groups"], 0)
        self.assertEqual(
            output.model_card["algorithm"],
            "calibrated-histogram-gradient-boosting-with-tfidf-svd",
        )

    def test_technology_classifier_uses_only_reviewed_taxonomy(self):
        data = technology_fixture()
        output = train_technology_classifier(data)
        predictions = output.estimator.predict(
            [
                "autonomous maritime navigation planning and vehicle control synthetic test",
                "thermal composite material manufacturing and coating synthetic test",
            ]
        )
        self.assertTrue(set(predictions).issubset({"autonomy", "materials", "sensing"}))
        self.assertEqual(
            output.model_card["taxonomy"]["review_id"], "synthetic-test-review"
        )

    def test_impact_quantiles_exclude_censored_rows_and_are_monotonic(self):
        data = impact_fixture()
        output = train_research_impact_quantiles(data)
        numeric, categorical = tabular_feature_names(data)
        predictions = output.estimator.predict_quantiles(
            tabular_matrix(data.rows[:10], numeric, categorical)
        )
        self.assertTrue(np.all(predictions[0.10] <= predictions[0.50]))
        self.assertTrue(np.all(predictions[0.50] <= predictions[0.90]))
        self.assertEqual(output.receipt["rows_excluded"]["explicitly_censored"], 12)

    def test_anomaly_model_emits_review_language_without_probability_claim(self):
        data = anomaly_fixture()
        output = train_anomaly_detector(data)
        numeric, categorical = tabular_feature_names(data)
        details = output.estimator.predict_details(
            tabular_matrix(data.rows[-10:], numeric, categorical)
        )
        self.assertTrue(any(item["review_required"] for item in details))
        self.assertTrue(
            all(item["semantics"] == "analyst review signal only" for item in details)
        )
        holdout = output.model_card["evaluation"]["holdout"]
        self.assertFalse(holdout["probability_metrics_reported"])
        self.assertNotIn("roc_auc", holdout)

    def test_observed_signal_proxy_never_claims_internal_success(self):
        data = observed_signal_fixture()
        output = train_observed_signal_proxy(data)
        semantics = output.model_card["output_semantics"].lower()
        self.assertIn("never", semantics)
        self.assertIn("internal onr success", semantics)
        with self.assertRaises(TrainingRefusal) as raised:
            train_observed_signal_proxy(observed_signal_fixture(internal_claim=True))
        self.assertEqual(raised.exception.code, "unsupported_internal_outcome_claim")


if __name__ == "__main__":
    unittest.main()
