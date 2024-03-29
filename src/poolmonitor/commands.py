# -*- coding: utf-8 -*-
"""
This is a skeleton file that can serve as a starting point for a Python
console script. To run this script uncomment the following lines in the
[options.entry_points] section in setup.cfg:

    console_scripts =
         fibonacci = poolmonitor.skeleton:run

Then run `python setup.py install` which will install the command `fibonacci`
inside your current environment.
Besides console scripts, the header (i.e. until _logger...) of this file can
also be used as template for Python modules.

Note: This skeleton file can be safely removed if not needed!
"""

import argparse
import sys
import os
import logging
import math
from .settings import config
from .aleph import create_distribution_tx_post, get_latest_successful_distribution
        
import hiyapyco
from pathlib import Path

from poolmonitor import __version__

__author__ = "Moshe Malawach"
__copyright__ = "Moshe Malawach"
__license__ = "mit"

_logger = logging.getLogger(__name__)


def parse_args(args):
    """Parse command line parameters

    Args:
      args ([str]): command line parameters as list of strings

    Returns:
      :obj:`argparse.Namespace`: command line parameters namespace
    """
    parser = argparse.ArgumentParser(
        description="Pool monitoring tool")
    parser.add_argument(
        "--version",
        action="version",
        version="poolmonitor {ver}".format(ver=__version__))
    parser.add_argument('-c', '--config', action="store", dest="config_file")
    parser.add_argument(
        "-v",
        "--verbose",
        dest="loglevel",
        help="set loglevel to INFO",
        action="store_const",
        const=logging.INFO)
    parser.add_argument(
        "-vv",
        "--very-verbose",
        dest="loglevel",
        help="set loglevel to DEBUG",
        action="store_const",
        const=logging.DEBUG)
    parser.add_argument(
        "-a",
        "--act",
        dest="act",
        help="Do actual bqtch transfer",
        action="store_true")
    parser.add_argument(
        "-s",
        "--start-height",
        dest="start_height",
        help="Starting height",
        type=int,
        default=-1)
    parser.add_argument(
        "-e",
        "--end-height",
        dest="end_height",
        help="Ending height",
        type=int,
        default=-1)
    return parser.parse_args(args)


def setup_logging(loglevel):
    """Setup basic logging

    Args:
      loglevel (int): minimum loglevel for emitting messages
    """
    logformat = "[%(asctime)s] %(levelname)s:%(name)s:%(message)s"
    logging.basicConfig(level=loglevel, stream=sys.stdout,
                        format=logformat, datefmt="%Y-%m-%d %H:%M:%S")


def main(args):
    """Main entry point allowing external calls

    Args:
      args ([str]): command line parameter list
    """
    args = parse_args(args)
    setup_logging(args.loglevel)

    
    default_config_file = os.path.join(Path(__file__).resolve().parent, 'config_default.yaml')
    if args.config_file:
        config.update(hiyapyco.load(default_config_file, args.config_file))
    else:
        config.update(hiyapyco.load(default_config_file))

    from . import uniswap, balancer
    from .ethereum import get_web3, transfer_tokens
    uniswap.set_pools()
    balancer.set_pools()

    pool_weights = {
        pool['address'] : pool['weight_processor'](pool) * pool.get('weight', 1) for pool in config['pools']
    }

    pool_weights = {
        a: pw / sum(pool_weights.values()) for a, pw in pool_weights.items()
    }

    per_block = config['reward_per_block']

    distribution = dict(
        incentive="liquidity",
        status="calculation",
        pool_weights=pool_weights,
        chain=config['web3']['chain_name'],
        chain_id=config['web3']['chain_id'],
        pools=[]
    )

    to_distribute = dict()

    end_height = args.end_height

    if end_height == -1:
        end_height = get_web3().eth.blockNumber

    start_height = args.start_height

    if start_height == -1:
        last_end_height, dist = get_latest_successful_distribution()

        if last_end_height and dist:
            start_height = last_end_height + 1
        
        else:
            start_height = 0


    for pool in config['pools']:
        rewards, start_height, end_height = \
            pool['history_processor'](pool,
                                      per_block*pool_weights[pool['address']],
                                      start_height, end_height)
        pool_info = {
            'address': pool['address'],
            'type': pool.get('type', 'uniswap'),
            'per_block': per_block*pool_weights[pool['address']],
            'distribution': rewards,
            'start': start_height,
            'end': end_height
        }
        for address, amount in rewards.items():
            if address != "0x0000000000000000000000000000000000000000":
                to_distribute[address] = to_distribute.get(address, 0) + amount
        
        distribution['pools'].append(pool_info)

    if args.act:
        # distribution['status'] = ''
        print("Doing distribution")
        print(distribution)
        distribution['status'] = 'distribution'

        max_items = config.get('batch_size', 40)

        distribution_list = list(to_distribute.items())

        for i in range(math.ceil(len(to_distribute) / max_items)):
            step_items = distribution_list[max_items*i:max_items*(i+1)]
            print(f"doing batch {i} of {len(step_items)} items")
            transfer_tokens(dict(step_items), metadata=distribution)

    create_distribution_tx_post(distribution)


def run():
    """Entry point for console_scripts
    """
    main(sys.argv[1:])


if __name__ == "__main__":
    run()
