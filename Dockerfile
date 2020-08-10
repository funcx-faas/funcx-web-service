FROM python:3.7-alpine
RUN apk update && \
    apk add --no-cache gcc musl-dev linux-headers && \
    apk add postgresql-dev libffi-dev g++ make libressl-dev

WORKDIR /opt/funcx-web-service

COPY ./requirements.txt .
RUN pip install -r requirements.txt

COPY web-entrypoint.sh .

COPY ./funcx_web_service/ ./funcx_web_service/

ENV FLASK_APP ./application.py
ENV FLASK_DEBUG 1
ENV FLASK_RUN_HOST 0.0.0.0

CMD sh web-entrypoint.sh
