import csv
import io
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import List, Optional, Union

from fastapi import Body, Depends, FastAPI, File, HTTPException, Request, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import os
import sys

# Garante que o diretório atual do projeto está no PYTHONPATH do ambiente do Render/Linux
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import settings
from database import get_db, init_db
from models import InsightDiario, LogAuditoria, Venda
from schemas import (
    GeminiInsightOutput,
    IngestResponse,
    InsightRequest,
    InsightResponse,
    LogAuditoriaResponse,
    VendaCreate,
)

try:
    from services.ai import gerar_insight_executivo
    from services.audit import auditar_venda_diaria
except ModuleNotFoundError:
    from ai import gerar_insight_executivo
    from audit import auditar_venda_diaria

# Configuração de logging estruturado
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Inicializando o microserviço e sincronizando esquema do banco de dados...")
    await init_db()
    yield
    logger.info("Encerrando o microserviço.")


app = FastAPI(
    title="Microserviço de Ingestão e Insights (Gemini API)",
    description="API de alta performance para ingestão de vendas, auditoria de anomalias e inteligência empresarial via Gemini AI.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Exceção não tratada no endpoint %s: %s", request.url.path, str(exc), exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Erro interno no servidor.", "error": str(exc)},
    )


@app.get("/health", tags=["Saúde"])
async def health_check():
    return {"status": "ok", "ambiente": settings.ENVIRONMENT, "modelo_gemini": settings.GEMINI_MODEL}


from pydantic import ValidationError


@app.post(
    "/api/v1/ingest",
    response_model=IngestResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Ingestão"],
)
async def ingest_vendas(
    request: Request,
    file: Optional[UploadFile] = File(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Endpoint para ingestão de vendas diárias.
    Suporta payload em JSON (objeto individual ou lista) ou upload de arquivo CSV.
    Valida os dados com Pydantic v2, executa regra de auditoria e salva no PostgreSQL.
    """
    vendas_para_processar: List[VendaCreate] = []
    content_type = request.headers.get("content-type", "")

    # 1. Processamento se enviado via arquivo CSV
    if "multipart/form-data" in content_type and file is not None:
        if not file.filename.lower().endswith(".csv"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Formato inválido. O arquivo enviado deve possuir extensão .csv",
            )
        try:
            content = await file.read()
            decoded_content = content.decode("utf-8")
            csv_reader = csv.DictReader(io.StringIO(decoded_content))

            for idx, row in enumerate(csv_reader, start=1):
                try:
                    data_val = datetime.strptime(row["data"].strip(), "%Y-%m-%d").date()
                    faturamento_val = float(row["faturamento"])
                    qtd_pedidos_val = int(row["qtd_pedidos"])
                    produtos_raw = row.get("produtos", None)
                    produtos_val = (
                        json.loads(produtos_raw)
                        if produtos_raw and produtos_raw.strip().startswith(("[", "{"))
                        else produtos_raw
                    )

                    venda_obj = VendaCreate(
                        empresa_id=row["empresa_id"].strip(),
                        data=data_val,
                        faturamento=faturamento_val,
                        qtd_pedidos=qtd_pedidos_val,
                        produtos=produtos_val,
                    )
                    vendas_para_processar.append(venda_obj)
                except (KeyError, ValueError, ValidationError) as val_err:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail=f"Falha de validação na linha {idx} do CSV: {str(val_err)}",
                    )
        except HTTPException:
            raise
        except Exception as exc:
            logger.error("Erro na leitura do CSV: %s", str(exc), exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Não foi possível ler e parsear o arquivo CSV enviado.",
            )

    # 2. Processamento se enviado via JSON Body
    else:
        try:
            body = await request.json()
            if isinstance(body, list):
                vendas_para_processar = [VendaCreate.model_validate(item) for item in body]
            elif isinstance(body, dict):
                vendas_para_processar = [VendaCreate.model_validate(body)]
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="O payload JSON deve ser um objeto ou um array de objetos.",
                )
        except ValidationError as val_err:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=val_err.errors(),
            )
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Payload JSON inválido: {str(exc)}",
            )

    alertas_gerados: List[LogAuditoria] = []
    vendas_salvas = 0

    try:
        for item in vendas_para_processar:
            # Criação do modelo ORM
            nova_venda = Venda(
                empresa_id=item.empresa_id,
                data=item.data,
                faturamento=item.faturamento,
                qtd_pedidos=item.qtd_pedidos,
                produtos=item.produtos,
            )
            db.add(nova_venda)

            # Execução da regra de auditoria automatizada
            alerta = await auditar_venda_diaria(
                db=db,
                empresa_id=item.empresa_id,
                data_referencia=item.data,
                faturamento_dia=item.faturamento,
            )
            if alerta:
                alertas_gerados.append(alerta)

            vendas_salvas += 1

        await db.commit()
        logger.info(
            "Processamento concluído com sucesso: %d vendas ingeridas, %d alertas gerados.",
            vendas_salvas,
            len(alertas_gerados),
        )

        return IngestResponse(
            status="sucesso",
            vendas_processadas=vendas_salvas,
            alertas_criados=[LogAuditoriaResponse.model_validate(a) for a in alertas_gerados],
        )

    except Exception as exc:
        await db.rollback()
        logger.error("Erro na persistência dos dados: %s", str(exc), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Falha ao persistir vendas no banco de dados: {str(exc)}",
        )


@app.post(
    "/api/v1/generate-insight",
    response_model=InsightResponse,
    status_code=status.HTTP_200_OK,
    tags=["Insights IA"],
)
async def generate_insight(
    request_data: InsightRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Gera um insight diário para a empresa na data_referencia.
    Recupera vendas e logs de auditoria, realiza chamada com Structured Output na Gemini API
    e salva o resultado na tabela insights_diarios.
    """
    empresa_id = request_data.empresa_id
    data_ref = request_data.data_referencia

    try:
        # Busca vendas do dia
        stmt_venda = select(Venda).where(Venda.empresa_id == empresa_id, Venda.data == data_ref)
        res_venda = await db.execute(stmt_venda)
        venda = res_venda.scalars().first()

        # Busca anomalias de auditoria gravadas
        stmt_auditoria = select(LogAuditoria).where(
            LogAuditoria.empresa_id == empresa_id,
            LogAuditoria.data_referencia == data_ref,
        )
        res_auditoria = await db.execute(stmt_auditoria)
        anomalias = list(res_auditoria.scalars().all())

        # Geração do insight via SDK da Gemini
        ai_output: GeminiInsightOutput = await gerar_insight_executivo(
            empresa_id=empresa_id,
            data_referencia=data_ref.isoformat(),
            venda=venda,
            anomalias=anomalias,
        )

        # Registro no banco de dados
        novo_insight = InsightDiario(
            empresa_id=empresa_id,
            data_referencia=data_ref,
            resumo=ai_output.resumo,
            alertas_principais=ai_output.alertas_principais,
            acao_recomendada=ai_output.acao_recomendada,
        )
        db.add(novo_insight)
        await db.commit()
        await db.refresh(novo_insight)

        logger.info("Insight gerado e salvo para %s em %s.", empresa_id, data_ref)
        return InsightResponse.model_validate(novo_insight)

    except Exception as exc:
        await db.rollback()
        logger.error("Erro ao gerar insight para %s em %s: %s", empresa_id, data_ref, str(exc), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Falha ao processar insight executivo: {str(exc)}",
        )
