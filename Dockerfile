FROM python:3.7-alpine
WORKDIR /opt/funcx-web-service
ENV FLASK_APP application.py
ENV FLASK_RUN_HOST 0.0.0.0
RUN apk update && \
    apk add --no-cache gcc musl-dev linux-headers && \
    apk add postgresql-dev
RUN apk add libffi-dev g++ make

COPY ./requirements.txt ./requirements.txt
RUN pip install --upgrade pip
RUN pip install -r requirements.txt
CMD ["flask", "run"]
