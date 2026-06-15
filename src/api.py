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
    data = request.get_json() or {}
    region = data.get('region', os.getenv('TARGET_REGION', 'Cyberjaya'))
    keywords = data.get('keywords', ['cafe', 'restaurant', 'lounge'])
    
    logger.info(f"Running pipeline for {region} with keywords: {keywords}")
    
    # Return immediately since the pipeline takes time
    return jsonify({
        "status": "pipeline_triggered",
        "region": region,
        "keywords": keywords,
        "message": "Pipeline is running in background. Check logs for results."
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
