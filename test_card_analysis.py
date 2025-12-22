"""
Test Script for Card-by-Card Analysis API
"""

import requests
import json

# Change this to your Railway URL after deployment
API_URL = "http://localhost:8000"
# API_URL = "https://YOUR-APP.up.railway.app"


def test_basic_analysis():
    """Test basic card-by-card analysis"""
    print("\n" + "="*70)
    print("TEST 1: Basic Opening Bid Analysis")
    print("="*70)
    
    response = requests.post(f"{API_URL}/analyze", json={
        "hand": "AK5.QJ3.KQ82.AT3",
        "auction": [],
        "seat": 0,
        "dealer": 0
    })
    
    if response.status_code == 200:
        data = response.json()
        
        print(f"\n✅ Analysis successful!")
        print(f"Full hand: {data['full_hand']}")
        print(f"\n📊 Summary:")
        print(f"  Final recommendation: {data['summary']['final_recommendation']}")
        print(f"  Confidence: {data['summary']['final_confidence']:.1%}")
        print(f"  Bid changed {data['summary']['num_changes']} times")
        
        print(f"\n📈 Key steps:")
        # Show every 3rd step
        for i, step in enumerate(data['analysis_steps']):
            if i % 3 == 0 or i == len(data['analysis_steps']) - 1:
                print(f"  {step['num_cards']:2d} cards: {step['cards_shown']:20s} → {step['recommended_bid']:4s} ({step['confidence']:.1%})")
        
        if data['summary']['bid_changes']:
            print(f"\n⚠️  Bid changes:")
            for change in data['summary']['bid_changes']:
                print(f"  • Card {change['at_card']}: {change['from_bid']} → {change['to_bid']}")
                print(f"    Cards: {change['cards_shown']}")
        
    else:
        print(f"❌ Error: {response.status_code}")
        print(response.text)


def test_response_analysis():
    """Test analysis of response to partner's bid"""
    print("\n" + "="*70)
    print("TEST 2: Response to Partner's 1♣")
    print("="*70)
    
    response = requests.post(f"{API_URL}/analyze", json={
        "hand": "KJ54.AQ3.K82.AT3",
        "auction": ["1C"],
        "seat": 1,
        "dealer": 0
    })
    
    if response.status_code == 200:
        data = response.json()
        
        print(f"\n✅ Analysis successful!")
        print(f"Hand: {data['full_hand']}")
        print(f"Auction: {' - '.join(data['auction'])}")
        print(f"\nFinal bid: {data['summary']['final_recommendation']} ({data['summary']['final_confidence']:.1%})")
        print(f"Number of bid changes: {data['summary']['num_changes']}")
    else:
        print(f"❌ Error: {response.status_code}")


def test_html_output():
    """Test HTML visualization"""
    print("\n" + "="*70)
    print("TEST 3: HTML Visualization")
    print("="*70)
    
    response = requests.post(f"{API_URL}/analyze/html", json={
        "hand": "AKJ54.3.K82.AT32",
        "auction": [],
        "seat": 0,
        "dealer": 0
    })
    
    if response.status_code == 200:
        data = response.json()
        
        # Save HTML to file
        with open("card_analysis_result.html", "w", encoding="utf-8") as f:
            f.write(data['html'])
        
        print(f"\n✅ HTML generated successfully!")
        print(f"Saved to: card_analysis_result.html")
        print(f"Open it in your browser to see the beautiful visualization!")
    else:
        print(f"❌ Error: {response.status_code}")


def test_weak_hand():
    """Test with a weak hand"""
    print("\n" + "="*70)
    print("TEST 4: Weak Hand (Should Stay PASS Longer)")
    print("="*70)
    
    response = requests.post(f"{API_URL}/analyze", json={
        "hand": "543.862.J93.9742",
        "auction": [],
        "seat": 0,
        "dealer": 0
    })
    
    if response.status_code == 200:
        data = response.json()
        
        print(f"\n✅ Analysis successful!")
        print(f"Hand: {data['full_hand']}")
        
        # Find when it stops being PASS
        pass_steps = [s for s in data['analysis_steps'] if s['recommended_bid'] == 'PASS']
        
        print(f"\nPASS for first {len(pass_steps)} cards")
        print(f"Final recommendation: {data['summary']['final_recommendation']}")
        
        # Show the transition
        for i, step in enumerate(data['analysis_steps'][-5:], len(data['analysis_steps'])-4):
            print(f"  {step['num_cards']:2d} cards: {step['recommended_bid']}")
    else:
        print(f"❌ Error: {response.status_code}")


def test_preempt():
    """Test preemptive hand"""
    print("\n" + "="*70)
    print("TEST 5: Preemptive Hand")
    print("="*70)
    
    response = requests.post(f"{API_URL}/analyze", json={
        "hand": "5.74.KQJ98532.86",
        "auction": [],
        "seat": 0,
        "dealer": 0
    })
    
    if response.status_code == 200:
        data = response.json()
        
        print(f"\n✅ Analysis successful!")
        print(f"Hand: {data['full_hand']} (long diamonds!)")
        print(f"Final: {data['summary']['final_recommendation']} ({data['summary']['final_confidence']:.1%})")
        
        if data['summary']['bid_changes']:
            print(f"\nBid evolution:")
            prev_bid = "PASS"
            for step in data['analysis_steps']:
                if step['recommended_bid'] != prev_bid:
                    print(f"  Card {step['num_cards']}: {prev_bid} → {step['recommended_bid']}")
                    prev_bid = step['recommended_bid']
    else:
        print(f"❌ Error: {response.status_code}")


def main():
    print("\n" + "🌉"*35)
    print("    CARD-BY-CARD ANALYSIS API - TEST SUITE")
    print("🌉"*35)
    print(f"\nTesting API at: {API_URL}")
    
    try:
        # Check health
        health = requests.get(f"{API_URL}/health", timeout=5)
        if health.status_code == 200:
            data = health.json()
            if data.get('models_loaded'):
                print("✅ API is ready!\n")
            else:
                print("⏳ API is loading models...\n")
                return
        else:
            print("❌ API not responding\n")
            return
    except Exception as e:
        print(f"❌ Cannot connect to API: {e}")
        print("Make sure the API is running!")
        return
    
    # Run tests
    test_basic_analysis()
    input("\nPress Enter to continue...")
    
    test_response_analysis()
    input("\nPress Enter to continue...")
    
    test_html_output()
    input("\nPress Enter to continue...")
    
    test_weak_hand()
    input("\nPress Enter to continue...")
    
    test_preempt()
    
    print("\n" + "🌉"*35)
    print("    ✅ ALL TESTS COMPLETE!")
    print("🌉"*35)
    print("\nCheck out card_analysis_result.html for the visualization!\n")


if __name__ == "__main__":
    main()
