# 1. Usa uma imagem leve do Python 3.10 (Linux)
FROM python:3.10-slim

# 2. Define a pasta de trabalho dentro do container
WORKDIR /app

# 3. Copia o arquivo de dependências para dentro
COPY requirements.txt .

# 4. Instala as bibliotecas
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copia TODO o resto do seu projeto
COPY . .

# 6. Informa a porta
EXPOSE 8000

# 7. Comando para iniciar
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
