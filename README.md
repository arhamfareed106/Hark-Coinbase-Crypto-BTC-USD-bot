# Hark Coinbase Crypto BTC/USD Bot

## Description

This is an automated cryptocurrency trading bot designed to trade the BTC-USD pair on the Coinbase exchange. It utilizes the Coinbase Advanced Trade API, which supports lower fees for Coinbase One members.

The bot's core logic involves a backtesting phase where it analyzes historical price data to identify potentially profitable trading patterns. It then uses these identified patterns to execute trades in a live environment. The bot operates on a minutely cycle, continuously monitoring prices and executing strategies.

## Features

-   **Coinbase Advanced Trade API**: Connects securely using EC keys and HMAC signatures for the latest API.
-   **Strategy Backtesting**: Uses a `Cartesian_Trier` function to test numerous combinations of strategy parameters against historical price data from CSV files.
-   **Dynamic Strategy Selection**: Automatically enables trading models (e.g., `abcdthen_a_model`, `abcthen_model`) based on their backtested win rates.
-   **Live Trading**: Places market buy orders and attempts to place limit sell orders to secure profits. Includes fallback to market sell orders.
-   **Risk Management**:
    -   Trades a configurable percentage of the available USD balance (e.g., 5%).
    -   Automatically deactivates a trading strategy if its live win rate falls below a certain threshold (e.g., 60%).
    -   Includes a stop-loss mechanism to sell if the price drops significantly after a buy.
    -   Features a server slippage detector to monitor for execution issues.
-   **Data Persistence**: Fetches and stores historical price data in CSV files (`btc_hourly_prices_360days.csv`, `btc_minutely_prices_10days.csv`).
-   **Comprehensive Logging**: Logs all major actions, API calls, trades, and errors to `bot_log.txt` and the console.

## Prerequisites

-   Python 3.x
-   A Coinbase account with API access enabled.

## Setup

1.  **Install Dependencies**:
    Install the required Python packages. It's recommended to use a virtual environment.

    ```bash
    pip install -r requirements.txt
    ```

2.  **API Keys**:
    The bot requires an API key from Coinbase. Create a new API key with `trade` permissions for the desired wallet. The bot is configured to use EC keys.

    Create a file named `aknpk.json` in the same directory as the bot script. Paste your key details into this file using the following format:

    ```json
    {
      "name": "organizations/YOUR_ORG_ID/apiKeys/YOUR_API_KEY_ID",
      "privateKey": "-----BEGIN EC PRIVATE KEY-----\nYOUR_PRIVATE_KEY\n-----END EC PRIVATE KEY-----",
      "apiSecret": "YOUR_API_SECRET_FOR_ADVANCED_TRADE"
    }
    ```
    *Replace the placeholder values with your actual Coinbase API key information.*

3.  **Historical Data**:
    The bot uses two CSV files for backtesting: `btc_hourly_prices_360days.csv` and `btc_minutely_prices_10days.csv`. The script will create these files automatically if they do not exist. The bot will then populate them over time. For effective backtesting on the first run, you may want to pre-populate these files with historical data.

## Usage

1.  **Configure the Bot**:
    Open the `Hark Coinbase Crypto BTC USD bot.py` file and configure the main settings:
    -   `hourly_bot`: Set to `True` to run the hourly-data-based strategies.
    -   `minutely_bot`: Set to `True` to run the minutely-data-based strategies.
    -   `connect_run`: **This is the master switch.** Set to `True` to enable live trading with real funds. If `False`, the bot will run in a simulation mode without executing trades.

    ```python
    # Determine if this bot is hourly or minutely
    hourly_bot = True
    minutely_bot = False

    # ... later in the file ...

    # Set to True to enable live trading with Coinbase API
    connect_run = False # Set this to True to enable trading
    ```

2.  **Run the Bot**:
    Execute the script from your terminal:

    ```bash
    python "Hark Coinbase Crypto BTC USD bot.py"
    ```

    The bot will initialize, connect to the Coinbase API, run the backtesting strategies, and then enter the main trading loop if `connect_run` is enabled.

## Strategy Overview

The bot is built around a pattern-matching engine.

1.  **Increments Generation**: It first generates a list of numerical increments (e.g., 1.002, 1.004, etc.).
2.  **Cartesian Trier**: It then iterates through historical price data (A, B, C, D points). For each set of points, it tests thousands of combinations of the generated increments to see which conditions would have resulted in a "win" (price went up) or a "loss".
3.  **Model Viability**: The results are tallied. If a specific pattern (e.g., "ABCD rising lows") has a high win rate (e.g., >70%) over a large number of occurrences, its corresponding model is enabled for live trading.
4.  **Live Execution**: In the main loop, the bot checks if the current price action matches the conditions of any of the enabled models. If a match is found, it executes a trade.

## Disclaimer

This software is for educational purposes only. Trading cryptocurrency is highly volatile and carries a substantial risk of loss. The author is not a financial advisor. You are solely responsible for any and all trading decisions you make. Use this software at your own risk. Past performance is not indicative of future results.