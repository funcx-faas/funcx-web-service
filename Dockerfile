FROM funcx-web-base
WORKDIR /opt/funcx-web-service
ENV FLASK_APP ./application.py
ENV FLASK_DEBUG 1
ENV FLASK_RUN_HOST 0.0.0.0

COPY ./requirements.txt ./requirements.txt
RUN pip install -r requirements.txt

# use iptables to have flask receive via 80 and 8080
# this allows us to easily receive traffic intended for funcx.org
RUN apk add iptables
EXPOSE 80/tcp
CMD sh web-entrypoint.sh
