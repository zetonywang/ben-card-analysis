"""
Ben Bridge Card-by-Card Analysis API
Analyzes complete bridge deals - bidding AND play card-by-card
Shows quality ratings (OK, ?, ??, Forced) for each card played
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
import sys
import os
from contextlib import asynccontextmanager
import logging
import asyncio

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

models = None
sampler = None
CardByCard = None
app_state = {'ready': False, 'error': None}


@asynccontextmanager
async def lifespan(app: FastAPI):
    global models, sampler, CardByCard, app_state
    
    logger.info("🔄 Loading Ben bridge models...")
    
    try:
        ben_path = "/app/ben"
        src_path = os.path.join(ben_path, "src")
        
        if not os.path.exists(ben_path):
            raise RuntimeError(f"Ben not found at {ben_path}")
        
        os.chdir(ben_path)
        sys.path.insert(0, src_path)
        
        from nn.models_tf2 import Models
        from analysis import CardByCard as CBC
        from sample import Sample
        import conf
        
        CardByCard = CBC
        
        config_path = os.path.join(ben_path, 'src', 'config', 'default.conf')
        
        if not os.path.exists(config_path):
            raise RuntimeError(f"Config not found at {config_path}")
        
        logger.info(f"📋 Loading config from: {config_path}")
        conf_obj = conf.load(config_path)
        
        logger.info("🧠 Loading neural network models...")
        models = Models.from_conf(conf_obj, '.')
        sampler = Sample.from_conf(conf_obj, False)
        
        # Disable PIMC (can cause issues)
        models.pimc_use_declaring = False
        models.pimc_use_defending = False
        
        # Disable DDS (double-dummy solver) - not available in container
        models.use_dds = False
        models.dds_use_declaring = False
        models.dds_use_defending = False
        
        app_state['ready'] = True
        logger.info("✅ Models loaded and ready!")
        
    except Exception as e:
        logger.error(f"❌ Failed to load models: {e}", exc_info=True)
        app_state['error'] = str(e)
        raise
    
    yield
    
    logger.info("🔴 Shutting down...")


app = FastAPI(
    title="Ben Bridge Card-by-Card Analysis API",
    version="2.0.0",
    description="Analyze complete bridge deals including bidding and play card-by-card",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class DealAnalysisRequest(BaseModel):
    dealer: str = Field(..., description="Dealer: N, E, S, or W")
    vuln: List[bool] = Field(..., description="[NS vulnerable, EW vulnerable]")
    hands: List[str] = Field(..., description="4 hands: [North, East, South, West] in format 'AK5.QJ3.K82.AT3'")
    auction: List[str] = Field(..., description="Complete auction e.g. ['1N', 'PASS', '4H', 'PASS', 'PASS', 'PASS']")
    play: List[str] = Field(default=[], description="Cards played e.g. ['C2', 'D3', 'CA', ...]")


class BidAnalysis(BaseModel):
    bid: str
    quality: str
    suggested_bid: Optional[str]
    candidates: List[Dict]
    notes: Optional[str]


class CardAnalysis(BaseModel):
    card: str
    quality: str  # "OK", "?", "??", "Forced"
    trick_num: int
    player: str
    suggested_card: Optional[str]
    candidates: List[Dict]
    expected_tricks: Optional[float]
    expected_score: Optional[float]
    losing: Optional[float]  # How much it costs if it's a mistake


class DealAnalysisResponse(BaseModel):
    dealer: str
    vulnerability: Dict[str, bool]
    hands: List[str]
    contract: str
    declarer: str
    bidding_analysis: List[BidAnalysis]
    opening_lead_analysis: CardAnalysis
    play_analysis: List[CardAnalysis]
    summary: Dict


@app.get("/")
def root():
    return {
        "status": "online",
        "ready": app_state.get('ready', False),
        "service": "Ben Bridge Card-by-Card Analysis API",
        "version": "2.0.0",
        "endpoints": {
            "/analyze": "Analyze complete deal (bidding + play)",
            "/health": "Health check"
        }
    }


@app.get("/health")
def health():
    return {
        "status": "healthy" if app_state.get('ready') else "loading",
        "models_loaded": app_state.get('ready', False),
        "error": app_state.get('error')
    }


@app.post("/analyze", response_model=DealAnalysisResponse)
async def analyze_deal(request: DealAnalysisRequest):
    """
    Analyze a complete bridge deal including bidding and play card-by-card
    
    Shows for each bid and card:
    - Quality rating (OK, ?, ??, Forced)
    - Suggested alternatives
    - Expected tricks/score
    - Sample hands
    """
    
    if not app_state.get('ready'):
        raise HTTPException(
            status_code=503,
            detail=f"Models not ready. Error: {app_state.get('error', 'Still loading...')}"
        )
    
    try:
        logger.info("🎴 Starting card-by-card analysis...")
        
        # Validate inputs
        if len(request.hands) != 4:
            raise HTTPException(status_code=400, detail="Must provide exactly 4 hands")
        
        if len(request.vuln) != 2:
            raise HTTPException(status_code=400, detail="vuln must be [NS, EW]")
        
        # Create CardByCard analyzer
        card_by_card = CardByCard(
            request.dealer,
            request.vuln,
            request.hands,
            request.auction,
            request.play,
            models,
            sampler,
            False  # verbose
        )
        
        # Run the analysis (this is async in Ben)
        logger.info("⏳ Analyzing (this may take 30-60 seconds)...")
        await card_by_card.analyze()
        logger.info("✅ Analysis complete!")
        
        # Parse contract
        contract = "PASSED OUT"
        declarer = "N/A"
        if request.auction and any(bid not in ['PASS', 'X', 'XX'] for bid in request.auction):
            for i in range(len(request.auction) - 1, -1, -1):
                if request.auction[i] not in ['PASS', 'X', 'XX']:
                    contract = request.auction[i]
                    declarer_seat = i % 4
                    declarer = ['N', 'E', 'S', 'W'][declarer_seat]
                    break
        
        # Extract bidding analysis
        bidding_analysis = []
        for i, bid in enumerate(request.auction):
            bid_key = f"bid_{i}"
            if bid_key in card_by_card.bids:
                bid_info = card_by_card.bids[bid_key]
                quality = bid_info.get('quality', '1.0')
                
                # Determine quality label
                try:
                    q_val = float(quality)
                    if q_val >= 0.9:
                        quality_label = "OK"
                    elif q_val >= 0.7:
                        quality_label = "?"
                    else:
                        quality_label = "??"
                except:
                    quality_label = "OK"
                
                candidates = bid_info.get('candidates', [])
                suggested = candidates[0]['call'] if candidates else None
                
                bidding_analysis.append(BidAnalysis(
                    bid=bid,
                    quality=quality_label,
                    suggested_bid=suggested,
                    candidates=candidates[:5],  # Top 5
                    notes=None
                ))
        
        # Extract opening lead analysis
        opening_lead = None
        if request.play and len(request.play) > 0:
            lead_card = request.play[0]
            if lead_card in card_by_card.cards:
                lead_info = card_by_card.cards[lead_card].to_dict()
                quality = lead_info.get('quality', '1.0')
                
                try:
                    q_val = float(quality)
                    if q_val >= 0.9:
                        quality_label = "OK"
                    elif q_val >= 0.7:
                        quality_label = "?"
                    else:
                        quality_label = "??"
                except:
                    quality_label = "OK"
                
                candidates = lead_info.get('candidates', [])
                suggested = candidates[0]['card'] if candidates else None
                
                opening_lead = CardAnalysis(
                    card=lead_card,
                    quality=quality_label,
                    trick_num=1,
                    player=lead_info.get('who', ''),
                    suggested_card=suggested,
                    candidates=candidates[:5],
                    expected_tricks=None,
                    expected_score=candidates[0].get('expected_score_imp') if candidates else None,
                    losing=None
                )
        
        # Extract play analysis
        play_analysis = []
        for i, card in enumerate(request.play[1:], 2):  # Skip opening lead
            if card in card_by_card.cards:
                card_info = card_by_card.cards[card].to_dict()
                quality = card_info.get('quality', '1.0')
                
                # Determine quality
                try:
                    q_val = float(quality)
                    if q_val >= 0.9:
                        quality_label = "OK"
                    elif q_val >= 0.7:
                        quality_label = "?"
                    else:
                        quality_label = "??"
                except:
                    quality_label = "OK"
                
                # Check if it's forced
                candidates = card_info.get('candidates', [])
                if len(candidates) == 1:
                    quality_label = "Forced"
                
                suggested = candidates[0]['card'] if candidates else None
                
                # Calculate losing amount for mistakes
                losing = None
                if candidates and len(candidates) > 1:
                    best_score = candidates[0].get('expected_score_imp', 0)
                    played_score = next((c.get('expected_score_imp', 0) for c in candidates if c['card'] == card), None)
                    if best_score and played_score:
                        losing = abs(best_score - played_score)
                
                play_analysis.append(CardAnalysis(
                    card=card,
                    quality=quality_label,
                    trick_num=(i - 1) // 4 + 1,
                    player=card_info.get('who', ''),
                    suggested_card=suggested if suggested != card else None,
                    candidates=candidates[:5],
                    expected_tricks=candidates[0].get('expected_tricks_dd') if candidates else None,
                    expected_score=candidates[0].get('expected_score_imp') if candidates else None,
                    losing=losing
                ))
        
        # Create summary
        mistakes = sum(1 for p in play_analysis if p.quality in ["?", "??"])
        big_mistakes = sum(1 for p in play_analysis if p.quality == "??")
        
        summary = {
            "contract": contract,
            "declarer": declarer,
            "total_cards_played": len(request.play),
            "total_tricks": len(request.play) // 4,
            "mistakes": mistakes,
            "big_mistakes": big_mistakes,
            "notes": f"Analysis found {mistakes} questionable plays ({big_mistakes} serious mistakes)"
        }
        
        return DealAnalysisResponse(
            dealer=request.dealer,
            vulnerability={"NS": request.vuln[0], "EW": request.vuln[1]},
            hands=request.hands,
            contract=contract,
            declarer=declarer,
            bidding_analysis=bidding_analysis,
            opening_lead_analysis=opening_lead,
            play_analysis=play_analysis,
            summary=summary
        )
        
    except Exception as e:
        logger.error(f"Analysis error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
