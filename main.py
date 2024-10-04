from web3 import Web3
from openpyxl import load_workbook
from datetime import datetime
import json

URL = 'https://bsc-dataseed1.binance.org'
RouterContract = "0x10ED43C718714eb63d5aA57B78B54704E256024E"
BNBTokenAddress = "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c"
USDTokenAddress  = "0x55d398326f99059fF775485246999027B3197955"

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


# def getTokenPriceFromTokenAddr(provider: Web3, contractAddr: str, tokenAddress: str, tokensToSell: int) -> float:
#     try:
#         tokenRouter = provider.eth.contract(address=tokenAddress, abi=tokenABI)
#         tokenDecimals = tokenRouter.functions.decimals().call()
#         tokensToSell = int(str(tokensToSell).ljust(tokenDecimals + len(str(tokensToSell)), '0'))

#         router = provider.eth.contract(address=contractAddr, abi=pancakeSwapABI)
#         amountOut = router.functions.getAmountsOut(tokensToSell, [tokenAddress, BNBTokenAddress]).call()
#         amountOut = provider.from_wei(amountOut[1], 'ether')
#         print(f'💰 TOKEN PRICE: {amountOut}')
#         return amountOut
#     except Exception as e:
#         print(f"Error fetching token price for {tokenAddress}: {e}")
#         return 0

def getTokenPriceFromPoolAddr(provider: Web3, poolAddr: str, dexType: str, bnbPrice: float, pairType: str) -> float:
    try:
        before, separator, majorToken = pairType.partition("/")
        if(dexType == "Pancakeswap v3" or dexType == "Uniswap v3"):
            # Create a contract object for the liquidity pool
            pool_contract = provider.eth.contract(address=poolAddr, abi=v3_abi)

            # Call slot0 to get the current pool state
            slot0 = pool_contract.functions.slot0().call()
            sqrt_price_x96 = slot0[0]  # Get the current price from slot0

            def decode_sqrt_price(sqrt_price_x96):
                price = (sqrt_price_x96 / (2**96))**2
                return price

            token_price = decode_sqrt_price(sqrt_price_x96)
            if(majorToken == "WETH"):
                token_price = 1e12 * token_price
            else:
                token_price = 1 / token_price
        elif(dexType == "THENA FUSION"):
            pool_contract = provider.eth.contract(address=poolAddr, abi=thenaABI)

            # Fetch reserves from the pool (usually it's getReserves or a similar function)
            globalState = pool_contract.functions.globalState().call()

            sqrt_price_x64 = globalState[0]

            def decode_sqrt_price(sqrt_price_x64):
                price = (sqrt_price_x64 / (2**96))**2
                return price
            
            token_price = decode_sqrt_price(sqrt_price_x64)
        else:
            # Create a contract object for the liquidity pool                                                                                                                                                                                           
            pool_contract = provider.eth.contract(address=poolAddr, abi=v2_abi)


            # Call getReserves to fetch the pool reserves
            reserves = pool_contract.functions.getReserves().call()

            # Reserve 0 (Token0, e.g. WBNB), Reserve 1 (Token1, your token)
            reserve0 = reserves[0]  # Token1 (your token)
            reserve1 = reserves[1]  # WBNB or BNB

            # Calculate price of Token1 in terms of WBNB
            token_price = reserve1 / reserve0
        
        if(majorToken == "WBNB" or majorToken == "BNB"):
            token_price = float(token_price) * float(bnbPrice)

        print(f'✅ 🛒: {dexType},   🔗: {pairType},   💰: {token_price}')
        return token_price
    except Exception as e:
        print(f"Error fetching token price for {poolAddr}: {e}")
        return 0

if __name__ == '__main__':
    w3 = Web3(Web3.HTTPProvider(URL))
    if w3.is_connected():
        excel = load_workbook('pairs.xlsx')
        sheet = excel['pairs']

        for i in range(2, 7452):
        # for i in range(7012, 7022):
            try:
                dexType = sheet[f'A{i}'].value  # the cell of dex type eg: Pancakeswap v2
                pairType = sheet[f'B{i}'].value # the cell of pair type eg: CATI/USDT
                poolAddr = sheet[f'C{i}'].value # the cell of pool address eg: 0x1234567890ABCDEF

                tokensToSell = 1
                checksum_address = w3.to_checksum_address(poolAddr) # convert the pool address to checksum eg: 0x123ab4567ef89 -> 0x123Ab456eF89
                
                bnb_price = getBNBPrice(provider = w3)                
                priceInBNB = getTokenPriceFromPoolAddr(provider = w3, poolAddr = checksum_address, dexType = dexType, bnbPrice = bnb_price, pairType = pairType)
                sheet[f'H{i}'] = priceInBNB

                if priceInBNB > 0:
                    sheet[f'J{i}'] = '✔✔✔'
                else:
                    sheet[f'J{i}'] = '❌❌❌'

                current_date = datetime.now().date()
                current_time = datetime.now().time().strftime("%H:%M:%S")
                sheet[f'J{i}'] = f'{current_date}:{current_time}'
            except Exception as e:
                excel.save('modified_pair.xlsx')
                print(f'👉 Saved to modified_pair.xlsx file')
                print(f"Error occoured {i}: {e}")

        excel.save('modified_pair.xlsx')
        print(f'👉 Saved to modified_pair.xlsx file')


