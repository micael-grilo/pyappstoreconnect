#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import logging
import pyappstoreconnect
import yaml
from deepmerge import always_merger

logging.basicConfig(level=logging.INFO, handlers=[logging.StreamHandler()])
logger = logging.getLogger(__name__)
logger.info("starting script")

client = pyappstoreconnect.Client(
    requestsRetry=False,
    userAgent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    logLevel='debug',
)

# load config file
configFile = './test.yml'
cfg = dict()
if os.path.isfile(configFile):
    with open(configFile, 'r') as ymlfile:
        try:
            cfg = always_merger.merge(cfg,yaml.load(ymlfile,Loader=yaml.Loader))
        except Exception as e:
            logger.warning(f"skipping load load config file='{configFile}', error='{str(e)}'")


# get username and password
username = cfg.get('username') or input("Please enter username: ")
password = cfg.get('password') or input(f"Please enter password for username={username}: ")

# login
login = client.login(username=username, password=password)
# check login:
if login:
    logger.info(f"login success")
else:
    logger.error(f"login failed")
    exit(1)

# variables
appleId = cfg.get('appleId') or input("Please enter appleId: ")
dateFrom = cfg.get('dateFrom') or input("Please enter dateFrom, example 2024-10-11T00:00:00Z: ")
dateTo = cfg.get('dateTo') or input("Please enter dateTo, example 2024-10-18T00:00:00Z: ")

## tests functions

# get appAnalytics stat
def getAppAnalytics():
    logging.info("get appAnalytics")
    analyticsResponses = client.appAnalytics(appleId, startTime=dateFrom, endTime=dateTo, groupsByMap={"pageViewUnique":"source"})
    for analyticsResponse in analyticsResponses:
        if not analyticsResponses:
            logger.error(f"bad analyticsResponse={analyticsResponse}")
            exit(1)
        logger.info(f"analyticsResponse='{analyticsResponse}'")

# get benchmarks stat
def getBenchmarks():
    logging.info(f"get benchmarks")
    benchmarks = client.benchmarks(appleId, optionKeys=14)
    for benchmark in benchmarks:
        logger.info(f"optionKeys=14, benchmark='{benchmark}'")
    benchmarks = client.benchmarks(appleId, optionKeys=2)
    for benchmark in benchmarks:
        logger.info(f"optionKeys=2, benchmark='{benchmark}'")

# get analytics (filter replacement)
def getAnalyticsByGroups():
    logger.info(f"get analytics by groups")
    analyticsResponses = client.metricsWithGroups(
        appleId,
        metrics = [
            'impressionsTotalUnique',
            'pageViewUnique',
            'totalDownloads',
        ],
        groups = [
            'source',
            'storefront',
            'appReferrer',
            'domainReferrer',
        ],
        startTime = dateFrom,
        endTime = dateTo,
        frequency = 'day',
    )
    for analyticsResponse in analyticsResponses:
        if not analyticsResponses:
            logger.error(f"bad analyticsResponse={analyticsResponse}")
            exit(1)
        logger.info(f"analyticsResponse='{analyticsResponse}'")

## run tests:
if __name__ == "__main__":
    getAppAnalytics()
    getBenchmarks()
    getAnalyticsByGroups()
