#!/usr/bin/env python3

''' miles.py - Web crawler to download files in parallel. '''

from typing import Iterator, Optional

import os
import concurrent.futures
import itertools
import re
import sys
import tempfile
import time
import urllib.parse
import pprint
from urllib.parse import urljoin

import requests

# Constants

FILE_REGEX = {
    'jpg': [r'<img.*src="?([^\" ]+.jpg)', r'<a.*href="?([^\" ]+.jpg)'],
    'mp3': [r'<audio.*src="?([^\" ]+.mp3)', r'a.*href="?([^\" ]+.mp3)'], 
    'pdf': [r'<a.*href="?([^\" ]+.pdf)'],
    'png': [r'<img.*src="?([^\" ]+.png)', r'<a.*href="?([^\" ]+.png)'],
}

MEGABYTES   = 1<<20
DESTINATION = '.'
CPUS        = 1

# Functions

def usage(exit_status: int=0) -> None:
    ''' Print usgae message and exit. '''
    print(f'''Usage: miles.py [-d DESTINATION -n CPUS -f FILETYPES] URL
Crawl the given URL for the specified FILETYPES and download the files to the
DESTINATION folder using CPUS cores in parallel.
    -d DESTINATION      Save the files to this folder (default: {DESTINATION})
    -n CPUS             Number of CPU cores to use (default: {CPUS})
    -f FILETYPES        List of file types: jpg, mp3, pdf, png (default: all)
Multiple FILETYPES can be specified in the following manner:
    -f jpg,png
    -f jpg -f png''', file=sys.stderr)
    sys.exit(exit_status)

def resolve_url(base: str, url: str) -> str:
    ''' Resolve absolute url from base url and possibly relative url.
    >>> base = 'https://www3.nd.edu/~pbui/teaching/cse.20289.sp24/'
    >>> resolve_url(base, 'static/img/ostep.jpg')
    'https://www3.nd.edu/~pbui/teaching/cse.20289.sp24/static/img/ostep.jpg'
    >>> resolve_url(base, 'https://automatetheboringstuff.com/')
    'https://automatetheboringstuff.com/'
    '''
    return urljoin(base, url) 

def extract_urls(url: str, file_types: list[str]) -> Iterator[str]:
    ''' Extract urls of specified file_types from url.
    >>> url = 'https://www3.nd.edu/~pbui/teaching/cse.20289.sp24/'
    >>> extract_urls(url, ['jpg']) # doctest: +ELLIPSIS
    <generator object extract_urls at ...>
    >>> len(list(extract_urls(url, ['jpg'])))
    2
    '''
    response = requests.get(url)
    if not response:
        exit(5)

    for filetype in file_types:
        for regex in FILE_REGEX[filetype]:
            for relative_url in re.findall(regex, response.text):
                yield resolve_url(url, relative_url) 

def download_url(url: str, destination: str=DESTINATION) -> Optional[str]:
    ''' Download url to destination folder.
    >>> url = 'https://www3.nd.edu/~pbui/teaching/cse.20289.sp24/static/img/ostep.jpg'
    >>> destination = tempfile.TemporaryDirectory()
    >>> path = download_url(url, destination.name)
    Downloading https://www3.nd.edu/~pbui/teaching/cse.20289.sp24/static/img/ostep.jpg...
    >>> path # doctest: +ELLIPSIS
    '/tmp/.../ostep.jpg'
    >>> os.stat(path).st_size
    53696
    >>> destination.cleanup()
    '''
    print(f'Downloading {url}...')

    try:
        response = requests.get(url)
        response.raise_for_status()
    except requests.exceptions.RequestException:
        return None

    name = os.path.basename(url)
    local_path = os.path.join(destination, name)
    with open(file=local_path, mode='wb') as stream:
        stream.write(response.content)

    return local_path

def crawl(url: str, file_types: list[str], destination: str=DESTINATION, cpus: int=CPUS) -> None:
    ''' Crawl the url for the specified file type(s) and download all found
    files to destination folder.
    >>> url = 'https://www3.nd.edu/~pbui/teaching/cse.20289.sp24/'
    >>> destination = tempfile.TemporaryDirectory()
    >>> crawl(url, ['jpg'], destination.name) # doctest: +ELLIPSIS
    Files Downloaded: 2
    Bytes Downloaded: 0.07 MB
    Elapsed Time:     ... s
    Bandwidth:        0... MB/s
    >>> destination.cleanup()
    '''
    start = time.time()
    with concurrent.futures.ProcessPoolExecutor(cpus) as executor:
        urls = extract_urls(url, file_types)
        dsts = itertools.repeat(destination)
        files = [file for file in executor.map(download_url, urls, dsts) if file]
    end = time.time()

    Mbytes_downloaded = sum(os.stat(file).st_size for file in files) / (1024 * 1024)
    time_total = end - start
    bandwidth = Mbytes_downloaded/time_total
    print(f'Files Downloaded: {len(files)}')
    print(f'Bytes Downloaded: {Mbytes_downloaded:.2f} MB')
    print(f'Elapsed Time:     {time_total:.2f} s')
    print(f'Bandwidth:        {bandwidth:.2f} MB/s')


# Main Execution

def main(arguments=sys.argv[1:]) -> None:
    ''' Process command line arguments, crawl URL for specified FILETYPES,
    download files to DESTINATION folder using CPUS cores.
    >>> url = 'https://www3.nd.edu/~pbui/teaching/cse.20289.sp24/'
    >>> destination = tempfile.TemporaryDirectory()
    >>> main(f'-d {destination.name} -f jpg {url}'.split()) # doctest: +ELLIPSIS
    Files Downloaded: 2
    Bytes Downloaded: 0.07 MB
    Elapsed Time:     0... s
    Bandwidth:        0... MB/s
    >>> destination.cleanup()
    '''
    destination = DESTINATION
    cpus = CPUS
    file_types = []
    url = ''
    while len(arguments) > 0:
        argument = arguments.pop(0)

        match argument:
            case "-d":
                destination = arguments.pop(0)
            case "-n":
                cpus = int(arguments.pop(0))
            case "-f":
                types = arguments.pop(0)
                if ',' in types:
                    file_types.extend(types.split(','))
                else:
                    file_types.append(types)
            case "-h":
                usage(0)
            case _:
                if argument.startswith('-'):
                    usage(1)
                else:
                    url = argument

    if not url:
        usage(1)

    if not file_types:
        file_types = ['jpg', 'mp3', 'pdf', 'png']

    if not (os.path.exists(destination)):
        os.makedirs(destination)

    crawl(url, file_types, destination, cpus)


if __name__ == '__main__':
    main()