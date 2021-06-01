import web3
from web3.gas_strategies.time_based import medium_gas_price_strategy
from web3.gas_strategies.rpc import rpc_gas_price_strategy
from web3.exceptions import TransactionNotFound
from web3._utils.method_formatters import log_entry_formatter
import json
import os
from pathlib import Path
from eth_account.messages import defunct_hash_message, encode_defunct
from eth_account import Account
from eth_keys import keys
from hexbytes import HexBytes
from functools import lru_cache
from .settings import config
import requests

import logging
LOGGER = logging.getLogger(__name__)

DECIMALS = 10**18

NONCE = None

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

@lru_cache(maxsize=2)
def get_token_contract_abi():
    return json.load(open(os.path.join(Path(__file__).resolve().parent, 'abi/ALEPHERC20.json')))

@lru_cache(maxsize=2)
def get_token_contract(web3):
    tokens = web3.eth.contract(address=web3.toChecksumAddress(config['token']['address']), abi=get_token_contract_abi())
    return tokens

def get_gas_price(chain_id=1):
    if chain_id == 1:
        resp = requests.get('https://www.gasnow.org/api/v3/gas/price?utm_source=alephim')
        content = resp.json()
        return content['data']['standard']
    else:
        w3 = get_web3()
        return w3.eth.generateGasPrice()

@lru_cache(maxsize=2)
def get_account():
    if config['web3']['pkey']:
        pri_key = HexBytes(config['web3']['pkey'])
        account = Account.privateKeyToAccount(pri_key)
        return account
    else:
        return None

def transfer_tokens(targets, metadata=None):
    global NONCE
    w3 = get_web3()
    contract = get_token_contract(w3)
    account = get_account()

    addr_count = len(targets.keys())
    total = sum(targets.values())
    
    LOGGER.info(f"Preparing transfer of {total} to {addr_count}")
    gas_price = get_gas_price(config['web3']['chain_id'])
    
    if NONCE is None:
        NONCE = w3.eth.getTransactionCount(account.address)
    tx_hash = None
    
    success = False
    
    try:
        balance = contract.functions.balanceOf(account.address).call()/DECIMALS
        if (total >= balance):
            raise ValueError(f"Balance not enough ({total}/{balance})")
        
        tx = contract.functions.batchTransfer(
            [w3.toChecksumAddress(addr) for addr in targets.keys()],
            [int(amount*DECIMALS) for amount in targets.values()])
        # gas = tx.estimateGas({
        #     'chainId': 1,
        #     'gasPrice': gas_price,
        #     'nonce': NONCE,
        #     })
        # print(gas)
        tx = tx.buildTransaction({
            'chainId': config['web3']['chain_id'],
            'gas': 20000+(20000*len(targets)),
            'gasPrice': gas_price,
            'nonce': NONCE,
            })
        signed_tx = account.signTransaction(tx)
        tx_hash = w3.eth.sendRawTransaction(signed_tx.rawTransaction).hex()
        success = True
        NONCE += 1
        LOGGER.info(f"TX {tx_hash} created on ETH")
    
    except:
        LOGGER.exception("Error packing ethereum TX")
    
    if 'targets' not in metadata:
        metadata['targets'] = list()
    metadata['targets'].append({
        'success': success,
        'status': success and 'pending' or 'failed',
        'tx': tx_hash,
        'chain': 'ETH',
        'sender': account.address,
        'targets': targets,
        'total': total,
        'contract_total': str(int(total*DECIMALS))
    })

    return metadata


def get_logs_query(web3, contract,
                   start_height, end_height, topics,
                   load_mode='rpc'):
    if load_mode == 'rpc':
        logs = web3.eth.getLogs({'address': contract.address,
                                'fromBlock': start_height,
                                'toBlock': end_height,
                                'topics': topics})
        for log in logs:
            yield log
    elif load_mode == 'explorer':
        params = {
            "module": "logs",
            "action": "getLogs",
            "fromBlock": start_height,
            "toBlock": end_height,
            "address": contract.address,
            "apikey": config['web3']['explorer_api_key']
        }
        for i, topic in enumerate(topics):
            params[f"topic{i}"] = topic
            if i > 0:
                params[f"topic{i-1}_{i}_opr"] = "and"

        resp = requests.get(
            "https://api.bscscan.com/api",
            params=params
        )
        for item in resp.json()['result']:
            item['blockHash'] = None
            yield log_entry_formatter(item)


def get_logs(web3, contract, start_height, topics=None):
    load_mode = config['web3'].get('mode', 'rpc')
    try:
        logs = get_logs_query(web3, contract,
                              start_height+1, 'latest', topics=topics,
                              load_mode=load_mode)
        for log in logs:
            yield log
    except ValueError as e:
        # we got an error, let's try the pagination aware version.
        if (getattr(e, 'args')
                and len(e.args)
                and e.args[0]['code'] not in [-32005, -32000, -32603]):
            return

        last_block = web3.eth.blockNumber
#         if (start_height < config.ethereum.start_height.value):
#             start_height = config.ethereum.start_height.value

        end_height = start_height + config['web3']['big_block_range']

        while True:
            try:
                logs = get_logs_query(web3, contract,
                                      start_height, end_height, topics=topics,
                                      load_mode=load_mode)
                for log in logs:
                    yield log

                start_height = end_height + 1
                end_height = start_height + config['web3']['big_block_range']

                if start_height > last_block:
                    LOGGER.info("Ending big batch sync")
                    break

            except ValueError as e:
                if e.args[0]['code'] not in [-32005, -32000, -32603]:
                    end_height = start_height + config['web3']['small_block_range']
                else:
                    raise