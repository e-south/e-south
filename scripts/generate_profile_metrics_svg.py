"""
--------------------------------------------------------------------------------
e-south
e-south/scripts/generate_profile_metrics_svg.py

Fetches GitHub profile activity metrics and renders a radar SVG plus JSON snapshot.

Module Author(s): Eric J. South
--------------------------------------------------------------------------------
"""

from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List


@dataclass(frozen=True)
class MetricPoint:
    label: str
    value: float
    cap: float
    unit: str = ""


@dataclass(frozen=True)
class NormalizedMetric:
    label: str
    value: float
    cap: float
    normalized: float
    unit: str = ""


def normalize_metric_points(points: Iterable[MetricPoint]) -> List[NormalizedMetric]:
    normalized_points: List[NormalizedMetric] = []
    for point in points:
        if point.cap <= 0:
            raise ValueError(f"Cap must be positive for metric '{point.label}'.")
        clamped_ratio = max(0.0, min(point.value / point.cap, 1.0))
        normalized_points.append(
            NormalizedMetric(
                label=point.label,
                value=point.value,
                cap=point.cap,
                normalized=round(clamped_ratio * 100.0, 1),
                unit=point.unit,
            )
        )
    return normalized_points


def format_metric_value(metric: NormalizedMetric) -> str:
    rounded = round(metric.value)
    if metric.unit == "%" or metric.label.lower().endswith("rate"):
        return f"{rounded}%"
    return str(rounded)


def polygon_points_from_metrics(
    metrics: Iterable[NormalizedMetric],
    center_x: float,
    center_y: float,
    radius: float,
) -> str:
    points = list(metrics)
    total = len(points)
    coordinates: List[str] = []
    for idx, metric in enumerate(points):
        angle = -math.pi / 2 + (2 * math.pi * idx / total)
        scaled_radius = radius * (metric.normalized / 100.0)
        x = center_x + math.cos(angle) * scaled_radius
        y = center_y + math.sin(angle) * scaled_radius
        coordinates.append(f"{x:.1f},{y:.1f}")
    return " ".join(coordinates)


def build_radar_svg(metrics: List[NormalizedMetric]) -> str:
    if len(metrics) < 3:
        raise ValueError("Radar chart requires at least three metrics.")

    width = 920
    height = 600
    chart_center_x = 285
    chart_center_y = 300
    radius = 180

    axis_lines: List[str] = []
    label_text: List[str] = []

    for idx, metric in enumerate(metrics):
        angle = -math.pi / 2 + (2 * math.pi * idx / len(metrics))
        line_x = chart_center_x + math.cos(angle) * radius
        line_y = chart_center_y + math.sin(angle) * radius
        label_x = chart_center_x + math.cos(angle) * (radius + 38)
        label_y = chart_center_y + math.sin(angle) * (radius + 38)

        axis_lines.append(
            (
                f'<line x1="{chart_center_x}" y1="{chart_center_y}" '
                f'x2="{line_x:.1f}" y2="{line_y:.1f}" stroke="#d5d9e0" stroke-width="1" />'
            )
        )
        label_text.append(
            (
                f'<text x="{label_x:.1f}" y="{label_y:.1f}" '
                'font-size="14" fill="#3a404a" text-anchor="middle">'
                f"{metric.label}</text>"
            )
        )

    grid_polygons: List[str] = []
    for level in (20, 40, 60, 80, 100):
        level_metrics = [
            NormalizedMetric(
                label=m.label,
                value=m.value,
                cap=m.cap,
                normalized=float(level),
                unit=m.unit,
            )
            for m in metrics
        ]
        points = polygon_points_from_metrics(level_metrics, chart_center_x, chart_center_y, radius)
        grid_polygons.append(
            f'<polygon points="{points}" fill="none" stroke="#e4e8f0" stroke-width="1" />'
        )

    data_points = polygon_points_from_metrics(metrics, chart_center_x, chart_center_y, radius)

    metric_rows: List[str] = []
    legend_start_x = 560
    legend_start_y = 172
    for idx, metric in enumerate(metrics):
        y = legend_start_y + idx * 38
        metric_rows.append(
            (
                f'<text x="{legend_start_x}" y="{y}" font-size="16" fill="#141a24">'
                f"{metric.label}: {format_metric_value(metric)}"
                "</text>"
            )
        )

    svg = f"""
<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="GitHub Activity Radar">
  <rect x="0" y="0" width="{width}" height="{height}" fill="#f8fafc" />
  <text x="40" y="58" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="30" font-weight="700" fill="#0f172a">GitHub Activity Radar (Last 365 Days)</text>
  <text x="40" y="90" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="16" fill="#475569">Normalized against profile-scale targets to show overall engineering activity balance.</text>

  {''.join(grid_polygons)}
  {''.join(axis_lines)}

  <polygon points="{data_points}" fill="#2563eb33" stroke="#1d4ed8" stroke-width="3" />
  {''.join(label_text)}

  <rect x="530" y="130" width="340" height="240" rx="14" fill="#ffffff" stroke="#d7dce5" />
  <text x="560" y="152" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="18" font-weight="700" fill="#0f172a">Current Values</text>
  {''.join(metric_rows)}

  <text x="40" y="560" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-size="13" fill="#64748b">Automated refresh via GitHub Actions.</text>
</svg>
""".strip()

    return svg


def github_graphql(token: str, query: str, variables: Dict[str, Any]) -> Dict[str, Any]:
    command = ["gh", "api", "graphql", "-f", f"query={query}"]
    for key, value in variables.items():
        command.extend(["-F", f"{key}={value}"])

    environment = os.environ.copy()
    environment["GH_TOKEN"] = token

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "GitHub GraphQL request failed: "
            f"{result.stderr.strip() or result.stdout.strip()}"
        )

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("GitHub GraphQL response was not valid JSON.") from exc

    if payload.get("errors"):
        raise RuntimeError(f"GitHub GraphQL errors: {payload['errors']}")

    data = payload.get("data")
    if not data:
        raise RuntimeError("GitHub GraphQL response missing data payload.")
    return data


def fetch_profile_metrics(username: str, token: str) -> Dict[str, float]:
    now = datetime.now(timezone.utc)
    one_year_ago = now - timedelta(days=365)
    ninety_days_ago = now - timedelta(days=90)

    prs_query = f"author:{username} is:pr created:{one_year_ago.date()}..{now.date()}"
    merged_query = (
        f"author:{username} is:pr is:merged created:{one_year_ago.date()}..{now.date()}"
    )

    query = """
query ProfileMetrics(
  $login: String!,
  $from: DateTime!,
  $to: DateTime!,
  $prsQuery: String!,
  $mergedQuery: String!
) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      totalCommitContributions
      contributionCalendar {
        weeks {
          contributionDays {
            contributionCount
          }
        }
      }
    }
    repositories(
      first: 100,
      ownerAffiliations: OWNER,
      privacy: PUBLIC,
      isFork: false
    ) {
      nodes {
        pushedAt
      }
    }
  }
  prs: search(type: ISSUE, query: $prsQuery) {
    issueCount
  }
  merged: search(type: ISSUE, query: $mergedQuery) {
    issueCount
  }
}
"""

    response = github_graphql(
        token=token,
        query=query,
        variables={
            "login": username,
            "from": one_year_ago.isoformat(),
            "to": now.isoformat(),
            "prsQuery": prs_query,
            "mergedQuery": merged_query,
        },
    )

    user = response["user"]
    if user is None:
        raise RuntimeError(f"GitHub user '{username}' was not found.")

    commit_count = float(user["contributionsCollection"]["totalCommitContributions"])
    pr_count = float(response["prs"]["issueCount"])
    merged_count = float(response["merged"]["issueCount"])

    contribution_days = user["contributionsCollection"]["contributionCalendar"]["weeks"]
    active_days = 0
    for week in contribution_days:
        for day in week["contributionDays"]:
            if day["contributionCount"] > 0:
                active_days += 1

    active_repos = 0
    for repo in user["repositories"]["nodes"]:
        pushed_at = datetime.fromisoformat(repo["pushedAt"].replace("Z", "+00:00"))
        if pushed_at >= ninety_days_ago:
            active_repos += 1

    merge_rate = (merged_count / pr_count * 100.0) if pr_count else 0.0

    return {
        "commits": commit_count,
        "prs": pr_count,
        "merge_rate": merge_rate,
        "active_repos": float(active_repos),
        "active_days": float(active_days),
    }


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate GitHub profile activity radar chart assets."
    )
    parser.add_argument("--user", required=True, help="GitHub username to query.")
    parser.add_argument(
        "--output-svg",
        default="assets/activity-radar.svg",
        help="Output SVG path.",
    )
    parser.add_argument(
        "--output-json",
        default="assets/activity-metrics.json",
        help="Output JSON summary path.",
    )
    parser.add_argument(
        "--token-env",
        default="GITHUB_TOKEN",
        help="Environment variable name containing a GitHub token.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    token = os.getenv(args.token_env)
    if not token:
        raise SystemExit(
            f"Missing token in environment variable '{args.token_env}'."
        )

    raw_metrics = fetch_profile_metrics(args.user, token)
    metric_points = [
        MetricPoint(label="Commits", value=raw_metrics["commits"], cap=1000),
        MetricPoint(label="PRs", value=raw_metrics["prs"], cap=100),
        MetricPoint(
            label="Merge Rate",
            value=raw_metrics["merge_rate"],
            cap=100,
            unit="%",
        ),
        MetricPoint(label="Active Repos", value=raw_metrics["active_repos"], cap=20),
        MetricPoint(label="Active Days", value=raw_metrics["active_days"], cap=365),
    ]

    normalized = normalize_metric_points(metric_points)
    svg = build_radar_svg(normalized)

    output_svg = Path(args.output_svg)
    output_json = Path(args.output_json)

    write_text(output_svg, svg)
    write_json(
        output_json,
        {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "username": args.user,
            "metrics": [asdict(point) for point in normalized],
        },
    )

    print(f"Wrote {output_svg}")
    print(f"Wrote {output_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
