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

    print(config)

    from .pools import set_pools, process_pool_history, get_pool_weight
    set_pools()

    print(config)
    pool_weights = {
        pool['address'] : get_pool_weight(pool) for pool in config['pools']
    }

    pool_weights = {
        a: pw / sum(pool_weights.values()) for a, pw in pool_weights.items()
    }
    print(pool_weights)

    per_block = config['reward_per_block']

    for pool in config['pools']:
        process_pool_history(pool, per_block*pool_weights[pool['address']])


def run():
    """Entry point for console_scripts
    """
    main(sys.argv[1:])


if __name__ == "__main__":
    run()
