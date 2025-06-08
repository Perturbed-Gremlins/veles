FROM python:3.12-slim-bookworm as base

# Setup env
ENV LANG C.UTF-8
ENV LC_ALL C.UTF-8
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONFAULTHANDLER 1
ENV PATH=/home/ftuser/.local/bin:$PATH
ENV FT_APP_ENV="docker"

# Prepare environment
RUN mkdir /freqtrade \
  && apt-get update \
  && apt-get -y install sudo libatlas3-base curl sqlite3 libgomp1 \
  && apt-get clean \
  && useradd -u 1000 -G sudo -U -m -s /bin/bash ftuser \
  && chown ftuser:ftuser /freqtrade \
  # Allow sudoers
  && echo "ftuser ALL=(ALL) NOPASSWD: /bin/chown" >> /etc/sudoers

WORKDIR /freqtrade

# Install dependencies
FROM base as python-deps
RUN  apt-get update \
  && apt-get -y install build-essential wget libssl-dev git libffi-dev libgfortran5 pkg-config cmake gcc \
  && apt-get clean

RUN  wget https://github.com/ta-lib/ta-lib/releases/download/v0.6.4/ta-lib_0.6.4_amd64.deb
RUN dpkg -i ta-lib_0.6.4_amd64.deb

# Install dependencies
COPY --chown=ftuser:ftuser uv.lock /freqtrade/
USER ftuser

# Download the latest installer
ADD --chown=ftuser:ftuser https://astral.sh/uv/install.sh /uv-installer.sh

# Run the installer then remove it
RUN sh /uv-installer.sh

# Ensure the installed binary is on the `PATH`
ENV PATH="/home/ftuser/.local/bin/:$PATH"

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1

# Copy from the cache instead of linking since it's a mounted volume
ENV UV_LINK_MODE=copy

# Install the project's dependencies using the lockfile and settings
RUN --mount=type=cache,target=/home/ftuser/.cache/uv,uid=1000,gid=1000 \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-dev

# Copy dependencies to runtime-image
FROM base as runtime-image
COPY --from=python-deps /usr/local/lib /usr/local/lib
COPY --from=python-deps /usr/lib /usr/local/lib
ENV LD_LIBRARY_PATH /usr/local/lib

COPY --from=python-deps --chown=ftuser:ftuser /home/ftuser/.local /home/ftuser/.local


USER ftuser
# Install and execute
COPY --chown=ftuser:ftuser . /freqtrade/

# Ensure the installed binary is on the `PATH`
ENV PATH="/home/ftuser/.local/bin/:$PATH"


RUN --mount=type=cache,target=/home/ftuser/.cache/uv,uid=1000,gid=1000 \
    uv sync --locked --no-dev --all-extras  \
  && mkdir /freqtrade/generated_data/ \
  && uv run freqtrade install-ui
