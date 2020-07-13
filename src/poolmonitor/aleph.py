    
from aleph_client.main import create_post
from aleph_client.chains.ethereum import ETHAccount
from functools import lru_cache

from .settings import config

@lru_cache(maxsize=32)
def get_aleph_account():
    return ETHAccount(config['web3']['pkey'])


@lru_cache(maxsize=32)
def get_aleph_address():
    return (get_aleph_account()).get_address()


def create_distribution_tx_post(distribution):
    print(f"Preparing pending TX post {distribution}")
    post = create_post(
        get_aleph_account(),
        distribution,
        post_type='incentive-distribution',
        channel=config['aleph']['channel'],
        api_server=config['aleph']['api_server'])