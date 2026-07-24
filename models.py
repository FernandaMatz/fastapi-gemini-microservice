from datetime import date, datetime
from typing import Any, List, Optional
from sqlalchemy import String, Float, Integer, Date, DateTime, Text, JSON, func
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class Venda(Base):
    __tablename__ = "vendas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    empresa_id: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    data: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    faturamento: Mapped[float] = mapped_column(Float, nullable=False)
    qtd_pedidos: Mapped[int] = mapped_column(Integer, nullable=False)
    produtos: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LogAuditoria(Base):
    __tablename__ = "logs_auditoria"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    empresa_id: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    data_referencia: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    faturamento_dia: Mapped[float] = mapped_column(Float, nullable=False)
    media_ultimos_7_dias: Mapped[float] = mapped_column(Float, nullable=False)
    percentual_queda: Mapped[float] = mapped_column(Float, nullable=False)
    severidade: Mapped[str] = mapped_column(String(20), nullable=False, default="CRITICAL")
    mensagem: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class InsightDiario(Base):
    __tablename__ = "insights_diarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    empresa_id: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    data_referencia: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    resumo: Mapped[str] = mapped_column(Text, nullable=False)
    alertas_principais: Mapped[List[str]] = mapped_column(JSON, nullable=False)
    acao_recomendada: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
