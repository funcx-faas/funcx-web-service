FROM python:3.7-alpine
WORKDIR /opt/serializer
ENV FLASK_APP service.py
ENV FLASK_RUN_HOST 0.0.0.0
RUN apk update && \
    apk add --no-cache gcc musl-dev linux-headers

COPY ./requirements.txt requirements.txt
RUN pip install --upgrade pip
RUN pip install -r requirements.txt
CMD ["python3", "serializer/service.py"]
