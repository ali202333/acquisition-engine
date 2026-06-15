"""The Multi-Channel Outreach Builder."""
import asyncio
import json
import logging
import os
from typing import Optional

import openai

from src.config import Config
from src.models import BusinessProfile, DigitalStrategy, OutreachPackage
from src.utils.pdf_generator import ProposalPDFGenerator

logger = logging.getLogger(__name__)

PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "prompts")


def _load_prompt(filename: str) -> str:
    path = os.path.join(PROMPTS_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


class OutreachAgent:
    """Builds outreach packages (email, WhatsApp, PDF) for a business."""

    def __init__(self, pdf_generator: ProposalPDFGenerator, config: Config) -> None:
        self.pdf_generator = pdf_generator
        self.config = config
        self.client = openai.AsyncOpenAI(api_key=config.openai_api_key)

    async def _chat(self, messages: list[dict[str, str]], expect_json: bool = False) -> str:
        try:
            response = await self.client.chat.completions.create(
                model=self.config.llm_model,
                messages=messages,  # type: ignore[arg-type]
                temperature=self.config.temperature,
                response_format={"type": "json_object"} if expect_json else {"type": "text"},
            )
            return response.choices[0].message.content or ""
        except Exception as exc:
            logger.error("OpenAI API error in outreach: %s", exc)
            raise

    async def build_package(
        self, business: BusinessProfile, strategy: DigitalStrategy
    ) -> OutreachPackage:
        """Generate email, WhatsApp, and PDF for a single business."""
        name = business.business.name
        location = business.business.address
        top_pain = business.pain_points[0].description if business.pain_points else "limited online presence"

        # --- Email ---
        email_subject = f"A quick idea for {name}"
        email_body = (
            f"Hello {name} team,\n\n"
            f"I hope you're doing well. I was researching businesses in {location} and noticed your spot. "
            f"It looks like you might be facing: {top_pain}.\n\n"
            f"I help local F&B businesses in Cyberjaya build fast, modern websites and get found on Google.\n\n"
            f"Would you be open to a 15-minute chat this week? No pressure — just coffee.\n\n"
            f"Best,\n[Your Name]"
        )
        try:
            email_messages = [
                {"role": "system", "content": _load_prompt("email_prompt.txt")},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "business_name": name,
                            "location": location,
                            "pain_points": [pp.model_dump(mode="json") for pp in business.pain_points],
                            "personalization_paragraph": f"Hello {name} team, I hope you're doing well. I was researching businesses in {location} and noticed your spot.",
                        }
                    ),
                },
            ]
            email_raw = await self._chat(email_messages, expect_json=True)
            email_data = json.loads(email_raw)
            email_subject = email_data.get("subject", email_subject)
            email_body = email_data.get("body", email_body)
        except Exception as exc:
            logger.warning("Email generation failed for %s: %s", name, exc)

        # --- WhatsApp ---
        whatsapp_message = (
            f"Hi {name} team, I was checking out spots in {location} and yours looks great — "
            f"but I noticed {top_pain}. I help local F&B get online fast. Worth a quick chat? - [Your Name]"
        )
        try:
            wa_messages = [
                {"role": "system", "content": _load_prompt("whatsapp_prompt.txt")},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "business_name": name,
                            "top_pain_point": top_pain,
                            "location": location,
                        }
                    ),
                },
            ]
            wa_raw = await self._chat(wa_messages, expect_json=False)
            if wa_raw:
                whatsapp_message = wa_raw.strip()
        except Exception as exc:
            logger.warning("WhatsApp generation failed for %s: %s", name, exc)

        # --- PDF ---
        pdf_path = ""
        try:
            pdf_path = self.pdf_generator.generate(business, strategy)
        except Exception as exc:
            logger.error("PDF generation failed for %s: %s", name, exc)

        # --- Save sidecar files ---
        safe_name = "".join(c if c.isalnum() or c in " -_" else "_" for c in name).strip()
        folder = os.path.join(self.config.output_dir, safe_name)
        os.makedirs(folder, exist_ok=True)

        email_md_path = os.path.join(folder, "email.md")
        with open(email_md_path, "w", encoding="utf-8") as f:
            f.write(f"# Email for {name}\n\n**Subject:** {email_subject}\n\n{email_body}\n")

        wa_md_path = os.path.join(folder, "whatsapp.md")
        with open(wa_md_path, "w", encoding="utf-8") as f:
            f.write(f"# WhatsApp for {name}\n\n{whatsapp_message}\n")

        # Build proposal markdown
        proposal_md_lines = [
            f"# Proposal for {name}",
            "",
            "## Strategy",
            json.dumps(strategy.model_dump(mode="json"), indent=2),
            "",
            "## Pain Points",
        ]
        for pp in business.pain_points:
            proposal_md_lines.append(f"- {pp.category}: {pp.description} (severity {pp.severity})")
        proposal_md = "\n".join(proposal_md_lines)

        return OutreachPackage(
            business_name=name,
            proposal_md=proposal_md,
            email_subject=email_subject,
            email_body=email_body,
            whatsapp_message=whatsapp_message,
            pdf_path=pdf_path,
        )

    async def build_batch(
        self, packages: list[tuple[BusinessProfile, DigitalStrategy]]
    ) -> list[OutreachPackage]:
        """Build outreach packages in parallel."""
        tasks = [asyncio.create_task(self.build_package(b, s)) for b, s in packages]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        valid: list[OutreachPackage] = []
        for (biz, _), result in zip(packages, results):
            if isinstance(result, OutreachPackage):
                valid.append(result)
            elif isinstance(result, Exception):
                logger.error("Outreach failed for %s: %s", biz.business.name, result)
            else:
                logger.warning("Unexpected outreach result for %s", biz.business.name)
        return valid
