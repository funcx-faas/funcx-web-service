FROM python:3.7-alpine
RUN apk update && \
    apk add --no-cache gcc musl-dev linux-headers && \
    apk add postgresql-dev libffi-dev g++ make libressl-dev

WORKDIR /opt/funcx-web-service

COPY ./requirements.txt .
RUN pip install -r requirements.txt
RUN pip install gunicorn

COPY ./funcx_web_service/ ./funcx_web_service/
COPY web-entrypoint.sh .

CMD sh web-entrypoint.sh
