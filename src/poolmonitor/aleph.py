    
from aleph_client.main import create_post, get_posts
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

def get_latest_successful_distribution():
    posts = get_posts(
        types=["incentive-distribution"],
        addresses=[get_aleph_address()],
        api_server=config['aleph']['api_server'])

    current_post = None
    current_end_height = 0
    for post in posts['posts']:
        successful = False
        if post['content']['status'] != 'distribution':
            pass

        for target in post['content'].get('targets', []):
            if target['success']:
                successful = True
                break
        
        if successful:
            for pool in post['content'].get('pools', []):
                if pool['end'] >= current_end_height:
                    current_post = post
                    current_end_height = pool['end']
                    break

    return current_end_height, current_post['content']