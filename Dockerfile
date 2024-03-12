FROM linuxserver/nginx:1.24.0

ENV DOCKER_MODS=linuxserver/mods:universal-cron|linuxserver/mods:swag-auto-reload|linuxserver/mods:universal-stdout-logs

# Prevents Python from writing pyc files.
ENV PYTHONDONTWRITEBYTECODE=1

# Keeps Python from buffering stdout and stderr to avoid situations where
# the application crashes without emitting any logs due to buffering.
ENV PYTHONUNBUFFERED=1

ENV LOGS_TO_STDOUT="/config/log/refrapt/refrapt.log"

# Install python
RUN apk add --update --no-cache python3 wget \
    && ln -sf python3 /usr/bin/python

# Create a venv
RUN python3 -m venv /opt/venv --upgrade-deps
ENV PATH="/opt/venv/bin:$PATH"

# Install application
COPY [ "setup.py", "README.md", "./" ]
WORKDIR /refrapt
COPY refrapt .
WORKDIR /
RUN python3 -m pip install .

# Install the bootstrap file
COPY bootstrap.sh /custom-cont-init.d/

# Install the nginx conf
COPY default.conf /app/nginx/site-confs/
