#!/usr/bin/env python3
"""
Ben Card Analysis API - Neural Network Only
No DDS, No BBA - Pure Python mocks
"""

import sys
import os

# ============================================================
# STEP 1: SET UP PATHS
# ============================================================

# We should already be in /app/ben/src from Dockerfile
# But ensure the path is set
if '/app/ben/src' not in sys.path:
    sys.path.insert(0, '/app/ben/src')

print(f"Working dir: {os.getcwd()}")

# ============================================================
# STEP 2: MOCK DDS BEFORE ANY BEN IMPORTS
# ============================================================

class FakeDDS:
    """Fake DDS that does nothing"""
    __file__ = "/fake/dds"
    __path__ = ["/fake/dds"]
    
    def SetMaxThreads(self, *a): pass
    def SetThreading(self, *a): pass  
    def SetResources(self, *a): pass
    def FreeMemory(self, *a): pass
    def SolveBoard(self, *a): return 0
    def CalcDDtable(self, *a): return 0
    
    def __getattr__(self, name):
        def noop(*args, **kwargs):
            return 0
        return noop

# Mock the dds module
sys.modules['dds'] = FakeDDS()

# ============================================================
# STEP 2: PATCH SOURCE FILES
# ============================================================

def patch_files():
    """Patch Ben files to work without DDS/BBA"""
    
    # 1. Replace ddsolver/__init__.py completely
    dds_init = 'ddsolver/__init__.py'
    if os.path.exists(dds_init):
        with open(dds_init, 'w') as f:
            f.write('''
# Mock DDS - no library
class DDS:
    def __getattr__(self, name):
        return lambda *a, **k: 0

dds = DDS()
SetMaxThreads = lambda *a: None
SetThreading = lambda *a: None
SetResources = lambda *a: None
FreeMemory = lambda *a: None
SolveBoard = lambda *a: 0
CalcDDtable = lambda *a: 0
''')
    
    # 2. Replace bba/BBA.py completely
    bba_file = 'bba/BBA.py'
    if os.path.exists(bba_file):
        with open(bba_file, 'w') as f:
            f.write('''
# Mock BBA - no Windows DLL needed
class BBA:
    def __init__(self, *a, **k): pass
    def bid_hand(self, *a, **k): return {}
    def explain(self, *a, **k): return [], False, False
    def __getattr__(self, name):
        return lambda *a, **k: {}

def BBA_PLAYER(*a, **k):
    return BBA()
''')
    
    # 3. Patch sample.py for aceking safety
    sample_py = 'sample.py'
    if os.path.exists(sample_py):
        with open(sample_py, 'r') as f:
            content = f.read()
        
        replacements = [
            ('aceking.items()', '(aceking or {}).items()'),
            ('aceking.keys()', '(aceking or {}).keys()'),
            ('aceking.values()', '(aceking or {}).values()'),
            ('len(aceking)', 'len(aceking or {})'),
            ('aceking[', '(aceking or {})['),
            (', aceking)', ', (aceking or {}))'),
            (', aceking,', ', (aceking or {}),'),
        ]
        
        for old, new in replacements:
            content = content.replace(old, new)
        
        with open(sample_py, 'w') as f:
            f.write(content)
    
    # 4. Patch botbidder.py for aceking safety
    botbidder_py = 'botbidder.py'
    if os.path.exists(botbidder_py):
        with open(botbidder_py, 'r') as f:
            content = f.read()
        
        replacements = [
            ('aceking.items()', '(aceking or {}).items()'),
            ('aceking.keys()', '(aceking or {}).keys()'),
            ('len(aceking)', 'len(aceking or {})'),
            (', aceking)', ', (aceking or {}))'),
            (', aceking,', ', (aceking or {}),'),
        ]
        
        for old, new in replacements:
            content = content.replace(old, new)
        
        with open(botbidder_py, 'w') as f:
            f.write(content)
    
    # 5. Disable BBA in config
    config = 'config/default.conf'
    if os.path.exists(config):
        with open(config, 'r') as f:
            content = f.read()
        content = content.replace('consult_bba = True', 'consult_bba = False')
        with open(config, 'a') as f:
            f.write('\nconsult_bba = False\n')

print("Patching Ben files...")
patch_files()
print("Done patching!")

# ============================================================
# STEP 3: IMPORT AND RUN API
# ============================================================

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import asyncio

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global state
models = None
CardByCard = None

class AnalysisRequest(BaseModel):
    dealer: str
    vuln: List[bool]
    hands: List[str]
    auction: List[str]
    play: Optional[List[str]] = []

@asynccontextmanager
async def lifespan(app: FastAPI):
    global models, CardByCard
    logger.info("🔄 Loading Ben neural network models...")
    
    try:
        # The file is models_tf2.py, not models.py
        from nn.models_tf2 import Models
        from analysis import CardByCard as CBC
        CardByCard = CBC
        
        from configparser import ConfigParser
        conf = ConfigParser()
        conf.read('config/default.conf')
        
        logger.info("🧠 Loading models...")
        models = Models.from_conf(conf, '.')
        logger.info("✅ Models loaded!")
        
    except Exception as e:
        logger.error(f"❌ Load error: {e}")
        import traceback
        traceback.print_exc()
    
    yield

app = FastAPI(
    title="Ben Bridge Analysis API",
    description="Neural network only - no DDS/BBA",
    version="2.0",
    lifespan=lifespan
)

@app.get("/")
def root():
    return {"service": "Ben NN API", "status": "ready" if models else "loading"}

@app.get("/health")
def health():
    return {"status": "healthy", "models": models is not None}

@app.post("/analyze")
async def analyze(request: AnalysisRequest):
    if not models:
        raise HTTPException(503, "Models not loaded")
    
    try:
        logger.info("🎴 Analyzing...")
        
        cbc = CardByCard(
            dealer=request.dealer,
            vuln=request.vuln,
            hands=request.hands,
            auction=request.auction,
            play=request.play or [],
            models=models
        )
        
        # Run analysis in thread pool
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, cbc.analyze)
        
        # Build response
        result = {"status": "success", "bidding": [], "play": []}
        
        if hasattr(cbc, 'bid_analysis'):
            result["bidding"] = cbc.bid_analysis
        
        if hasattr(cbc, 'play_analysis'):
            result["play"] = cbc.play_analysis
            
        logger.info("✅ Done!")
        return result
        
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(500, str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
