"""Minimal Flask API wrapper for the acquisition engine."""
import os
import json
import logging
from flask import Flask, jsonify, request
from dotenv import load_dotenv

from src.config import get_config
from src.state_machine import StateMachine

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)


@app.route('/')
def health():
    """Health check endpoint."""
    return jsonify({
        "status": "acquisition-engine running",
        "version": "1.0.0",
        "region": os.getenv('TARGET_REGION', 'Cyberjaya')
    })


@app.route('/run', methods=['POST'])
def run_pipeline():
    """Trigger the acquisition pipeline."""
    import asyncio
    data = request.get_json() or {}
    region = data.get('region', os.getenv('TARGET_REGION', 'Cyberjaya'))
    keywords = data.get('keywords', ['cafe', 'restaurant', 'lounge'])
    
    logger.info(f"Running pipeline for {region} with keywords: {keywords}")
    
    try:
        # Run the actual pipeline
        config = get_config()
        
        async def execute():
            async with StateMachine(config) as sm:
                results = await sm.run(region=region, keywords=keywords)
                return results
        
        # Run async function in sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        results = loop.run_until_complete(execute())
        loop.close()
        
        return jsonify({
            "status": "success",
            "region": region,
            "keywords": keywords,
            "results_count": len(results) if results else 0,
            "message": f"Pipeline completed for {region}"
        })
    except Exception as e:
        logger.error(f"Pipeline error: {str(e)}")
        return jsonify({
            "status": "error",
            "error": str(e),
            "message": "Pipeline failed. Check logs for details."
        }), 500


@app.route('/proposals', methods=['GET'])
def get_proposals():
    """Get generated proposals."""
    proposals_dir = "output/proposals"
    proposals = []
    
    if os.path.exists(proposals_dir):
        for file in os.listdir(proposals_dir):
            if file.endswith('.json'):
                with open(os.path.join(proposals_dir, file), 'r') as f:
                    proposals.append(json.load(f))
    
    return jsonify({
        "status": "success",
        "proposals_count": len(proposals),
        "proposals": proposals
    })


@app.route('/status')
def status():
    """Get current status."""
    return jsonify({
        "status": "running",
        "config": {
            "region": os.getenv('TARGET_REGION', 'Cyberjaya'),
            "country": os.getenv('TARGET_COUNTRY', 'Malaysia'),
            "model": os.getenv('LLM_MODEL', 'gpt-4o-mini')
        }
    })


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
