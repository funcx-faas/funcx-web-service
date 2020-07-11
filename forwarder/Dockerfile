FROM funcx-web-base
WORKDIR /opt/forwarder
ENV FLASK_APP service.py
ENV FLASK_RUN_HOST 0.0.0.0
COPY ./requirements.txt requirements.txt
RUN pip install -r requirements.txt
ENV PYTHONPATH "${PYTHONPATH}:/opt/forwarder"
CMD ["python3", "/opt/forwarder/forwarder/service.py", \
     "-a", "forwarder", \
     "-r", "mockredis"]

