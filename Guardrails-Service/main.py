from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI
from nemoguardrails import LLMRails, RailsConfig
from nemoguardrails.rails.llm.options import RailStatus, RailType
from pydantic import BaseModel

load_dotenv()

app = FastAPI()

config = RailsConfig.from_path(str(Path(__file__).parent / "config"))
rails = LLMRails(config)


class InputCheck(BaseModel):
    text: str


class OutputCheck(BaseModel):
    text: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/check/input")
async def check_input(body: InputCheck):
    text = body.text.strip()
    if len(text) < 20:
        return {"pass": False, "reason": "Text too short to be an injury report"}

    result = await rails.check_async(
        messages=[{"role": "user", "content": text}],
        rail_types=[RailType.INPUT],
    )

    if result.status == RailStatus.BLOCKED:
        reason = f"Blocked by NeMo guardrails ({result.rail})" if result.rail else "Blocked by NeMo guardrails"
        return {"pass": False, "reason": reason}

    return {"pass": True, "reason": None}


@app.post("/check/output")
async def check_output(body: OutputCheck):
    text = body.text.strip()
    if not text:
        return {"pass": False, "reason": "Empty output text", "safe_text": None}

    result = await rails.check_async(
        messages=[{"role": "assistant", "content": text}],
        rail_types=[RailType.OUTPUT],
    )

    if result.status == RailStatus.BLOCKED:
        reason = f"Blocked by NeMo guardrails ({result.rail})" if result.rail else "Blocked by NeMo guardrails"
        return {"pass": False, "reason": reason, "safe_text": None}

    return {"pass": True, "reason": None, "safe_text": result.content or text}
