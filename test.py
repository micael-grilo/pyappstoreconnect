#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import logging
import pyappstoreconnect
import yaml
from deepmerge import always_merger

logging.basicConfig(level=logging.INFO, handlers=[logging.StreamHandler()])

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
            logging.warning(f"skipping load load config file='{configFile}', error='{str(e)}'")


# get username and password
username = cfg.get('username')
if not username:
    username = input(f"Please enter username: ")
password = cfg.get('password')
if not password:
    password = input(f"Please enter password for username={username}: ")

client.login(username=username, password=password)
