import logging
from typing import List, Optional
from google import genai
from google.genai import types
from google.genai.errors import APIError

from config import settings
from models import LogAuditoria, Venda
from schemas import GeminiInsightOutput

logger = logging.getLogger(__name__)


async def gerar_insight_executivo(
    empresa_id: str,
    data_referencia: str,
    venda: Optional[Venda],
    anomalias: List[LogAuditoria]
) -> GeminiInsightOutput:
    """
    Integração com a API do Gemini via SDK oficial 'google-genai'.
    Utiliza Structured Outputs para garantir o schema exato (resumo, alertas_principais, acao_recomendada).
    """
    detalhes_venda = (
        f"Faturamento do dia: R$ {venda.faturamento:.2f} | Quantidade de pedidos: {venda.qtd_pedidos} | "
        f"Produtos: {venda.produtos}"
        if venda else "Nenhum registro de vendas localizado para esta data."
    )

    alertas_str = (
        "\n".join([f"- [{a.severidade}] {a.mensagem}" for a in anomalias])
        if anomalias else "Nenhum alerta crítico ou anomalia registrada no dia."
    )

    prompt = f"""
Você é um consultor sênior de inteligência financeira e de negócios (BI).
Analise os dados financeiros da empresa e elabore um relatório executivo sucinto e acionável.

[CONTEXTO DO DIA]
- Empresa ID: {empresa_id}
- Data de Referência: {data_referencia}
- Dados de Vendas: {detalhes_venda}

[AUDITORIA E ANOMALIAS]
{alertas_str}

Instruções para a resposta:
1. Resumo: Breve síntese do desempenho financeiro do dia.
2. Alertas Principais: Array contendo pontos críticos ou anomalias identificadas.
3. Ação Recomendada: Recomendação prática e direta para a tomada de decisão da gestão.
"""

    if not settings.GEMINI_API_KEY or settings.GEMINI_API_KEY.strip() == "" or settings.GEMINI_API_KEY == "your_gemini_api_key_here":
        logger.warning("GEMINI_API_KEY não informada ou inválida no ambiente. Utilizando gerador local de contingência.")
        alertas_list = [a.mensagem for a in anomalias] if anomalias else ["Operação dentro da normalidade esperada."]
        return GeminiInsightOutput(
            resumo=f"Síntese operacional para a empresa '{empresa_id}' em {data_referencia}. {detalhes_venda}",
            alertas_principais=alertas_list,
            acao_recomendada="Insira uma chave válida na variável GEMINI_API_KEY para habilitar a geração por Inteligência Artificial."
        )

    try:
        logger.info("Enviando solicitação para Gemini API com modelo %s...", settings.GEMINI_MODEL)
        client = genai.Client(api_key=settings.GEMINI_API_KEY)

        response = client.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=GeminiInsightOutput,
                temperature=0.2,
            )
        )

        if response.parsed:
            logger.info("Insight gerado com sucesso via Structured Output (response.parsed).")
            return response.parsed

        if response.text:
            logger.info("Insight carregado a partir do conteúdo JSON textual da resposta.")
            return GeminiInsightOutput.model_validate_json(response.text)

        raise ValueError("A resposta retornada pela API Gemini veio sem conteúdo válido.")

    except APIError as api_err:
        logger.error("Erro da API Gemini [Status Code: %s]: %s", getattr(api_err, 'code', 'N/A'), str(api_err), exc_info=True)
        raise RuntimeError(f"Falha na API Gemini: {api_err.message if hasattr(api_err, 'message') else str(api_err)}") from api_err
    except Exception as exc:
        logger.error("Erro genérico ao invocar o serviço de IA: %s", str(exc), exc_info=True)
        raise
