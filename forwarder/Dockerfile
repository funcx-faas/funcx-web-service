FROM python:3.7-alpine
WORKDIR /opt/forwarder
ENV FLASK_APP service.py
ENV FLASK_RUN_HOST 0.0.0.0
RUN apk update && \
    apk add --no-cache gcc musl-dev linux-headers
RUN apk add libffi-dev g++ make libressl-dev
COPY ./requirements.txt requirements.txt
RUN pip install zmq
RUN pip install -r requirements.txt
CMD ["python3", "forwarder/service.py", \
     "-a", "forwarder", \
     "-r", "mockredis"]

