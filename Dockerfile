FROM python:3.6

# Environment setting
COPY . /app
RUN pip install -r /app/requirements.txt

RUN pip install gunicorn eventlet

# System packages installation
#RUN echo "deb http://nginx.org/packages/mainline/debian/ jessie nginx" >> /etc/apt/sources.list
#RUN wget https://nginx.org/keys/nginx_signing.key -O - | apt-key add -
#RUN apt-get update && apt-get install -y nginx 
#&& rm -rf /var/lib/apt/lists/*

# Nginx configuration
#RUN echo "daemon off;" >> /etc/nginx/nginx.conf
#RUN rm /etc/nginx/conf.d/default.conf
#COPY nginx.conf /etc/nginx/conf.d/nginx.conf

# Gunicorn default configuration
#COPY gunicorn.config.py /app/gunicorn.config.py

WORKDIR /app

EXPOSE 80 443 8000

ENV APP_SETTINGS='config.DevelopmentConfig'
ENV secret_key='supersecretkey'

ENTRYPOINT ["python", "/usr/local/bin/gunicorn", "application:application", "-b 0.0.0.0:80", "-k eventlet", "-w 1", "--threads", "8"]


