FROM python:3.7

ENV \
  # uwsgi settings
  UWSGI_VERSION=2.0.19.1 \
  # poetry settings
  POETRY_VERSION=1.1.7 \
  POETRY_VIRTUALENVS_CREATE=false \
  POETRY_NO_INTERACTION=1 \
  # expand path to include new tool locations
  PATH="$PATH:/uwsgi-venv/bin:/poetry-venv/bin"

# update to latest pip+setuptools versions
RUN python -m pip install -U pip setuptools

# Create a group and user
RUN addgroup uwsgi && useradd -g uwsgi uwsgi

# install uwsgi and poetry in isolated venvs so that they cannot pull in
# dependencies which could conflict with the application dependencies
RUN python -m venv /uwsgi-venv
RUN python -m venv /poetry-venv
RUN /uwsgi-venv/bin/pip install "uwsgi==${UWSGI_VERSION}"
RUN /poetry-venv/bin/pip install "poetry==${POETRY_VERSION}"

# install app dependencies
WORKDIR /opt/funcx-web-service
COPY ./poetry.lock pyproject.toml /opt/funcx-web-service/
RUN poetry install --no-ansi --no-dev

# copy app files into project dir
COPY uwsgi.ini .
COPY ./funcx_web_service/ ./funcx_web_service/
COPY ./migrations/ ./migrations/
COPY web-entrypoint.sh .

USER uwsgi
EXPOSE 5000

CMD sh web-entrypoint.sh
