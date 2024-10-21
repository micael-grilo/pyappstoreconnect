import os
import logging
import inspect
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry
import json
import datetime
import hashlib
import pickle
import re
from .settings import Settings # mixin
from .timeSeriesAnalytics import TimeSeriesAnalytics # mixin
from .appAnalytics import AppAnalytics # minix
from .benchmarks import Benchmarks # minix
from .metricsWithFilter import MetricsWithFilter # mixin
from .metricsWithGroup import MetricsWithGroup # mixin

class Client(
        Settings,
        TimeSeriesAnalytics,
        AppAnalytics,
        Benchmarks,
        MetricsWithFilter,
        MetricsWithGroup,
    ):
    """
    client for connect to appstoreconnect.apple.com
    based on https://github.com/fastlane/fastlane/blob/master/spaceship/
    usage:
```
import appstoreconnect
client = appstoreconnect.Client()
responses = client.appAnalytics(appleId)
for response in responses:
    print(response)
```
    """

    def __init__(self,
        cacheDirPath="./cache",
        requestsRetry=True,
        requestsRetrySettings={
            "total": 4, # maximum number of retries
            "backoff_factor": 30, # {backoff factor} * (2 ** ({number of previous retries}))
            "status_forcelist": [429, 500, 502, 503, 504], # HTTP status codes to retry on
            "allowed_methods": ['HEAD', 'TRACE', 'GET', 'PUT', 'OPTIONS', 'POST'],
        },
        logLevel=None,
        userAgent=None,
    ):
        self.logger = logging.getLogger(__name__)
        if logLevel:
            if re.match(r"^(warn|warning)$", logLevel, re.IGNORECASE):
                self.logger.setLevel(logging.WARNING)
            elif re.match(r"^debug$", logLevel, re.IGNORECASE):
                self.logger.setLevel(logging.DEBUG)
            else:
                self.logger.setLevel(logging.INFO)
        args = locals()
        for argName, argValue in args.items():
            if argName != 'self':
                setattr(self, argName, argValue)

        # create cache dir {{
        try:
            os.makedirs(self.cacheDirPath)
        except OSError:
            if not os.path.isdir(self.cacheDirPath):
                raise
        # }}

        self.xWidgetKey = self.getXWidgetKey()
        self.hashcash = self.getHashcash()
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/javascript",
            "X-Requested-With": "XMLHttpRequest",
            "X-Apple-Widget-Key": self.xWidgetKey,
            "X-Apple-HC": self.hashcash,
        }
        if userAgent:
            self.headers['User-Agent'] = userAgent
        self.session = requests.Session() # create a new session object
        # requests: define the retry strategy {{
        if self.requestsRetry:
            retryStrategy = Retry(**self.requestsRetrySettings)
            # create an http adapter with the retry strategy and mount it to session
            adapter = HTTPAdapter(max_retries=retryStrategy)
            self.session.mount('https://', adapter)
        # }}
        self.session.headers.update(self.headers)
        self.authTypes = ["hsa2"] # supported auth types
        self.xAppleIdSessionId = None
        self.scnt = None
        # persistent session cookie {{
        self.sessionCacheFile = self.cacheDirPath +'/sessionCacheFile.txt'
        if os.path.exists(self.sessionCacheFile) and os.path.getsize(self.sessionCacheFile) > 0:
            with open(self.sessionCacheFile, 'rb') as f:
                cookies = pickle.load(f)
                self.session.cookies.update(cookies)
        # }}

        self.apiSettingsAll = None

    def appleSessionHeaders(self):
        """
        return additional headers for appleconnect
        """

        defName = inspect.stack()[0][3]
        headers = {
            'X-Apple-Id-Session-Id': self.xAppleIdSessionId,
            'scnt': self.scnt,
        }
        self.logger.debug(f"def={defName}: headers={headers}")

        return headers

    def getXWidgetKey(self):
        """
        generate x-widget-key
        https://github.com/fastlane/fastlane/blob/master/spaceship/lib/spaceship/client.rb#L599
        """

        defName = inspect.stack()[0][3]
        cacheFile = self.cacheDirPath+'/WidgetKey.txt'
        if os.path.exists(cacheFile) and os.path.getsize(cacheFile) > 0:
            with open(cacheFile, "r") as file:
                 xWidgetKey = file.read()
        else:
            response = requests.get("https://appstoreconnect.apple.com/olympus/v1/app/config", params={ "hostname": "itunesconnect.apple.com" })
            try:
                data = response.json()
            except Exception as e:
                self.logger.error(f"def={defName}: failed get response.json(), error={str(e)}")
                return None
            with open(cacheFile, "w") as file:
                file.write(data['authServiceKey'])
            xWidgetKey = data['authServiceKey']

        self.logger.debug(f"def={defName}: xWidgetKey={xWidgetKey}")
        return xWidgetKey

    def getHashcash(self):
        """
        generate hashcash
        https://github.com/fastlane/fastlane/blob/master/spaceship/lib/spaceship/hashcash.rb
        """

        defName = inspect.stack()[0][3]
        response = requests.get(f"https://idmsa.apple.com/appleauth/auth/signin?widgetKey={self.xWidgetKey}")
        headers = response.headers
        bits = headers["X-Apple-HC-Bits"]
        challenge = headers["X-Apple-HC-Challenge"]

        # make hc {{
        version = 1
        date = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        counter = 0
        bits = int(bits)
        while True:
            hc = f"{version}:{bits}:{date}:{challenge}::{counter}"
            sha1_hash = hashlib.sha1(hc.encode()).digest()
            binary_hash = bin(int.from_bytes(sha1_hash, byteorder='big'))[2:] # сonvert to binary format
            if binary_hash.zfill(160)[:bits] == '0' * bits: # checking leading bits
                self.logger.debug(f"def={defName}: hc={hc}")
                return hc
            counter += 1
        # }}

    def handleTwoStepOrFactor(self,response):
        defName = inspect.stack()[0][3]

        responseHeaders = response.headers
        self.xAppleIdSessionId = responseHeaders["x-apple-id-session-id"]
        self.scnt = responseHeaders["scnt"]

        headers = self.appleSessionHeaders()

        r = self.session.get("https://idmsa.apple.com/appleauth/auth", headers=headers)
        self.logger.debug(f"def={defName}: response.status_code={r.status_code}")
        if r.status_code == 201:
            # success
            try:
                data = r.json()
            except Exception as e:
                raise Exception(f"def={defName}: failed get response.json(), error={str(e)}")
            self.logger.debug(f"def={defName}: response.json()={json.dumps(data)}")
            if 'trustedDevices' in data:
                self.logger.debug(f"def={defName}: trustedDevices={data['trustedDevices']}")
                self.handleTwoStep(r)
            elif 'trustedPhoneNumbers' in data:
                # read code from phone
                self.logger.debug(f"def={defName}: trustedPhoneNumbers={data['trustedPhoneNumbers']}")
                self.handleTwoFactor(r)
            else:
                raise Exception(f"Although response from Apple indicated activated Two-step Verification or Two-factor Authentication, we didn't know how to handle this response: #{r.text}")

        else:
            raise Exception(f"def={defName}: bad response.status_code={r.status_code}")

        return

    def handleTwoStep(self, response):
        # TODO write function for read code for trustedDevices
        return

    def handleTwoFactor(self,response):
        defName = inspect.stack()[0][3]
        try:
            data = response.json()
        except Exception as e:
            raise Exception(f"def={defName}: failed get response.json(), error={str(e)}")
        securityCode = data["securityCode"]
        # "securityCode": {
        #     "length": 6,
        #     "tooManyCodesSent": false,
        #     "tooManyCodesValidated": false,
        #     "securityCodeLocked": false
        # },
        codeLength = securityCode["length"]

        trustedPhone = data["trustedPhoneNumbers"][0]
        phoneNumber = trustedPhone["numberWithDialCode"]
        phoneId = trustedPhone["id"]
        pushMode = trustedPhone['pushMode']
        codeType = 'phone'
        code = input(f"Please enter the {codeLength} digit code you received at #{phoneNumber}: ")
        payload = {
            "securityCode": {
                "code": str(code),
            },
            "phoneNumber": {
                "id": phoneId,
            },
            "mode": pushMode,
        }
        headers = self.appleSessionHeaders()
        r = self.session.post(f"https://idmsa.apple.com/appleauth/auth/verify/{codeType}/securitycode", json=payload, headers=headers)
        self.logger.debug(f"def={defName}: response.status_code={r.status_code}")
        self.logger.debug(f"def={defName}: response.json()={json.dumps(r.json())}")

        if r.status_code == 200:
            self.storeSession()
            return True
        else:
            return False

    def storeSession(self):
        headers = self.appleSessionHeaders()
        r = self.session.get(f"https://idmsa.apple.com/appleauth/auth/2sv/trust", headers=headers)
        with open(self.sessionCacheFile, 'wb') as f:
            pickle.dump(self.session.cookies, f)

    def login(self, username, password):
        defName = inspect.stack()[0][3]

        url = "https://idmsa.apple.com/appleauth/auth/signin"
        headers = self.headers
        payload = {
            "accountName": username,
            "password": password,
            "rememberMe": True
        }

        response = self.session.post(url, json=payload, headers=headers)
        self.logger.debug(f"def={defName}: url={url}, response.status_code={response.status_code}")
        try:
            data = response.json()
        except Exception as e:
            self.logger.error(f"def={defName}: failed get response.json(), error={str(e)}, url='{url}', response.status_code='{str(response.status_code)}', response.text='{str(response.text)}'")
            return None

        if response.status_code == 409:
            # 2fa
            self.logger.debug(f"def={defName}: response.status_code={response.status_code}, go to 2fa auth")
            self.handleTwoStepOrFactor(response)
        elif response.status_code == 401:
            message = f"url={url}, response.status_code={response.status_code}, incorrect login or password"
            self.logger.error(f"def={defName}: {message}")
            raise Exception(message)
        elif response.status_code != 200:
            message = f"url={url}, wrong response.status_code={response.status_code}, should be 200 or 409"
            self.logger.error(f"def={defName}: {message}")
            raise Exception(message)

        # get api settings
        self.apiSettingsAll = self.getSettingsAll()

        return response

    def timeInterval(self, days):
        currentTime = datetime.datetime.now()
        past = currentTime - datetime.timedelta(days=days)
        startTime = past.strftime("%Y-%m-%dT00:00:00Z")
        endTime = currentTime.strftime("%Y-%m-%dT00:00:00Z")
        return { "startTime": startTime, "endTime": endTime }
