# Auction_App
An auction application designed for managing and running badminton tournament auctions.

## Features & Web UI
- **Data Persistence:** All auction data is automatically saved and loaded from `auction_data.json`.
- **Dual Interface:** The application provides two web interfaces:
    1.  **Auctioneer Console (Host-Only):** Accessible only from the machine running the script, this interface allows for all state changes (making sales, undoing actions).
    2.  **Live Viewer Board (Read-Only):** Accessible on any device connected to the same local network, this interface displays the auction state in real-time without allowing any modifications.
- **Core Functionality:** Manages team assignments, player costs (in tokens), and maintains a complete log of all transactions.

## Installation
This project requires Python 3.x to run and uses Flask as a dependency. To install the necessary packages, run:
```bash
pip install flask
```

## Usage
To run the auction application, execute the main Python file from the project root:
```bash
python3 Auction_app.py
```
