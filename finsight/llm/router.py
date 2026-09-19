from fastapi import APIRouter, Depends
from pydantic import BaseModel

from finsight import config
from finsight.deps import get_current_user
from finsight.llm import get_provider
from finsight.models import User

router = APIRouter()


class ModelInfo(BaseModel):
    id: str
    label: str


class LLMStatus(BaseModel):
    provider: str
    configured: bool
    default_model: str
    wtt_model: str
    models: list[ModelInfo]


@router.get("/models", response_model=LLMStatus)
def list_models(current_user: User = Depends(get_current_user)):
    """Active LLM provider, its default model, and the models the UI may offer."""
    p = get_provider()
    models = [ModelInfo(**m) for m in p.available_models()]
    ids = {m.id for m in models}
    # Configured default may not be pulled locally (Ollama) — offer one that exists.
    default = p.default_model if p.default_model in ids or not models else models[0].id
    return LLMStatus(
        provider=p.name,
        configured=p.is_configured(),
        default_model=default,
        wtt_model=config.WTT_MODEL or default,
        models=models,
    )
