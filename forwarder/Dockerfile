FROM funcx-web-base
WORKDIR /opt/forwarder
ENV FLASK_APP service.py
ENV FLASK_RUN_HOST 0.0.0.0
COPY ./requirements.txt requirements.txt
RUN pip install -r requirements.txt
ENV PYTHONPATH "${PYTHONPATH}:/opt/forwarder"
#CMD pip install -q -e ..  && python3 service.py -a forwarder -r mockredis
EXPOSE 55000-56000
COPY entrypoint.sh entrypoint.sh
CMD sh entrypoint.sh

