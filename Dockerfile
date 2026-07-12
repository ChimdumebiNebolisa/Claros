# Claros backend - Cloud Run
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements-server.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY main.py config.py schemas.py storage.py assignment_service.py gemini_service.py parser.py parser_layout.py manifest.py session_service.py agent.py exporter.py ./
COPY frontend ./frontend
COPY test_assignment.pdf ./

# Cloud Run listens on PORT (default 8080)
ENV PORT=8080
EXPOSE 8080

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
