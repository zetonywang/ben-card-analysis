"""
Ben Bridge Card-by-Card Analysis API
Shows how bidding recommendations change as cards are revealed progressively
Based on CardByCardAnalysis.ipynb concept
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional
import sys
import os
from contextlib import asynccontextmanager
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

models = None
sampler = None
BotBid = None
app_state = {'ready': False, 'error': None}


@asynccontextmanager
async def lifespan(app: FastAPI):
    global models, sampler, BotBid, app_state
    
    logger.info("🔄 Loading Ben bridge bidding models...")
    
    try:
        ben_path = "/app/ben"
        src_path = os.path.join(ben_path, "src")
        
        if not os.path.exists(ben_path):
            raise RuntimeError(f"Ben not found at {ben_path}")
        
        logger.info(f"✅ Found Ben at: {ben_path}")
        
        os.chdir(ben_path)
        sys.path.insert(0, src_path)
        
        from nn.models_tf2 import Models
        from botbidder import BotBid as BB
        from sample import Sample
        import conf
        
        BotBid = BB
        
        config_path = os.path.join(ben_path, 'src', 'config', 'default.conf')
        
        if not os.path.exists(config_path):
            raise RuntimeError(f"Config not found at {config_path}")
        
        logger.info(f"📋 Loading config from: {config_path}")
        conf_obj = conf.load(config_path)
        
        logger.info("🧠 Loading neural network models...")
        models = Models.from_conf(conf_obj, '.')
        sampler = Sample.from_conf(conf_obj, False)
        
        for attr in ["consult_bba", "use_bba_to_count_aces", "use_bba_to_count_keycards", 
                     "use_bba_to_estimate_shape", "use_bba_for_sampling", "use_bba"]:
            if hasattr(models, attr):
                setattr(models, attr, False)
        
        BB.bbabot = property(lambda self: None)
        
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
    version="1.0.0",
    description="Analyze how bidding recommendations change as cards are revealed",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class CardStep(BaseModel):
    """Represents one step in the card-by-card analysis"""
    cards_shown: str
    num_cards: int
    recommended_bid: str
    confidence: float
    all_candidates: List[dict]


class CardByCardRequest(BaseModel):
    hand: str = Field(..., description="Complete hand: 'KQJ.AT2.9876.AK3'")
    auction: List[str] = Field(default=[], description="Auction so far")
    seat: int = Field(default=0, ge=0, le=3)
    dealer: int = Field(default=0, ge=0, le=3)
    vuln_ns: bool = Field(default=False)
    vuln_ew: bool = Field(default=False)


class CardByCardResponse(BaseModel):
    full_hand: str
    auction: List[str]
    analysis_steps: List[CardStep]
    summary: dict


def parse_hand(hand_str: str) -> List[str]:
    """Parse hand string into individual cards"""
    suits = hand_str.split('.')
    cards = []
    
    suit_symbols = ['S', 'H', 'D', 'C']
    
    for i, suit_cards in enumerate(suits):
        suit = suit_symbols[i]
        for card in suit_cards:
            cards.append(f"{suit}{card}")
    
    return cards


def cards_to_hand(cards: List[str]) -> str:
    """Convert list of cards back to hand format"""
    suits = {'S': [], 'H': [], 'D': [], 'C': []}
    
    for card in cards:
        suit = card[0]
        rank = card[1]
        suits[suit].append(rank)
    
    # Join in the right order
    hand_parts = []
    for suit in ['S', 'H', 'D', 'C']:
        hand_parts.append(''.join(suits[suit]) if suits[suit] else '')
    
    return '.'.join(hand_parts)


def get_bid_for_partial_hand(partial_hand: str, auction: List[str], seat: int, dealer: int, vuln_ns: bool, vuln_ew: bool):
    """Get bid recommendation for a partial hand"""
    
    try:
        bot = BotBid(
            [vuln_ns, vuln_ew],
            partial_hand,
            models,
            sampler,
            seat=seat,
            dealer=dealer,
            ddsolver=None,
            bba_is_controlling=False,
            verbose=False,
        )
        
        candidates, passout = bot.get_bid_candidates(auction)
        
        if not candidates:
            return {
                "bid": "PASS",
                "confidence": 1.0,
                "candidates": [{"call": "PASS", "insta_score": 1.0}]
            }
        
        formatted_candidates = []
        for c in candidates[:5]:  # Top 5
            formatted_candidates.append({
                "call": c.bid,
                "insta_score": float(c.insta_score)
            })
        
        return {
            "bid": candidates[0].bid,
            "confidence": float(candidates[0].insta_score),
            "candidates": formatted_candidates
        }
        
    except Exception as e:
        logger.error(f"Error getting bid: {e}")
        return {
            "bid": "ERROR",
            "confidence": 0.0,
            "candidates": []
        }


@app.get("/")
def root():
    return {
        "status": "online",
        "ready": app_state.get('ready', False),
        "service": "Ben Bridge Card-by-Card Analysis API",
        "endpoints": {
            "/analyze": "Analyze hand card-by-card",
            "/analyze/html": "Get HTML visualization"
        }
    }


@app.get("/health")
def health():
    return {
        "status": "healthy" if app_state.get('ready') else "loading",
        "models_loaded": app_state.get('ready', False),
        "error": app_state.get('error')
    }


@app.post("/analyze", response_model=CardByCardResponse)
def analyze_card_by_card(request: CardByCardRequest):
    """
    Analyze how bidding recommendation changes as cards are revealed one by one
    """
    
    if not app_state.get('ready'):
        raise HTTPException(
            status_code=503,
            detail=f"Models not ready. Error: {app_state.get('error', 'Still loading...')}"
        )
    
    try:
        # Parse the full hand into individual cards
        all_cards = parse_hand(request.hand)
        
        analysis_steps = []
        
        # Analyze with increasing number of cards
        for i in range(1, len(all_cards) + 1):
            partial_cards = all_cards[:i]
            partial_hand = cards_to_hand(partial_cards)
            
            # Get bid recommendation for this partial hand
            result = get_bid_for_partial_hand(
                partial_hand,
                request.auction,
                request.seat,
                request.dealer,
                request.vuln_ns,
                request.vuln_ew
            )
            
            analysis_steps.append(CardStep(
                cards_shown=partial_hand,
                num_cards=i,
                recommended_bid=result['bid'],
                confidence=result['confidence'],
                all_candidates=result['candidates']
            ))
        
        # Create summary
        bid_changes = []
        for i in range(1, len(analysis_steps)):
            if analysis_steps[i].recommended_bid != analysis_steps[i-1].recommended_bid:
                bid_changes.append({
                    "at_card": i + 1,
                    "from_bid": analysis_steps[i-1].recommended_bid,
                    "to_bid": analysis_steps[i].recommended_bid,
                    "cards_shown": analysis_steps[i].cards_shown
                })
        
        summary = {
            "total_cards": len(all_cards),
            "final_recommendation": analysis_steps[-1].recommended_bid,
            "final_confidence": analysis_steps[-1].confidence,
            "bid_changes": bid_changes,
            "num_changes": len(bid_changes)
        }
        
        return CardByCardResponse(
            full_hand=request.hand,
            auction=request.auction,
            analysis_steps=analysis_steps,
            summary=summary
        )
        
    except Exception as e:
        logger.error(f"Analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/analyze/html")
def analyze_html(request: CardByCardRequest):
    """Get card-by-card analysis as beautiful HTML visualization"""
    
    result = analyze_card_by_card(request)
    
    # Build HTML
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Card-by-Card Analysis</title>
        <style>
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                padding: 20px;
                margin: 0;
            }
            .container {
                max-width: 1200px;
                margin: 0 auto;
                background: white;
                border-radius: 20px;
                padding: 30px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            }
            h1 {
                color: #667eea;
                text-align: center;
                margin-bottom: 10px;
            }
            .header-info {
                text-align: center;
                color: #666;
                margin-bottom: 30px;
                font-size: 1.1em;
            }
            .summary {
                background: #f8f9fa;
                border-left: 5px solid #667eea;
                padding: 20px;
                margin-bottom: 30px;
                border-radius: 10px;
            }
            .timeline {
                position: relative;
                padding-left: 50px;
            }
            .timeline::before {
                content: '';
                position: absolute;
                left: 20px;
                top: 0;
                bottom: 0;
                width: 3px;
                background: linear-gradient(to bottom, #667eea, #764ba2);
            }
            .step {
                position: relative;
                margin-bottom: 30px;
                background: white;
                border: 2px solid #e0e0e0;
                border-radius: 15px;
                padding: 20px;
                transition: all 0.3s;
            }
            .step:hover {
                transform: translateX(10px);
                box-shadow: 0 5px 20px rgba(102, 126, 234, 0.3);
                border-color: #667eea;
            }
            .step.changed {
                border-color: #ff6b6b;
                background: #fff5f5;
            }
            .step::before {
                content: attr(data-card);
                position: absolute;
                left: -44px;
                top: 50%;
                transform: translateY(-50%);
                width: 30px;
                height: 30px;
                background: #667eea;
                color: white;
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                font-weight: bold;
                font-size: 0.9em;
            }
            .step.changed::before {
                background: #ff6b6b;
                animation: pulse 2s infinite;
            }
            @keyframes pulse {
                0%, 100% { transform: translateY(-50%) scale(1); }
                50% { transform: translateY(-50%) scale(1.2); }
            }
            .cards {
                font-size: 1.3em;
                font-weight: bold;
                color: #333;
                margin-bottom: 15px;
                font-family: 'Courier New', monospace;
            }
            .bid {
                display: inline-block;
                background: #667eea;
                color: white;
                padding: 8px 20px;
                border-radius: 25px;
                font-size: 1.2em;
                font-weight: bold;
                margin-right: 15px;
            }
            .confidence {
                display: inline-block;
                color: #666;
                font-size: 0.95em;
            }
            .bar {
                height: 8px;
                background: #e0e0e0;
                border-radius: 4px;
                overflow: hidden;
                margin-top: 10px;
            }
            .bar-fill {
                height: 100%;
                background: linear-gradient(90deg, #667eea, #764ba2);
                transition: width 0.5s;
            }
            .change-alert {
                background: #fff3cd;
                border: 2px solid #ffc107;
                border-radius: 10px;
                padding: 10px 15px;
                margin-top: 15px;
                color: #856404;
            }
            .final-rec {
                background: linear-gradient(135deg, #667eea, #764ba2);
                color: white;
                padding: 20px;
                border-radius: 15px;
                text-align: center;
                font-size: 1.3em;
                margin-top: 30px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🃏 Card-by-Card Bidding Analysis</h1>
            <div class="header-info">
                <div><strong>Full Hand:</strong> {full_hand}</div>
                {auction_display}
            </div>
            
            <div class="summary">
                <h3>📊 Analysis Summary</h3>
                <p><strong>Total Cards:</strong> {total_cards}</p>
                <p><strong>Bid Changes:</strong> {num_changes} times</p>
                <p><strong>Final Recommendation:</strong> <span class="bid">{final_bid}</span> 
                   ({final_confidence:.1%} confidence)</p>
            </div>
            
            <h3>📈 Progressive Analysis</h3>
            <div class="timeline">
    """.format(
        full_hand=result.full_hand,
        auction_display=f"<div><strong>Auction:</strong> {' - '.join(result.auction)}</div>" if result.auction else "",
        total_cards=result.summary['total_cards'],
        num_changes=result.summary['num_changes'],
        final_bid=result.summary['final_recommendation'],
        final_confidence=result.summary['final_confidence']
    )
    
    # Add timeline steps
    for i, step in enumerate(result.analysis_steps):
        is_changed = i > 0 and step.recommended_bid != result.analysis_steps[i-1].recommended_bid
        
        change_html = ""
        if is_changed:
            change_html = f"""
                <div class="change-alert">
                    ⚠️ Bid changed from <strong>{result.analysis_steps[i-1].recommended_bid}</strong> to <strong>{step.recommended_bid}</strong>
                </div>
            """
        
        html += f"""
            <div class="step {'changed' if is_changed else ''}" data-card="{step.num_cards}">
                <div class="cards">{step.cards_shown}</div>
                <div>
                    <span class="bid">{step.recommended_bid}</span>
                    <span class="confidence">{step.confidence:.1%} confidence</span>
                </div>
                <div class="bar">
                    <div class="bar-fill" style="width: {step.confidence*100}%"></div>
                </div>
                {change_html}
            </div>
        """
    
    html += """
            </div>
            
            <div class="final-rec">
                ✅ Final Recommendation: <strong>{final_bid}</strong>
            </div>
        </div>
    </body>
    </html>
    """.format(final_bid=result.summary['final_recommendation'])
    
    return {"html": html}


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
