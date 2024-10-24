#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import pyappstoreconnect

logging.basicConfig(level=logging.INFO, handlers=[logging.StreamHandler()])

client = pyappstoreconnect.Client(
    requestsRetry=False,
    userAgent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    logLevel='debug',
)
username = input(f"Please enter username: ")
password = input(f"Please enter password for username={username}: ")

client.login(username=username, password=password)
