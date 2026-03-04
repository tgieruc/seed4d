# Copyright (C) 2025 co-pace GmbH (subsidiary of Continental AG).
# Licensed under the BSD-3-Clause License.
# @author: Marius Kästingschäfer and Théo Gieruc
# ==============================================================================

FROM carlasim/carla:0.9.16

USER root

RUN apt-get update \
    && apt install -y software-properties-common \
    && apt update && apt install -y python3 python3-pip apt-utils git wget psmisc tmux vulkan-utils xdg-user-dirs unzip zip

RUN pip install --upgrade pip
# RUN pip install carla==0.9.16
RUN pip install --ignore-installed blinker \
    && pip install jupyterlab matplotlib opencv-python scikit-image pandas tqdm pypng open3d tabulate

USER carla

CMD ["jupyter", "lab", "--ip=0.0.0.0", "--port=3333","--allow-root","--no-browser"]

EXPOSE 5894

# BUILD: docker build -t seed4d .
# RUN: docker run --privileged --name seed4d --gpus all --net=host --ipc=host --shm-size=20g -v /tmp/.X11-unix:/tmp/.X11-unix:rw seed4d sleep infinity