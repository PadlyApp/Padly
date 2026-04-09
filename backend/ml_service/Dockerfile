FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY ml_service/requirements.txt ml_service/requirements.txt
RUN pip install --no-cache-dir -r ml_service/requirements.txt

# The ML service imports from the app package (shared code in same monorepo),
# so we copy both app/ and ml_service/ into the image.
COPY app/ app/
COPY ml_service/ ml_service/

EXPOSE 8001

CMD ["uvicorn", "ml_service.main:app", "--host", "0.0.0.0", "--port", "8001"]
