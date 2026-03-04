# Copyright (C) 2025 co-pace GmbH (subsidiary of Continental AG).
# Licensed under the BSD-3-Clause License.
# @author: Marius Kästingschäfer and Théo Gieruc
# ==============================================================================

FROM carlasim/carla:0.9.16

USER root

RUN apt-get update \
    && apt install -y apt-utils git wget psmisc tmux vulkan-utils xdg-user-dirs unzip zip

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/
ENV UV_PYTHON_INSTALL_DIR="/opt/python"

# Install Python 3.12 and create venv at /opt/venv (not under /seed4d which gets volume-mounted)
COPY pyproject.toml uv.lock /tmp/seed4d-build/
RUN cd /tmp/seed4d-build \
    && uv venv --python 3.12 /opt/venv \
    && uv pip install --python /opt/venv/bin/python3 -r pyproject.toml \
    && uv pip install --python /opt/venv/bin/python3 /workspace/PythonAPI/carla/dist/carla-0.9.16-cp312-cp312-manylinux_2_31_x86_64.whl \
    && rm -rf /tmp/seed4d-build

ENV PATH="/opt/venv/bin:$PATH"
ENV VIRTUAL_ENV="/opt/venv"

USER carla

CMD ["jupyter", "lab", "--ip=0.0.0.0", "--port=3333","--allow-root","--no-browser"]

EXPOSE 5894

# BUILD: docker build -t seed4d .
# RUN: docker run --privileged --name seed4d --gpus all --net=host --ipc=host --shm-size=20g -v /tmp/.X11-unix:/tmp/.X11-unix:rw seed4d sleep infinity
