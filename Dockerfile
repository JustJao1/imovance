FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HOST=0.0.0.0 PORT=8000 IMOVEL_DB=/data/imovance.sqlite3 APP_ORIGIN=http://localhost:8000
COPY app.py commercial.py operations.py schema.sql ./
COPY static static
RUN mkdir /data && chown 65534:65534 /data
USER 65534:65534
EXPOSE 8000
CMD ["python","app.py"]
