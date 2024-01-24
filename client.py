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

cfg = {
    "cacheDirPath": "./cache",
}

class Client():
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

    def __init__(self, cfg=cfg):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.cfg = cfg
        self.xWidgetKey = self.getXWidgetKey()
        self.hashcash = self.getHashcash()
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/javascript",
            "X-Requested-With": "XMLHttpRequest",
            "X-Apple-Widget-Key": self.xWidgetKey,
            "X-Apple-HC": self.hashcash,
        }
        # requests: define the retry strategy {{
        retryStrategy = Retry(
            total=4, # maximum number of retries
            backoff_factor=10, # retry via 10, 20, 40, 80 sec
            status_forcelist=[429, 500, 502, 503, 504],  # HTTP status codes to retry on
        )
        # create an http adapter with the retry strategy and mount it to session
        adapter = HTTPAdapter(max_retries=retryStrategy)
        # Create a new session object
        self.session = requests.Session()
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)
        # }}
        self.session.headers.update(self.headers)
        self.authTypes = ["hsa2"] # supported auth types
        self.xAppleIdSessionId = None
        self.scnt = None
        # persistent session cookie {{
        try:
            os.makedirs(self.cfg['cacheDirPath'])
        except OSError:
            if not os.path.isdir(self.cfg['cacheDirPath']):
                raise
        self.sessionCacheFile = self.cfg['cacheDirPath'] +'/sessionCacheFile.txt'
        if os.path.exists(self.sessionCacheFile) and os.path.getsize(self.sessionCacheFile) > 0:
            with open(self.sessionCacheFile, 'rb') as f:
                cookies = pickle.load(f)
                self.session.cookies.update(cookies)
        # }}

    def appleSessionHeaders(self):
        """
        return additional headers for appleconnect
        """

        defName = inspect.stack()[0][3]
        headers = {
            'X-Apple-Id-Session-Id': self.xAppleIdSessionId,
            'scnt': self.scnt,
        }
        self.logger.debug(f"{defName}: headers={headers}")

        return headers

    def getXWidgetKey(self):
        """
        generate x-widget-key
        https://github.com/fastlane/fastlane/blob/master/spaceship/lib/spaceship/client.rb#L599
        """

        defName = inspect.stack()[0][3]
        cacheFile = self.cfg['cacheDirPath'] +'/WidgetKey.txt'
        if os.path.exists(cacheFile) and os.path.getsize(cacheFile) > 0:
            with open(cacheFile, "r") as file:
                 xWidgetKey = file.read()
        else:
            response = requests.get("https://appstoreconnect.apple.com/olympus/v1/app/config", params={ "hostname": "itunesconnect.apple.com" })
            data = response.json()
            with open(cacheFile, "w") as file:
                file.write(data['authServiceKey'])
            xWidgetKey = data['authServiceKey']

        self.logger.debug(f"{defName}: xWidgetKey={xWidgetKey}")
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
                self.logger.debug(f"{defName}: hc={hc}")
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
        self.logger.debug(f"{defName}: response.status_code={r.status_code}")
        self.logger.debug(f"{defName}: response.json()={json.dumps(r.json())}")
        if r.status_code == 201:
            # success
            data = r.json()
            if 'trustedDevices' in data:
                self.logger.debug(f"{defName}: trustedDevices={data['trustedDevices']}")
                self.handleTwoStep(r)
            elif 'trustedPhoneNumbers' in data:
                # read code from phone
                self.logger.debug(f"{defName}: trustedPhoneNumbers={data['trustedPhoneNumbers']}")
                self.handleTwoFactor(r)
            else:
                raise Exception(f"Although response from Apple indicated activated Two-step Verification or Two-factor Authentication, we didn't know how to handle this response: #{r.text}")

        else:
            raise Exception(f"{defName}: bad response.status_code={r.status_code}")

        return

    def handleTwoStep(self, response):
        # TODO write function for read code for trustedDevices
        return

    def handleTwoFactor(self,response):
        defName = inspect.stack()[0][3]
        data = response.json()
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
        self.logger.debug(f"{defName}: response.status_code={r.status_code}")
        self.logger.debug(f"{defName}: response.json()={json.dumps(r.json())}")

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
        url = "https://idmsa.apple.com/appleauth/auth/signin"
        headers = self.headers
        payload = {
            "accountName": username,
            "password": password,
            "rememberMe": True
        }

        response = self.session.post(url, json=payload, headers=headers)
        data = response.json()
        if response.status_code == 409:
            # 2fa
            self.logger.debug(f"response.status_code={response.status_code}, go to 2fa auth")
            self.handleTwoStepOrFactor(response)

        return response

    def timeInterval(self, days):
        currentTime = datetime.datetime.now()
        past = currentTime - datetime.timedelta(days=days)
        startTime = past.strftime("%Y-%m-%dT00:00:00Z")
        endTime = currentTime.strftime("%Y-%m-%dT00:00:00Z")
        return { "startTime": startTime, "endTime": endTime }

    def timeSeriesAnalytics(self, appIds, measures, startTime, endTime, frequency, viewBy):
        """
        https://github.com/fastlane/fastlane/blob/master/spaceship/lib/spaceship/tunes/tunes_client.rb#L633
        """
        if not isinstance(appIds, list):
            appIds = [appIds]
        if not isinstance(measures, list):
            measures = [measures]

        if not viewBy or not measures:
            group = None
        else:
            group = {
                "metric": measures[0],
                "dimension": viewBy,
                "rank": "DESCENDING",
                "limit": 3
            }

        payload = {
            "adamId": appIds,
            "dimensionFilters": [],
            "endTime": endTime,
            "frequency": frequency,
            "group": group,
            "measures": measures,
            "startTime": startTime,
        }
        headers = {
            "X-Requested-By": "appstoreconnect.apple.com",
        }
        response = self.session.post("https://appstoreconnect.apple.com/analytics/api/v1/data/time-series", json=payload, headers=headers)
        data = response.json()
        return data

    def appAnalytics(self, appleId, days=7, startTime=None, endTime=None):
        """
        https://github.com/fastlane/fastlane/blob/master/spaceship/lib/spaceship/tunes/app_analytics.rb
        returns iterable object
        """

        # set default time interval
        if not startTime and not endTime:
            timeInterval = self.timeInterval(days)
            startTime = timeInterval['startTime']
            endTime = timeInterval['endTime']

        metrics = [
            'impressionsTotal', # App Store / Impressions Unique Devices
            'pageViewCount', # App Store / Product Page Views Unique Devices
            'units', # Sales / App Units
            'iap', # Sales / In-App Purchases
            'sales', # Sales / Sales
            'payingUsers', # Sales / Paying Users
            'installs', # Usage / Installations
            'sessions', # Usage / Sessions
            'activeDevices', # Usage / Active Devices
            'rollingActiveDevices', # Usage / Active Devices 30 Days
            'crashes', # Usage / Crashes
        ]

        for metric in metrics:
            response = self.timeSeriesAnalytics(appleId,metric,startTime,endTime,"DAY",None)
            yield response