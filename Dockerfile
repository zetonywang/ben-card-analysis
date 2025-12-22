# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    git-lfs \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Create a stub libdds.so to prevent import errors
# This is just an empty shared library that does nothing
RUN echo 'void DDS_Version() {}' > /tmp/stub.c && \
    gcc -shared -fPIC -o /usr/local/lib/libdds.so /tmp/stub.c && \
    rm /tmp/stub.c && \
    ldconfig

# Initialize Git LFS
RUN git lfs install

# Clone Ben repository with LFS files
RUN git clone https://github.com/lorserker/ben.git && \
    cd ben && \
    git lfs pull

# Install Python dependencies from Ben
RUN pip install --no-cache-dir \
    tensorflow==2.15.0 \
    numpy \
    scipy \
    scikit-learn \
    fastapi \
    uvicorn \
    pydantic

# Copy API file
COPY card_analysis_api.py /app/ben/card_analysis_api.py

# Set working directory to ben
WORKDIR /app/ben

# Expose port
EXPOSE 8000

# Set Python path
ENV PYTHONPATH=/app/ben/src:$PYTHONPATH

# Run the API
CMD sh -c "uvicorn card_analysis_api:app --host 0.0.0.0 --port ${PORT:-8000}"
