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

# Create a comprehensive stub libdds.so with ALL DDS functions
# This prevents import errors and provides stub implementations
RUN echo '#include <stdio.h>\n\
void SetMaxThreads(int n) {}\n\
void SetResources(int maxMemoryMB, int maxThreads) {}\n\
void FreeMemory() {}\n\
int SolveBoard(void* dl, int target, int solutions, int mode, void* futp, int threadIndex) { return -1; }\n\
int SolveBoardPBN(void* dlPBN, int target, int solutions, int mode, void* futp, int threadIndex) { return -1; }\n\
int SolveAllBoards(void* bop, void* solvedBoards) { return -1; }\n\
int SolveAllBoardsBin(void* bop, void* solvedBoards) { return -1; }\n\
int SolveAllChunks(void* bop, void* solvedBoards, int chunkSize) { return -1; }\n\
int SolveAllChunksBin(void* bop, void* solvedBoards, int chunkSize) { return -1; }\n\
int SolveAllChunksPBN(void* bop, void* solvedBoards, int chunkSize) { return -1; }\n\
int CalcDDtable(void* tableDeal, void* table) { return -1; }\n\
int CalcDDtablePBN(void* tableDealPBN, void* table) { return -1; }\n\
int CalcAllTables(void* dealsp, int mode, int trumpFilter[5], void* resp, void* presp) { return -1; }\n\
int CalcAllTablesPBN(void* dealsp, int mode, int trumpFilter[5], void* resp, void* presp) { return -1; }\n\
void DDS_Version() {}\n\
void GetDDSInfo(void* info) {}\n\
int AnalysePlayBin(void* dl, void* play, void* solved, int thrId) { return -1; }\n\
int AnalysePlayPBN(void* dlPBN, void* playPBN, void* solvedPlay, int thrId) { return -1; }\n\
int AnalyseAllPlaysBin(void* dl, void* play, void* solved, int chunkSize) { return -1; }\n\
int AnalyseAllPlaysPBN(void* dlPBN, void* playPBN, void* solvedp, int chunkSize) { return -1; }\n\
void ErrorMessage(int code, char* msg) { if(msg) msg[0]=0; }\n\
int Par(void* tablep, void* presp, int vulnerable) { return -1; }\n\
int DealerPar(void* tablep, void* presp, int dealer, int vulnerable) { return -1; }\n\
int DealerParBin(void* tablep, void* presp, int dealer, int vulnerable) { return -1; }\n\
int SidesParBin(void* tablep, void* sidesRes, int vulnerable) { return -1; }\n\
int SidesPar(void* tablep, void* sidesRes, int vulnerable) { return -1; }\n\
int ConvertToDealerTextFormat(void* pres, char* resp) { return -1; }\n\
int ConvertToSidesTextFormat(void* pres, void* resp) { return -1; }\n\
int CalcPar(void* tableDeal, int vulnerable, void* resp, void* presp) { return -1; }\n\
int CalcParPBN(void* tableDealPBN, void* tablep, int vulnerable, void* resp, void* presp) { return -1; }' > /tmp/stub.c && \
    gcc -shared -fPIC -o /usr/local/lib/libdds.so /tmp/stub.c && \
    rm /tmp/stub.c && \
    ldconfig

# Initialize Git LFS
RUN git lfs install

# Clone Ben repository with LFS files
RUN git clone https://github.com/lorserker/ben.git && \
    cd ben && \
    git lfs pull

# Copy stub library to Ben's ddsolver directory where it looks for it
RUN cp /usr/local/lib/libdds.so /app/ben/src/ddsolver/libdds.so && \
    cp /usr/local/lib/libdds.so /app/ben/src/ddsolver/dds.dll && \
    cp /usr/local/lib/libdds.so /app/ben/libdds.so

# Install Python dependencies from Ben
RUN pip install --no-cache-dir \
    tensorflow==2.17.0 \
    keras==3.6.0 \
    numpy \
    scipy \
    scikit-learn \
    fastapi \
    uvicorn \
    pydantic \
    colorama \
    tqdm \
    dill

# Copy API file
COPY card_analysis_api.py /app/ben/card_analysis_api.py

# Set working directory to ben
WORKDIR /app/ben

# Expose port
EXPOSE 8000

# Set Python path and library paths
ENV PYTHONPATH=/app/ben/src:$PYTHONPATH
ENV LD_LIBRARY_PATH=/usr/local/lib:/app/ben/src/ddsolver:$LD_LIBRARY_PATH

# Run the API
CMD sh -c "uvicorn card_analysis_api:app --host 0.0.0.0 --port ${PORT:-8000}"
