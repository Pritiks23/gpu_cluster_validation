"""
Report Generator: Creates HTML validation reports

Generates professional, human-readable HTML report from ValidationReport.
Includes:
- Overall status and health score
- Phase-by-phase results
- Failed check details and remediation guidance
- Topology diagrams (ASCII in HTML)
- Timeline of execution
"""

import html
from pathlib import Path
from typing import List

from gpu_cluster_validation.models import ValidationReport, StatusEnum, PhaseResult, CheckResult


class ReportGenerator:
    """Generate HTML validation reports"""

    def __init__(self, report: ValidationReport):
        self.report = report

    def generate_html(self, output_path: Path) -> None:
        """
        Generate HTML report file.
        
        Args:
            output_path: Where to save HTML file
        """
        html_content = self._build_html()
        with open(output_path, "w") as f:
            f.write(html_content)

    def _build_html(self) -> str:
        """Build complete HTML document"""
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GPU Cluster Validation Report</title>
    <style>
{self._get_css()}
    </style>
</head>
<body>
    <div class="container">
{self._build_header()}
{self._build_summary()}
{self._build_phases()}
{self._build_recommendations()}
{self._build_footer()}
    </div>
</body>
</html>"""

    def _get_css(self) -> str:
        """CSS styling for report"""
        return """        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: #f5f5f5;
            color: #333;
            line-height: 1.6;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }
        
        header {
            background: white;
            border-bottom: 4px solid #1a73e8;
            padding: 30px;
            margin-bottom: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        h1 {
            color: #1a73e8;
            margin-bottom: 10px;
            font-size: 2.5em;
        }
        
        .cluster-info {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }
        
        .info-card {
            background: #f9f9f9;
            padding: 15px;
            border-radius: 4px;
            border-left: 4px solid #ddd;
        }
        
        .info-card.pass {
            border-left-color: #34a853;
        }
        
        .info-card.fail {
            border-left-color: #ea4335;
        }
        
        .info-card h3 {
            color: #666;
            font-size: 0.9em;
            margin-bottom: 8px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        .info-card .value {
            font-size: 1.8em;
            font-weight: bold;
            color: #1a73e8;
        }
        
        .status-badge {
            display: inline-block;
            padding: 8px 16px;
            border-radius: 20px;
            font-weight: bold;
            font-size: 0.9em;
        }
        
        .status-badge.pass {
            background: #d4edda;
            color: #155724;
            border: 1px solid #c3e6cb;
        }
        
        .status-badge.fail {
            background: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
        }
        
        .status-badge.error {
            background: #f8d7da;
            color: #721c24;
        }
        
        .status-badge.warning {
            background: #fff3cd;
            color: #856404;
        }
        
        .phase-section {
            background: white;
            margin-bottom: 20px;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        .phase-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .phase-header.fail {
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        }
        
        .phase-title {
            font-size: 1.3em;
            font-weight: bold;
        }
        
        .phase-content {
            padding: 20px;
        }
        
        .check-list {
            list-style: none;
        }
        
        .check-item {
            padding: 15px;
            margin-bottom: 10px;
            background: #f9f9f9;
            border-left: 4px solid #ddd;
            border-radius: 4px;
        }
        
        .check-item.pass {
            border-left-color: #34a853;
            background: #f1f8f5;
        }
        
        .check-item.fail {
            border-left-color: #ea4335;
            background: #fef8f6;
        }
        
        .check-item.error {
            border-left-color: #fbbc04;
            background: #fef9f3;
        }
        
        .check-name {
            font-weight: bold;
            color: #1a73e8;
            margin-bottom: 5px;
        }
        
        .check-message {
            margin-bottom: 5px;
            color: #555;
        }
        
        .check-errors {
            margin-top: 8px;
            padding: 8px;
            background: #fff;
            border-left: 2px solid #ea4335;
            border-radius: 2px;
            color: #ea4335;
            font-family: monospace;
            font-size: 0.9em;
        }
        
        .check-remediation {
            margin-top: 10px;
            padding: 10px;
            background: #e8f4fd;
            border-left: 2px solid #1a73e8;
            border-radius: 2px;
            color: #1a73e8;
            font-size: 0.9em;
        }
        
        .recommendations {
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }
        
        .recommendations h2 {
            color: #1a73e8;
            margin-bottom: 20px;
        }
        
        .recommendations ul {
            list-style: none;
            padding-left: 0;
        }
        
        .recommendations li {
            padding: 10px 0;
            padding-left: 30px;
            position: relative;
        }
        
        .recommendations li:before {
            content: "→";
            position: absolute;
            left: 0;
            color: #1a73e8;
            font-weight: bold;
        }
        
        footer {
            text-align: center;
            padding: 20px;
            color: #999;
            font-size: 0.9em;
            margin-top: 40px;
        }
        
        .progress-bar {
            width: 100%;
            height: 8px;
            background: #e0e0e0;
            border-radius: 4px;
            overflow: hidden;
            margin: 10px 0;
        }
        
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #34a853, #4cb749);
            transition: width 0.3s ease;
        }
"""

    def _build_header(self) -> str:
        """Build HTML header with title and summary"""
        status_class = self.report.overall_status.value.lower()
        return f"""    <header>
        <h1>🖥️ GPU Cluster Validation Report</h1>
        <p><strong>Cluster:</strong> {html.escape(self.report.cluster_name)}</p>
        <p><strong>Timestamp:</strong> {self.report.timestamp.strftime('%Y-%m-%d %H:%M:%S')}</p>
        <div style="margin-top: 15px;">
            <span class="status-badge {status_class}">{self.report.overall_status.value}</span>
        </div>
    </header>"""

    def _build_summary(self) -> str:
        """Build summary cards"""
        health_pct = self.report.health_score
        health_color = "#34a853" if health_pct >= 90 else "#fbbc04" if health_pct >= 70 else "#ea4335"

        return f"""    <div class="cluster-info">
        <div class="info-card {'pass' if self.report.deployment_ready else 'fail'}">
            <h3>Overall Status</h3>
            <div class="value">{self.report.overall_status.value}</div>
        </div>
        <div class="info-card">
            <h3>Health Score</h3>
            <div class="value" style="color: {health_color};">{self.report.health_score:.1f}%</div>
            <div class="progress-bar">
                <div class="progress-fill" style="width: {self.report.health_score}%;"></div>
            </div>
        </div>
        <div class="info-card">
            <h3>Validation Duration</h3>
            <div class="value">{self.report.duration_seconds:.1f}s</div>
        </div>
        <div class="info-card">
            <h3>Test Results</h3>
            <div class="value">{self.report.total_pass}/{self.report.total_checks}</div>
            <p style="font-size: 0.9em; color: #666; margin-top: 5px;">checks passed</p>
        </div>
    </div>
    <div style="margin-top: 20px;">
        <p><strong>Deployment Ready:</strong> 
            <span style="color: {'#34a853' if self.report.deployment_ready else '#ea4335'}; font-weight: bold;">
                {'✓ YES' if self.report.deployment_ready else '✗ NO'}
            </span>
        </p>
    </div>"""

    def _build_phases(self) -> str:
        """Build phase results sections"""
        html_parts = []
        for phase in self.report.phases:
            html_parts.append(self._build_phase_section(phase))
        return "\n".join(html_parts)

    def _build_phase_section(self, phase: PhaseResult) -> str:
        """Build single phase section"""
        status_class = phase.status.value.lower()
        checks_html = "\n".join(
            self._build_check_item(check) for check in phase.checks
        )

        return f"""    <div class="phase-section">
        <div class="phase-header {status_class}">
            <div>
                <div class="phase-title">Phase {phase.phase}: {html.escape(phase.name)}</div>
                <p style="margin-top: 5px; opacity: 0.9;">{phase.pass_count}/{phase.check_count} checks passed</p>
            </div>
            <span class="status-badge {status_class}">{phase.status.value}</span>
        </div>
        <div class="phase-content">
            <ul class="check-list">
{checks_html}
            </ul>
        </div>
    </div>"""

    def _build_check_item(self, check: CheckResult) -> str:
        """Build single check result item"""
        status_class = check.status.value.lower()
        
        errors_html = ""
        if check.errors:
            errors_html = f"""
                <div class="check-errors">
                    {html.escape('; '.join(check.errors))}
                </div>"""
        
        remediation_html = ""
        if check.remediation:
            remediation_html = f"""
                <div class="check-remediation">
                    💡 <strong>Remediation:</strong> {html.escape(check.remediation)}
                </div>"""

        return f"""            <li class="check-item {status_class}">
                <div class="check-name">{html.escape(check.name)}</div>
                <div class="check-message">{html.escape(check.message)}</div>
                <div style="font-size: 0.85em; color: #999;">Duration: {check.duration_seconds:.3f}s</div>
{errors_html}{remediation_html}
            </li>"""

    def _build_recommendations(self) -> str:
        """Build recommendations section"""
        if not self.report.recommendations:
            return ""

        items_html = "\n".join(
            f"            <li>{html.escape(rec)}</li>"
            for rec in self.report.recommendations
        )

        return f"""    <div class="recommendations">
        <h2>📋 Recommendations</h2>
        <ul>
{items_html}
        </ul>
    </div>"""

    def _build_footer(self) -> str:
        """Build footer"""
        return f"""    <footer>
        <p>Generated by GPU Cluster Validation Suite v1.0.0</p>
        <p>For questions or issues, contact: infrastructure-team@company.com</p>
    </footer>"""
