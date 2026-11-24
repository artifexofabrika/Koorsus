# Arkiv

A private, on-premise document assistant for legal, medical, and professional offices.

Arkiv runs on a customer-owned appliance. It answers questions from the firm's own
documents, cites the source of every claim, and refuses when the answer is not in
the documents. No cloud, no subscription, no data leaving the office.

## What it is

- Flask web application on port 5001, HTTPS.
- Retrieval-augmented generation over a document estate: text, Markdown, PDF,
  DOCX, ODT.
- Hybrid retrieval (semantic + keyword, fused by reciprocal rank) over ChromaDB.
- Local LLM served via llama.cpp on port 8080.
- Every document is tagged with an uploader and a matter reference. The Ask page
  scopes retrieval to one matter, so a firm with a hundred active cases gets the
  right documents, not the closest match.
- Shared office PIN gates the front door. Password-manager compatible.

## What it does not do

- No cloud. No telemetry. No outbound connections.
- No subscription. The appliance is the product.
- No legal advice. It answers from documents and cites them.
- No case management, billing, drafting, or research databases.

## Hardware

NVIDIA Jetson Orin Nano 8GB (base tier). Orin NX 16GB for larger firms.
Same appliance, same software, different capacity.

## Install (developer)

    git clone https://github.com/artifexofabrika/arkiv.git
    cd arkiv
    cp config.example.py config.py
    # edit config.py: set SECRET_KEY and ARKIV_PIN
    python3 -m venv .venv
    . .venv/bin/activate
    pip install -r requirements.txt
    python app.py            # development, port 5001

For production, use the systemd unit and Gunicorn with TLS. See INSTALL.md.

## License

GPL v3. The customer owns the appliance and can inspect, modify, and run the
software without restriction. The consultancy sells the appliance, the
installation, and the maintenance, not the software license.

## Status

Version 0.1.0. Working on a demo corpus of two matters. Pre-customer-install.
Items remaining before a first commercial deployment: installation procedure,
backup and restore, per-user login tier.
