"""Shared pytest configuration for every Python test in the repo."""

import os

from hypothesis import HealthCheck, settings

# Wall-clock deadlines make property tests flaky on loaded machines and under
# coverage; they do not affect correctness, so they are off. The number of
# examples is NOT reduced. CI uses more examples than local runs.
settings.register_profile("dev", deadline=None, max_examples=100)
settings.register_profile(
    "ci",
    deadline=None,
    max_examples=300,
    print_blob=True,
    suppress_health_check=[HealthCheck.too_slow],
)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "ci" if os.environ.get("CI") else "dev"))
