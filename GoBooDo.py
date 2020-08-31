#!/usr/bin/python3

import json
import random
import requests
from bs4 import BeautifulSoup
import os
import sys
import pickle
from storeImages import StoreImages
from makePDF import createBook
import argparse
from time import sleep

from stem import Signal
from stem.control import Controller
from fake_useragent import UserAgent

import cProfile
import pstats

# suppress urllib3 warning

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

parser = argparse.ArgumentParser(description='Welcome to GoBooDo')

parser.add_argument("--id")
args = parser.parse_args()

# load config
# TODO Move configuration to arguments
with open('settings.json') as ofile:
    settings = json.load(ofile)

alt_countrys = {
    "co.in"
    "com"
    "co.uk"
    "co.nz"
}   # TODO Add more countries to make it more anonymous


class GoBooDo:
    def __init__(self, id,):
        self.id = id
        self.country = settings['country']
        self.resethead()
        self.pageLinkDict = {}
        self.pageList = []
        self.lastCheckedPage = ""
        self.obstinatePages = []
        self.path = os.path.join(os.getcwd(), id)
        self.dataPath = os.path.join(self.path, 'data')
        self.found = False
        if os.path.isdir(self.dataPath):
            self.found = True
        else:
            os.mkdir(self.path)
            os.mkdir(self.dataPath)

    def resethead(self):
        try:
            req = requests.get("https://google."+self.country, verify=False)

            # Randomized User-Agent
            self.head = {
                'Host': 'books.google.'+self.country,
                'User-Agent': UserAgent().random,
                'Accept': '*/*',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'close',
                'Cookie': "NID=" + str(req.cookies['NID']),
            }

        except Exception as e:
            if 'captcha'.encode() in req.content:
                print("IP detected by Google for too much requests, asking for captcha completion. Please wait some minutes before trying again. \n")
                self.tor_newiden()
            else:
                if e == KeyboardInterrupt:
                    exit()
                print(e)

    def createPageDict(self, jsonResponse):
        for pageData in jsonResponse[0]['page']:
            self.pageList.append(pageData['pid'])
            self.pageLinkDict[pageData['pid']] = {}
            self.pageLinkDict[pageData['pid']]['src'] = ""
            self.pageLinkDict[pageData['pid']]['order'] = pageData['order']

    def getInitialData(self):
        initUrl = "https://books.google." + self.country + \
            "/books?id=" + self.id + "&printsec=frontcover"
        pageData = requests.get(initUrl, headers=self.head, verify=False)
        soup = BeautifulSoup(pageData.content, "html5lib")
        self.name = soup.findAll("title")[0].contents[0]
        print(f'Downloading {self.name[:-15]}')
        if self.found == False:
            scripts = (soup.findAll('script'))
            try:
                stringResponse = (
                    "["+scripts[6].text.split("_OC_Run")[1][1:-2]+"]")
            except:
                stringResponse = (
                    "["+scripts[-4].text.split("_OC_Run")[1][1:-2]+"]")
            jsonResponse = json.loads(stringResponse)
            self.createPageDict(jsonResponse)
            print(
                f'Pages to be fetched in the current iteration are : {len(self.pageList)}')
            for elem in jsonResponse[3]['page']:
                page = elem['pid']
                self.pageList.remove(page)
                self.pageLinkDict[page]['src'] = elem['src']
        else:
            try:
                with open(os.path.join(self.dataPath, 'obstinatePages.pkl'), 'rb') as ofile:
                    self.pageList = pickle.load(ofile)
                with open(os.path.join(self.dataPath, 'pageLinkDict.pkl'), 'rb') as ofile:
                    self.pageLinkDict = pickle.load(ofile)
                print(
                    f'An earlier download attempt was detected, GoBooDo will continue using the previous state.')
                print(
                    f'The total pages available for fetching are {len(self.pageList)}')
            except:
                print(
                    'Please delete the corresponding folder and start again or the book is not available for preview.')
                exit(0)

    def insertIntoPageDict(self, subsequentJsonData):
        if(len(self.pageList) == 0):
            return False
        for pageData in subsequentJsonData['page']:
            if('src' in pageData.keys() and pageData['src'] != ""):
                lastPage = pageData['pid']
                self.pageLinkDict[lastPage]['src'] = pageData['src']
                try:
                    self.pageList.remove(lastPage)
                    print(f'Fetched link for {lastPage}.')
                except Exception as e:
                    if e == KeyboardInterrupt:
                        sys.exit()
                    pass
        return True

    def tor_newiden(self):
        print('Getting new tor identity...')
        with Controller.from_port(port=9051) as c:
            c.authenticate()
            c.signal(Signal.NEWNYM)
        self.country = random.choice(alt_countrys)
        self.resethead()

    def fetchPageLinks(self):
        self.resethead()
        proxyDict = {
            'http': 'socks5://127.0.0.1:9050',
            'https': 'socks5://127.0.0.1:9050'
        }
        try:
            self.b_url = "https://books.google."+self.country+"/books?id=" + str(self.id) + "&pg=" +\
                str(self.pageList[0]) + "&jscmd=click3"
            pageData = requests.get(
                self.b_url, headers=self.head, proxies=proxyDict, verify=False)
        except Exception as e:
            if e == KeyboardInterrupt:
                sys.exit()
            print('Could not connect with this node')
            self.tor_newiden()
        return pageData.json()

    def processBook(self):
        print('------------------- Fetching Images -------------------')
        downloadService = StoreImages(
            self.path, settings['proxy_images'], settings['page_resolution'], settings['tesseract_path'])
        downloadService.getImages(settings['max_retry_images']+1)
        print('------------------- Creating PDF -------------------')
        service = createBook(self.name, self.path)
        service.makePdf()

    def start(self):
        # TODO Fix the Image not available Problem

        try:
            self.getInitialData()
        except:
            print('Received invalid response')
            sys.exit(0)
        try:
            lastFirstList = self.pageList[0]
        except:
            print(
                'There appears to be no page links to be fetched, fetching the images for downloaded links')
            return self.processBook()
        maxPageLimit = 0
        maxPageLimitHit = settings['max_retry_links']+2
        while True:
            try:
                interimData = self.fetchPageLinks()
            except:
                pass
            self.insertIntoPageDict(interimData)
            try:
                if (maxPageLimit == self.pageList[0]):
                    maxPageLimitHit -= 1
                    self.tor_newiden()
                if (maxPageLimitHit == 1):
                    maxPageLimitHit = settings['max_retry_links']+2
                    print(f'Could not fetch link for page {self.pageList[0]}')
                    self.tor_newiden()
                    self.obstinatePages.append(self.pageList[0])
                    self.pageList = self.pageList[1:]
                if (lastFirstList == self.pageList[0]):
                    maxPageLimit = lastFirstList
                lastFirstList = self.pageList[0]
            except:
                break
        with open(os.path.join(self.dataPath, 'obstinatePages.pkl'), 'wb+') as ofile:
            pickle.dump(list(set(self.obstinatePages)), ofile)
        with open(os.path.join(self.dataPath, 'pageLinkDict.pkl'), 'wb+') as ofile:
            pickle.dump(self.pageLinkDict, ofile)
        self.processBook()


if __name__ == "__main__":
    print('''
 .88888.            888888ba                    888888ba                      dP                     
d8'   `88           88    `8b                   88    `8b                     88                     
88        .d8888b. a88aaaa8P' .d8888b. .d8888b. 88     88 .d8888b.          d8888P .d8888b. 88d888b. 
88   YP88 88'  `88  88   `8b. 88'  `88 88'  `88 88     88 88'  `88 88888888   88   88'  `88 88'  `88 
Y8.   .88 88.  .88  88    .88 88.  .88 88.  .88 88    .8P 88.  .88            88   88.  .88 88       
 `88888'  `88888P'  88888888P `88888P' `88888P' 8888888P  `88888P'            dP   `88888P' dP       
ooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooo
                                                                                                                                                                                                                                     
    ''')
    book_id = args.id
    if(book_id == None or len(book_id) != 12):
        print('No book id given or incorrect book id given')
        sys.exit(0)
    retry_time = settings['global_retry_time']
    if retry_time != 0:
        while True:
            book = GoBooDo(args.id)
            book.start()
            print(
                'The programming is currently waiting for the next iteration and can be exited safely.')
            if len(book.obstinatePages) == 0:
                print('There are no pages to be fetched. Exiting...')
                sys.exit(0)
            sleep(retry_time)
    else:
        book = GoBooDo(args.id)
        book.start()
