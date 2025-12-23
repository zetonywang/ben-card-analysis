FROM python:3.11-slim

WORKDIR /app

# Install git only
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

# Clone Ben
RUN git clone https://github.com/lorserker/ben.git

# Install Python dependencies
RUN pip install --no-cache-dir \
    tensorflow==2.17.0 \
    keras==3.6.0 \
    numpy \
    fastapi \
    uvicorn \
    pydantic \
    tqdm \
    colorama \
    configparser

# Copy API to Ben src directory
COPY card_analysis_api.py /app/ben/src/card_analysis_api.py

# Set working directory to Ben src
WORKDIR /app/ben/src

# Set Python path
ENV PYTHONPATH=/app/ben/src

EXPOSE 8080

CMD ["python", "card_analysis_api.py"]
