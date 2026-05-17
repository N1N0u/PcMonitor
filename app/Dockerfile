FROM nvidia/cuda:12.3.0-devel-ubuntu22.04

WORKDIR /app

ENV CUDA_HOME=/usr/local/cuda
ENV PATH=$CUDA_HOME/bin:$PATH
ENV LD_LIBRARY_PATH=$CUDA_HOME/lib64:$LD_LIBRARY_PATH

# Install Python + tools + stress-ng
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    git \
    build-essential \
    stress-ng \
    && rm -rf /var/lib/apt/lists/*

# Install gpu-burn
RUN git clone https://github.com/wilicc/gpu-burn.git && \
    cd gpu-burn && \
    make CUDA_HOME=/usr/local/cuda

COPY requirements.txt .

RUN pip3 install --no-cache-dir -r requirements.txt

COPY app.py .

EXPOSE 5000

CMD ["python3", "app.py"]
