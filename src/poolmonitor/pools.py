import json
import os
from pathlib import Path
from .settings import config
from .ethereum import get_web3


from web3 import Web3
from web3._utils.events import (
    construct_event_topic_set,
)
from web3.middleware import geth_poa_middleware, local_filter_middleware
from web3.contract import get_event_data
from web3.gas_strategies.rpc import rpc_gas_price_strategy

def get_contract_abi():
    return json.load(open(os.path.join(Path(__file__).resolve().parent, 'abi/IUniswapV2Pair.json')))['abi']

def get_pair(address, web3):
    return web3.eth.contract(address,
                             abi=get_contract_abi())

def set_pools():
    web3 = get_web3()
    for pool in config['pools']:
        pool['contract'] = get_pair(Web3.toChecksumAddress(pool['address']), web3)


def get_logs_query(web3, contract, start_height, end_height, topics):
    logs = web3.eth.getLogs({'address': contract.address,
                             'fromBlock': start_height,
                             'toBlock': end_height,
                             'topics': topics})
    for log in logs:
        yield log

def get_logs(web3, contract, start_height, topics=None):
    print(start_height)
    try:
        logs = get_logs_query(web3, contract,
                              start_height+1, 'latest', topics=topics)
        for log in logs:
            yield log
    except ValueError as e:
        # we got an error, let's try the pagination aware version.
        if e.args[0]['code'] != -32005:
            return

        last_block = web3.eth.blockNumber
#         if (start_height < config.ethereum.start_height.value):
#             start_height = config.ethereum.start_height.value

        end_height = start_height + 6000

        while True:
            try:
                logs = get_logs_query(web3, contract,
                                      start_height, end_height, topics=topics)
                for log in logs:
                    yield log

                start_height = end_height + 1
                end_height = start_height + 6000

                if start_height > last_block:
                    LOGGER.info("Ending big batch sync")
                    break

            except ValueError as e:
                if e.args[0]['code'] == -32005:
                    end_height = start_height + 100
                else:
                    raise


def process_pool_history(pool, per_block):
    abi = pool['contract'].events.Transfer._get_event_abi()
    web3 = get_web3()
    topic = construct_event_topic_set(abi, web3.codec)
    weights = dict()
    balances = dict()
    reward_start = max(pool['start_height'], config['reward_start'])
    last_height = reward_start

    def update_weights(since, current):
        for addr, value in balances.items():
            if value > 0:
                weights[addr] = weights.get('addr', 0) + (value * (current-since))

    for i in get_logs(web3, pool['contract'], pool['start_height'], topics=topic):
        evt_data = get_event_data(web3.codec, abi, i)
        args = evt_data['args']
        height = evt_data['blockNumber']
        if height > reward_start:
            update_weights(last_height, height)

        balances[args['from']] = balances.get(args['from'], 0) - args.value
        balances[args.to] = balances.get(args.to, 0) + args.value
        last_height = height
    
    height = web3.eth.blockNumber
    update_weights(last_height, height)
    total_weight = sum(weights.values())
    total_balance = sum([b for b in balances.values() if b > 0])
    weights = {a: w / total_weight for a, w in weights.items()}
    print(weights)
    balparts = {a: w / total_balance for a, w in balances.items() if w > 0}
    print(balparts)

    total_blocks = height - reward_start
    reward_owed = {a: w*per_block*total_blocks for a, w in balparts.items()}
    print(reward_owed)
    print("Total", sum(reward_owed.values()))

def get_pool_weight(pool):
    t0, t1, last_height = pool['contract'].functions.getReserves().call()
    if config['token']['address'].lower() == pool['contract'].functions.token0().call().lower():
        return t0
    elif config['token']['address'].lower() == pool['contract'].functions.token1().call().lower():
        return t1
    else:
        raise ValueError('Pool not in pair with correct token')