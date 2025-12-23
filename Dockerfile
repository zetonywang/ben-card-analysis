FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Clone Ben repository
RUN git clone https://github.com/lorserker/ben.git

# Install Python dependencies
RUN pip install --no-cache-dir \
    tensorflow==2.17.0 \
    keras==3.6.0 \
    numpy \
    flask \
    fastapi \
    uvicorn \
    python-multipart \
    grpcio \
    configparser \
    websockets \
    pydantic \
    tqdm \
    --break-system-packages

# Create stub DDS library with all 32 functions
RUN echo 'void SetMaxThreads(int x) {}' > /tmp/dds_stub.c && \
    echo 'void SetThreading(int x) {}' >> /tmp/dds_stub.c && \
    echo 'void SetResources(int x, int y) {}' >> /tmp/dds_stub.c && \
    echo 'int SolveBoard(void* a, void* b, int c) { return 0; }' >> /tmp/dds_stub.c && \
    echo 'int SolveBoardPBN(void* a, void* b, int c) { return 0; }' >> /tmp/dds_stub.c && \
    echo 'int CalcDDtable(void* a, void* b) { return 0; }' >> /tmp/dds_stub.c && \
    echo 'int CalcDDtablePBN(void* a, void* b) { return 0; }' >> /tmp/dds_stub.c && \
    echo 'int CalcAllTables(void* a, int b, int* c, void* d, int e) { return 0; }' >> /tmp/dds_stub.c && \
    echo 'int CalcAllTablesPBN(void* a, int b, int* c, void* d, int e) { return 0; }' >> /tmp/dds_stub.c && \
    echo 'int SolveAllBoards(void* a, void* b) { return 0; }' >> /tmp/dds_stub.c && \
    echo 'int SolveAllBoardsBin(void* a, void* b) { return 0; }' >> /tmp/dds_stub.c && \
    echo 'int SolveAllChunks(void* a, void* b, int c) { return 0; }' >> /tmp/dds_stub.c && \
    echo 'int SolveAllChunksBin(void* a, void* b, int c) { return 0; }' >> /tmp/dds_stub.c && \
    echo 'int SolveAllChunksPBN(void* a, void* b, int c) { return 0; }' >> /tmp/dds_stub.c && \
    echo 'int Par(void* a, void* b, int c) { return 0; }' >> /tmp/dds_stub.c && \
    echo 'int CalcPar(void* a, int b, void* c, void* d) { return 0; }' >> /tmp/dds_stub.c && \
    echo 'int CalcParPBN(void* a, void* b, int c, void* d, void* e) { return 0; }' >> /tmp/dds_stub.c && \
    echo 'int SidesPar(void* a, void* b, int c) { return 0; }' >> /tmp/dds_stub.c && \
    echo 'int SidesParBin(void* a, void* b, int c) { return 0; }' >> /tmp/dds_stub.c && \
    echo 'int DealerPar(void* a, void* b, int c, int d) { return 0; }' >> /tmp/dds_stub.c && \
    echo 'int DealerParBin(void* a, void* b, int c, int d) { return 0; }' >> /tmp/dds_stub.c && \
    echo 'int ConvertToDealerTextFormat(void* a, void* b) { return 0; }' >> /tmp/dds_stub.c && \
    echo 'int AnalysePlayBin(void* a, void* b, void* c, int d) { return 0; }' >> /tmp/dds_stub.c && \
    echo 'int AnalysePlayPBN(void* a, void* b, void* c, int d) { return 0; }' >> /tmp/dds_stub.c && \
    echo 'int AnalyseAllPlaysBin(void* a, void* b, void* c, int d) { return 0; }' >> /tmp/dds_stub.c && \
    echo 'int AnalyseAllPlaysPBN(void* a, void* b, void* c, int d) { return 0; }' >> /tmp/dds_stub.c && \
    echo 'int TracePlayBin(void* a, void* b, void* c, int d) { return 0; }' >> /tmp/dds_stub.c && \
    echo 'int TracePlayPBN(void* a, void* b, void* c, int d) { return 0; }' >> /tmp/dds_stub.c && \
    echo 'int TraceAllPlaysBin(void* a, void* b, void* c, int d) { return 0; }' >> /tmp/dds_stub.c && \
    echo 'int TraceAllPlaysPBN(void* a, void* b, void* c, int d) { return 0; }' >> /tmp/dds_stub.c && \
    echo 'void ErrorMessage(int code, char* line) {}' >> /tmp/dds_stub.c && \
    echo 'void GetDDSInfo(void* info) {}' >> /tmp/dds_stub.c && \
    gcc -shared -fPIC -o /usr/lib/libdds.so /tmp/dds_stub.c && \
    rm /tmp/dds_stub.c

# Copy libraries to expected locations
RUN cp /usr/lib/libdds.so /app/ben/bin/ 2>/dev/null || mkdir -p /app/ben/bin && cp /usr/lib/libdds.so /app/ben/bin/ && \
    cp /usr/lib/libdds.so /app/ben/src/ddsolver/ 2>/dev/null || mkdir -p /app/ben/src/ddsolver && cp /usr/lib/libdds.so /app/ben/src/ddsolver/ && \
    cp /usr/lib/libdds.so /app/ben/ 2>/dev/null || true

# ============================================================
# PATCH BBA - Direct sed commands (more reliable than Python)
# ============================================================

# Create NoOpBBA module
RUN cat > /app/ben/src/bba/noop_bba.py << 'NOOP_EOF'
# NoOp BBA - provides dummy implementations when BBA library is not available

class NoOpBBA:
    """A no-op BBA that returns empty/neutral values for all methods"""
    
    def __init__(self, *args, **kwargs):
        pass
    
    def bid_hand(self, *args, **kwargs):
        return {}
    
    def explain(self, *args, **kwargs):
        return [], False, False
    
    def get_bid(self, *args, **kwargs):
        return None
    
    def items(self):
        return {}.items()
    
    def keys(self):
        return {}.keys()
    
    def values(self):
        return {}.values()
    
    def get(self, key, default=None):
        return default
    
    def __iter__(self):
        return iter({})
    
    def __len__(self):
        return 0
    
    def __bool__(self):
        return False
    
    def __getitem__(self, key):
        return None
    
    def __contains__(self, key):
        return False
    
    def __getattr__(self, name):
        def noop(*args, **kwargs):
            return {}
        return noop

_noop_instance = None

def get_noop_bba(*args, **kwargs):
    global _noop_instance
    if _noop_instance is None:
        _noop_instance = NoOpBBA()
    return _noop_instance
NOOP_EOF

# Patch BBA.py - Replace RuntimeError with NoOpBBA return
RUN sed -i '1i from bba.noop_bba import get_noop_bba, NoOpBBA' /app/ben/src/bba/BBA.py && \
    sed -i 's/raise RuntimeError.*dll is not available on this platform.*/print("BBA disabled, using NoOpBBA"); return NoOpBBA/' /app/ben/src/bba/BBA.py

# Patch sample.py - Add aceking None guard at every function that uses it
RUN sed -i '/def.*aceking.*:$/a\        aceking = aceking if aceking is not None else {}' /app/ben/src/sample.py

# Patch botbidder.py - Add import
RUN sed -i '1i from bba.noop_bba import get_noop_bba' /app/ben/src/botbidder.py

# Aggressive aceking fixes in sample.py - wrap all aceking usages
RUN sed -i 's/aceking\.items()/(aceking or {}).items()/g' /app/ben/src/sample.py && \
    sed -i 's/aceking\.keys()/(aceking or {}).keys()/g' /app/ben/src/sample.py && \
    sed -i 's/aceking\.values()/(aceking or {}).values()/g' /app/ben/src/sample.py && \
    sed -i 's/len(aceking)/len(aceking or {})/g' /app/ben/src/sample.py && \
    sed -i 's/aceking\[/( aceking or {} )[/g' /app/ben/src/sample.py

# Aggressive aceking fixes in botbidder.py
RUN sed -i 's/aceking\.items()/(aceking or {}).items()/g' /app/ben/src/botbidder.py && \
    sed -i 's/aceking\.keys()/(aceking or {}).keys()/g' /app/ben/src/botbidder.py && \
    sed -i 's/len(aceking)/len(aceking or {})/g' /app/ben/src/botbidder.py && \
    sed -i 's/, aceking)/, (aceking or {}))/g' /app/ben/src/botbidder.py && \
    sed -i 's/, aceking,/, (aceking or {}),/g' /app/ben/src/botbidder.py

# Patch config to disable BBA
RUN sed -i 's/consult_bba = True/consult_bba = False/g' /app/ben/src/config/default.conf 2>/dev/null || true && \
    echo "consult_bba = False" >> /app/ben/src/config/default.conf

# ============================================================
# End BBA patches
# ============================================================

# Set PYTHONPATH
ENV PYTHONPATH=/app/ben/src
ENV LD_LIBRARY_PATH=/usr/lib:/app/ben/bin:/app/ben/src/ddsolver

# Copy API file
COPY card_analysis_api.py /app/ben/card_analysis_api.py

WORKDIR /app/ben

EXPOSE 8080

CMD ["python", "-m", "uvicorn", "card_analysis_api:app", "--host", "0.0.0.0", "--port", "8080"]
