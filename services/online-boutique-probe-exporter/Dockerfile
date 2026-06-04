FROM python:3.11-slim

WORKDIR /app
COPY services/online-boutique-probe-exporter/app.py /app/app.py

ENV PORT=9105
EXPOSE 9105

CMD ["python", "/app/app.py"]

