from web3 import Web3
from openpyxl import load_workbook
from web3.middleware import geth_poa_middleware

from datetime import datetime
import json
import csv

Modified_Excel = 'modified_pair.xlsx'
URL = 'https://bsc-dataseed1.binance.org'
RouterContract = "0x10ED43C718714eb63d5aA57B78B54704E256024E"
BNBTokenAddress = "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c"
USDTokenAddress  = "0x55d398326f99059fF775485246999027B3197955"

pool_addrs = dict()
small_price_data = dict()
medium_price_data = dict()
large_price_data = dict()

with open('token_abi.json', 'r') as f:
    tokenABI = json.load(f)

with open('v2_abi.json', 'r') as f:
    v2_abi = json.load(f)

with open('v3_abi.json', 'r') as f:
    v3_abi = json.load(f)

with open('thena_abi.json', 'r') as f:
    thenaABI = json.load(f)

def getBNBPrice(provider: Web3) -> float:   
    bnbToSell = provider.to_wei("1", "ether")
    contractAddr = w3.to_checksum_address(RouterContract)
    router = provider.eth.contract(address=contractAddr, abi=v2_abi)
    amountOut = router.functions.getAmountsOut(bnbToSell, [BNBTokenAddress, USDTokenAddress]).call()
    amountOut = provider.from_wei(amountOut[1], 'ether')
    return amountOut

def getTokenPriceFromPoolAddress(provider: Web3, row: list, bnb_price: float) -> float:
    dex_type = row[0]  # the cell of dex type eg: Pancakeswap v2
    pair_type = row[1] # the cell of pair type eg: CATI/USDT
    pool_addr = row[2] # the cell of pool address eg: 0x1234567890ABCDEF
    pool_addr = provider.to_checksum_address(pool_addr)

    try:
        before, separator, majorToken = pair_type.partition("/")
        if(dex_type == "Pancakeswap v3" or dex_type == "Uniswap v3"):
            # Create a contract object for the liquidity pool
            pool_contract = provider.eth.contract(address=pool_addr, abi=v3_abi)

            # Call slot0 to get the current pool state
            slot0 = pool_contract.functions.slot0().call()
            print(slot0)
            sqrt_price_x96 = slot0[0]  # Get the current price from slot0

            def decode_sqrt_price(sqrt_price_x96):
                price = (sqrt_price_x96 / (2**96))**2
                return price

            token_price = decode_sqrt_price(sqrt_price_x96)
            if(majorToken == "WETH"):
                token_price = 1e12 * token_price
            else:
                token_price = 1 / token_price
        elif(dex_type == "THENA FUSION"):
            pool_contract = provider.eth.contract(address=pool_addr, abi=thenaABI)

            # Fetch reserves from the pool (usually it's getReserves or a similar function)
            globalState = pool_contract.functions.globalState().call()

            sqrt_price_x64 = globalState[0]

            def decode_sqrt_price(sqrt_price_x64):
                price = (sqrt_price_x64 / (2**96))**2
                return price
            
            token_price = decode_sqrt_price(sqrt_price_x64)
        else:
            # Create a contract object for the liquidity pool                                                                                                                                                                                           
            pool_contract = provider.eth.contract(address=pool_addr, abi=v2_abi)


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
        
        if(majorToken == "WBNB" or majorToken == "BNB"):
            token_price = float(token_price) * float(bnb_price)

        return token_price
    except Exception as e:
        print(f"Error fetching token price for {pool_addr}: {e}")
        return 0

def isStableCoin(token_name: str) -> bool:
    if(token_name == "USDT" or token_name == "WBNB" or token_name == "ETH" or token_name == "USDC"):
        return True

def calculateBalance(token_name1: str, token_name2: str, balance: int):
    majorToken1, pool_addr1, token_price1 = pool_addrs[token_name1]
    majorToken2, pool_addr2, token_price2 = pool_addrs[token_name2]

    if(pool_addr1 == "" or pool_addr2 == ""):
        return 0
    elif(token_name1 == token_name2):
        return 1
    else:
        return token_price1 * balance / token_price2


if __name__ == '__main__':
    w3 = Web3(Web3.HTTPProvider(URL))
    if w3.is_connected():

        small_price = int(input("Please enter small price: "))
        medium_price = int(input("Please enter medium price: "))
        large_price = int(input("Please enter large price: "))

        with open('pairs.csv', mode='r') as file:
            reader = csv.reader(file)

            is_title = True
            for row in reader:
                if(is_title):
                    is_title = False
                    continue

                print(row)

                try:
                    dex_type = row[0]  # the cell of dex type eg: Pancakeswap v2
                    pair_type = row[1] # the cell of pair type eg: CATI/USDT
                    pool_addr = row[2] # the cell of pool address eg: 0x1234567890ABCDEF
                
                    quoteToken, separator, majorToken = pair_type.partition("/")
                    checksum_address = w3.to_checksum_address(pool_addr) # convert the pool address to checksum eg: 0x123ab4567ef89 -> 0x123Ab456eF89

                    bnb_price = getBNBPrice(provider = w3)                
                    token_price = getTokenPriceFromPoolAddress(provider = w3, row=row, bnb_price = bnb_price)

                    if(quoteToken in pool_addrs):
                        if(isStableCoin(quoteToken)):
                            pool_addrs[quoteToken] = [majorToken, checksum_address, token_price]
                    else:
                        pool_addrs[quoteToken] = [majorToken, checksum_address, token_price]
                except:
                    pool_addrs[quoteToken] = [majorToken, "", 0]
                    continue

        index = 1
        for quoteToken, (majorToken, pool_addr, token_price) in pool_addrs.items():
            
            if 0 not in small_price_data:
                small_price_data[0] = []

            if 0 not in medium_price_data:
                medium_price_data[0] = []

            if 0 not in large_price_data:
                large_price_data[0] = []
                
            if(index == 1):
                small_price_data[0].append("")
                medium_price_data[0].append("")
                large_price_data[0].append("")
            
            small_price_data[0].append(quoteToken)
            medium_price_data[0].append(quoteToken)
            large_price_data[0].append(quoteToken)
        
            small_price_data[index + 1] = []
            small_price_data[index + 1].insert(0, quoteToken)
            medium_price_data[index + 1] = []
            medium_price_data[index + 1].insert(0, quoteToken)
            large_price_data[index + 1] = []
            large_price_data[index + 1].insert(0, quoteToken)

            index += 1


        for i in range(index):
            token1 = small_price_data[0][i]
            if(token1 == ""): continue

            print(f'token1: {token1}')
            for j in range(index):
                token2 = small_price_data[0][j]
                if(token2 == ""): continue
                
                print(f'token2: {token2}')
                exchange_balance = calculateBalance(token1, token2, small_price)
                small_price_data[i + 1].append(exchange_balance)

                exchange_balance = calculateBalance(token1, token2, medium_price)
                medium_price_data[i + 1].append(exchange_balance)

                exchange_balance = calculateBalance(token1, token2, large_price)
                large_price_data[i + 1].append(exchange_balance)

        with open('small_price.csv', mode='w', newline='') as file:
            writer = csv.writer(file)
            writer.writerows(small_price_data.values())

        with open('medium_price.csv', mode='w', newline='') as file:
            writer = csv.writer(file)
            writer.writerows(medium_price_data.values())

        with open('large_price.csv', mode='w', newline='') as file:
            writer = csv.writer(file)
            writer.writerows(large_price_data.values())

        print("done!!!")