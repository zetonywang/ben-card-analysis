#!/usr/bin/env python3
"""
Ben Card Analysis API - Neural Network Only
No DDS, No BBA - Pure Python mocks
"""

import sys
import os
import ctypes

# ============================================================
# STEP 0: PREVENT ALL DDS LIBRARY LOADING
# ============================================================

# Store original CDLL
_original_cdll = ctypes.CDLL

class MockCDLL:
    """Mock for any C library"""
    def __init__(self, *args, **kwargs):
        pass
    def __getattr__(self, name):
        def noop(*args, **kwargs):
            return 0
        return noop

def _fake_cdll(name, *args, **kwargs):
    """Intercept CDLL calls and return mock for dds/libdds"""
    if 'dds' in str(name).lower():
        print(f"Blocked loading: {name}")
        return MockCDLL()
    # Allow other libraries
    return _original_cdll(name, *args, **kwargs)

# Patch ctypes.CDLL BEFORE anything else
ctypes.CDLL = _fake_cdll

# ============================================================
# STEP 1: SET UP PATHS
# ============================================================

# We should already be in /app/ben/src from Dockerfile
# But ensure the path is set
if '/app/ben/src' not in sys.path:
    sys.path.insert(0, '/app/ben/src')

print(f"Working dir: {os.getcwd()}")

# ============================================================
# STEP 2: MOCK DDS AND DDSOLVER BEFORE ANY BEN IMPORTS
# ============================================================

import types

# Create a proper mock module for ddsolver
fake_ddsolver = types.ModuleType('ddsolver')
fake_ddsolver.__file__ = '/fake/ddsolver/__init__.py'
fake_ddsolver.__path__ = ['/fake/ddsolver']

# Create a mock dds object
class MockDDS:
    def __getattr__(self, name):
        def noop(*args, **kwargs):
            return 0
        return noop

fake_ddsolver.dds = MockDDS()

# Add all expected functions to the module
def _noop(*args, **kwargs):
    return 0

fake_ddsolver.SetMaxThreads = _noop
fake_ddsolver.SetThreading = _noop
fake_ddsolver.SetResources = _noop
fake_ddsolver.FreeMemory = _noop
fake_ddsolver.SolveBoard = _noop
fake_ddsolver.SolveBoardPBN = _noop
fake_ddsolver.CalcDDtable = _noop
fake_ddsolver.CalcDDtablePBN = _noop
fake_ddsolver.CalcAllTables = _noop
fake_ddsolver.CalcAllTablesPBN = _noop
fake_ddsolver.SolveAllBoards = _noop
fake_ddsolver.Par = _noop
fake_ddsolver.CalcPar = _noop
fake_ddsolver.AnalysePlayBin = _noop
fake_ddsolver.AnalysePlayPBN = _noop

# Also create a fake dds module
fake_dds = types.ModuleType('dds')
fake_dds.__file__ = '/fake/dds/__init__.py'
for name in ['SetMaxThreads', 'SetThreading', 'SetResources', 'FreeMemory', 
             'SolveBoard', 'CalcDDtable', 'CalcDDtablePBN']:
    setattr(fake_dds, name, _noop)

# Install mocks in sys.modules BEFORE any Ben imports
sys.modules['dds'] = fake_dds
sys.modules['ddsolver'] = fake_ddsolver
sys.modules['ddsolver.dds'] = fake_dds

print("Mocked dds and ddsolver modules")

# ============================================================
# STEP 2: PATCH SOURCE FILES
# ============================================================

def patch_files():
    """Patch Ben files to work without DDS/BBA"""
    
    # NOTE: We do NOT patch ddsolver/__init__.py - we rely on sys.modules mock instead
    # This avoids issues with import order and module loading
    
    # 1. Replace bba/BBA.py completely
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
    
    # 3. Patch sample.py for aceking safety (but DON'T comment out imports - let them use mock)
    sample_py = 'sample.py'
    if os.path.exists(sample_py):
        with open(sample_py, 'r') as f:
            lines = f.readlines()
        
        new_lines = []
        for line in lines:
            # Skip function definitions - don't modify parameter names
            if 'def ' in line:
                new_lines.append(line)
                continue
            
            # Only modify non-def lines for aceking safety
            line = line.replace('aceking.items()', '(aceking or {}).items()')
            line = line.replace('aceking.keys()', '(aceking or {}).keys()')
            line = line.replace('aceking.values()', '(aceking or {}).values()')
            line = line.replace('len(aceking)', 'len(aceking or {})')
            # Be careful with subscript - only if followed by [ not in def
            if 'aceking[' in line:
                line = line.replace('aceking[', '(aceking or {})[')
            new_lines.append(line)
        
        with open(sample_py, 'w') as f:
            f.writelines(new_lines)
    
    # 4. Patch botbidder.py for aceking safety
    botbidder_py = 'botbidder.py'
    if os.path.exists(botbidder_py):
        with open(botbidder_py, 'r') as f:
            lines = f.readlines()
        
        new_lines = []
        for line in lines:
            # Skip function definitions
            if 'def ' in line:
                new_lines.append(line)
                continue
            
            line = line.replace('aceking.items()', '(aceking or {}).items()')
            line = line.replace('aceking.keys()', '(aceking or {}).keys()')
            line = line.replace('len(aceking)', 'len(aceking or {})')
            new_lines.append(line)
        
        with open(botbidder_py, 'w') as f:
            f.writelines(new_lines)
    
    # NOTE: We don't comment out ddsolver imports - they will use our mock from sys.modules
    
    # 5. Disable BBA in config
    config = 'config/default.conf'
    if os.path.exists(config):
        with open(config, 'r') as f:
            content = f.read()
        content = content.replace('consult_bba = True', 'consult_bba = False')
        with open(config, 'a') as f:
            f.write('\nconsult_bba = False\n')
    
    # NOTE: All ddsolver imports will use our mock from sys.modules - no need to comment them out

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
sampler = None

class AnalysisRequest(BaseModel):
    dealer: str
    vuln: List[bool]
    hands: List[str]
    auction: List[str]
    play: Optional[List[str]] = []

@asynccontextmanager
async def lifespan(app: FastAPI):
    global models, CardByCard, sampler
    logger.info("🔄 Loading Ben neural network models...")
    
    try:
        # The file is models_tf2.py, not models.py
        from nn.models_tf2 import Models
        from analysis import CardByCard as CBC
        from sample import Sample
        
        CardByCard = CBC
        
        from configparser import ConfigParser
        conf = ConfigParser()
        conf.read('config/default.conf')
        
        logger.info("🧠 Loading models...")
        models = Models.from_conf(conf, '..')  # Models are in /app/ben/models, we're in /app/ben/src
        
        # Create sampler
        sampler = Sample.from_conf(conf, '..')
        
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
            models=models,
            sampler=sampler,
            verbose=False
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
