# Import sample modules
from web3 import Web3
from web3.middleware import geth_poa_middleware

from datetime import datetime
import json
import csv

# Utility Variables for BSC
RPC_Endpoint = 'https://bsc-dataseed1.binance.org'
RouterContract = "0x10ED43C718714eb63d5aA57B78B54704E256024E"
BNBTokenAddress = "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c"
USDTokenAddress  = "0x55d398326f99059fF775485246999027B3197955"

# All pool informations
pool_array = {}
pool_map = {}
# All token informations
token_array = {}
# All base token informations
base_array = dict()

# Import ABIs
with open('token_abi.json', 'r') as f:
    tokenABI = json.load(f)
with open('v2_abi.json', 'r') as f:
    v2_abi = json.load(f)
with open('v3_abi.json', 'r') as f:
    v3_abi = json.load(f)
with open('thena_abi.json', 'r') as f:
    thenaABI = json.load(f)

# Getting the BNB Price
def getBNBPrice(provider: Web3) -> float:   
    bnbToSell = provider.to_wei("1", "ether")
    contractAddr = w3.to_checksum_address(RouterContract)
    router = provider.eth.contract(address=contractAddr, abi=v2_abi)
    amountOut = router.functions.getAmountsOut(bnbToSell, [BNBTokenAddress, USDTokenAddress]).call()
    amountOut = provider.from_wei(amountOut[1], 'ether')
    return amountOut

# Getting the tokenPrice from pool
def getTokenPriceFromPoolAddress(provider: Web3, 
                                 dex_name : str,
                                 quoteToken : str,
                                 baseToken : str,
                                 pool_address : str) -> float:
    try:
        if(dex_name == "Pancakeswap v3" or dex_name == "Uniswap v3"):
            # Create a contract object for the liquidity pool
            pool_contract = provider.eth.contract(address=pool_address, abi=v3_abi)

            # Call slot0 to get the current pool state
            slot0 = pool_contract.functions.slot0().call()
            # print(slot0)
            sqrt_price_x96 = slot0[0]  # Get the current price from slot0

            def decode_sqrt_price(sqrt_price_x96):
                price = (sqrt_price_x96 / (2**96))**2
                return price

            token_price = decode_sqrt_price(sqrt_price_x96)
            # if(baseToken == "WETH"):
            #     token_price = 1e12 * token_price
            # else:
            #     token_price = 1 / token_price
                
        elif(dex_name == "THENA FUSION"):
            pool_contract = provider.eth.contract(address=pool_address, abi=thenaABI)

            # Fetch reserves from the pool (usually it's getReserves or a similar function)
            globalState = pool_contract.functions.globalState().call()

            sqrt_price_x64 = globalState[0]

            def decode_sqrt_price(sqrt_price_x64):
                price = (sqrt_price_x64 / (2**96))**2
                return price
            
            token_price = decode_sqrt_price(sqrt_price_x64)
            
        else:
            # Create a contract object for the liquidity pool                                                                                                                                                                                           
            pool_contract = provider.eth.contract(address=pool_address, abi=v2_abi)

            # Call getReserves to fetch the pool reserves
            reserves = pool_contract.functions.getReserves().call()
            token0_address = pool_contract.functions.token0().call()

            # Reserve 0 (Token0, e.g. WBNB), Reserve 1 (Token1, your token)
            reserve0 = reserves[0]  # Token1 (your token)
            reserve1 = reserves[1]  # WBNB or BNB

            # Calculate price
            if(token0_address == BNBTokenAddress or token0_address == USDTokenAddress):
                token_price = reserve0 / reserve1
            else:
                token_price = reserve1 / reserve0
        
        bnb_price = getBNBPrice(provider)
        if(baseToken == "WBNB"):
            token_price = float(token_price) * float(bnb_price)

        return token_price
    except Exception as e:
        print(f"Error fetching token price for {pool_address}: {e}")
        return 0

def getTokenPrice(provider: Web3, 
                 token_name : str) -> float:
    
    try:
        if (token_name not in pool_array):
            print("Unfortunately, unable to find the relevant token pool")
            return 0

        baseToken = ""
        if ("USDT" in pool_array[token_name]):
            baseToken = "USDT"
        
        elif ("WBNB" in pool_array[token_name]):
            baseToken = "WBNB"
        
        if baseToken != "":
            dex_name = pool_array[token_name][baseToken]["dex_name"]
            pool_address = pool_array[token_name][baseToken]["address"]
            
            return getTokenPriceFromPoolAddress(provider, dex_name, token_name, baseToken, pool_address)
        else:
            # A -> Route, Route -> USDT or WBNB
            route = ""
            if "route" not in pool_array[token_name]:
                return 0
            route = pool_array[token_name]["route"]
            
            dex_name = pool_array[token_name][route]["dex_name"]
            pool_address = pool_array[token_name][route]["address"]
            token_price = getTokenPriceFromPoolAddress(provider, dex_name, token_name, route, pool_address)
            
            token_price2 = getTokenPrice(provider, route)
            
            return float(token_price) * float(token_price2)
        
    except Exception as e:
        print("Error : ", e)
        return 0
    
        

# Check if stable coin
def isStableCoin(token_name: str) -> bool:
    if(token_name == "USDT" or token_name == "WBNB" or token_name == "USDC"):
        return True
    
def isWBNB(token_name: str) -> bool:
    if(token_name == "WBNB"):
        return True

# Calculate Balance
def calculateBalance(token_name1: str, token_name2: str, balance: int):
    baseToken1, pool_addr1, token_price1 = pool_array[token_name1]
    baseToken2, pool_addr2, token_price2 = pool_array[token_name2]

    if(pool_addr1 == "" or pool_addr2 == ""):
        return 0
    elif(token_name1 == token_name2):
        return 1
    else:
        return token_price1 * balance / token_price2

def updateResult(provider : Web3):
    w3.middleware_onion.inject(geth_poa_middleware, layer=0)

    # Get the latest block
    block = w3.eth.get_block('latest', full_transactions=False)
    block_number = block.number

    print(f'Latest Block Number : {block_number}')
    # Get all transactions from the block
    transactions = block['transactions']

    index = 0
    monitored = 0
    for tx_hash in block['transactions']:
        if (index % 10 ==0):
            print('.',end='', flush=True)
        index += 1
        tx = w3.eth.get_transaction(tx_hash)

        from_address = tx['from']
        to_address = tx['to']
        
        quoteToken = ""
        baseToken = ""
        
        if(from_address in pool_map):
            quoteToken = pool_map[from_address]["quoteToken"]
            baseToken = pool_map[from_address]["baseToken"]
            monitored += 1

        elif(to_address in pool_map):
            quoteToken = pool_map[to_address]["quoteToken"]
            baseToken = pool_map[to_address]["baseToken"]
            monitored += 1

        else:
            continue

        print(quoteToken, "/", baseToken)

    print('')
    print("Total transactions :",index)
    print("Monitored :",monitored)

        # bnb_price = getBNBPrice(provider = w3)                
        # token_price = getTokenPriceFromPoolAddress(provider = w3, index=index + 1, bnb_price = bnb_price)

        # writeToExcel(block_number, index, token_price, True)

# Main function
if __name__ == '__main__':
    w3 = Web3(Web3.HTTPProvider(RPC_Endpoint))
    if w3.is_connected():
        print("====================================================")
        print("🗝️  Start analyzing pairs.csv file ...")
        print("====================================================")
        
        with open('pairs_all.csv', mode='r') as file:
            reader = csv.reader(file)
            cnt = 0
            for row in reader:
                if(cnt == 0):
                    cnt = 1
                    continue

                try: 
                    dex_name = row[0]       # the cell of dex type eg: Pancakeswap v2
                    token_pairs = row[1]    # the cell of pair type eg: CATI/USDT
                    pool_address = row[2]   # the cell of pool address eg: 0x1234567890ABCDEF
                
                    quoteToken, separator, baseToken = token_pairs.partition("/")
                    pool_address = w3.to_checksum_address(pool_address) # convert the pool address to checksum eg: 0x123ab4567ef89 -> 0x123Ab456eF89

                    if quoteToken not in pool_array:
                        pool_array[quoteToken] = {}
                    pool_array[quoteToken][baseToken] = {"dex_name" : dex_name, "address" : pool_address}
                    pool_map[pool_address] = {"quoteToken" : quoteToken, "baseToken" : baseToken}
                    
                    if baseToken not in pool_array:
                        pool_array[baseToken] = {}
                    pool_array[baseToken][quoteToken] = {"dex_name" : dex_name, "address" : pool_address}
                    
                except:
                    # ignore tokens with the unknown address
                    continue
            
                cnt += 1
                
        # Filter tokens ()
        print("====================================================")
        print("🗝️  Filtering tokens ...")        
        print("====================================================")

        for quoteToken in pool_array:
            if "WBNB" not in pool_array[quoteToken] and "USDT" not in pool_array[quoteToken]:
                route = ""
                for baseToken in pool_array[quoteToken]:
                    if "WBNB" in pool_array[baseToken] or "USDT" in pool_array[baseToken]:
                        route = baseToken
                        break
                
                if (route != ""):
                    token_array[quoteToken] = True
                    pool_array[quoteToken]["route"] = route
            else:
                token_array[quoteToken] = True

        print("====================================================")
        # while(1):
        updateResult(w3)
        

        # print ("Valuable Tokens")
        # for index, quoteToken in enumerate(token_array):
        #     print(index, quoteToken)
        #     token_price = getTokenPrice(w3, quoteToken)
        #     print("price : ", token_price, "$")


        # print("Specified Base Tokens : ")
        # for index, cur in enumerate(base_array):
        #     print(index, " : ",cur)
        
#       small_price = int(input("Input small price 💰 : "))
#       medium_price = int(input("Input medium price 💰 : "))
#       large_price = int(input("Input large price 💰 : "))
        
#       print("1 ", quoteToken, " = ", token_price, " ", baseToken)
#       print("https://dexscreener.com/bsc/" + pool_address)

#       bnb_price = getBNBPrice(provider = w3)                
#       token_price = getTokenPriceFromPoolAddress(provider = w3, 
#       dex_name = dex_name,
#       quoteToken = quoteToken, 
#       baseToken = baseToken,
#       pool_address = pool_address,
#       bnb_price = bnb_price)