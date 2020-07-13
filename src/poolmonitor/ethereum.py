import web3
from web3.gas_strategies.time_based import medium_gas_price_strategy
from web3.gas_strategies.rpc import rpc_gas_price_strategy
from web3.exceptions import TransactionNotFound
import json
from eth_account.messages import defunct_hash_message, encode_defunct
from eth_account import Account
from eth_keys import keys
from hexbytes import HexBytes
from async_lru import alru_cache
from functools import lru_cache
from aiocache import cached
from .settings import config

@lru_cache(maxsize=2)
def get_web3():
    w3 = None
    if config['web3'].get('url'):
        w3 = web3.Web3(web3.providers.rpc.HTTPProvider(config['web3'].get('url')))
    else:
        from web3.auto.infura import w3 as iw3
        assert w3.isConnected()
        w3 = iw3
    
    w3.eth.setGasPriceStrategy(rpc_gas_price_strategy)
    
    return w3