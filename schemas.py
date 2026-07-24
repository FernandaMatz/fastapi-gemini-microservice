from datetime import date, datetime
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, ConfigDict, Field, field_validator


class VendaBase(BaseModel):
    empresa_id: str = Field(..., min_length=1, max_length=50, json_schema_extra={"example": "empresa_abc"})
    data: date = Field(..., json_schema_extra={"example": "2026-07-24"})
    faturamento: float = Field(..., ge=0.0, description="O faturamento do dia não pode ser negativo.")
    qtd_pedidos: int = Field(..., ge=0, description="A quantidade de pedidos não pode ser negativa.")
    produtos: Optional[Union[List[Any], Dict[str, Any]]] = Field(
        default=None,
        description="Lista ou objeto contendo detalhes dos produtos vendidos."
    )

    @field_validator("faturamento")
    @classmethod
    def validar_faturamento(cls, v: float) -> float:
        if v < 0:
            raise ValueError("Faturamento não pode ser um valor negativo.")
        return round(v, 2)


class VendaCreate(VendaBase):
    pass


class VendaResponse(VendaBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LogAuditoriaResponse(BaseModel):
    id: int
    empresa_id: str
    data_referencia: date
    faturamento_dia: float
    media_ultimos_7_dias: float
    percentual_queda: float
    severidade: str
    mensagem: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class IngestResponse(BaseModel):
    status: str
    vendas_processadas: int
    alertas_criados: List[LogAuditoriaResponse]


class InsightRequest(BaseModel):
    empresa_id: str = Field(..., min_length=1, json_schema_extra={"example": "empresa_abc"})
    data_referencia: date = Field(..., json_schema_extra={"example": "2026-07-24"})


class GeminiInsightOutput(BaseModel):
    """Esquema Pydantic para Saídas Estruturadas (Structured Outputs) da API Gemini."""
    resumo: str = Field(
        ...,
        description="Resumo executivo conciso sobre o desempenho de vendas da empresa na data de referência."
    )
    alertas_principais: List[str] = Field(
        ...,
        description="Array contendo os alertas principais, anomalias e pontos de atenção detectados."
    )
    acao_recomendada: str = Field(
        ...,
        description="Plano de ação claro e prático recomendado para a liderança da empresa."
    )


class InsightResponse(BaseModel):
    id: int
    empresa_id: str
    data_referencia: date
    resumo: str
    alertas_principais: List[str]
    acao_recomendada: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
