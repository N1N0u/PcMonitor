FROM nvidia/cuda:12.3.0-devel-ubuntu22.04

WORKDIR /app

ENV CUDA_HOME=/usr/local/cuda
ENV PATH=$CUDA_HOME/bin:$PATH
ENV LD_LIBRARY_PATH=$CUDA_HOME/lib64:$LD_LIBRARY_PATH

RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    stress-ng \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip3 install --no-cache-dir -r requirements.txt

# CUDA-enabled PyTorch
RUN pip3 install torch torchvision torchaudio \
    --index-url https://download.pytorch.org/whl/cu121

COPY app.py .

EXPOSE 5000

CMD ["python3", "app.py"]