from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel

try:
    from nemoguardrails import LLMRails, RailsConfig
except Exception:  # pragma: no cover - environment-specific import failures
    LLMRails = None
    RailsConfig = None

load_dotenv()

app = FastAPI()


class InputCheck(BaseModel):
    text: str


class OutputCheck(BaseModel):
    text: str


class CheckResult(BaseModel):
    passed: bool
    reason: Optional[str] = None
    safe_text: Optional[str] = None


def _build_rails() -> Optional[LLMRails]:
    if LLMRails is None or RailsConfig is None:
        return None
    config_path = Path(__file__).parent / "config"
    config = RailsConfig.from_path(str(config_path))
    return LLMRails(config)


rails = _build_rails()


def _extract_content(rails_response: object) -> str:
    if isinstance(rails_response, dict):
        return str(rails_response.get("content", "")).strip()
    return str(rails_response).strip()


def _is_refusal(text: str) -> bool:
    lowered = text.lower()
    refusal_markers = [
        "i'm sorry",
        "i cannot",
        "i can not",
        "i can't",
        "cannot help",
        "cannot comply",
        "can't comply",
        "not able to help",
    ]
    return any(marker in lowered for marker in refusal_markers)


async def _run_guardrail(text: str) -> CheckResult:
    if rails is None:
        return CheckResult(
            passed=False,
            reason="NeMo Guardrails is unavailable in this Python runtime. Use Python 3.10-3.12.",
        )
    response = await rails.generate_async(messages=[{"role": "user", "content": text}])
    content = _extract_content(response)
    if not content or _is_refusal(content):
        return CheckResult(passed=False, reason="Blocked by NeMo guardrails")
    return CheckResult(passed=True, safe_text=content)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/check/input")
async def check_input(body: InputCheck):
    text = body.text.strip()
    if len(text) < 20:
        return {"pass": False, "reason": "Text too short to be an injury report"}

    # Fallback keeps the endpoint usable if NeMo cannot load.
    if rails is None:
        keywords = ["injury", "pain", "player", "tear", "fracture", "strain", "foot", "knee", "ankle"]
        lower = text.lower()
        if not any(word in lower for word in keywords):
            return {"pass": False, "reason": "Does not look like a sports injury report"}
        return {"pass": True, "reason": None}

    result = await _run_guardrail(text)
    return {"pass": result.passed, "reason": result.reason}


@app.post("/check/output")
async def check_output(body: OutputCheck):
    text = body.text.strip()
    result = await _run_guardrail(text)
    if not result.passed:
        return {"pass": False, "reason": result.reason, "safe_text": None}
    return {"pass": True, "reason": None, "safe_text": result.safe_text}