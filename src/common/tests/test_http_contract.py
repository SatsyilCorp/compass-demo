"""Contract tests for API Gateway identity and CORS normalization."""
from __future__ import annotations

import json
import os
import unittest

from compass_common import http


def jwt_event(claims):
    return {
        "version": "2.0",
        "routeKey": "GET /dashboard",
        "requestContext": {
            "http": {
                "method": "GET",
                "path": "/dashboard",
                "protocol": "HTTP/1.1",
            },
            "authorizer": {"jwt": {"claims": claims, "scopes": None}},
        },
    }


class IdentityContractTests(unittest.TestCase):
    def test_native_jwt_viewer_derives_role_and_org(self):
        claims = http.get_claims(
            jwt_event(
                {
                    "sub": "user-viewer",
                    "cognito:username": "viewer.demo",
                    "cognito:groups": '["compass-viewer"]',
                }
            )
        )
        self.assertEqual(claims.role, "viewer")
        self.assertEqual(claims.org_unit, "Code-30")
        self.assertTrue(claims.is_authenticated)
        self.assertFalse(claims.is_corporate)

    def test_native_jwt_poweruser_derives_corporate_context(self):
        claims = http.get_claims(
            jwt_event(
                {
                    "sub": "user-power",
                    "cognito:groups": "[compass-poweruser]",
                }
            )
        )
        self.assertEqual(
            (claims.role, claims.org_unit),
            ("poweruser", "ONR-Corporate"),
        )
        self.assertTrue(claims.is_corporate)

    def test_group_precedence_is_stable_not_input_order(self):
        claims = http.get_claims(
            jwt_event(
                {
                    "cognito:groups": "compass-viewer,compass-poweruser",
                }
            )
        )
        self.assertEqual(claims.role, "poweruser")
        self.assertEqual(claims.org_unit, "ONR-Corporate")

    def test_unrecognized_group_fails_closed(self):
        claims = http.get_claims(
            jwt_event({"cognito:groups": "ordinary-cognito-user"})
        )
        self.assertFalse(claims.is_authenticated)
        self.assertIsNone(claims.role)
        self.assertIsNone(claims.org_unit)

    def test_conflicting_role_and_org_fail_closed(self):
        claims = http.get_claims(
            {
                "requestContext": {
                    "authorizer": {
                        "lambda": {
                            "role": "viewer",
                            "org_unit": "ONR-Corporate",
                        }
                    }
                }
            }
        )
        self.assertFalse(claims.is_authenticated)

    def test_recognized_group_overrides_conflicting_explicit_role(self):
        claims = http.get_claims(
            jwt_event(
                {
                    "role": "poweruser",
                    "cognito:groups": "compass-viewer",
                }
            )
        )
        self.assertEqual((claims.role, claims.org_unit), ("viewer", "Code-30"))


class RequestAccessorTests(unittest.TestCase):
    def test_named_http_api_stage_is_removed_from_handler_path(self):
        event = {
            "requestContext": {
                "stage": "prod",
                "http": {"method": "GET", "path": "/prod/scale/profiles"},
            }
        }

        self.assertEqual(http.get_path(event), "/scale/profiles")

    def test_default_or_absent_stage_keeps_handler_path(self):
        default_event = {
            "requestContext": {
                "stage": "$default",
                "http": {"path": "/scale/profiles"},
            }
        }
        absent_event = {"requestContext": {"http": {"path": "/scale/profiles"}}}

        self.assertEqual(http.get_path(default_event), "/scale/profiles")
        self.assertEqual(http.get_path(absent_event), "/scale/profiles")

    def test_stage_prefix_must_match_a_complete_path_segment(self):
        event = {
            "requestContext": {
                "stage": "prod",
                "http": {"path": "/production/scale/profiles"},
            }
        }

        self.assertEqual(http.get_path(event), "/production/scale/profiles")


class CorsContractTests(unittest.TestCase):
    def setUp(self):
        self.previous = os.environ.get("CORS_ALLOW_ORIGINS")
        os.environ["CORS_ALLOW_ORIGINS"] = (
            "https://demo.example.gov,http://localhost:3000"
        )

    def tearDown(self):
        if self.previous is None:
            os.environ.pop("CORS_ALLOW_ORIGINS", None)
        else:
            os.environ["CORS_ALLOW_ORIGINS"] = self.previous

    def test_allowed_origin_is_reflected_exactly(self):
        response = http.json_response(
            200,
            {"ok": True},
            origin="https://demo.example.gov/",
        )
        self.assertEqual(
            response["headers"]["Access-Control-Allow-Origin"],
            "https://demo.example.gov",
        )
        self.assertEqual(response["headers"]["Vary"], "Origin")
        self.assertEqual(json.loads(response["body"]), {"ok": True})

    def test_unknown_origin_and_wildcard_override_are_rejected(self):
        unknown = http.json_response(
            200,
            {},
            origin="https://attacker.example",
        )
        self.assertNotIn("Access-Control-Allow-Origin", unknown["headers"])

        wildcard = http.json_response(
            200,
            {},
            headers={"Access-Control-Allow-Origin": "*"},
        )
        self.assertNotIn("Access-Control-Allow-Origin", wildcard["headers"])

        arbitrary = http.json_response(
            200,
            {},
            headers={"Access-Control-Allow-Origin": "https://attacker.example"},
        )
        self.assertNotIn("Access-Control-Allow-Origin", arbitrary["headers"])


if __name__ == "__main__":
    unittest.main()
