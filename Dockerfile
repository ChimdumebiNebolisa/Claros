# Claros backend - Cloud Run
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements-server.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY main.py config.py schemas.py storage.py assignment_service.py gemini_service.py parser.py parser_layout.py manifest.py session_service.py observability.py rate_limit.py agent.py exporter.py ocr_adapter.py document_model.py document_pipeline.py semantic_classifier.py worksheet_contract.py review_service.py sample_catalog.py ./
COPY evaluation ./evaluation
COPY demo ./demo
COPY frontend ./frontend
COPY test_assignment.pdf ./
COPY ["claros favicon.png", "./"]
COPY ["claros logo.png", "./"]

RUN useradd --create-home --uid 10001 claros && chown -R claros:claros /app
USER claros

# Cloud Run listens on PORT (default 8080)
ENV PORT=8080
EXPOSE 8080

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
