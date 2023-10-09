import json
import os
import sys

import requests
import imagehash

from PIL import Image
from pathlib import Path

import argparse

import config

quiet = False
verbose = False

parser = argparse.ArgumentParser(
    prog='Downbooru',
    description='Tool for downloading images from gelbooru.com',
    epilog='dupa'
)

parser.add_argument('tags',
                    nargs='*',
                    type=str,
                    help='<Required> Image tags to search',
                    default=('rick_astley',))
parser.add_argument('-f', '--furry',
                    action='store_true',
                    help='<Optional, default: false> Disable filtering "furry" tag.')
parser.add_argument('-s', '--safety',
                    type=int,
                    help='<Optional, default: 2> Number 0-3 indicating minimum safety ranking of requested images,'
                         'where 3 indicates absolute SFW (gelbooru usually has very few of those, hence default 2), '
                         'and 0 indicates explicit NSFW',
                    default=2)
parser.add_argument('-d', '--dir',
                    type=str,
                    help='<Optional, default: "img/[tags]"> Custom path for saving images')
parser.add_argument('-q', '--quiet',
                    action='store_true',
                    help='<Optional, default: true> Disable prints')
parser.add_argument('-v', '--verbose',
                    action='store_true',
                    help='<Optional, default: false> Enable debug prints')

API_INFO = f'&api_key={config.API_KEY}&user_id={config.USER_ID}'
api_url = f'https://www.gelbooru.com/index.php?page=dapi&s=post&q=index{API_INFO}'

ratings = [
    'explicit',
    'questionable',
    'sensitive',
    'general'
]


def parse_query(limit=-1, page=-1, tags=(), pid=-1, json=1, safety=1):
    url = api_url
    if limit != -1:
        url += f"&limit={limit}" if limit != -1 else ""
    if page != -1:
        url += f"&pid={page}" if page != -1 else ""
    if len(tags) > 0:
        url += f"&tags=rating:{ratings[safety]}"
        for tag in tags:
            log(tag, debug=True)
            url += '+' + '_'.join(tag.lower().split(' '))
    if pid != -1:
        url += f'&id={pid}'
    url += f'&json={json}'
    log(url, debug=True)
    return url


def get_json(query):
    req = requests.get(query)
    return req.json()


def get_image(url):
    return Image.open(requests.get(url, stream=True).raw)


def log(log_str: str, file=None, debug=False):
    if not quiet:
        if not debug or verbose:
            print(log_str, file=file)


def fetch_images(safety=1, limit=100, tags=(), furry=False, dir=None):
    image_path = f'img/{"_".join(tags)}' if dir is None else dir
    Path(image_path).mkdir(parents=True, exist_ok=True)

    if not furry:
        tags += ('-furry',)

    for j in range(safety, 4):
        count = limit
        page = 0

        while count == limit:
            data = get_json(parse_query(tags=tags, limit=1000, safety=j, page=page))

            try:
                count = len(data['post'])
            except KeyError:
                pass

            parsed_data = {}
            log(f'Fetched {len(data["post"])} images | {page}', file=sys.stderr)

            hashes = set()
            for i, entry in enumerate(data['post']):
                status = 'OK'
                extension = entry['file_url'].split('/')[-1].split('.')[-1]

                log(f'Getting image {entry["id"]} {i + 1}/{len(data["post"])} | {page}', file=sys.stderr)
                try:
                    try:
                        open(f'{image_path}/{entry["id"]}.{extension}', 'r')
                        log(f'Image {entry["id"]} exists.', file=sys.stderr)
                    except FileNotFoundError:
                        with open(f'{image_path}/{entry["id"]}.{extension}', 'w+') as file:
                            image = get_image(entry['file_url'])

                            image_hash = imagehash.average_hash(image, 32)
                            if image_hash in hashes:
                                log(f'Image {entry["id"]} is a duplicate')
                                continue
                            hashes.add(image_hash)

                            image.save(f'{image_path}/{entry["id"]}.{extension}')
                except Exception as e:
                    log(f'Getting image {entry["id"]} failed: {e}', file=sys.stderr)

                    os.remove(f'{image_path}/{entry["id"]}.{extension}')
                    status = 'ERROR'

                parsed_data[entry['id']] = [entry['source'], entry['file_url'], status]

            page += 1

    with open(f'{image_path}/src.json', 'w+') as file:
        json.dump(parsed_data, file)


if __name__ == '__main__':
    args = parser.parse_args()
    quiet = args.quiet
    verbose = args.verbose
    fetch_images(safety=min(max(args.safety, 0), len(ratings) - 1), tags=tuple(args.tags), furry=args.furry,
                 dir=args.dir)
