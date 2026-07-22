"""
CLI: Command-line interface for validation suite

Usage:
  gpu-cluster-validate --cluster config/cluster.yaml --output reports/
  gpu-cluster-validate --help

The CLI:
1. Parses command-line arguments
2. Loads YAML cluster config
3. Runs validation pipeline
4. Generates HTML report
5. Returns appropriate exit code for CI/CD
"""

import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path

import click

from gpu_cluster_validation.engine import run_validation
from gpu_cluster_validation.reports.generator import ReportGenerator


# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@click.command()
@click.option(
    "--cluster",
    type=click.Path(exists=True),
    required=True,
    help="Path to cluster.yaml configuration file",
)
@click.option(
    "--output",
    type=click.Path(),
    default="reports/",
    help="Output directory for reports (default: reports/)",
)
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"]),
    default="INFO",
    help="Logging level",
)
@click.option(
    "--no-html",
    is_flag=True,
    help="Skip HTML report generation",
)
@click.option(
    "--json-only",
    is_flag=True,
    help="Generate JSON report only (no HTML)",
)
def cli(cluster: str, output: str, log_level: str, no_html: bool, json_only: bool):
    """
    Validate GPU cluster hardware and fabric.
    
    This tool automates the acceptance testing workflow when new GPU hardware
    (e.g., NVIDIA HGX racks) arrives at a data center. It runs 5 validation phases:
    
    1. Hardware Inventory - Verify GPU count, SKU, drivers, CUDA, NVLink
    2. Fabric Topology - Discover and verify InfiniBand fabric structure
    3. Fabric Health - Detect CRC errors, signal issues, link flaps
    4. Performance - Measure RDMA bandwidth/latency against SLAs
    5. GPU Communication - Validate NCCL, AllReduce, GPUDirect RDMA
    
    Example:
      gpu-cluster-validate --cluster config/cluster.yaml --output reports/
    """
    # Update logging level
    logging.getLogger().setLevel(getattr(logging, log_level))
    logger.info(f"Validation suite starting (log level: {log_level})")

    # Validate inputs
    config_path = Path(cluster)
    if not config_path.exists():
        logger.error(f"Config file not found: {cluster}")
        sys.exit(2)

    output_path = Path(output)
    output_path.mkdir(parents=True, exist_ok=True)

    # Run validation pipeline
    try:
        report = asyncio.run(run_validation(str(config_path)))
    except Exception as e:
        logger.exception(f"Validation pipeline failed: {e}")
        sys.exit(2)

    # Generate reports
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_base = output_path / f"validation_report_{timestamp}"

    # JSON report (always generated)
    json_path = report_base.with_suffix(".json")
    with open(json_path, "w") as f:
        f.write(report.model_dump_json(indent=2))
    logger.info(f"JSON report: {json_path}")

    # HTML report (unless --json-only)
    if not json_only and not no_html:
        try:
            html_path = report_base.with_suffix(".html")
            generator = ReportGenerator(report)
            generator.generate_html(html_path)
            logger.info(f"HTML report: {html_path}")
        except Exception as e:
            logger.warning(f"Failed to generate HTML report: {e}")

    # Summary to stdout
    click.echo("\n" + "=" * 80)
    click.echo(f"GPU Cluster Validation - {report.cluster_name}")
    click.echo("=" * 80)
    click.echo(f"Status: {report.overall_status.value}")
    click.echo(f"Health Score: {report.health_score:.1f}%")
    click.echo(f"Duration: {report.duration_seconds:.1f}s")
    click.echo(f"Checks: {report.total_pass}/{report.total_checks} passed")
    click.echo(f"Deployment Ready: {'YES' if report.deployment_ready else 'NO'}")

    if report.recommendations:
        click.echo("\nRecommendations:")
        for rec in report.recommendations:
            click.echo(f"  • {rec}")

    if report.failed_phases:
        click.echo("\nFailed Phases:")
        for phase in report.failed_phases:
            click.echo(f"  • Phase {phase.phase}: {phase.name}")
            for check in phase.failed_checks:
                click.echo(f"    - {check.name}: {check.message}")

    click.echo("=" * 80)

    # Exit with appropriate code
    exit_code = 0 if report.overall_status.value == "PASS" else (
        1 if report.overall_status.value == "FAIL" else 2
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    cli()
