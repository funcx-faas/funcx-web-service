FROM funcx-web-base
WORKDIR /opt/funcx-web-service
ENV FLASK_APP application.py
ENV FLASK_RUN_HOST 0.0.0.0

COPY ./requirements.txt ./requirements.txt
RUN pip install -r requirements.txt
CMD ["flask", "run"]
