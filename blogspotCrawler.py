#!/usr/bin/env python3

import sys
import signal
import os.path
import errno
import time
import re

import argparse
from dataclasses import dataclass
from concurrent.futures import *

import requests
from bs4 import BeautifulSoup, Tag

REMAINING_FILE = "~/.config/scripts/PyBloggerRemaining.txt"


@dataclass
class JobInfo:
    """Saves info from a job
    """
    url: str = ""
    fname: str = ""
    remaining: int = 5

class ProcessPagination:
    """Process a pagination
    """
    def __init__(self, baseurl: str, destination: str, max_workers: int=None):
        self.baseurl = baseurl
        self.url = baseurl
        self.destination = destination
        self.running = True
        self.executor = ThreadPoolExecutor(max_workers)
        self.done = 0
        self.total = 0
        self.lastdone = JobInfo()
        self.remaining = {}

    @staticmethod
    def response_to_file(fname, content):
        soup = BeautifulSoup(content, 'html.parser')

        if not os.path.exists(os.path.dirname(fname)):
            try:
                os.makedirs(os.path.dirname(fname))
            except OSError as exc: # Guard against race condition
                if exc.errno != errno.EEXIST:
                    raise
        
        reglob = re.compile(".*")

        title = soup.find(reglob, itemprop="name").getText().strip()
        tags = [x.getText() for x in soup.find_all("a", {"rel":"tag"})]
        body = soup.find("div", class_="post-body")

        # TODO: Download images
        # TODO: "Flatten" html and/or convert to Markdown

        with open(fname, 'w+') as f:
            print("---", file=f)
            print("layout: default", file=f)
            print("title:", title, file=f)
            print("tags:", "[" + ",".join(tags) + "]", file=f)
            print("---", file=f)
            print(body, file=f)

        # TODO: Return images so executor can add them to the queue
        return True

    @staticmethod
    def process_post(url, fname):
        """Downloads and process one post
        """
        response = requests.get(url, timeout=5)

        response.raise_for_status()

        return ProcessPagination.response_to_file(fname, response.content)

    def process_post_callback(self, future):
        if future.cancelled():
            return

        if future.result():
            self.done += 1
            self.lastdone = self.remaining[future]
        else:
            if self.remaining[future].remaining > 0:
                self.resubmit(self.remaining[future])

        del self.remaining[future]

    def process_one_page(self, url):
        """Adds urls from current page to the executor

        Args:
            executor (Executor): Executor
            url (str): Url to process

        Returns:
            url of next page to process or None if there isnt any
        """
        page = requests.get(url)
        soup = BeautifulSoup(page.content, 'html.parser')

        for x in soup.select("h3.post-title a"):
            self.submit(x['href'])

        next_page = soup.select("#blog-pager-older-link a")

        return next_page[0]['href'] if next_page else None

    def printStatus(self, url, total, current=None):
        if url != self.baseurl:
            url = url[len(self.baseurl):]

        w = os.get_terminal_size().columns

        outstr = f"Done {current}/{total} "
        donelen = len(outstr)
        remainingspace = w - len(outstr)-3
        if len(url) >= remainingspace:
            outstr += url[:remainingspace] + "..."
        else:
            outstr += url

        outstr += " "*(w - len(outstr))
        print(outstr, end="\r", flush=True)

    def submit(self, url: str, remaining_tries=5):
        fname = os.path.join(self.destination, url[len(self.baseurl):].strip('/'))
        future = self.executor.submit(self.process_post, url, fname)
        future.add_done_callback(self.process_post_callback)
        self.remaining[future] = JobInfo(url, fname, remaining_tries)
        self.total += 1

    def resubmit(self, ji: JobInfo):
        future = self.executor.submit(self.process_post, ji.url, ji.fname)
        self.remaining[future] = JobInfo(ji.url, ji.fname, ji.remaining-1)

    def write_remaining(self):
        """Writes remaining to REMAINING_FILE"""
        rmfile = os.path.expanduser(REMAINING_FILE)
        with open(rmfile, 'w') as f:
            print(self.url, file=f)

            for ji in self.remaining.values():
                print(ji.url, file=f)

        print("Saved remaining to", os.path.expanduser(REMAINING_FILE))

    def process(self):
        """Main processing function"""
        rmfile = os.path.expanduser(REMAINING_FILE)
        self.url = self.baseurl
        if os.path.isfile(rmfile):
            with open(rmfile, 'r') as f:
                aux = f.readline().strip()
                if aux:
                    self.url = aux
                    print("Ressuming from", self.url)

                for line in f:
                    self.submit(line.strip())

        while self.url and self.running:
            self.printStatus(self.url, self.total, self.done)
            self.url = self.process_one_page(self.url)

        self.printStatus(self.lastdone.url, self.total, self.done)
        _, not_done = wait(self.remaining.keys(), .5, ALL_COMPLETED)
        while self.running and not_done:
            self.printStatus(self.lastdone.url, self.total, self.done)
            _, not_done = wait(self.remaining.keys(), .5, ALL_COMPLETED)

        print("\nFinished!")

    def stop(self):
        """Stops the executor"""
        self.running = False
        self.executor.shutdown(wait=True, cancel_futures=True)
        self.write_remaining()

def main():

    parser = argparse.ArgumentParser(description="Blogspot crawler",
        epilog="(C) David Davó - https://ddavo.me. Licensed under a MIT License.")
    parser.add_argument('url', type=str, help='Blog url')
    parser.add_argument('-o', '--output',
        dest='destination',
        type=str, 
        default="./",
        help="Output folder"
    )
    parser.add_argument('-t', '--threads',
        dest='threads',
        type=int,
        default=None,
        help="Number of threads"
    )

    args = parser.parse_args()

    process_pagination = ProcessPagination(
        baseurl=args.url,
        destination=args.destination,
        max_workers=args.threads)

    def signal_handler(sig, frame):
        # TODO: Add 5 seconds timeout or something like
        # that to threads, before killing them (as they are daemons)

        print("Received SIGINT")
        process_pagination.stop()

        sys.exit(1)

    signal.signal(signal.SIGINT, signal_handler)

    process_pagination.process()

    sys.exit(0)

if __name__ == "__main__":
    main()
