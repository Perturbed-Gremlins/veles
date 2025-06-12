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

# Copy dependencies to runtime-image
FROM base as runtime-image

ENV LD_LIBRARY_PATH /usr/local/lib

RUN  apt-get update \
  && apt-get -y install git build-essential wget libtool libssl-dev git libffi-dev libgfortran5 pkg-config cmake gcc autoconf \
  && apt-get clean

RUN wget https://github.com/ta-lib/ta-lib/releases/download/v0.6.4/ta-lib-0.6.4-src.tar.gz  && tar -xzf ta-lib-0.6.4-src.tar.gz && cd ta-lib-0.6.4 &&  \
    ./configure -- && make && sudo make install




#
#
# Install dependencies
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


# Install and execute
COPY --chown=ftuser:ftuser . /freqtrade/

# Ensure the installed binary is on the `PATH`
ENV PATH="/home/ftuser/.local/bin/:$PATH"


RUN uv sync --no-dev --all-extras  \
  && mkdir /freqtrade/generated_data/ \
  && uv run freqtrade install-ui
