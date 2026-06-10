FROM python:3.12-slim

WORKDIR /app

# Install system deps for OpenCV and ReportLab
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# YOLO model must be mounted or copied separately — not committed to source
# docker run -v /path/to/yolov8s-worldv2.pt:/app/yolov8s-worldv2.pt ...

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
