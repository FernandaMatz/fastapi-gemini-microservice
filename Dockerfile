# Imagem base oficial do Python slim
FROM python:3.11-slim

# Evita criação de arquivos .pyc e garante logs descompactados
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Instala dependências do sistema necessárias para compilação
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copia e instala as dependências do Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o código da aplicação
COPY . .

# Expõe a porta flexível para Cloud Run e Render
EXPOSE 8000

# Execução com suporte à variável PORT do ambiente de nuvem
CMD exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
