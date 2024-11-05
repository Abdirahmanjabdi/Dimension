import os
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone

# Set the API key
API_KEY = 'csjaib1r01qujq2aokugcsjaib1r01qujq2aokv0'  # Replace with your actual API key

# Define trading pairs and timeframe
TRADING_PAIRS = ['OANDA:GBP_USD']
TIMEFRAME = '1'  # in minutes

# Function to fetch data from Finnhub with error handling
def get_finnhub_data(symbol, start_date, end_date):
    url = f'https://finnhub.io/api/v1/forex/candle?symbol={symbol}&resolution={TIMEFRAME}&from={int(start_date.timestamp())}&to={int(end_date.timestamp())}&token={API_KEY}'
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raises HTTPError if the request fails
        data = response.json()

        # Verify response data structure
        if data.get('s') == 'ok':
            # Parse the data into a DataFrame
            df = pd.DataFrame({
                'time': pd.to_datetime(data['t'], unit='s', utc=True),
                'open': data['o'],
                'high': data['h'],
                'low': data['l'],
                'close': data['c']
            }).set_index('time')
            return df
        else:
            print(f"Error fetching data for {symbol}: {data.get('error', 'Unknown error')}")
            return pd.DataFrame()

    except requests.exceptions.RequestException as e:
        print(f"Request error for {symbol}: {e}")
        return pd.DataFrame()

# Function to identify market structure
def identify_market_structure(df):
    # Use a 15-minute resample for higher timeframe analysis
    higher_tf_trend = df['close'].resample('15min').ohlc().dropna()
    higher_tf_trend['direction'] = np.where(higher_tf_trend['close'] > higher_tf_trend['open'], 'up', 'down')

    # Define higher highs and lower lows in the lower timeframe
    lower_tf_structure = df[['high', 'low']].copy()
    lower_tf_structure['higher_high'] = (
        (lower_tf_structure['high'] > lower_tf_structure['high'].shift(1)) &
        (lower_tf_structure['high'] > lower_tf_structure['high'].shift(-1))
    )
    lower_tf_structure['lower_low'] = (
        (lower_tf_structure['low'] < lower_tf_structure['low'].shift(1)) &
        (lower_tf_structure['low'] < lower_tf_structure['low'].shift(-1))
    )

    return higher_tf_trend, lower_tf_structure

# Function to identify order blocks
def identify_order_blocks(df):
    return [
        {'price': df['high'].iloc[i], 'type': 'sell'} if df['high'].iloc[i] > max(df['high'].iloc[i-1], df['high'].iloc[i+1]) else
        {'price': df['low'].iloc[i], 'type': 'buy'} if df['low'].iloc[i] < min(df['low'].iloc[i-1], df['low'].iloc[i+1]) else None
        for i in range(1, len(df)-1)
    ]

# Function to detect liquidity inducements
def detect_liquidity_inducements(df):
    return [
        {'price': df['high'].iloc[i], 'type': 'sell'} if df['high'].iloc[i] > max(df['high'].iloc[i-1], df['high'].iloc[i+1]) else
        {'price': df['low'].iloc[i], 'type': 'buy'} if df['low'].iloc[i] < min(df['low'].iloc[i-1], df['low'].iloc[i+1]) else None
        for i in range(1, len(df)-1)
    ]

# Function to detect time-based manipulation within a session
def detect_time_based_manipulation(df, session):
    session_start, session_end = pd.to_datetime(session['start']).time(), pd.to_datetime(session['end']).time()
    session_data = df.between_time(session_start, session_end)

    return [
        {'price': session_data['high'].iloc[i], 'type': 'sell'} if session_data['high'].iloc[i] > max(session_data['high'].iloc[i-1], session_data['high'].iloc[i+1]) else
        {'price': session_data['low'].iloc[i], 'type': 'buy'} if session_data['low'].iloc[i] < min(session_data['low'].iloc[i-1], session_data['low'].iloc[i+1]) else None
        for i in range(1, len(session_data)-1)
    ]

# Function to calculate risk per trade
def calculate_risk(account_balance, risk_percentage=0.6):
    return account_balance * (risk_percentage / 100)

# Function to identify major liquidity zones
def identify_liquidity_zones(df):
    return [
        {'price': df['high'].iloc[i], 'type': 'sell'} if df['high'].iloc[i] > max(df['high'].iloc[i-1], df['high'].iloc[i+1]) else
        {'price': df['low'].iloc[i], 'type': 'buy'} if df['low'].iloc[i] < min(df['low'].iloc[i-1], df['low'].iloc[i+1]) else None
        for i in range(1, len(df)-1)
    ]

# Function to send alerts using webhook
def send_alert(opportunity):
    webhook_url = os.getenv('http://chief.hallow.tech/webhook')
    payload = {"text": f"Alert: {opportunity}"}

    try:
        response = requests.post(webhook_url, json=payload)
        response.raise_for_status()
        print(f"Alert sent: {opportunity}")
    except requests.exceptions.RequestException as e:
        print(f"Failed to send alert: {e}")

# Function for lower timeframe confirmation
def lower_timeframe_confirmation(df, higher_timeframe_zone):
    lower_tf_df = df.resample('5min').ohlc().dropna()

    for i in range(1, len(lower_tf_df)-1):
        if higher_timeframe_zone == 'sell' and (lower_tf_df['close'].iloc[i] < lower_tf_df['open'].iloc[i]).any():
            return True
        elif higher_timeframe_zone == 'buy' and (lower_tf_df['close'].iloc[i] > lower_tf_df['open'].iloc[i]).any():
            return True

    return False

# Main trading algorithm with backtesting for the last three months (July, August, and September)
def trading_algorithm():
    account_balance = 100000  # Example account balance

    # Define the start and end dates for backtesting (last three months: July, August, September)
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=90)

    for pair in TRADING_PAIRS:
        df = get_finnhub_data(pair, start_date, end_date)

        if not df.empty:
            # Identify market structure
            higher_tf_trend, lower_tf_structure = identify_market_structure(df)

            # Identify order blocks and liquidity inducements
            order_blocks = [ob for ob in identify_order_blocks(df) if ob]
            liquidity_inducements = [li for li in detect_liquidity_inducements(df) if li]

            # Detect time-based manipulation during trading hours
            trading_hours = {'start': '09:00', 'end': '16:00'}
            manipulations = [m for m in detect_time_based_manipulation(df, trading_hours) if m]

            # Identify major liquidity zones
            liquidity_zones = [lz for lz in identify_liquidity_zones(df) if lz]

            # Placeholder logic for lower timeframe confirmation and trade execution
            for ob in order_blocks:
                if lower_timeframe_confirmation(df, ob['type']):
                    risk_amount = calculate_risk(account_balance)
                    stop_loss_price = ob['price'] - 3 * 0.0001  # Assumed pip value
                    take_profit_price = ob['price'] + 5.33 * 3 * 0.0001

                    opportunity = {
                        'pair': pair,
                        'entry_price': ob['price'],
                        'stop_loss': stop_loss_price,
                        'take_profit': take_profit_price,
                        'risk_amount': risk_amount,
                        'confidence_level': 'High'
                    }

                    send_alert(opportunity)
                    print(f"Executing trade for {pair}: {opportunity}")

# Run the trading algorithm
if __name__ == "__main__":
    trading_algorithm()