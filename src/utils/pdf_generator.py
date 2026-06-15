"""Markdown-to-PDF proposal generator using Jinja2 + WeasyPrint."""
import logging
import os
from datetime import datetime
from typing import Any

import markdown
from jinja2 import Template
from weasyprint import HTML, CSS

from src.models import BusinessProfile, DigitalStrategy

logger = logging.getLogger(__name__)

# Inline CSS tuned for WeasyPrint compatibility
DEFAULT_CSS = """
@page {
    size: A4;
    margin: 2cm;
}
body {
    font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
    font-size: 11pt;
    line-height: 1.6;
    color: #1a0f0a;
}
.header {
    text-align: center;
    border-bottom: 3px solid #c9a87c;
    padding-bottom: 12px;
    margin-bottom: 24px;
}
.header h1 {
    font-size: 24pt;
    color: #1a0f0a;
    margin: 0;
}
.header p {
    color: #c9a87c;
    font-size: 10pt;
    margin: 4px 0 0 0;
}
.logo-placeholder {
    width: 80px;
    height: 80px;
    border: 2px dashed #c9a87c;
    margin: 0 auto 12px auto;
    line-height: 80px;
    text-align: center;
    color: #c9a87c;
    font-size: 9pt;
}
.meta {
    margin-bottom: 18px;
}
.meta table {
    width: 100%;
    border-collapse: collapse;
}
.meta td {
    padding: 4px 0;
    font-size: 10pt;
}
.meta td.label {
    color: #c9a87c;
    font-weight: bold;
    width: 30%;
}
h2 {
    font-size: 14pt;
    color: #1a0f0a;
    border-bottom: 1px solid #c9a87c;
    padding-bottom: 4px;
    margin-top: 24px;
}
h3 {
    font-size: 12pt;
    color: #1a0f0a;
    margin-top: 16px;
}
ul, ol {
    margin-top: 6px;
    padding-left: 20px;
}
li {
    margin-bottom: 4px;
}
.price-box {
    background: #fdf8f3;
    border: 1px solid #c9a87c;
    padding: 12px;
    margin-top: 12px;
    text-align: center;
}
.price-box strong {
    font-size: 16pt;
    color: #1a0f0a;
}
.footer {
    margin-top: 36px;
    border-top: 1px solid #c9a87c;
    padding-top: 8px;
    font-size: 9pt;
    color: #888;
    text-align: center;
}
"""

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Proposal for {{ business_name }}</title>
    <style>{{ css }}</style>
</head>
<body>
    <div class="header">
        <div class="logo-placeholder">LOGO</div>
        <h1>Digital Presence Proposal</h1>
        <p>{{ business_name }} &mdash; {{ location }}</p>
    </div>

    <div class="meta">
        <table>
            <tr><td class="label">Date</td><td>{{ date }}</td></tr>
            <tr><td class="label">Prepared by</td><td>Your Web Development Partner</td></tr>
            <tr><td class="label">Contact</td><td>hello@yourstudio.my</td></tr>
        </table>
    </div>

    <div class="content">
        {{ content_html|safe }}
    </div>

    <div class="price-box">
        <strong>Estimated Investment: RM {{ pricing_estimate_myr }}</strong><br>
        <span>50% deposit to begin &mdash; 50% on delivery</span>
    </div>

    <div class="footer">
        Built for local Cyberjaya F&B businesses. This proposal is confidential and intended solely for {{ business_name }}.
    </div>
</body>
</html>
"""


class ProposalPDFGenerator:
    """Generate professional PDF proposals from markdown strategy content."""

    def __init__(self, output_dir: str) -> None:
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def generate(self, business: BusinessProfile, strategy: DigitalStrategy) -> str:
        """Render markdown proposal to PDF. Returns file path."""
        business_name = business.business.name
        safe_name = "".join(c if c.isalnum() or c in " -_" else "_" for c in business_name).strip()
        folder = os.path.join(self.output_dir, safe_name)
        os.makedirs(folder, exist_ok=True)

        pdf_path = os.path.join(folder, "proposal.pdf")

        # Build markdown content from strategy
        md_lines: list[str] = [
            f"# Digital Presence Proposal for {business_name}",
            "",
            "## Executive Summary",
            strategy.estimated_impact or "We have identified key opportunities to grow your digital presence.",
            "",
            "## Current State Analysis",
            f"- **Website:** {'Yes' if business.business.has_website else 'No'} (SEO Score: {business.seo.overall_score}/100)",
            f"- **Mobile Friendly:** {'Yes' if business.seo.mobile_friendly else 'No'}",
            f"- **Meta Description:** {'Present' if business.seo.meta_description_present else 'Missing'}",
            f"- **SSL (HTTPS):** {'Yes' if business.seo.has_ssl else 'No'}",
            f"- **Online Menu:** {'Yes' if business.seo.has_menu_online else 'No'}",
            f"- **Social Platforms Found:** {', '.join(business.social.platforms_found) or 'None'}",
            "",
            "## Recommended Solutions",
        ]
        for rec in strategy.recommendations:
            md_lines.append(f"- {rec}")
        md_lines += [
            "",
            "## Proposed Services",
        ]
        for svc in strategy.proposed_services:
            md_lines.append(f"- {svc}")
        md_lines += [
            "",
            "## Timeline",
            strategy.timeline or "Week 1-2: Discovery & Design | Week 3-4: Development | Week 5: Launch & SEO",
            "",
            "## Investment",
            f"**Total Estimate:** RM {strategy.pricing_estimate_myr:,.2f}",
            "",
            "## Next Steps",
            "1. Reply to schedule a free 15-minute consultation.",
            "2. We'll visit your location (if in Cyberjaya) to understand your vibe.",
            "3. Sign a simple agreement and begin.",
        ]

        proposal_md = "\n".join(md_lines)
        content_html = markdown.markdown(proposal_md, extensions=["tables", "fenced_code"])

        template = Template(HTML_TEMPLATE)
        html_out = template.render(
            css=DEFAULT_CSS,
            business_name=business_name,
            location=business.business.address,
            date=datetime.now().strftime("%d %B %Y"),
            content_html=content_html,
            pricing_estimate_myr=f"{strategy.pricing_estimate_myr:,.2f}",
        )

        # Also write markdown for reference
        md_path = os.path.join(folder, "proposal.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(proposal_md)

        HTML(string=html_out).write_pdf(pdf_path)
        logger.info("PDF generated: %s", pdf_path)
        return pdf_path
