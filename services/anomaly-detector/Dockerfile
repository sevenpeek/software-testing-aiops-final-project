FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY src /app/src
COPY services/anomaly-detector /app/services/anomaly-detector
COPY data /app/data

EXPOSE 8088

CMD ["python", "services/anomaly-detector/app.py", "--host", "0.0.0.0", "--port", "8088"]

