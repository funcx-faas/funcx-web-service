FROM python:3.7

# Create a group and user
RUN addgroup uwsgi && useradd -g uwsgi uwsgi

WORKDIR /opt/funcx-web-service

COPY ./requirements.txt .

RUN pip install -r requirements.txt
RUN pip install --disable-pip-version-check uwsgi

COPY uwsgi.ini .
COPY ./funcx_web_service/ ./funcx_web_service/
COPY ./migrations/ ./migrations/
COPY web-entrypoint.sh .

USER uwsgi
EXPOSE 5000

CMD sh web-entrypoint.sh
