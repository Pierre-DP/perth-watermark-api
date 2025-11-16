#!/bin/bash
pip install -r requirements.txt
gunicorn app:app -b 0.0.0.0:$PORT --workers 2 --threads 2
