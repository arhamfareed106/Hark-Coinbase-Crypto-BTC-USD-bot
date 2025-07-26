import shutil
import pandas as pd
import datetime
import time
import os
from collections import Counter
import json
import base64
import hashlib
import hmac
import requests
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import ec, utils
from cryptography.hazmat.backends import default_backend
import http
import http.client
import logging

# Configure logging
"""
"""


# Determine if this bot is hourly or minutely DIFFERENTLY from whether None, whether False, as conditions diffable for. 
hourly_bot = None # None as default, instead of False, which is for offing and panic selling 100%
minutely_bot = None # None as default, instead of false, which is for offing the bot, and panic selling 100%


"""
json details from the other coder can be pasted here. below
"""


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot_log.txt"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("CoinbaseBot")

# Configure logging


# CoinbaseECAuth class (previously in coinbase_ec_auth.py)
class CoinbaseECAuth:
    def __init__(self, json_key_path):
        # Load the EC key from JSON file
        with open(json_key_path, 'r') as f:
            key_data = json.load(f)
        
        self.api_key_id = key_data['name'].split('/')[-1]
        self.private_key_str = key_data['privateKey']
        self.api_secret = key_data.get('apiSecret', '')
        
        # Parse the EC private key
        self.private_key = serialization.load_pem_private_key(
            self.private_key_str.encode(),
            password=None,
            backend=default_backend()
        )
        
        # Advanced Trade API endpoints
        self.base_url = 'https://api.coinbase.com'
        self.advanced_url = 'https://api.coinbase.com/api/v3/brokerage'
        
    

    def _sign_request(self, method, path, body=''):
        timestamp = str(int(time.time()))
        message = timestamp + method + path + (body if body else '')
        
        # Create a hash of the message
        digest = hashlib.sha256(message.encode()).digest()
        
        # Sign the hash with EC key
        signature = self.private_key.sign(
            digest,
            ec.ECDSA(hashes.SHA256())
        )
        
        # Convert signature to base64
        signature_b64 = base64.b64encode(signature).decode()
        
        return {
            'CB-ACCESS-KEY': self.api_key_id,
            'CB-ACCESS-SIGN': signature_b64,
            'CB-ACCESS-TIMESTAMP': timestamp,
            'Content-Type': 'application/json'
        }
        
    
    def _sign_advanced_request(self, method, path, body=''):
        """Sign requests for Advanced Trade API"""
        timestamp = str(int(time.time()))
        
        # For Advanced Trade API
        message = timestamp + method + path + (body if body else '')
        
        # Create a hash of the message
        hmac_key = base64.b64decode(self.api_secret)
        signature = hmac.new(hmac_key, message.encode(), hashlib.sha256)
        signature_b64 = base64.b64encode(signature.digest()).decode()
        
        return {
            'CB-ACCESS-KEY': self.api_key_id,
            'CB-ACCESS-SIGN': signature_b64,
            'CB-ACCESS-TIMESTAMP': timestamp,
            'Content-Type': 'application/json'
        }
    
    
    def get(self, url, params=None, advanced=False):
        path = url.split('api.coinbase.com')[-1]
        if advanced:
            headers = self._sign_advanced_request('GET', path)
        else:
            headers = self._sign_request('GET', path)
        return requests.get(url, headers=headers, params=params
        
    
    def post(self, url, data=None, advanced=False):
        path = url.split('api.coinbase.com')[-1]
        body = json.dumps(data) if data else ''
        if advanced:
            headers = self._sign_advanced_request('POST', path, body)
        else:
            headers = self._sign_request('POST', path, body)
        return requests.post(url, headers=headers, json=data)
    

    # Coinbase API wrapper methods
    def get_time(self, epoch=False):
        response = self.get(f'{self.base_url}/v2/time')
        data = response.json()['data']
        if epoch:
            return int(time.mktime(time.strptime(data['iso'], "%Y-%m-%dT%H:%M:%SZ")))
        return data
        
    
    def get_spot_price(self, currency_pair='BTC-USD'):
        response = self.get(f'{self.base_url}/v2/prices/{currency_pair}/spot')
        return float(response.json()['data']['amount'])
    
    def get_buy_price(self, currency_pair='BTC-USD'):
        response = self.get(f'{self.base_url}/v2/prices/{currency_pair}/buy')
        return float(response.json()['data']['amount'])
    
    def get_sell_price(self, currency_pair='BTC-USD'):
        response = self.get(f'{self.base_url}/v2/prices/{currency_pair}/sell')
        return float(response.json()['data']['amount'])
    
    def get_account_balance(self, currency='USD'):
        """Get account balance for a specific currency"""
        response = self.get(f'{self.base_url}/v2/accounts')
        accounts = response.json()['data']
        
        for account in accounts:
            if account['currency']['code'] == currency:
                return float(account['balance']['amount'])
        
        return 0.0
    
    
    
    def place_market_order(self, product_id, side, funds=None, size=None):
        """Place market order using Advanced Trade API (supports Coinbase One zero fees)"""
        data = {
            "client_order_id": int(time.time() * 1000)),
            "product_id": product_id,
            "side": side,
            "order_configuration": {
                "market_market_ioc": {}
            }
        }
        
        if side == 'buy' and funds:
            data["order_configuration"]["market_market_ioc"] = {"quote_size": (funds)}
        elif side == 'sell' and size:
            data["order_configuration"]["market_market_ioc"] = {"base_size": (size)}
        
        response = self.post(f'{self.advanced_url}/orders', data, advanced=True)
        return response.json()
        
        
        
    def place_limit_order(self, product_id, side, price, size):
        """Place limit order using Advanced Trade API (supports Coinbase One zero fees)"""
        data = {
            "client_order_id": (int(time.time() * 1000)),
            "product_id": product_id,
            "side": side,
            "order_configuration": {
                "limit_limit_gtc": {
                    "base_size": (size),
                    "limit_price": (price),
                    "post_only": False
                }
            }
        }
        
        response = self.post(f'{self.advanced_url}/orders', data, advanced=True)
        return response.json()
        
        
        
    def cancel_order(self, order_id):
        """Cancel order using Advanced Trade API"""
        data = {
            "order_ids": [order_id]
        }
        response = self.post(f'{self.advanced_url}/orders/batch_cancel', data, advanced=True)
        return response.json() 


# Coinbase API info setups

"""

"""


# Initialize perf_counter variables for timing
last_time_check = time.perf_counter()
minute_counter = time.perf_counter()
# One for below the bottom row 1m sleep maker


# Initialize our custom Coinbase client with EC key
logger.info("Initializing Coinbase API client...")
client = CoinbaseECAuth('aknpk.json')



# Check if CSV data files exist, create empty ones if not
if not os.path.exists('btc_hourly_prices_360days.csv'):
    pd.DataFrame().to_csv('btc_hourly_prices_360days.csv', header=False, index=False)
    logger.info("Created empty btc_hourly_prices_360days.csv file")

if not os.path.exists('btc_minutely_prices_10days.csv'):
    pd.DataFrame().to_csv('btc_minutely_prices_10days.csv', header=False, index=False)
    logger.info("Created empty btc_minutely_prices_10days.csv file")


# Test API connection
try:
    current_time = client.get_time()
    logger.info(f"Successfully connected to Coinbase API. Server time: {current_time['iso']}")
    
    spot_price = client.get_spot_price()
    logger.info(f"Current BTC-USD spot price: ${spot_price}")
except Exception as e:
    logger.error(f"Failed to connect to Coinbase API: {e}")
    raise
    
    


"""
Task. Coinbase API basics
"""

# Coinbase API helper functions
def coinbase_market_buy(amount_usd):
    """Place a market buy order for BTC using USD amount"""
    try:
        logger.info(f"Placing market buy order for ${amount_usd} of BTC")
        result = client.place_market_order(product_id='BTC-USD', side='buy', funds=(amount_usd))
        logger.info(f"Buy order result: {result}")
        return result
    except Exception as e:
        logger.error(f"Market buy error: {e}")
        return None
        

def coinbase_market_sell(btc_amount):
    """Place a market sell order for BTC"""
    try:
        logger.info(f"Placing market sell order for {btc_amount} BTC")
        result = client.place_market_order(product_id='BTC-USD', side='sell', size=(btc_amount))
        logger.info(f"Sell order result: {result}")
        return result
    except Exception as e:
        logger.error(f"Market sell error: {e}")
        return None


def coinbase_limit_sell(btc_amount, price):
    """Place a limit sell order for BTC"""
    try:
        logger.info(f"Placing limit sell order for {btc_amount} BTC at price ${price}")
        result = client.place_limit_order(product_id='BTC-USD', side='sell', price=(price), size=(btc_amount))
        logger.info(f"Limit sell order result: {result}")
        return result
    except Exception as e:
        logger.error(f"Limit sell error: {e}")
        return None
        

def cancel_order_after_timeout(order_id, timeout=120): # 2m
    """Cancel an order after specified timeout"""
    try:
        logger.info(f"Waiting {timeout} seconds before cancelling order {order_id}")
        time.sleep(timeout)
        result = client.cancel_order(order_id)
        logger.info(f"Cancel order result: {result}")
        return True
    except Exception as e:
        logger.error(f"Cancel order error: {e}")
        return False


def get_btc_balance():
    """Get current BTC balance"""
    try:
        balance = client.get_account_balance('BTC')
        logger.info(f"Current BTC balance: {balance}")
        return balance
    except Exception as e:
        logger.error(f"Error getting BTC balance: {e}")
        return 0.0

def get_usd_balance():
    """Get current USD balance"""
    try:
        balance = client.get_account_balance('USD')
        logger.info(f"Current USD balance: {balance}")
        return balance
    except Exception as e:
        logger.error(f"Error getting USD balance: {e}")
        return 0.0

# Calculate trade amount (5% of USD balance)
def calculate_trade_amount():
    usd_balance = get_usd_balance()
    trade_amount = usd_balance * 0.05
    logger.info(f"Calculated trade amount: ${trade_amount} (5% of ${usd_balance})")
    return trade_amount

#Calculate BTC amount to sell (100% of what was bought)
def calculate_sell_amount(bought_amount_usd, bought_price):
    btc_amount = bought_amount_usd / bought_price
    logger.info(f"Calculated sell amount: {btc_amount} BTC")
    return btc_amount




# Overview of the projected plan, and procedural notes. This part is actually already done. 
"""
From here, pre-generated numerical increments are made to be referrable as existing list values, so the for for cartesian may try alternate combinations
to imported csv based price history data of hourly, 180 days, and for the other list, minutely, 10 days, to attempt as if brute force guesses, 
to figure and record wins and losses scenarios, to determine the likely variables afterwards, in sets of price relations, by doing this as the back-testing,

and, using one-minutely API requesting mode, anyway, despite hourly data, to keep track as live, instead of waiting another hour, from ABCD's C point.

To do this, my cartesian for loops nest must become applied to the iterable list of price history from the csv, a list made to be referrable with read mode, 
Per each index position, the index position-sensitive code parts will scan through and auto-try (here, after), switching many variables, per index position, before moving onto the next
And, of those, the correct variables will match with the real history, and from the recordings of those scenarios and their variables, the accurate, usable ranges 
will be determined for making my buy conditions with. 

The ten-setted group sorting and list passing of letter variables for discovering the "common" occurred ranges of win-scenario price activity relations, will become useful 
"""

"""
Task Control+F find "Task" 
"""
# Simply answer annotations where I marked with "Task", use Control+Find to find them. Few.
# perf counter set up to not conflict with bottom row's 1m sleep 
# Write in Coinbase-fit API commands which request for current_time (server_time), price at get-moment, limit sell, spot sell, spot buy, limit buy, 5% of wallet, 100% sell, timed.
# It'll record get-moment-price at xyz moment(s), and then, by using math, use the remaining logics written, thereafter, while recording times and prices, as it runs, minutely. 
# Needing a few hours to start bidding, after starting the bot; fine. 
# One coin, one bot, likely, one strategy per bot. I'll just run many instances of the same bot, and manually choose a few factors, each. 

"""

"""




# Currency pairs decision
BTC_USD = 'BTC-USD'

# The function of getting the current time
def server_time():
    """Get current server time from Coinbase API in epoch format"""
    try:
        server_time = client.get_time(epoch=True)  # epoch form gives a simple number
        return server_time
    except Exception as e:
        logger.error(f"Error getting server time: {e}")
        return int(time.time())  # Fallback to local time
    
        
        # Initialize server time
    try:
        server_time_value = server_time()
        logger.info(f"Server time initialized: {server_time_value}")
    except Exception as e:
        server_time_value = int(time.time())
        logger.error(f"Failed to get server time, using local time: {server_time_value}")



def server_buy_price():
    """Get current buy price from Coinbase API"""
    try:
        price = client.get_buy_price(currency_pair='BTC-USD')
        logger.info(f"Current buy price: ${price}")
        return price
    except Exception as e:
        logger.error(f"Error getting buy price: {e}")
        return None

    try:
        server_buy_price_value = server_buy_price()
    except Exception as e:
        server_buy_price_value = None
        logger.error(f"Failed to initialize buy price: {e}")
        



def server_sell_price():
    """Get current sell price from Coinbase API"""
    try:
        price = client.get_sell_price(currency_pair='BTC-USD')
        logger.info(f"Current sell price: ${price}")
        return price
    except Exception as e:
        logger.error(f"Error getting sell price: {e}")
        return None
        
    try:
        server_sell_price_value = server_sell_price()
    except Exception as e:
        server_sell_price_value = None
        logger.error(f"Failed to initialize sell price: {e}")




def server_spot_price():
    """Get current spot price from Coinbase API"""
    try:
        price = client.get_spot_price(currency_pair='BTC-USD')
        logger.info(f"Current spot price: ${price}")
        return price
    except Exception as e:
        logger.error(f"Error getting spot price: {e}")
        return None
        
    try:
        server_spot_price_value = server_spot_price()
    except Exception as e:
        server_spot_price_value = None
        logger.error(f"Failed to initialize spot price: {e}")


"""
"""
# Import, input the csv price histories by hours. 
# Task 
csv_imported_price_history_hourly = [] # 180 days 

# Import, input the csv price histories by minutely
# Task
csv_imported_price_history_minutely = [] # Get amount for 10 days, not 180 days


# This crypto bot will still react minutely, no matter which mode of data scanning was used.
# The bottom row is using a 1 minute sleeper. 



# Import, input the csv price histories by hours. 
# Task . Check if right.
try:
    csv_imported_price_history_hourly = pd.read_csv('btc_hourly_prices_360days.csv', header=None)
    if not csv_imported_price_history_hourly.empty:
        csv_imported_price_history_hourly = csv_imported_price_history_hourly[0].tolist()
    else:
        csv_imported_price_history_hourly = []
    logger.info(f"Loaded hourly price history: {len(csv_imported_price_history_hourly)} entries")
except Exception as e:
    csv_imported_price_history_hourly = [] # Fallback to empty list if file not found or error
    logger.error(f"Error loading hourly price history: {e}")




# Import, input the csv price histories by minutely
# Task . Check if right.
try:
    csv_imported_price_history_minutely = pd.read_csv('btc_minutely_prices_10days.csv', header=None)
    if not csv_imported_price_history_minutely.empty:
        csv_imported_price_history_minutely = csv_imported_price_history_minutely[0].tolist()
    else:
        csv_imported_price_history_minutely = []
    logger.info(f"Loaded minutely price history: {len(csv_imported_price_history_minutely)} entries")
except Exception as e:
    csv_imported_price_history_minutely = [] # Fallback to empty list if file not found or error
    logger.error(f"Error loading minutely price history: {e}")




# Save current price to CSV files for historical data
def update_price_history():
    """Update price history CSV files with current price"""
    current_spot = server_spot_price()
    if current_spot is not None:
        # Update hourly file if it's a new hour
        now = datetime.datetime.now()
        if now.minute == 0:
            try:
                with open('btc_hourly_prices_360days.csv', 'a') as f:
                    f.write(f"{current_spot}\n")
                logger.info(f"Added hourly price ${current_spot} to history")
            except Exception as e:
                logger.error(f"Error updating hourly price history: {e}")
        
        # Update minutely file
        try:
            with open('btc_minutely_prices_10days.csv', 'a') as f:
                f.write(f"{current_spot}\n")
            logger.info(f"Added minutely price ${current_spot} to history")
        except Exception as e:
            logger.error(f"Error updating minutely price history: {e}")
            
        # Trim minutely file to keep only last 10 days (14400 minutes)
        try:
            minutely_data = pd.read_csv('btc_minutely_prices_10days.csv', header=None)
            if len(minutely_data) > 14400:
                minutely_data = minutely_data.tail(14400)
                minutely_data.to_csv('btc_minutely_prices_10days.csv', header=False, index=False)
                logger.info("Trimmed minutely price history to 10 days")
        except Exception as e:
            logger.error(f"Error trimming minutely price history: {e}")



# Setting up variables for below use, if/as needed for relations of price activity referencing
aprice = None
bprice = None
cprice = None
dprice = None
eprice = None
# In the above-est for loop, the index positions in it can be set with the variables above to reference to each needed index position, as the for loop iterates.


# Some of these may not be used, optionally, depending on model strategy referred by using these variables
ax = 0
axx = 0

bx = 0
bxx = 0

cx = 0
cxx = 0

dx = 0
dxx = 0

dc = 0
cd = 0

bc = 0
cb = 0

ba = 0
ab = 0

ac = 0


# Lists to pre-generate incremental numerical values into, positioned by index [], to iter through alternative combinations

axlist = []
axxlist = []

bxlist = []
bxxlist = []

cxlist = []
cxxlist = []

dxlist = []
dxxlist = []

dclist = []
cdlist = []

bclist = []
cblist = []

balist = []
ablist = []

aclist = []


def Increments_Generator():
    
    for i in range(30): # Numerical generator for the sake of making numerical increments
        axvalue += 0.002
        axvalue.extend(axlist)
    
        axxvalue += 0.002
        axxvalue.extend(axxlist)
        
        bxvalue += 0.002
        bxvalue.extend(bxlist)
        
        bxxvalue += 0.002
        bxxvalue.extend(bxxlist)
        
        cxvalue += 0.002
        cxvalue.extend(cxlist)
        
        cxxvalue += 0.002
        cxxvalue.extend(cxxlist)

        dxvalue += 0.002
        dxvalue.extend(dxlist)
        
        dxxvalue += 0.002
        dxxvalue.extend(dxxlist)
        
        abvalue += 0.002
        abvalue.extend(ablist)
        
        acvalue += 0.002
        acvalue.extend(aclist)
        
        bavalue += 0.002
        bavalue.extend(balist)
        
        bcvalue += 0.002
        bcvalue.extend(bclist)

        dcvalue += 0.002
        dcvalue.extend(dclist)
        
        cbvalue += 0.002
        cbvalue.extend(cblist)


        # Used for hourly result price mark
        cdvalue += 0.002
        cdvalue.extend(cdlist)
        
        
Increments_Generator()
    
    

"""
Kept as a list of references
"""
# Current time to compare and calculate bought_time time gap.  
# Task. Check if right.
# Make these work for Coinbase setups above. Most likely fine.
current_time = server_time_value  # Already using value

price_now = server_spot_price_value  # Use value

current_price = server_spot_price_value  # Use value

bought_time = server_time_value  # Use value

bought_price = server_spot_price_value  # Use value

sold_time = server_time_value  # Use value

sold_price = server_spot_price_value  # Use value

time_now = server_time_value  # Use value

"""
Kept as a list of references
"""

# For collection of groups of ten for counting and processing model wins, after getting csv based records wins vs losses of scenarios in alternate combos.

# Hourly list
abcd_then_a_model = [] # Not to be confused with abcdthen_a_model binary variable 

abc_then_model = []

dropped_abc_then_model = []

ab_then_model = []

dropped_ab_then_model = []
# Hourly list


"""

"""


# Minutely lists
aspike_then_model = []

# Minutely lists


"""
The above is for processing the recorded wins and losses data, after the for for nested cartesian loops figured vs actual price history, using variable increments to test strategy
"""

# Hourly lists


wins_risinglows_abcd = [] 
losses_risinglows_abcd = []
totalcount_abcd = len(wins_risinglows_abcd) + len(losses_risinglows_abcd)


wins_rising_abc = []
losses_rising_abc = []
totalcount_abc = len(wins_rising_abc) + len(losses_rising_abc)


dropped_wins_rising_abc = []
dropped_losses_rising_abc = []
totalcount_dropped_abc = len(dropped_wins_rising_abc) + len(dropped_losses_rising_abc)


wins_rising_ab = []
losses_rising_ab = []
totalcount_ab = len(wins_rising_ab) + len(losses_rising_ab)


dropped_wins_rising_ab = []
dropped_losses_rising_ab = []
totalcount_dropped_ab = len(dropped_wins_rising_ab) + len(dropped_losses_rising_ab)


# Hourly lists

"""
"""

# Minutely lists


wins_rising_aspike = []
losses_rising_aspike = []
totalcount_aspike = len(wins_rising_aspike) + len(losses_rising_aspike)


# Minutely lists

"""
"""

# Alternating incremental variables to be combination-tried as if a per-each by each every, an orderly shuffle, not needing order for it to have tried, to guess patterns with.
def Cartesian_Trier(): # I only need to copy paste this into a new def, and change up just enough, for the minutely, "version" of this exact.

    # Must have filled this within-file list with the gotten csv readable, even if in the same correct folder.
    for i, indexposition in enumerate(csv_imported_price_history_hourly): # Task, make this variable list match to use the csv reader
        if i + 3 >= len(csv_imported_price_history_hourly):
            break # Prevent index out of range errors
        
        aprice = [indexposition+0] #i
        bprice = [indexposition+1]
        cprice = [indexposition+2]
        dprice = [indexposition+3] # i+3
        
        # For now, eprice will only be for result price, in actual trades.
        
        # abcd, bcde, cdef, in this pattern, as the for loop iterates one by one in the price history list.
        # With no changes to the index positions of 1,2,3,4 for the price history list, while applying axx, bx, etc, on the side.
        
        a = aprice
        b = bprice
        c = cprice
        d = dprice   
      
        
        # Orders of these will not directly affect the referenced index positions of the above for loop iteration, for price history scans
        # Similar to mentally applying each conditions onto each index position, in abcd, bcde, cdef mode. 
        # It auto-tries every of these, before moving onto the next try, while still maintaining the index positions referred as 1,2,3,4 for real prices past-occurred
        
        
        for ax in axlist: # 
            for axx in axxlist: # 
                for ac in aclist: # 
                    for bx in bxlist: # 
                        for bxx in bxxlist: # 
                            for cd in cdlist: # 
                                
                                
                                # abcd strategy targeting for when c is higher than a, rising low points, and then a rise. 
                                
                                # Incremental variables must have been 1.00x, not 0.00x
                                if a < b and b >= 1+ax * a and b <= 1+axx * a and b <= 1+bxx * c and c > a * 1+ac and b >= 1+bx * c and d >= 1+cd * c:
                                   
                                    # At that correct moment where real price history matches these conditions
                                    wins_risinglows_abcd.extend(a, 1+ax, b, 1+axx, c, 1+ac, 1+bx, 1+bxx, 1+cd, d)

                                   
                                    
                                if a < b and b >= 1+ax * a and b <= 1+axx * a and b <= 1+bxx * c and c > a * 1+ac and b >= 1+bx * c and d < 1+cd * c: 
                                    
                                    # At that correct moment where real price history matches these conditions
                                    losses_risinglows_abcd.extend(a, 1+ax, b, 1+axx, c, 1+ac, 1+bx, 1+bxx, 1+cd, d)
                                    
                                    
                                 """
                                 """
                                
                                
                                # abc1 strategy targeting for when a price drop occurred, and then a rise. 
                                if a > b and b >= 1+ax * a and b <= 1+axx * a and b <= 1+bxx * c and c >= b * 1+cd:
                                    
                                    dropped_wins_risinglows_abc.extend(a, 1+ax, b, 1+axx, c, 1+ac, 1+bx, 1+bxx, 1+cd)
                                
                                
                              
                                
                                
                                # abc1 # Sets of 9
                                if a > b and b >= 1+ax * a and b <= 1+axx * a and b <= 1+bxx * c and c < b * 1+cd:
                                    
                                    dropped_losses_risinglows_abc.extend(a, 1+ax, b, 1+axx, c, 1+ac, 1+bx, 1+bxx, 1+cd)
                                
                                
                                """
                                
                                """
                                
                                # sets of six
                                # abc and then. 
                                if a < b and b >= 1+ax * a and b <= 1+axx * a and c >= b * 1+cd:
                                
                                    wins_risinglows_abc.extend(a, 1+ax, b, 1+axx, c, 1+cd)
                                
                                
                                
                                if a < b and b >= 1+ax * a and b <= 1+axx * a and c < b * 1+cd:
                                
                                    losses_risinglows_abc.extend(a, 1+ax, b, 1+axx, c, 1+cd)
                                
                                
                                """
                                """
                                
                               
                                # sets of five
                                # ab and then. 
                                if a < b and b >= 1+ax * a and c >= b * 1+cd:
                                
                                    wins_risinglows_ab.extend(a, 1+ax, b, c, 1+cd)
                                
                                
                                
                                
                                if a < b and b >= 1+ax * a and c < b * 1+cd:
                                
                                    losses_risinglows_ab.extend(a, 1+ax, b, c, 1+cd)
                                    
                                    
                                    
                                """
                                """                                
                                    
                                
                                # sets of five
                                # ab and then. Dropped price version
                                if a > b and b <= 1+ax * a and c >= b * 1+cd:
                                
                                    dropped_wins_risinglows_ab.extend(a, 1+ax, b, c, 1+cd)
                                
                                
                                
                                
                                if a > b and b <= 1+ax * a and c < b * 1+cd:
                                
                                    dropped_losses_risinglows_ab.extend(a, 1+ax, b, c, 1+cd)    
                                    
                                
                                """
                                """
                                
    

                                
                          
# Making a variable to refer to the def here
cartesian_trier = Cartesian_Trier()




def wins_count_lister():

    for eachiterationpoint in wins_rising_ab:
        
        iterpoint = int(eachiterationpoint) # Integer number form of the resulting index position of the for loop iter reference position as it goes
        
        first_place = [0] # iter-er goes one by one, the rest of actual variables here that matter to count in group sets of 5
        second_place = [1] # + ten positions counting is coded below, for these index positions to properly change according to ifs, as the for loop goes
        third_place = [2]
        fourth_place = [3]
        fifth_place = [4]
        
        
        # For groups of five
        if iterpoint == 0: #
            ab_then_model.append(first_place) 
            ab_then_model.append(second_place)
            ab_then_model.append(third_place)
            ab_then_model.append(fourth_place)
            ab_then_model.append(fifth_place)
            
        
        iter_count = 0 # Does not auto-increase per for loop iteration
        
        
        if iterpoint == iter_count + 5: # Meaning iteration reached 6th position
            iter_count += 5 # 
        
        
        if iter_count += 5: # Each time this point addition counting occurs from tracking the iterpoint, that will be when the referred index positions will be appended for. 
            
            # Update their referred index position as the iteration goes to 6th, iter count updates from that as a reaction, then append that one set, wait. 
            first_place [+=5]
            second_place [+=5]
            third_place [+=5]
            fourth_place [+=5]
            fifth_place [+=5]
          
            
            # The "waited" set of x number, wait until next trigger by above conditions. Not bcde, not cdef, 
            ab_then_model.append(first_place) 
            ab_then_model.append(second_place)
            ab_then_model.append(third_place)
            ab_then_model.append(fourth_place)
            ab_then_model.append(fifth_place)
            
        #
        #
        
    for eachiterationpoint in dropped_wins_rising_ab:
    
        iterpoint = int(eachiterationpoint) # Integer number form of the resulting index position of the for loop iter reference position as it goes
        
        first_place = [0] # iter-er goes one by one, the rest of actual variables here that matter to count in group sets of 5
        second_place = [1] # + ten positions counting is coded below, for these index positions to properly change according to ifs, as the for loop goes
        third_place = [2]
        fourth_place = [3]
        fifth_place = [4]
        
        
        # For groups of five
        if iterpoint == 0: #
            dropped_ab_then_model.append(first_place) 
            dropped_ab_then_model.append(second_place)
            dropped_ab_then_model.append(third_place)
            dropped_ab_then_model.append(fourth_place)
            dropped_ab_then_model.append(fifth_place)
            
        
        iter_count = 0 # Does not auto-increase per for loop iteration
        
        
        if iterpoint == iter_count + 5: # Meaning iteration reached 6th position
            iter_count += 5 # 
        
        
        if iter_count += 5: # Each time this point addition counting occurs from tracking the iterpoint, that will be when the referred index positions will be appended for. 
            
            # Update their referred index position as the iteration goes to 6th, iter count updates from that as a reaction, then append that one set, wait. 
            first_place [+=5]
            second_place [+=5]
            third_place [+=5]
            fourth_place [+=5]
            fifth_place [+=5]
          
            
            # The "waited" set of x number(s), then, waits until next trigger by above conditions. Not bcde, not cdef, 
            dropped_ab_then_model.append(first_place) 
            dropped_ab_then_model.append(second_place)
            dropped_ab_then_model.append(third_place)
            dropped_ab_then_model.append(fourth_place)
            dropped_ab_then_model.append(fifth_place)
            
        #
        #

    # Sets of six, not five, for this one
    for eachiterationpoint in wins_rising_abc:
    
        iterpoint = int(eachiterationpoint) # Integer number form of the resulting index position of the for loop iter reference position as it goes
        
        first_place = [0] # iter-er goes one by one, the rest of actual variables here that matter to count in group sets of 6
        second_place = [1] # + ten positions counting is coded below, for these index positions to properly change according to ifs, as the for loop goes
        third_place = [2]
        fourth_place = [3]
        fifth_place = [4]
        sixth_place = [5]
        
        
        # For groups of six
        if iterpoint == 0: #
            abc_then_model.append(first_place) 
            abc_then_model.append(second_place)
            abc_then_model.append(third_place)
            abc_then_model.append(fourth_place)
            abc_then_model.append(fifth_place)
            abc_then_model.append(sixth_place)
            
        
        iter_count = 0 # Does not auto-increase per for loop iteration
        
        
        if iterpoint == iter_count + 6: # Meaning iteration reached 6th position
            iter_count += 6 # 
        
        
        if iter_count += 6: # Each time this point addition counting occurs from tracking the iterpoint, that will be when the referred index positions will be appended for. 
            
            # Update their referred index position as the iteration goes to 7th, iter count updates from that as a reaction, then append that one set, wait. 
            first_place [+=6]
            second_place [+=6]
            third_place [+=6]
            fourth_place [+=6]
            fifth_place [+=6]
            sixth_place [+=6]
          
            
            # The "waited" set of x number, wait until next trigger by above conditions. Not bcde, cdef, 
            abc_then_model.append(first_place) 
            abc_then_model.append(second_place)
            abc_then_model.append(third_place)
            abc_then_model.append(fourth_place)
            abc_then_model.append(fifth_place)
            abc_then_model.append(sixth_place)
            
        #
        #    
        
    # Sets of nine    
    for eachiterationpoint in dropped_wins_rising_abc:
    
        iterpoint = int(eachiterationpoint) # Integer number form of the resulting index position of the for loop iter reference position as it goes
        
        first_place = [0] # iter-er goes one by one, the rest of actual variables here that matter to count in group sets of 9
        second_place = [1] # + ten positions counting is coded below, for these index positions to properly change according to ifs, as the for loop goes
        third_place = [2]
        fourth_place = [3]
        fifth_place = [4]
        sixth_place = [5]
        seventh_place = [6]
        eighth_place = [7]
        ninth_place = [8]
      
        
        
        # For groups of nine
        if iterpoint == 0: #
            dropped_abc_then_model.append(first_place) 
            dropped_abc_then_model.append(second_place)
            dropped_abc_then_model.append(third_place)
            dropped_abc_then_model.append(fourth_place)
            dropped_abc_then_model.append(fifth_place)
            dropped_abc_then_model.append(sixth_place)
            dropped_abc_then_model.append(seventh_place)
            dropped_abc_then_model.append(eighth_place)
            dropped_abc_then_model.append(ninth_place)
            
        
        iter_count = 0 # Does not auto-increase per for loop iteration's default auto-right [i]
        
        
        if iterpoint == iter_count + 9: # Meaning iteration reached 6th position
            iter_count += 9 # 
        
        
        if iter_count += 9: # Each time this point addition counting occurs from tracking the iterpoint, that will be when the referred index positions will be appended for. 
            
            # Update their referred index position as the iteration goes to 10th, iter count updates from that as a reaction, then append that one set, wait. 
            first_place [+=9]
            second_place [+=9]
            third_place [+=9]
            fourth_place [+=9]
            fifth_place [+=9]
            sixth_place [+=9]
            seventh_place [+=9]
            eighth_place [+=9]
            ninth_place [+=9]
          
            
            # The "waited" set of x number, wait until next trigger by above conditions. Not bcde, cdef, 
            dropped_abc_then_model.append(first_place) 
            dropped_abc_then_model.append(second_place)
            dropped_abc_then_model.append(third_place)
            dropped_abc_then_model.append(fourth_place)
            dropped_abc_then_model.append(fifth_place)
            dropped_abc_then_model.append(sixth_place)
            dropped_abc_then_model.append(seventh_place)
            dropped_abc_then_model.append(eighth_place)
            dropped_abc_then_model.append(ninth_place)
            
        # abc dropped model above, sets of 9
        

    
    for eachiterationpoint in wins_risinglows_abcd: # Every iteration move right 1 more index position must instead count for groups of actual NEXT ten, NOT iter each like bced, cedf.
        
        # In wins risinglows abcd, this part will count in sets of ten.
        
        """
        Other lists in this def, the count shall be NOT in sets of ten. 
        """
        
        # The for loop will still normally iterate through itself, as a defaultive one by one to the right.
        iterpoint = int(eachiterationpoint) # Integer number form of the resulting index position of the for loop iter reference position as it goes
        
        first_place = [0] # iter-er goes one by one, the rest of actual variables here that matter to count in group sets of 10
        second_place = [1] # + ten positions counting is coded below, for these index positions to properly change according to ifs, as the for loop goes
        third_place = [2]
        fourth_place = [3]
        fifth_place = [4]
        sixth_place = [5]
        seventh_place = [6]
        eighth_place = [7]
        ninth_place = [8]
        tenth_place = [9]
        
        # Pass groups of ten then, into abcd_then_a_model list for usable range pattern finding. 
        if iterpoint == 0: # Which will be once, and then waited by this if condition, instead of constantly appending per iter until eleventh position is reached. 
            abcd_then_a_model.append(first_place) 
            abcd_then_a_model.append(second_place)
            abcd_then_a_model.append(third_place)
            abcd_then_a_model.append(fourth_place)
            abcd_then_a_model.append(fifth_place)
            abcd_then_a_model.append(six_place)
            abcd_then_a_model.append(seventh_place)
            abcd_then_a_model.append(eighth_place)
            abcd_then_a_model.append(ninth_place)
            abcd_then_a_model.append(tenth_place)
         
        
        iter_count = 0 # Does not auto-increase per for loop iteration
        
        
        if iterpoint == iter_count + 10: # Meaning iteration reached 11th position
            iter_count += 10 # While iterpoint is at 21st position, saying integer 20 numerical value, itercount will then become 20, unreactive until 30 30. 
        
        
        if iter_count += 10: # Each time this point addition counting occurs from tracking the iterpoint, that will be when the referred index positions will be appended for. 
            
            # Update their referred index position as the iteration goes to 11th, iter count updates from that as a reaction, then append that one set, wait. 
            first_place [+=10]
            second_place [+=10]
            third_place [+=10]
            fourth_place [+=10]
            fifth_place [+=10]
            sixth_place [+=10]
            seventh_place [+=10]
            eighth_place [+=10]
            ninth_place [+=10]
            tenth_place [+=10]
            
            # The "waited" set of ten, wait until next ten trigger by above conditions. Not bcde, cdef, 
            abcd_then_a_model.append(first_place) 
            abcd_then_a_model.append(second_place)
            abcd_then_a_model.append(third_place)
            abcd_then_a_model.append(fourth_place)
            abcd_then_a_model.append(fifth_place)
            abcd_then_a_model.append(six_place)
            abcd_then_a_model.append(seventh_place)
            abcd_then_a_model.append(eighth_place)
            abcd_then_a_model.append(ninth_place)
            abcd_then_a_model.append(tenth_place)
            # Groups of ten, for their win variables, into pre-common-count-sort list, and then from that list, also, ten-set commons sort-counting then, too. 
            
        
wins_count_lister = wins_count_lister()


"""
To refine the gotten history's varied ranges of win vs loss scenarios, IF needed for accurate enough range constraints to actual-bid with. A decent settle resort.
"""


abcdthen_range_constraints_gotten_a = None


abthen_range_constraints_gotten_a = None
dropped_abthen_range_constraints_gotten_a = None

abcthen_range_constraints_gotten_a = None
dropped_abcthen_range_constraints_gotten_a = None


aandupspike_then_range_constraints_gotten_a = None


# Determine if that model is viable without MANUALLY counting amounts for deciding accurate-enough usable variable ranges for buy condition. 


if totalcount_abcd >= 2000 and len(wins_risinglows_abcd) / totalcount_abcd >= 0.70:
    abcdthen_a_model = True # Not to be confused with abcd_then_a_model meant for the other [] list.
    if len(most_win_thresholds_abcd) > 0:
       abcdthen_range_constraints_gotten_a = True


if totalcount_abc >= 2000 and len(wins_rising_abc) / totalcount_abc >= 0.70:
    abcthen_model = True
    if len(most_win_thresholds_abc) > 0:
       abcthen_range_constraints_gotten_a = True
   


if totalcount_ab >= 2000 and len(wins_rising_ab) / totalcount_ab >= 0.70:
    abthen_model = True
    if len(most_win_thresholds_ab) > 0:
       abthen_range_constraints_gotten_a = True
    
    

if totalcount_dropped_abc >= 2000 and len(dropped_wins_rising_abc) / totalcount_dropped_abc >= 0.70:
    dropped_abcthen_model = True
    if len(most_win_thresholds_dropped_abc) > 0:
       dropped_abcthen_range_constraints_gotten_a = True
    
    

if totalcount_dropped_ab >= 2000 and len(dropped_wins_rising_ab) / totalcount_dropped_ab >= 0.70:
    dropped_abthen_model = True
    if len(most_win_thresholds_dropped_ab) > 0:
       dropped_abthen_range_constraints_gotten_a = True
       
"""

"""


# Minutely strategy

if totalcount_aspike >= 2000 and len(wins_rising_aspike) / totalcount_aspike >= 0.70:
    aandupspike_model = True
    if len(most_win_thresholds_aandupspike) > 0:
       aandupspike_then_range_constraints_gotten_a = True
    
# Minutely strategy
    


# From below, an additional condition of range constraints judgement for True or None (default variable-make).

abcdthen_range_constraints_gotten_b = None

abcthen_range_constraints_gotten_b = None
dropped_abcthen_range_constraints_gotten_b = None

abthen_range_constraints_gotten_b = None
dropped_abthen_range_constraints_gotten_b = None

aandupspike_then_range_constraints_gotten_b = None



"""
ABCD below
"""

win_constraint_thresholds_abcd_one = []
win_constraint_thresholds_abcd_two = []
win_constraint_thresholds_abcd_three = []
win_constraint_thresholds_abcd_four = []
win_constraint_thresholds_abcd_five = []
win_constraint_thresholds_abcd_six = []
win_constraint_thresholds_abcd_seven = []
win_constraint_thresholds_abcd_eight = []

loss_constraint_thresholds_abcd_one = []
loss_constraint_thresholds_abcd_two = []
loss_constraint_thresholds_abcd_three = []
loss_constraint_thresholds_abcd_four = []
loss_constraint_thresholds_abcd_five = []
loss_constraint_thresholds_abcd_six = []
loss_constraint_thresholds_abcd_seven = []
loss_constraint_thresholds_abcd_eight = []

#
win_constraints_thresholds_counter_abcd = [
win_constraint_thresholds_abcd_one, 
win_constraint_thresholds_abcd_two, 
win_constraint_thresholds_abcd_three,
win_constraint_thresholds_abcd_four,
win_constraint_thresholds_abcd_five,
win_constraint_thresholds_abcd_six,
win_constraint_thresholds_abcd_seven,
win_constraint_thresholds_abcd_eight]

#
loss_constraints_thresholds_counter_abcd = [
loss_constraint_thresholds_abcd_one, 
loss_constraint_thresholds_abcd_two, 
loss_constraint_thresholds_abcd_three,
loss_constraint_thresholds_abcd_four,
loss_constraint_thresholds_abcd_five,
loss_constraint_thresholds_abcd_six,
loss_constraint_thresholds_abcd_seven,
loss_constraint_thresholds_abcd_eight]

# Which had the highest number value in amount of appends

most_win_thresholds_abcd = []
most_loss_thresholds_abcd = []



if len(most_win_thresholds_abcd) >= 1.5 * len(most_loss_thresholds_abcd) and len(most_win_thresholds_abcd) >= 30:
    abcdthen_range_constraints_gotten_b = True



"""
ABCD above
"""

"""
ABC below
"""

win_constraint_thresholds_abc_one = []
win_constraint_thresholds_abc_two = []
win_constraint_thresholds_abc_three = []
win_constraint_thresholds_abc_four = []
win_constraint_thresholds_abc_five = []
win_constraint_thresholds_abc_six = []
win_constraint_thresholds_abc_seven = []
win_constraint_thresholds_abc_eight = []

loss_constraint_thresholds_abc_one = []
loss_constraint_thresholds_abc_two = []
loss_constraint_thresholds_abc_three = []
loss_constraint_thresholds_abc_four = []
loss_constraint_thresholds_abc_five = []
loss_constraint_thresholds_abc_six = []
loss_constraint_thresholds_abc_seven = []
loss_constraint_thresholds_abc_eight = []


#
win_constraints_thresholds_counter_abc = [
win_constraint_thresholds_abc_one, 
win_constraint_thresholds_abc_two, 
win_constraint_thresholds_abc_three,
win_constraint_thresholds_abc_four,
win_constraint_thresholds_abc_five,
win_constraint_thresholds_abc_six,
win_constraint_thresholds_abc_seven,
win_constraint_thresholds_abc_eight]

#
loss_constraints_thresholds_counter_abc = [
loss_constraint_thresholds_abc_one, 
loss_constraint_thresholds_abc_two, 
loss_constraint_thresholds_abc_three,
loss_constraint_thresholds_abc_four,
loss_constraint_thresholds_abc_five,
loss_constraint_thresholds_abc_six,
loss_constraint_thresholds_abc_seven,
loss_constraint_thresholds_abc_eight]

# Which had the highest number value in amount of appends

most_win_thresholds_abc = []
most_loss_thresholds_abc = []



if len(most_win_thresholds_abc) >= 1.5 * len(most_loss_thresholds_abc) and len(most_win_thresholds_abc) >= 30:
    abcthen_range_constraints_gotten_b = True



"""
ABC above
"""

"""
May not use every of these listed
"""

"""
DROPPED ABC below
"""


win_constraint_thresholds_dropped_abc_one = []
win_constraint_thresholds_dropped_abc_two = []
win_constraint_thresholds_dropped_abc_three = []
win_constraint_thresholds_dropped_abc_four = []
win_constraint_thresholds_dropped_abc_five = []
win_constraint_thresholds_dropped_abc_six = []
win_constraint_thresholds_dropped_abc_seven = []
win_constraint_thresholds_dropped_abc_eight = []


win_constraint_thresholds_counter_dropped_abc = [
win_constraint_thresholds_dropped_abc_one,
win_constraint_thresholds_dropped_abc_two,
win_constraint_thresholds_dropped_abc_three,
win_constraint_thresholds_dropped_abc_four,
win_constraint_thresholds_dropped_abc_five,
win_constraint_thresholds_dropped_abc_six,
win_constraint_thresholds_dropped_abc_seven,
win_constraint_thresholds_dropped_abc_eight]


most_win_thresholds_dropped_abc = []
# Which had the highest number value in amount of appends


loss_constraint_thresholds_dropped_abc_one = []
loss_constraint_thresholds_dropped_abc_two = []
loss_constraint_thresholds_dropped_abc_three = []
loss_constraint_thresholds_dropped_abc_four = []
loss_constraint_thresholds_dropped_abc_five = []
loss_constraint_thresholds_dropped_abc_six = []
loss_constraint_thresholds_dropped_abc_seven = []
loss_constraint_thresholds_dropped_abc_eight = []


loss_constraint_thresholds_counter_dropped_abc = [
loss_constraint_thresholds_dropped_abc_one,
loss_constraint_thresholds_dropped_abc_two,
loss_constraint_thresholds_dropped_abc_three,
loss_constraint_thresholds_dropped_abc_four,
loss_constraint_thresholds_dropped_abc_five,
loss_constraint_thresholds_dropped_abc_six,
loss_constraint_thresholds_dropped_abc_seven,
loss_constraint_thresholds_dropped_abc_eight]



most_loss_thresholds_dropped_abc = []
# Which had the highest number value in amount of appends



if len(most_win_thresholds_dropped_abc) >= 1.5 * len(most_loss_thresholds_dropped_abc) and len(most_win_thresholds_dropped_abc) >= 30:
    dropped_abcthen_range_constraints_gotten_b = True



"""
DROPPED ABC above
"""

"""
AB below
"""

win_constraint_thresholds_ab_one = []
win_constraint_thresholds_ab_two = []
win_constraint_thresholds_ab_three = []
win_constraint_thresholds_ab_four = []
win_constraint_thresholds_ab_five = []
win_constraint_thresholds_ab_six = []
win_constraint_thresholds_ab_seven = []
win_constraint_thresholds_ab_eight = []

loss_constraint_thresholds_ab_one = []
loss_constraint_thresholds_ab_two = []
loss_constraint_thresholds_ab_three = []
loss_constraint_thresholds_ab_four = []
loss_constraint_thresholds_ab_five = []
loss_constraint_thresholds_ab_six = []
loss_constraint_thresholds_ab_seven = []
loss_constraint_thresholds_ab_eight = []


#
win_constraints_thresholds_counter_ab = [
win_constraint_thresholds_ab_one, 
win_constraint_thresholds_ab_two, 
win_constraint_thresholds_ab_three,
win_constraint_thresholds_ab_four,
win_constraint_thresholds_ab_five,
win_constraint_thresholds_ab_six,
win_constraint_thresholds_ab_seven,
win_constraint_thresholds_ab_eight]

most_win_thresholds_ab = []
# Which had the highest number value in amount of appends


#
loss_constraints_thresholds_counter_ab = [
loss_constraint_thresholds_ab_one, 
loss_constraint_thresholds_ab_two, 
loss_constraint_thresholds_ab_three,
loss_constraint_thresholds_ab_four,
loss_constraint_thresholds_ab_five,
loss_constraint_thresholds_ab_six,
loss_constraint_thresholds_ab_seven,
loss_constraint_thresholds_ab_eight]

most_loss_thresholds_ab = []
# Which had the highest number value in amount of appends


if len(most_win_thresholds_ab) >= 1.5 * len(most_loss_thresholds_ab) and len(most_win_thresholds_ab) >= 30:
    abthen_range_constraints_gotten_b = True



"""
AB above
"""

"""
May not use every of these listed.
"""

"""
DROPPED AB below
"""

win_constraint_thresholds_dropped_ab_one = []
win_constraint_thresholds_dropped_ab_two = []
win_constraint_thresholds_dropped_ab_three = []
win_constraint_thresholds_dropped_ab_four = []
win_constraint_thresholds_dropped_ab_five = []
win_constraint_thresholds_dropped_ab_six = []
win_constraint_thresholds_dropped_ab_seven = []
win_constraint_thresholds_dropped_ab_eight = []


win_constraint_thresholds_counter_dropped_ab = [
win_constraint_thresholds_dropped_ab_one,
win_constraint_thresholds_dropped_ab_two,
win_constraint_thresholds_dropped_ab_three,
win_constraint_thresholds_dropped_ab_four,
win_constraint_thresholds_dropped_ab_five,
win_constraint_thresholds_dropped_ab_six,
win_constraint_thresholds_dropped_ab_seven,
win_constraint_thresholds_dropped_ab_eight]


loss_constraint_thresholds_dropped_ab_one = []
loss_constraint_thresholds_dropped_ab_two = []
loss_constraint_thresholds_dropped_ab_three = []
loss_constraint_thresholds_dropped_ab_four = []
loss_constraint_thresholds_dropped_ab_five = []
loss_constraint_thresholds_dropped_ab_six = []
loss_constraint_thresholds_dropped_ab_seven = []
loss_constraint_thresholds_dropped_ab_eight = []


loss_constraint_thresholds_counter_dropped_ab = [
loss_constraint_thresholds_dropped_ab_one,
loss_constraint_thresholds_dropped_ab_two,
loss_constraint_thresholds_dropped_ab_three,
loss_constraint_thresholds_dropped_ab_four,
loss_constraint_thresholds_dropped_ab_five,
loss_constraint_thresholds_dropped_ab_six,
loss_constraint_thresholds_dropped_ab_seven,
loss_constraint_thresholds_dropped_ab_eight]

most_win_thresholds_dropped_ab = []
# Which had the highest number value in amount of appends

most_loss_thresholds_dropped_ab = []
# Which had the highest number value in amount of appends


if len(most_win_thresholds_dropped_ab) >= 1.5 * len(most_loss_thresholds_dropped_ab) and len(most_win_thresholds_dropped_ab) >= 30:
    dropped_abthen_range_constraints_gotten_b = True


"""
DROPPED AB above
"""

"""
AandUpspike below 
"""
# To match with aspike_then_model variable above, when cartesian trier has minutely, as well. I will simply copy paste my own code above, and make that part occur, alone.

win_constraint_thresholds_aandupspike_one = []
win_constraint_thresholds_aandupspike_two = []
win_constraint_thresholds_aandupspike_three = []
win_constraint_thresholds_aandupspike_four = []
win_constraint_thresholds_aandupspike_five = []
win_constraint_thresholds_aandupspike_six = []
win_constraint_thresholds_aandupspike_seven = []
win_constraint_thresholds_aandupspike_eight = []

loss_constraint_thresholds_aandupspike_one = []
loss_constraint_thresholds_aandupspike_two = []
loss_constraint_thresholds_aandupspike_three = []
loss_constraint_thresholds_aandupspike_four = []
loss_constraint_thresholds_aandupspike_five = []
loss_constraint_thresholds_aandupspike_six = []
loss_constraint_thresholds_aandupspike_seven = []
loss_constraint_thresholds_aandupspike_eight = []


#
win_constraints_thresholds_counter_aandupspike = [
win_constraint_thresholds_aandupspike_one, 
win_constraint_thresholds_aandupspike_two, 
win_constraint_thresholds_aandupspike_three,
win_constraint_thresholds_aandupspike_four,
win_constraint_thresholds_aandupspike_five,
win_constraint_thresholds_aandupspike_six,
win_constraint_thresholds_aandupspike_seven,
win_constraint_thresholds_aandupspike_eight]

most_win_thresholds_aandupspike = []
# Which had the highest number value in amount of appends


#
loss_constraints_thresholds_counter_aandupspike = [
loss_constraint_thresholds_aandupspike_one, 
loss_constraint_thresholds_aandupspike_two, 
loss_constraint_thresholds_aandupspike_three,
loss_constraint_thresholds_aandupspike_four,
loss_constraint_thresholds_aandupspike_five,
loss_constraint_thresholds_aandupspike_six,
loss_constraint_thresholds_aandupspike_seven,
loss_constraint_thresholds_aandupspike_eight]

most_loss_thresholds_aandupspike = []
# Which had the highest number value in amount of appends



if len(most_win_thresholds_aandupspike) >= 1.5 * len(most_loss_thresholds_aandupspike) and len(most_win_thresholds_aandupspike) >= 30:
    aandupspike_then_range_constraints_gotten_b = True


"""
AandUpspike above
"""



"""
The purpose of above is towards determining (below) which of the constrainted lists are more commonly occur, amongst each other.
"""


#(a, 1+ax, b, 1+axx, c, 1+ac, 1+bx, 1+bxx, 1+cd   abc1 
#(a, 1+ax, b, 1+axx, c, 1+cd)  abc and then 
#(a, 1+ax, b, c, 1+cd) ab and then

def constraints_guesser(): # To refine for the usable ranges of patterns occurred, not simply the wins and losses recorded in its varieties of "ranges" from the cartesian

    for indexposition in abcd_then_a_model: # Although indexposition, iterpoint, itercount do not match in positions, the i>>next will work out with positionings in group-set.
        
        iterpoint = int(indexposition) #Non-global variable, contained within this def.
        
        first_place = [0]
        second_place = [1] 
        third_place = [2]
        fourth_place = [3]
        fifth_place = [4]
        sixth_place = [5]
        seventh_place = [6]
        eighth_place = [7]
        ninth_place = [8]
        tenth_place = [9]
        
        # Kept consistent with the above def in trier(s)
        a = first_place
        ax = second_place 
        b = third_place
        axx = fourth_place
        c = fifth_place
        ac = sixth_place
        bx = seventh_place
        bxx = eighth_place
        cd = ninth_place
        d = tenth_place
        
        
        #(a, 1+ax, b, 1+axx, c, 1+ac, 1+bx, 1+bxx, 1+cd, d). 
        
        # Must exclude 1+ here to become consistent, because these listed values were already 1+ax, etc
        
        # abcd and then, list 1
        if ax <= 1.004 and axx <= 1.004 and ac <= 1.004 and bx <= 1.004 and bxx <= 1.004 and cd <= 1.004 and d >= cd * c:
        
            win_constraint_thresholds_abcd_one.extend(a, ax, b, axx, c, ac, bx, bxx, cd, d)
            
            
        if ax <= 1.004 and axx <= 1.004 and ac <= 1.004 and bx <= 1.004 and bxx <= 1.004 and cd <= 1.004 and d < cd * c:
            
            loss_constraint_thresholds_abcd_one.extend(a, ax, b, axx, c, ac, bx, bxx, cd, d)
            
            
        
        # abcd and then, list 2, feasible. Though of range constraints, not including combinatorial diff'd numbers per; I'll settle. 
        
        if ax <= 1.006 and axx <= 1.006 and ac <= 1.006 and bx <= 1.006 and bxx <= 1.006 and cd <= 1.006 and d >= cd * c:
        
            win_constraint_thresholds_abcd_two.extend(a, ax, b, axx, c, ac, bx, bxx, cd, d)
            
            
        if ax <= 1.006 and axx <= 1.006 and ac <= 1.006 and bx <= 1.006 and bxx <= 1.006 and cd <= 1.006 and d < cd * c:
            
            loss_constraint_thresholds_abcd_two.extend(a, ax, b, axx, c, ac, bx, bxx, cd, d)

        
        
        # abcd and then, list 3
        
        if ax <= 1.008 and axx <= 1.008 and ac <= 1.008 and bx <= 1.008 and bxx <= 1.008 and cd <= 1.008 and d >= cd * c:
        
            win_constraint_thresholds_abcd_three.extend(a, ax, b, axx, c, ac, bx, bxx, cd, d)
            
            
        if ax <= 1.008 and axx <= 1.008 and ac <= 1.008 and bx <= 1.008 and bxx <= 1.008 and cd <= 1.008 and d < cd * c:
            
            loss_constraint_thresholds_abcd_three.extend(a, ax, b, axx, c, ac, bx, bxx, cd, d)
        
            
            
        # abcd and then, list 4
        
        if ax <= 1.01 and axx <= 1.01 and ac <= 1.01 and bx <= 1.01 and bxx <= 1.01 and cd <= 1.01 and d >= cd * c:
        
            win_constraint_thresholds_abcd_four.extend(a, ax, b, axx, c, ac, bx, bxx, cd, d)
            
            
        if ax <= 1.01 and axx <= 1.01 and ac <= 1.01 and bx <= 1.01 and bxx <= 1.01 and cd <= 1.01 and d < cd * c:
            
            loss_constraint_thresholds_abcd_four.extend(a, ax, b, axx, c, ac, bx, bxx, cd, d)
            
            
        # abcd and then, list 5
        
        if ax <= 1.012 and axx <= 1.012 and ac <= 1.012 and bx <= 1.012 and bxx <= 1.012 and cd <= 1.012 and d >= cd * c:
        
            win_constraint_thresholds_abcd_five.extend(a, ax, b, axx, c, ac, bx, bxx, cd, d)
            
            
        if ax <= 1.012 and axx <= 1.012 and ac <= 1.012 and bx <= 1.012 and bxx <= 1.012 and cd <= 1.012 and d < cd * c:
            
            loss_constraint_thresholds_abcd_five.extend(a, ax, b, axx, c, ac, bx, bxx, cd, d)
            
            
        # abcd and then, list 6
        
        if ax <= 1.014 and axx <= 1.014 and ac <= 1.014 and bx <= 1.014 and bxx <= 1.014 and cd <= 1.014 and d >= cd * c:
        
            win_constraint_thresholds_abcd_six.extend(a, ax, b, axx, c, ac, bx, bxx, cd, d)
            
            
        if ax <= 1.014 and axx <= 1.014 and ac <= 1.014 and bx <= 1.014 and bxx <= 1.014 and cd <= 1.014 and d < cd * c:
            
            loss_constraint_thresholds_abcd_six.extend(a, ax, b, axx, c, ac, bx, bxx, cd, d)
            
            
        # abcd and then, list 7
        
        if ax <= 1.016 and axx <= 1.016 and ac <= 1.016 and bx <= 1.016 and bxx <= 1.016 and cd <= 1.016 and d >= cd * c:
        
            win_constraint_thresholds_abcd_seven.extend(a, ax, b, axx, c, ac, bx, bxx, cd, d)
            
            
        if ax <= 1.016 and axx <= 1.016 and ac <= 1.016 and bx <= 1.016 and bxx <= 1.016 and cd <= 1.016 and d < cd * c:
            
            loss_constraint_thresholds_abcd_seven.extend(a, ax, b, axx, c, ac, bx, bxx, cd, d)
            
            
        # abcd and then, list 8
        
        if ax <= 1.018 and axx <= 1.018 and ac <= 1.018 and bx <= 1.018 and bxx <= 1.018 and cd <= 1.018 and d >= cd * c:
        
            win_constraint_thresholds_abcd_eight.extend(a, ax, b, axx, c, ac, bx, bxx, cd, d)
            
            
        if ax <= 1.018 and axx <= 1.018 and ac <= 1.018 and bx <= 1.018 and bxx <= 1.018 and cd <= 1.018 and d < cd * c:
            
            loss_constraint_thresholds_abcd_eight.extend(a, ax, b, axx, c, ac, bx, bxx, cd, d)
        
        
            
            
        """
        After the abcd varied range guesses for finding right constraints, then moves on to check the next group of tens.
        """        
            
        iter_count = 0 # Does not auto-increase per for loop iteration, per i to the right.
        
        
        if iterpoint == iter_count + 10: # Meaning iteration reached 11th position
            iter_count += 10 # While iterpoint is at 21st position, saying integer 20 numerical value, itercount will then become 20, unreactive until 30. 
        
        
        if iter_count += 10: # Each time this point addition counting occurs from tracking the iterpoint, which will be when the referred index positions to be appended of. 
            
            first_place [+=10] # Now, 11th, and there-on, the above conditions reapply.
            second_place [+=10]
            third_place [+=10]
            fourth_place [+=10]
            fifth_place [+=10]
            sixth_place [+=10]
            seventh_place [+=10]
            eighth_place [+=10]
            ninth_place [+=10]
            tenth_place [+=10]
            
            
        """
        abcd above
        """
        
    """
    abc below
    """
        
        # abc strategy 
    for indexposition in abc_then_a_model:
        
        iterpoint = int(indexposition)
        
        first_place = [0]
        second_place = [1] 
        third_place = [2]
        fourth_place = [3]
        fifth_place = [4]
        sixth_place = [5]
        
        
        a = first_place
        ax = second_place 
        b = third_place
        axx = fourth_place
        c = fifth_place
        cd = sixth_place
        
        #(a, 1+ax, b, 1+axx, c, 1+cd)  abc and then 
        
        # abc and then, list 1
        if ax <= 1.004 and axx <= 1.004 and ac <= 1.004 and bx <= 1.004 and bxx <= 1.004 and cd <= 1.004 and c >= b * cd:
        
            win_constraint_thresholds_abc_one.extend(a, ax, b, axx, c, cd)
            
            
        if ax <= 1.004 and axx <= 1.004 and ac <= 1.004 and bx <= 1.004 and bxx <= 1.004 and cd <= 1.004 and c < b * cd:
            
            loss_constraint_thresholds_abc_one.extend(a, ax, b, axx, c, cd)
            
        

        
        # abc and then, list 2
        if ax <= 1.006 and axx <= 1.006 and ac <= 1.006 and bx <= 1.006 and bxx <= 1.006 and cd <= 1.006 and c >= b * cd:
        
            win_constraint_thresholds_abc_two.extend(a, ax, b, axx, c, cd)
            
            
        if ax <= 1.006 and axx <= 1.006 and ac <= 1.006 and bx <= 1.006 and bxx <= 1.006 and cd <= 1.006 and c < b * cd:
            
            loss_constraint_thresholds_abc_two.extend(a, ax, b, axx, c, cd)
        
        
        # abc and then, list 3
        if ax <= 1.008 and axx <= 1.008 and ac <= 1.008 and bx <= 1.008 and bxx <= 1.008 and cd <= 1.008 and c >= b * cd:
        
            win_constraint_thresholds_abc_three.extend(a, ax, b, axx, c, cd)
            
            
        if ax <= 1.008 and axx <= 1.008 and ac <= 1.008 and bx <= 1.008 and bxx <= 1.008 and cd <= 1.008 and c < b * cd:
            
            loss_constraint_thresholds_abc_three.extend(a, ax, b, axx, c, cd)
            
            
            
        # abc and then, list 4
        if ax <= 1.01 and axx <= 1.01 and ac <= 1.01 and bx <= 1.01 and bxx <= 1.01 and cd <= 1.01 and c >= b * cd:
        
            win_constraint_thresholds_abc_four.extend(a, ax, b, axx, c, cd)
            
            
        if ax <= 1.01 and axx <= 1.01 and ac <= 1.01 and bx <= 1.01 and bxx <= 1.01 and cd <= 1.01 and c < b * cd:
            
            loss_constraint_thresholds_abc_four.extend(a, ax, b, axx, c, cd)
            
            
            
        # abc and then, list 5
        if ax <= 1.012 and axx <= 1.012 and ac <= 1.012 and bx <= 1.012 and bxx <= 1.012 and cd <= 1.012 and c >= b * cd:
        
            win_constraint_thresholds_abc_five.extend(a, ax, b, axx, c, cd)
            
            
        if ax <= 1.012 and axx <= 1.012 and ac <= 1.012 and bx <= 1.012 and bxx <= 1.012 and cd <= 1.012 and c < b * cd:
            
            loss_constraint_thresholds_abc_five.extend(a, ax, b, axx, c, cd)
            
            
            
        # abc and then, list 6
        if ax <= 1.014 and axx <= 1.014 and ac <= 1.014 and bx <= 1.014 and bxx <= 1.014 and cd <= 1.014 and c >= b * cd:
        
            win_constraint_thresholds_abc_six.extend(a, ax, b, axx, c, cd)
            
            
        if ax <= 1.014 and axx <= 1.014 and ac <= 1.014 and bx <= 1.014 and bxx <= 1.014 and cd <= 1.014 and c < b * cd:
            
            loss_constraint_thresholds_abc_six.extend(a, ax, b, axx, c, cd)
        
        
        
        # abc and then, list 7
        if ax <= 1.016 and axx <= 1.016 and ac <= 1.016 and bx <= 1.016 and bxx <= 1.016 and cd <= 1.016 and c >= b * cd:
        
            win_constraint_thresholds_abc_seven.extend(a, ax, b, axx, c, cd)
            
            
        if ax <= 1.016 and axx <= 1.016 and ac <= 1.016 and bx <= 1.016 and bxx <= 1.016 and cd <= 1.016 and c < b * cd:
            
            loss_constraint_thresholds_abc_seven.extend(a, ax, b, axx, c, cd)
            
            
            
        # abc and then, list 8
        if ax <= 1.018 and axx <= 1.018 and ac <= 1.018 and bx <= 1.018 and bxx <= 1.018 and cd <= 1.018 and c >= b * cd:
        
            win_constraint_thresholds_abc_eight.extend(a, ax, b, axx, c, cd)
            
            
        if ax <= 1.018 and axx <= 1.018 and ac <= 1.018 and bx <= 1.018 and bxx <= 1.018 and cd <= 1.018 and c < b * cd:
            
            loss_constraint_thresholds_abc_eight.extend(a, ax, b, axx, c, cd)
        
            
            
            
        """
        After the abc varied range guesses for finding right constraints, then moves on to check the next group of sixes
        """        
            
        iter_count = 0 # Does not auto-increase per for loop iteration
        
        
        if iterpoint == iter_count + 6: # Meaning iteration reached seventh position
            iter_count += 6 
        
        
        if iter_count += 6:
            
            first_place [+=6]
            second_place [+=6]
            third_place [+=6]
            fourth_place [+=6]
            fifth_place [+=6]
            sixth_place [+=6]
        
        """
        abc above
        """
        
    """
    ab below
    """

    # ab strategy 
    for indexposition in ab_then_a_model:
        
        iterpoint = int(indexposition)
        
        first_place = [0]
        second_place = [1] 
        third_place = [2]
        fourth_place = [3]
        fifth_place = [4]
        
        
        a = first_place
        ax = second_place 
        b = third_place
        c = fourth_place
        cd = fifth_place
        
        
        #(a, 1+ax, b, c, 1+cd) ab and then
        
        # ab and then, list 1
        if ax <= 1.004 and b >= 1.004 * a and c >= b * cd)
        
            win_constraint_thresholds_ab_one.extend(a, ax, b, c, cd)
            
            
        if ax <= 1.004 and b >= 1.004 * a and c < b * cd)
            
            loss_constraint_thresholds_ab_one.extend(a, ax, b, c, cd)
            
        

        # ab and then, list 2
        if ax <= 1.006 and b >= 1.006 * a and c >= b * cd)
        
            win_constraint_thresholds_ab_two.extend(a, ax, b, c, cd)
            
            
        if ax <= 1.006 and b >= 1.006 * a and c < b * cd)
            
            loss_constraint_thresholds_ab_two.extend(a, ax, b, c, cd)
            
        
         # ab and then, list 3
        if ax <= 1.008 and b >= 1.008 * a and c >= b * cd)
        
            win_constraint_thresholds_ab_three.extend(a, ax, b, c, cd)
            
            
        if ax <= 1.008 and b >= 1.008 * a and c < b * cd)
            
            loss_constraint_thresholds_ab_three.extend(a, ax, b, c, cd)
        
        
        # ab and then, list 4
        if ax <= 1.01 and b >= 1.01 * a and c >= b * cd)
        
            win_constraint_thresholds_ab_four.extend(a, ax, b, c, cd)
            
            
        if ax <= 1.01 and b >= 1.01 * a and c < b * cd)
            
            loss_constraint_thresholds_ab_four.extend(a, ax, b, c, cd)
            
        
        # ab and then, list 5
        if ax <= 1.012 and b >= 1.012 * a and c >= b * cd)
        
            win_constraint_thresholds_ab_five.extend(a, ax, b, c, cd)
            
            
        if ax <= 1.012 and b >= 1.012 * a and c < b * cd)
            
            loss_constraint_thresholds_ab_five.extend(a, ax, b, c, cd)
            
            
        # ab and then, list 6
        if ax <= 1.014 and b >= 1.014 * a and c >= b * cd)
        
            win_constraint_thresholds_ab_six.extend(a, ax, b, c, cd)
            
            
        if ax <= 1.014 and b >= 1.014 * a and c < b * cd)
            
            loss_constraint_thresholds_ab_six.extend(a, ax, b, c, cd)
        
        
        # ab and then, list 7
        if ax <= 1.016 and b >= 1.016 * a and c >= b * cd)
        
            win_constraint_thresholds_ab_seven.extend(a, ax, b, c, cd)
            
            
        if ax <= 1.016 and b >= 1.016 * a and c < b * cd)
            
            loss_constraint_thresholds_ab_seven.extend(a, ax, b, c, cd)
        
        
        # ab and then, list 8
        if ax <= 1.018 and b >= 1.018 * a and c >= b * cd)
        
            win_constraint_thresholds_ab_eight.extend(a, ax, b, c, cd)
            
            
        if ax <= 1.018 and b >= 1.018 * a and c < b * cd)
            
            loss_constraint_thresholds_ab_eight.extend(a, ax, b, c, cd)
        
            
            
        """
        After the abc varied range guesses for finding right constraints, then iteration moves on to check the next group of sixes
        """        
            
        iter_count = 0 # Does not auto-increase per for loop iteration
        
        
        if iterpoint == iter_count + 5: # Meaning iteration reached seventh position
            iter_count += 5 # While iterpoint is at 16st position, saying integer 15 numerical value, itercount will then become 15, unreactive until 20. 
        
        
        if iter_count += 5: # Each time this point addition counting occurs from tracking the iterpoint, that will be when the referred index positions will be appended for. 
            
            first_place [+=5]
            second_place [+=5]
            third_place [+=5]
            fourth_place [+=5]
            fifth_place [+=5]
            
        
# Does it need any other code to make it run the results? Or, just making the variable mention here does? 
constraints_guesser = constraints_guesser()
# Task: Must it re-mention a return result execute of constraints guesser? Or, would this be enough to make run with the csv-gotten above?

   
"""
Dropped'ss above required to be written. By me, not another coder. Same exact copy-patterns for minutely, as well.
"""        



"""
Each coin will get a different bot, using one strategy, per coin, per 1m time frame type. 
"""

# No need to make options of many coins. 

"""
Count most commons, pick usable range for strategy models, otherwise, collecting wins and losses is just records of those history scenarios which match larger-range variables. 
"""
        
"""    
"""    

"""
May decide to not use ALL these variables. 
"""
time_now_a = None
time_then_a = None
time_now_b = None
time_then_b = None
time_now_c = None
time_then_c = None 
time_now_d = None
time_then_d = None
time_now_e = None
time_then_e = None
time_now_f = None
time_then_f = None
time_now_g = None
time_then_g = None
time_now_h = None
time_then_h = None
time_now_i = None
time_then_i = None
time_now_j = None
time_then_j = None
time_now_k = None
time_then_k = None
time_now_l = None
time_then_l = None
time_now_m = None
time_then_m = None
time_now_n = None
time_then_n = None
time_now_o = None
time_then_o = None
time_now_p = None
time_then_p = None
time_now_q = None
time_then_q = None
time_now_r = None
time_then_r = None
time_now_s = None
time_then_s = None
time_now_t = None
time_then_t = None
time_now_u = None
time_then_u = None


"""
May decide to not use ALL these variables
"""

price_now_a = None
price_then_a = None # Likely used for price_125_minutes_ago
price_now_b = None
price_then_b = None # Likely used for price_65_minutes_ago
price_now_c = None
price_then_c = None # Likely used for price_5_minutes_ago

price_now_d = None
price_then_d = None # Likely used for price_125_minutes_ago , for a different buy condition grouping. 
price_now_e = None
price_then_e = None
price_now_f = None
price_then_f = None
price_now_g = None
price_then_g = None
price_now_h = None
price_then_h = None
price_now_i = None
price_then_i = None
price_now_j = None
price_then_j = None
price_now_k = None
price_then_k = None
price_now_l = None
price_then_l = None
price_now_m = None
price_then_m = None
price_now_n = None
price_then_n = None
price_now_o = None
price_then_o = None
price_now_p = None
price_then_p = None
price_now_q = None
price_then_q = None
price_now_r = None
price_then_r = None
price_now_s = None
price_then_s = None
price_now_t = None
price_then_t = None
price_now_u = None
price_then_u = None


"""
May decide to not use ALL these variables
"""

wallet_now_a = None
wallet_then_a = None
wallet_now_b = None
wallet_then_b = None
wallet_now_c = None
wallet_then_c = None 
wallet_now_d = None
wallet_then_d = None
wallet_now_e = None
wallet_then_e = None
wallet_now_f = None
wallet_then_f = None
wallet_now_g = None
wallet_then_g = None
wallet_now_h = None
wallet_then_h = None
wallet_now_i = None
wallet_then_i = None
wallet_now_j = None
wallet_then_j = None
wallet_now_k = None
wallet_then_k = None
wallet_now_l = None
wallet_then_l = None
wallet_now_m = None
wallet_then_m = None
wallet_now_n = None
wallet_then_n = None

"""
The hourly bot will need to run for hours to make a first action, because it is not calling for past hourly prices, but, recording as it runs, instead. Fine. 
"""

price_185_minutes_ago = None # Not being used. Fine-able
price_155_minutes_ago = None # Not being used

price_125_minutes_ago = None
price_95_minutes_ago = None # Not being used
price_65_minutes_ago = None
price_35_minutes_ago = None # Not being used

price_25_minutes_ago = None # Not being used
price_15_minutes_ago = None # Not being used

price_10_minutes_ago = None # Not being used

price_5_minutes_ago = None
price_4_minutes_ago = None
price_3_minutes_ago = None
price_2_minutes_ago = None
price_1_minute_ago = None


"""

May decide to not use ALL these variables

"""

time_mark_a = None # 125 minutes ago
time_mark_b = None # 65 minutes ago
time_mark_c = None # 5 minutes ago  . Consistent for both hourly and minutely bot. 
time_mark_d = None # 4 minutes ago
time_mark_e = None # 3 minutes ago
time_mark_f = None # 2 minutes ago
time_mark_g = None # 1 minute ago alt.

time_mark_h = None # 10 minutes ago

#

price_mark_a = None # 15 minutes ago
price_mark_b = None # 25 minutes ago
price_mark_c = None # 35 minutes ago
price_mark_d = None # 45 minutes ago

price_mark_e = None # 95 minutes ago
price_mark_f = None # 155 minutes ago
price_mark_g = None # 185 minutes ago
price_mark_h = None # 215 minutes ago

#

price_at_time_mark_a = None
price_at_time_mark_b = None
price_at_time_mark_c = None
price_at_time_mark_d = None
price_at_time_mark_e = None
price_at_time_mark_f = None
price_at_time_mark_g = None
price_at_time_mark_h = None



"""
"""

# Refreshable collection of time marked points, as time_mark counts and refreshes itself. 
time_mark_list = [] # Index positions for time_mark_list and price_mark_list should always match, both being the right recordings at that time. One coin, one buy, one sell.
time_mark = 0
price_mark_list = []


if hourly_bot == True: # This code file will use pre-deciding manual input on which mode it will count with. Though checking minutely, anyway with bottom row sleep 1m.
    
    minutely_bot = None # Not false
    
    # Every time this bot awakens from 1 minute sleep, afterwards, 1m sleep being the condition used, it'll keep a new record of time and price marks. Refreshive as time progresses. 
        
    if time_mark >= 0: # Must refresh these variables as the bot keeps counting minutely by sleep at bottom
        time_mark += 1 # instantly 1, instead of using 0 that way
        
        # Task. Will this server_time actually return result and make variable update value from Coinbase server request ping?
        time_mark_a = server_time
        time_mark_list.append(time_mark_a)
        
        # Task. This get price now function must work with Coinbase. 
        price_at_time_mark_a = server_spot_price # This can be toleratedly different by like 1 second, if slippage type delay lag ever occurs when pinging.
        price_mark_list.append(price_at_time_mark_a)
        
        
        
    if time_mark == 60:

        time_mark_b = server_time 
        time_mark_list.append(time_mark_b)
        
        price_at_time_mark_b = server_spot_price
        price_mark_list.append(price_at_time_mark_b)
        
        

    if time_mark == 120:  

        time_mark_c = server_time 
        time_mark_list.append(time_mark_c)
        
        price_at_time_mark_c = server_spot_price
        price_mark_list.append(price_at_time_mark_c)
        
        time_mark = 0 # Resettive refresh point. Order of code structure from top to bottom matters.
    

    # With minutely sleep and request frequency, SOME minutely misses by .clearing this way may be ok.     
        
    if len(time_mark_list) > 3:
        time_mark_list.del(0:3) # So that xth becomes 1st position, in a selective delete.
        
    if len(price_mark_list) > 3:
        # Task: Same with above. 
        price_mark_list.del(0:3)

"""
"""

if minutely_bot == True: # Will manually decide if minutely or hourly, anyway, per coin, per instance of bot use.
    
    hourly_bot = None # Not false
        
        
    # Every time this bot awakens from 1 minute sleep, it'll keep a new record of time and price marks. Refresh as betweens of 1m sleep.
    if time_mark >= 0:
        time_mark += 1 # instantly 1 for this model, 1 as the start, instead of 0
        
    
        
        
    if time_mark == 1: #

        time_mark_p = server_time
        time_mark_list.append(time_mark_p)
        
        price_at_time_mark_p = server_spot_price
        price_mark_list.append(price_at_time_mark_p)
        
        

    if time_mark == 2:  

        time_mark_o = server_time 
        time_mark_list.append(time_mark_o)
        
        price_at_time_mark_o = server_spot_price
        price_mark_list.append(price_at_time_mark_o)
        
        
        
    if time_mark == 3:

        time_mark_n = server_time 
        time_mark_list.append(time_mark_n)
        
        price_at_time_mark_n = server_spot_price
        price_mark_list.append(price_at_time_mark_n)
        
        

    if time_mark == 4:  

        time_mark_m = server_time 
        time_mark_list.append(time_mark_m)
        
        price_at_time_mark_m = server_spot_price
        price_mark_list.append(price_at_time_mark_m)    
        
        
        # As a declaration of reset point, that I will use only 4 minutes range price-time checks, with my strategies written. 
        
        time_mark = 0 # The bot runs from top to bottom, and this does not conflict with the 0-conditions above. 
        # time_mark resets to "zero" as numerical value, helps restart the time mark loop above.

        
        
        # 1,2,3,4,5. No fifth index part as dots of time points in this model decision.
        
        
    if len(time_mark_list) > 4:
        time_mark_list.del(0:4) # fifth as 1st anew, in resettive loop
        
    if len(price_mark_list) > 4:
        price_mark_list.del(0:4) # 
    
"""
"""

"""
"""

# Get the current minute by epoch time format
# Despite epoch time, the time mark counting in my bot will still keep numerical minutely one-one track, within its file-domestic lists, anyway.

if current_time != None:


    if current_time - time_mark_a == 125:
        price_125_minutes_ago = price_mark_a # Value reference set in past point
        
    if current_time - time_mark_b == 65:
        price_65_minutes_ago = price_mark_b # Value reference set in past point
        
    if current_time - time_mark_c == 5:
        price_5_minutes_ago = price_mark_c # Value reference set in past point
        


# Could optionally put these under an if condition.    
    
    

    if current_time - time_mark_i == 8:
        price_4_minutes_ago = price_mark_i # Value reference set in past point
        
    if current_time - time_mark_j == 7:
        price_3_minutes_ago = price_mark_j # Value reference set in past point
        
    if current_time - time_mark_k == 6:
        price_2_minutes_ago = price_mark_k # Value reference set in past point

    if current_time - time_mark_l == 5:
        price_1_minute_ago = price_mark_l # Value reference set in past point    

    if current_time - time_mark_m == 4:
        price_4_minutes_ago = price_mark_m # Value reference set in past point
        
    if current_time - time_mark_n == 3:
        price_3_minutes_ago = price_mark_n # Value reference set in past point
        
    if current_time - time_mark_o == 2:
        price_2_minutes_ago = price_mark_o # Value reference set in past point

    if current_time - time_mark_p == 1:
        price_1_minute_ago = price_mark_p # Value reference set in past point
        
        

"""
"""

# Minutely model can be lacking for now.
# Minutely can still simply use the existing code above, copy paste some parts, change up a few points each, then it will be able. 
   
"""
"""


"""
abcd_then_a_model buys and sells
"""  

tried_limit_sell = None # Default and refreshive.

if hourly_bot == True and abcdthen_a_model == True and abcdthen_range_constraints_gotten_a == True:

    
# Task. Make these into coinbase buy sells. limit order, auto re-try limit order if it didn't go through, cancel after 2 minutes, (if order cancel req'd) if it doesn't work. 

# Only needs one example of each coinbase API function, and I'll fill in the remaining as logicable. 

# Make limit sells as if default. Spot sells for panic sells. Spot sells for auto-retry type of resort settle-sell. 
# Sell 100% of that 5% of wallet, each bid. 100% sell, always by time. 

# Market SPOT sell if limit sells and re-tries did not work for limit sells. 
# Market BUY is ok. Limit Sells by default, good. 

    # abcd model written without its collective data model for price relations with setted range constraints ( I will do that part, later )
    if current_price > price_5_minutes_ago and price_65_minutes_ago >= price_125_minutes_ago and price_5_minutes_ago >= price_125_minutes_ago:
        # buy function 
        position_held = True
        
        time_then_a = current_time # time_NOW_a is for sell-if.  
        # Does this auto-return-result the current time?
        # Task. Answer.
        
        bought_time = time_then_a # Different from time_mark_a
        
        #Possibly a server_spot_price return function lambda, here.
        
        bought_price = server_spot_price # To keep track of price, for later references. Result of before and after buy and sell, as actual change in wallet. Diffs. 
        


    # LIMIT ORDER SELL Function CONDITION:
    # Possibly make this into a nested if condition, one being get current price, get current time, so these variable logics will actually work. 
    if position_held == True and time_now_a - bought_time >= 60 and current_price >= 1.005 * bought_price: 
        # sell function 
        position_held = False
        tried_limit_sell = True
        
    if tried_limit_sell == True: # Auto-Try again just in case it didn't go through the server. Auto SPOT Sell as needed, within or after 2 minutes after limit sell attempt. 
        if position_held == True and time_now_a - bought_time >= 60 and current_price >= 1.005 * bought_price: 
            def CEX_order_limit(("BTC", "USD"), "SELL", 0.05, price)  
            position_held = False
            tried_limit_sell = None
        
    # Auto sell order after this minute, then.    
    if position_held == True and time_now_a - bought_time >= 61 and current_price >= 1.004 * bought_price: # Adjust to possible price drop at expected time to sell, slight unexpected
        def CEX_order_limit(("BTC", "USD"), "SELL", 0.05, price)  
        position_held = False
        
# If Coinbase API requires order cancel of any type, just to Spot Sell as if emergency, then, cancel whatever order, do spot sell as a 2 minute last resort. 
        
    # By time, default sell to whatever result
    if position_held == True and time_now_a - bought_time >= 62:
        def CEX_order_market(("BTC", "USD"), "SELL", 0.05)
        position_held = False
        
    # By time, default sell to whatever result
    if position_held == True and time_now_a - bought_time >= 63:
        def CEX_order_market(("BTC", "USD"), "SELL", 0.05)
        position_held = False
        
        
    # Semi panic settle off sell    
    if position_held == True and time_now_a - bought_time >= 62 and current_price <= 1.002 * bought_price:
        def CEX_order_market(("BTC", "USD"), "SELL", 0.05)
        position_held = False
        
    # Panic sell
    if position_held == True and time_now_a - bought_time >= 5 and current_price <= 0.98 * bought_price: # 2% sharp decrease allowed. I've seen 1.5% sharp downs just before rises. 
        def CEX_order_market(("BTC", "USD"), "SELL", 0.05) # 0.05 being the all of the buy-in. 5% of wallet, every time.
        position_held = False



# Win Loss Math to deactivate bot if it starts not having a good enough win rate. 
win_history_abcdthen_a = []
loss_history_abcdthen_a = []
ordercount = 1 # a counter by index length


if position_held == False and sold_price > bought_price:
    win_history_abcdthen_a.append(ordercount)

if position_held == False and sold_price < bought_price:
    loss_history_abcdthen_a.append(ordercount)

# List for length    
total_win_loss_abcdthen_a = [len(win_history_abcdthen_a) + len(loss_history_abcdthen_a)]

# Numerical expression of rate. 
win_rate_abcdthen_a = len(win_history_abcdthen_a) / len(total_win_loss_abcdthen_a) # This division is the win percentage out of total transactions amounts.

if win_rate_abcdthen_a < 0.60 and len(total_win_loss_abcdthen_a) >= 20: # At least 20 orders happened, and its recorded wins are lesser than needed.
    abcdthen_a_model = False # This updates the condition above, the bot should stop trading, automatically. 

    if position_held == True: # If any are somehow still traded in, with this bot. 
        def CEX_order_market(("BTC", "USD"), "SELL", 0.05)
        position_held = False


"""
abcd_then_a_model above
"""



"""
abc and then model buys and sells
"""


tried_limit_sell = None

if hourly_bot == True and abcthen_model == True and abcthen_range_constraints_gotten_a == True:

    #abc and then model written without price relations from collected data to set ranges for
    if current_price > price_1_minute_ago and price_1_minute_ago > price_2_minutes_ago and price_2_minutes_ago > price_3_minutes_ago:
        def CEX_order_market(("BTC", "USD"), "BUY", 0.05)
        position_held = True
        
        time_then_b = current_time
        bought_time = time_then_b
        bought_price = price_then_b
        
    if position_held == True and time_now - bought_time >= 4: # Unconditionally sell by time, since data collection suggested it should be bidded for. 
        def CEX_order_limit(("BTC", "USD"), "SELL", 0.05, price) 
        position_held = False
        tried_limit_sell = True
        
    if tried_limit_sell == True:
        if position_held == True and time_now - bought_time >= 4: # Unconditionally sell by time, since data collection suggested it should be bidded for. 
            def CEX_order_limit(("BTC", "USD"), "SELL", 0.05, price) 
            position_held = False
            tried_limit_sell = None
            
    # Semi panic sell after default limit sell.
    if tried_limit_sell == True: # AND, it didn't go through, and an additional threshold condition of down spike
        if position_held == True and time_now - bought_time >= 4 and current_price <= 0.995:
            def CEX_order_market(("BTC", "USD"), "SELL", 0.05) 
            position_held = False
            tried_limit_sell = None
            
    # Final retry of limit sell, unless that semi panic market sell happened.
    if position_held == True and time_now - bought_time >= 5: # In case of rebound up price after limit sell fails above
        def CEX_order_limit(("BTC", "USD"), "SELL", 0.05, price) 
        position_held = False
        
    # Semi panic sell after above final limit sell retry.
    if tried_limit_sell == True: # AND, it didn't go through, and an additional threshold condition of down spike
        if position_held == True and time_now - bought_time >= 5:
            def CEX_order_market(("BTC", "USD"), "SELL", 0.05) 
            position_held = 
            tried_limit_sell = None

    if position_held == True and time_now - bought_time >= 6: # Resort to market sell after fifth minute does not allow limit sell, above.
        def CEX_order_market(("BTC", "USD"), "SELL", 0.05) 
        position_held = False

    if position_held == True and time_now - bought_time >= 7: # Resort to market sell after fifth minute does not allow limit sell, above.
        def CEX_order_market(("BTC", "USD"), "SELL", 0.05) 
        position_held = False


# Win Loss Math to deactivate bot if it starts not gaining a good enough win rate. 
win_history_abcthen = []
loss_history_abcthen = []
ordercount = 1 # a counter by index length


if position_held == False and sold_price > bought_price:
    win_history_abcthen.append(ordercount)

if position_held == False and sold_price < bought_price:
    loss_history_abcthen.append(ordercount)

# List for length    
total_win_loss_abcthen = [len(win_history_abcthen) + len(loss_history_abcthen)]

# Numerical expression of rate. 
win_rate_abcthen = len(win_history_abcthen) / len(total_win_loss_abcthen) # This division is the win percentage out of total transactions amounts.

if win_rate_abcthen < 0.60 and len(total_win_loss_abcthen) >= 20: # At least 20 orders happened, and its recorded wins are lesser than needed, compared to total trades. 
    abcthen_model = False # This updates the condition above, the bot will stop trading, automatically. 

    if position_held == True: # If any are somehow still traded in, with this bot. 
        def CEX_order_market(("BTC", "USD"), "SELL", 0.05)
        position_held = False




"""
abc_then_model above
"""



"""
ab and then model buys and sells
"""


tried_limit_sell = None

if hourly_bot == True and abthen_model == True and abthen_range_constraints_gotten_a == True:

    #ab and then model written without price relations from collected data to set ranges for
    if current_price > price_1_minute_ago and price_1_minute_ago > price_2_minutes_ago:
        def CEX_order_market(("BTC", "USD"), "BUY", 0.05)
        position_held = True
        time_then_c = current_time
        bought_time = time_then_c
        bought_price = price_then_c

    if position_held == True and time_now - bought_time >= 3: # Unconditionally sell by time, since data collection suggested it should be bidded for. 
        def CEX_order_limit(("BTC", "USD"), "SELL", 0.05, price) 
        position_held = False
        tried_limit_sell = True
        
    # In case order did not go through    
    if tried_limit_sell == True:
        if position_held == True and time_now - bought_time >= 3: #  
            def CEX_order_limit(("BTC", "USD"), "SELL", 0.05, price) 
            position_held = False
            tried_limit_sell = None # updates it to restore varible toggle default condition
            
    # Final limit sell retry
    if position_held == True and time_now - bought_time >= 4: # Up to this minute, still retries limit sell, unless, that panic sell below, market sell if threshold. 
        def CEX_order_limit(("BTC", "USD"), "SELL", 0.05, price) 
        position_held = False

    if position_held == True and time_now - bought_time >= 5: # 
        def CEX_order_market(("BTC", "USD"), "SELL", 0.05) 
        position_held = False
        
    if position_held == True and time_now - bought_time >= 6: # 
        def CEX_order_market(("BTC", "USD"), "SELL", 0.05) 
        position_held = False
        
    if position_held == True and time_now - bought_time >= 7: # 
        def CEX_order_market(("BTC", "USD"), "SELL", 0.05) 
        position_held = False

    # Semi panic sell after default limit sell.
    if tried_limit_sell == True: # AND, it didn't go through   
        if position_held == True and time_now - bought_time >= 3 and current_price <= 0.995:
            def CEX_order_market(("BTC", "USD"), "SELL", 0.05) 
            position_held = False



# Win Loss Math to deactivate bot if it starts not gaining a good enough win rate. 
win_history_abthen = []
loss_history_abthen = []
ordercount = 1 # a counter by index length


if position_held == False and sold_price > bought_price:
    win_history_abthen.append(ordercount)

if position_held == False and sold_price < bought_price:
    loss_history_abthen.append(ordercount)

# List for length    
total_win_loss_abthen = [len(win_history_abthen) + len(loss_history_abthen)]

# Numerical expression of rate. 
win_rate_abthen = len(win_history_abthen) / len(total_win_loss_abthen) # This division is the win percentage out of total transactions amounts.

if win_rate_abthen < 0.60 and len(total_win_loss_abthen) >= 20: # At least 20 orders happened, and its recorded wins are lesser than needed, compared to total trades. 
    abthen_model = False # This updates the condition above, the bot will stop trading, automatically. 

    if position_held == True: # If any are somehow still traded in, with this bot. 
        def CEX_order_market(("BTC", "USD"), "SELL", 0.05)
        position_held = False
        
        


"""
ab_then_model above
"""


"""
aandupspike and then model buy sell
"""


tried_limit_sell = None

if minutely_bot == True and aandupspike_model == True and aandupspike_then_range_constraints_gotten_a == True:

    #a upspike and then model written without price relations from collected data to set ranges for
    if current_price > price_1_minute_ago:
        def CEX_order_market(("BTC", "USD"), "BUY", 0.05)
        position_held = True
        time_then_d = current_time
        bought_time = time_then_d
        bought_price = price_now

    if position_held == True and time_now - bought_time >= 2: # Unconditionally sell by time, since data collection suggested it should be bidded for. 
        def CEX_order_limit(("BTC", "USD"), "SELL", 0.05, price) 
        position_held = False
        sold_price = price_now

    if tried_limit_sell == True:
        if position_held == True and time_now - bought_time >= 2: # Unconditionally sell by time, since data collection suggested it should be bidded for. 
            def CEX_order_limit(("BTC", "USD"), "SELL", 0.05, price) 
            position_held = False
            tried_limit_sell = None
            sold_price = price_now

    if tried_limit_sell == True:
        if position_held == True and time_now - bought_time >= 3: # Unconditionally sell by time, since data collection suggested it should be bidded for. 
            def CEX_order_market(("BTC", "USD"), "SELL", 0.05) 
            position_held = False
            tried_limit_sell = None
            sold_price = price_now
            
    if position_held == True and time_now - bought_time >= 4: # Resort to market sell, if somehow, order did not process 
        def CEX_order_market(("BTC", "USD"), "SELL", 0.05) 
        position_held = False
        sold_price = price_now


# Win Loss Math to deactivate bot if it starts ever not having a good enough win rate. 
win_history_aandupspike = []
loss_history_aandupspike = []
ordercount = 1 # a counter by index length


if position_held == False and sold_price > bought_price:
    win_history_aandupspike.append(ordercount)

if position_held == False and sold_price < bought_price:
    loss_history_aandupspike.append(ordercount)

# List for length    
total_win_loss_aandupspike = [len(win_history_aandupspike) + len(loss_history_aandupspike)]

# Numerical expression of rate. 
win_rate_aandupspike = len(win_history_aandupspike) / len(total_win_loss_aandupspike) # This division is the win percentage out of total transactions amounts.

if win_rate_aandspike < 0.60 and len(total_win_loss_aandupspike) >= 20: # At least 20 orders happened, and its recorded wins are lesser than needed, compared to total trades. 
    aandupspike_model = False # This updates the condition above, the bot will stop trading, automatically. 

    if position_held == True: # If any are somehow still traded in, with this bot. 
        def CEX_order_market(("BTC", "USD"), "SELL", 0.05)
        position_held = False
        
        

    
"""
aandupspike_model above
"""

"""
Server slippage fault detector and transaction difference counter for semi-tax counting function
"""


# Record every individual result between buy and sell prices, as actual results, each transaction. Including results as negative numbers. 
buy_sell_results = [] # May or may not become used. 


transaction_result_difference = None
transaction_result_difference = sold_price - bought_price


# Coinbase will also have its own tax-related counting features.


# Record if the sold price was higher than buy price, but, the records do not reflect that despite transaction record, implying LIMIT sell efforts did not prevent loss. 
price_slippage_server_fault_detection = 0
price_slippage_server_fault = None

if bought_price: # As in occurred.
    result_records.append(bought_price)

if sold_price:
    result_records.append(sold_price)


result_records = [] # One buy, one sell, append one, append one.
result_track_position_a = result_records[i] # a buy price
result_track_position_b = result_records[i+1] # a sell price

    
# These records will be appended from elseway.

#                                    Sold price 
if bought_price < sold_price and result_track_position_b < bought_price: # Contradiction catch by counting "actual" result vs occurred given.
    price_slippage_server_fault_detection += 1
    
    
    print("sold price higher than bought price prior, but result is contradictive for its number value, just prior.")

# If the actual result does not == match the bought price and sold price, even if the sell price was higher, but my records didn't say that, it means this was a server fault. 

slippage_transaction_counts_record = int(price_slippage_server_fault_detection)


# This as after-clear every 2, which is after the above check.
if len(result_records) = 2:
    result_records.clear()


if slippage_transaction_counts_record >= 20 and len(buy_sell_results) >= 100: # Despite limit-sell efforts. 
    price_slippage_server_fault = True # As in too high
    
    print("Server slippage rate was determined as too frequent, at over 25% of transactions, counting from over 20 transactions")
    
    hourly_bot = False
    minutely_bot = False    
    
if price_slippage_server_fault == True: # May need to shut the whole crypto bot for then, since, despite limit-sell-ness, slippage still a problem, despite sold at higher.
    
    hourly_bot = False
    minutely_bot = False
    
    print("Server slippage rate was determined over 20%. Auto shutting-down bot by indirect False declaration, not buying anymore.")
     
    # If no quick panic sell, despite emergency auto sells existent in this code file, the remaining x% of coin-in may need to be manually sold on CoinBase.
    
    

"""
Important default None as a falsive, to prevent running API requests, during the above's every written functions. 
"""

connect_run = None # Manual edit-mode input, only. Not within command prompt. Only in this type of editor mode. Save as, make newish.
   
"""
Not using the same user_input() type of function for convenience. This connect_run being non-True by analog edit helps prevent unplanned API runs. 
"""


# I will remember to use None and False as different. 
if hourly_bot == False or minutely_bot == False and position_held == True:
    position_held = False # This shall be made to work with Coinbase as auto-panic-sell, 100% sell all. 100% sell all, every time, anyway.
    connect_run = False # The additive condition to make request reponses thereafter
    
    
if hourly_bot == False or minutely_bot == False:
    connect_run = None
    
   
# When requesting connection and running with API, only as manually input for the 2nd part (connect_run variable), the bot shall sleep 1 minutely.    
if hourly_bot == True or minutely_bot == True and connect_run == True: # As conditional for sleep 1 minute mode, for 1 minutely live action request with API, to begin.    

    # This entire bot sleeps every minute. This as condition to refresh every 1 minute. 
    # Only when both conditions are true that way, so that the above tasks are not constantly conflictin with processing capacity, per minute, while sleeping 1m. 
    time.sleep(minutes=1)
    # This as row bot.
    last_time_check = True # This was a perf_counter variable, above