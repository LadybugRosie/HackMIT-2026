FROM python:3.11-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1

COPY factcheck-service/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY factcheck-service/app /app/app
COPY factcheck-service/openfactcheck /app/openfactcheck

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
