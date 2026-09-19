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
    return LLMStatus(
        provider=p.name,
        configured=p.is_configured(),
        default_model=p.default_model,
        wtt_model=config.WTT_MODEL or p.default_model,
        models=[ModelInfo(**m) for m in p.available_models()],
    )
