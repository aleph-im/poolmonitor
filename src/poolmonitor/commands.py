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
from .settings import config
from .aleph import create_distribution_tx_post
        
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
        default=0)
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

    from .uniswap import set_pools, process_pool_history, get_pool_weight
    from .ethereum import get_web3, transfer_tokens
    set_pools()

    pool_weights = {
        pool['address'] : get_pool_weight(pool) for pool in config['pools']
    }

    pool_weights = {
        a: pw / sum(pool_weights.values()) for a, pw in pool_weights.items()
    }

    per_block = config['reward_per_block']

    distribution = dict(
        incentive="liquidity",
        status="calculation",
        pool_weights=pool_weights,
        pools = []
    )

    to_distribute = dict()

    end_height = args.end_height

    if end_height == -1:
        end_height = get_web3().eth.blockNumber

    start_height = args.start_height


    for pool in config['pools']:
        rewards, start_height, end_height = process_pool_history(pool, per_block*pool_weights[pool['address']], start_height, end_height)
        pool_info = {
            'address': pool['address'],
            'type': pool.get('type', 'uniswap'),
            'per_block': per_block*pool_weights[pool['address']],
            'distribution': rewards,
            'start': start_height,
            'end': end_height
        }
        for address, amount in rewards.items():
            to_distribute[address] = to_distribute.get(address, 0) + amount
        
        distribution['pools'].append(pool_info)

    if args.act:
        # distribution['status'] = ''
        print("Doing distribution")
        print(distribution)
        distribution['status'] = 'distribution'
        transfer_tokens(to_distribute, metadata=distribution)

    create_distribution_tx_post(distribution)


def run():
    """Entry point for console_scripts
    """
    main(sys.argv[1:])


if __name__ == "__main__":
    run()
