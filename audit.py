import logging
from datetime import date, timedelta
from typing import Optional
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import LogAuditoria, Venda

logger = logging.getLogger(__name__)


async def auditar_venda_diaria(
    db: AsyncSession,
    empresa_id: str,
    data_referencia: date,
    faturamento_dia: float
) -> Optional[LogAuditoria]:
    """
    Executa a regra de auditoria:
    Verifica se o faturamento do dia é pelo menos 30% menor do que a média dos últimos 7 dias
    gravados no banco para a empresa especificada. Se sim, gera um LogAuditoria com severidade 'CRITICAL'.
    """
    try:
        data_inicio = data_referencia - timedelta(days=7)

        stmt = (
            select(func.avg(Venda.faturamento), func.count(Venda.id))
            .where(
                Venda.empresa_id == empresa_id,
                Venda.data >= data_inicio,
                Venda.data < data_referencia
            )
        )
        result = await db.execute(stmt)
        row = result.first()

        media_faturamento_raw, count_dias = row if row else (None, 0)

        if media_faturamento_raw is None or count_dias == 0:
            logger.info(
                "Auditoria para empresa '%s' na data %s: sem histórico nos 7 dias anteriores.",
                empresa_id, data_referencia
            )
            return None

        media_faturamento = float(media_faturamento_raw)
        limite_critico = media_faturamento * 0.70

        if faturamento_dia <= limite_critico:
            percentual_queda = round(((media_faturamento - faturamento_dia) / media_faturamento) * 100, 2)
            mensagem = (
                f"Alerta Crítico: O faturamento do dia (R$ {faturamento_dia:.2f}) foi {percentual_queda}% "
                f"menor que a média dos últimos {count_dias} dias registrados (R$ {media_faturamento:.2f})."
            )

            log_auditoria = LogAuditoria(
                empresa_id=empresa_id,
                data_referencia=data_referencia,
                faturamento_dia=faturamento_dia,
                media_ultimos_7_dias=round(media_faturamento, 2),
                percentual_queda=percentual_queda,
                severidade="CRITICAL",
                mensagem=mensagem
            )

            db.add(log_auditoria)
            await db.flush()
            logger.warning("Auditoria disparada para %s em %s: %s", empresa_id, data_referencia, mensagem)
            return log_auditoria

        logger.info(
            "Auditoria concluída para %s em %s: Faturamento dentro da margem esperada.",
            empresa_id, data_referencia
        )
        return None

    except Exception as exc:
        logger.error("Erro inesperado durante auditoria de vendas: %s", str(exc), exc_info=True)
        raise
