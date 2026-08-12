from __future__ import annotations

import importlib.util
from pathlib import Path
import tarfile
import tempfile
import unittest


SCRIPT = Path(__file__).with_name("submit_training.py")
SPEC = importlib.util.spec_from_file_location("submit_training", SCRIPT)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class SubmitTrainingTests(unittest.TestCase):
    def test_source_archive_is_complete_and_free_of_caches(self) -> None:
        repo = Path(__file__).resolve().parents[3]
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "source.tar.gz"
            digest = module.build_source_archive(repo, target)
            self.assertEqual(len(digest), 64)
            with tarfile.open(target, "r:gz") as archive:
                names = set(archive.getnames())
            self.assertIn("train.py", names)
            self.assertIn("public_intelligence/models/usaspending_funding.py", names)
            self.assertFalse(any("__pycache__" in name for name in names))

    def test_job_spec_is_isolated_kms_encrypted_and_candidate_only(self) -> None:
        spec = module.build_job_spec(
            job_name="test-job",
            role_arn="arn:aws:iam::123456789012:role/test",
            image_uri=module.DEFAULT_IMAGE,
            bucket="test-bucket",
            prefix="mlops/jobs/test-job",
            kms_key_arn="arn:aws:kms:us-east-1:123456789012:key/test",
            dataset_sha256="a" * 64,
            source_sha256="b" * 64,
        )
        self.assertTrue(spec["EnableNetworkIsolation"])
        self.assertTrue(spec["EnableInterContainerTrafficEncryption"])
        self.assertEqual(spec["ResourceConfig"]["InstanceCount"], 1)
        self.assertEqual(spec["StoppingCondition"]["MaxRuntimeInSeconds"], 1800)
        self.assertIn(
            {"Key": "compass:approval-state", "Value": "candidate-only"},
            spec["Tags"],
        )


if __name__ == "__main__":
    unittest.main()
