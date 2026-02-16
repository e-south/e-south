"""
--------------------------------------------------------------------------------
e-south
e-south/tests/test_generate_profile_metrics_svg.py

Validates profile metric normalization and radar SVG rendering output.

Module Author(s): Eric J. South
--------------------------------------------------------------------------------
"""

import unittest

from scripts.generate_profile_metrics_svg import (
    MetricPoint,
    build_radar_svg,
    normalize_metric_points,
)


class GenerateProfileMetricsSvgTests(unittest.TestCase):
    def test_normalize_metric_points_applies_caps(self) -> None:
        points = [
            MetricPoint(label="Commits", value=813, cap=1000),
            MetricPoint(label="PRs", value=35, cap=100),
            MetricPoint(label="Merge Rate", value=97, cap=100),
            MetricPoint(label="Active Repos", value=7, cap=20),
            MetricPoint(label="Active Days", value=134, cap=365),
        ]

        normalized = normalize_metric_points(points)

        self.assertEqual(len(normalized), 5)
        self.assertAlmostEqual(normalized[0].normalized, 81.3, places=1)
        self.assertAlmostEqual(normalized[1].normalized, 35.0, places=1)
        self.assertAlmostEqual(normalized[2].normalized, 97.0, places=1)
        self.assertAlmostEqual(normalized[3].normalized, 35.0, places=1)
        self.assertAlmostEqual(normalized[4].normalized, 36.7, places=1)

    def test_build_radar_svg_includes_labels_and_title(self) -> None:
        points = [
            MetricPoint(label="Commits", value=813, cap=1000),
            MetricPoint(label="PRs", value=35, cap=100),
            MetricPoint(label="Merge Rate", value=97, cap=100),
            MetricPoint(label="Active Repos", value=7, cap=20),
            MetricPoint(label="Active Days", value=134, cap=365),
        ]

        normalized = normalize_metric_points(points)
        svg = build_radar_svg(normalized)

        self.assertIn("<svg", svg)
        self.assertIn("GitHub Activity Radar (Last 365 Days)", svg)
        self.assertIn("Commits: 813", svg)
        self.assertIn("PRs: 35", svg)
        self.assertIn("Merge Rate: 97%", svg)
        self.assertIn("<polygon", svg)


if __name__ == "__main__":
    unittest.main()
