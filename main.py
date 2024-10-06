from web3 import Web3
from openpyxl import load_workbook
from web3.middleware import geth_poa_middleware

from datetime import datetime
import json

Modified_Excel = 'modified_pair.xlsx'
URL = 'https://bsc-dataseed1.binance.org'
RouterContract = "0x10ED43C718714eb63d5aA57B78B54704E256024E"
BNBTokenAddress = "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c"
USDTokenAddress  = "0x55d398326f99059fF775485246999027B3197955"
pool_addrs = dict()

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


# def gettoken_priceFromTokenAddr(provider: Web3, contractAddr: str, tokenAddress: str, tokensToSell: int) -> float:
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

def getTokenPriceFromPoolAddress(provider: Web3, index: int, bnb_price: float) -> float:
    dex_type = sheet[f'A{index}'].value  # the cell of dex type eg: Pancakeswap v2
    pair_type = sheet[f'B{index}'].value # the cell of pair type eg: CATI/USDT
    pool_addr = sheet[f'C{index}'].value # the cell of pair type eg: CATI/USDT
    pool_addr = provider.to_checksum_address(pool_addr)

    try:
        before, separator, majorToken = pair_type.partition("/")
        if(dex_type == "Pancakeswap v3" or dex_type == "Uniswap v3"):
            # Create a contract object for the liquidity pool
            pool_contract = provider.eth.contract(address=pool_addr, abi=v3_abi)

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

def writeToExcel(block_number: int, index:int, token_price: float, save: bool):
    sheet[f'D{index}'] = token_price

    current_date = datetime.now().date()
    current_time = datetime.now().time().strftime("%H:%M:%S")
    sheet[f'E{index}'] = f'{current_date}:{current_time}'

    dex_type = sheet[f'A{index}'].value  # the cell of dex type eg: Pancakeswap v2
    pair_type = sheet[f'B{index}'].value # the cell of pair type eg: CATI/USDT

    if(block_number < 0):
        print(f'✅ 🛒: {dex_type},   🔗: {pair_type},   💰: {token_price},   ⏰: {current_date}:{current_time}')
    else:
        print(f'✅ Updated : {block_number}, 🛒: {dex_type},   🔗: {pair_type},   💰: {token_price},   ⏰: {current_date}:{current_time}')

    if(save):
        excel.save(Modified_Excel)

if __name__ == '__main__':
    w3 = Web3(Web3.HTTPProvider(URL))
    if w3.is_connected():
        excel = load_workbook('pairs.xlsx')
        sheet = excel['pairs']

        for i in range(2, 7452):
        # for i in range(2, 5):
            try:
                dex_type = sheet[f'A{i}'].value  # the cell of dex type eg: Pancakeswap v2
                pair_type = sheet[f'B{i}'].value # the cell of pair type eg: CATI/USDT
                pool_addr = sheet[f'C{i}'].value # the cell of pool address eg: 0x1234567890ABCDEF
                
                checksum_address = w3.to_checksum_address(pool_addr) # convert the pool address to checksum eg: 0x123ab4567ef89 -> 0x123Ab456eF89
                pool_addrs[checksum_address] = i
                
                bnb_price = getBNBPrice(provider = w3)                
                token_price = getTokenPriceFromPoolAddress(provider = w3, index=i, bnb_price = bnb_price)
                writeToExcel(-1, i, token_price, False)
            except Exception as e:
                excel.save(Modified_Excel)
                print(f'👉 Saved to modified_pair.xlsx file')
                print(f"Error occoured {i}: {e}")

        excel.save(Modified_Excel)
        w3.middleware_onion.inject(geth_poa_middleware, layer=0)

        while(1):
            # Get the block data
            block = w3.eth.get_block('latest', full_transactions=False)

            # Get all transactions from the block
            transactions = block['transactions']

            for tx_hash in block['transactions']:
                tx = w3.eth.get_transaction(tx_hash)
                # if not isinstance(tx, dict):
                #     continue

                from_address = tx['from']
                to_address = tx['to']

                if(from_address in pool_addrs):
                    index = pool_addrs[from_address]

                elif(to_address in pool_addrs):
                    index = pool_addrs[to_address]

                else:
                    continue

                bnb_price = getBNBPrice(provider = w3)                
                token_price = getTokenPriceFromPoolAddress(provider = w3, index=index + 1, bnb_price = bnb_price)

                writeToExcel(block.number, index, token_price, True)