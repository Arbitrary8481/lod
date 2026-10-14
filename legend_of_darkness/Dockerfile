FROM python:3.12-alpine

RUN apk add --no-cache tzdata

WORKDIR /app
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY app/ /app/

ENV DATA_DIR=/data
CMD ["python", "-u", "server.py"]
