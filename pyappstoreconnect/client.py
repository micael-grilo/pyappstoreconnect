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
        self.logger = logging.getLogger(self.__class__.__name__)
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
        cacheFile = self.cacheDirPath+'/WidgetKey.txt'
        if os.path.exists(cacheFile) and os.path.getsize(cacheFile) > 0:
            with open(cacheFile, "r") as file:
                 xWidgetKey = file.read()
        else:
            response = requests.get("https://appstoreconnect.apple.com/olympus/v1/app/config", params={ "hostname": "itunesconnect.apple.com" })
            try:
                data = response.json()
            except Exception as e:
                self.logger.error(f"{defName}: failed get response.json(), error={str(e)}")
                return None
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
        if r.status_code == 201:
            # success
            try:
                data = r.json()
            except Exception as e:
                raise Exception(f"{defName}: failed get response.json(), error={str(e)}")
            self.logger.debug(f"{defName}: response.json()={json.dumps(data)}")
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
        try:
            data = response.json()
        except Exception as e:
            raise Exception(f"{defName}: failed get response.json(), error={str(e)}")
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
        defName = inspect.stack()[0][3]

        url = "https://idmsa.apple.com/appleauth/auth/signin"
        headers = self.headers
        payload = {
            "accountName": username,
            "password": password,
            "rememberMe": True
        }

        response = self.session.post(url, json=payload, headers=headers)
        try:
            data = response.json()
        except Exception as e:
            self.logger.error(f"{defName}: failed get response.json(), error={str(e)}")
            return None

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

    def timeSeriesAnalytics(self, appIds, measures, startTime, endTime, frequency, group=None, dimensionFilters=list(), apiVersion='v1'):
        """
        https://github.com/fastlane/fastlane/blob/master/spaceship/lib/spaceship/tunes/tunes_client.rb#L633
        """

        defName = inspect.stack()[0][3]
        if not isinstance(appIds, list):
            appIds = [appIds]
        if not isinstance(measures, list):
            measures = [measures]

        payload = {
            "adamId": appIds,
            "measures": measures,
            "dimensionFilters": dimensionFilters,
            "startTime": startTime,
            "endTime": endTime,
            "frequency": frequency,
        }
        if group != None:
            payload['group'] = group
        headers = {
            "X-Requested-By": "appstoreconnect.apple.com",
        }
        url=f"https://appstoreconnect.apple.com/analytics/api/{apiVersion}/data/time-series"
        self.logger.debug(f"payload={json.dumps(payload)}")
        response = self.session.post(url, json=payload, headers=headers)

        # check status_code
        if response.status_code != 200:
            self.logger.error(f"{defName}: status_code = {response.status_code}, payload={payload}, response.text={response.text}")
            return False

        # check json data
        try:
            data = response.json()
        except Exception as e:
            self.logger.error(f"{defName}: failed get response.json(), error={str(e)}")
            return None

        # check results
        if 'results' not in data:
            self.logger.error(f"{defName}: 'results' not found in response.json() = {data}")
            return False

        return data

    def appAnalytics(self, appleId, days=7, startTime=None, endTime=None, groupsByMap=dict()):
        """
        https://github.com/fastlane/fastlane/blob/master/spaceship/lib/spaceship/tunes/app_analytics.rb
        returns iterable object
        groupsByMap - map for limits grouping, if not set, will be get grouping for all metrics (more 150 results)
            format:
                { "metric": "group" }

            example:
                groupsByMap={
                    "pageViewUnique": "source",
                    "updates": "storefront",
                }
        """

        defName = inspect.stack()[0][3]
        # set default time interval
        if not startTime and not endTime:
            timeInterval = self.timeInterval(days)
            startTime = timeInterval['startTime']
            endTime = timeInterval['endTime']

        metrics = [
            # app store {{
            'impressionsTotal', # The number of times the app's icon was viewed on the App Store on devices running iOS 8, tvOS 9, macOS 10.14.1, or later.
            'impressionsTotalUnique', # The number of unique devices running iOS 8, tvOS 9, macOS 10.14.1, or later, that viewed the app's icon on the App Store.
            'conversionRate', # Calculated by dividing total downloads and pre-orders by unique device impressions. When a user pre-orders an app, it counts towards your conversion rate. It is not counted again when it downloads to their device.
            'pageViewCount', # The number of times the app's product page was viewed on the App Store on devices running iOS 8, tvOS 9, macOS 10.14.1, or later.
            'pageViewUnique', # The number of unique devices running iOS 8, tvOS 9, macOS 10.14.1, or later, that viewed your app's product page on the App Store.
            'updates', # The number of times the app has been updated to its latest version.
            # }}
            # downloads {{
            'units', # The number of first-time downloads on devices with iOS, tvOS, or macOS.
            'redownloads', # The number of redownloads on a device running iOS, tvOS, or macOS. Redownloads do not include auto-downloads, restores, or updates.
            'totalDownloads', # The number of first-time downloads and redownloads on devices with iOS, tvOS, or macOS.
            # }}
            # sales {{
            'iap', # The number of in-app purchases on devices with iOS, tvOS, or macOS.
            'proceeds', # The estimated amount of proceeds the developer will receive from their sales, minus Apple’s commission. May not match final payout due to final exchange rates and transaction lifecycle.
            'sales', # The total amount billed to customers for purchasing apps, bundles, and in-app purchases.
            'payingUsers', # The number of unique users that paid for the app or an in-app purchase.
            # }}
            # usage {{
            'installs', # The total number of times your app has been installed. Includes redownloads and restores on the same or different device, downloads to multiple devices sharing the same Apple ID, and Family Sharing installations.
            'sessions', # The number of times the app has been used for at least two seconds.
            'activeDevices', # The total number of devices with at least one session during the selected period.
            'rollingActiveDevices', # The total number of devices with at least one session within 30 days of the selected day.
            'crashes', # The total number of crashes. Actual crash reports are available in Xcode.
            'uninstalls', # The number of times your app has been deleted on devices running iOS 12.3, tvOS 13.0, or macOS 10.15.1 or later.
            # }}
        ]
        defaultSettings = {
            'appIds': appleId,
            'startTime': startTime,
            'endTime': endTime,
            'frequency': 'day',
            'group': None,
        }

        # grouping by
        groups = [
            'source', # source type: web referrer, app referrer, etc...
            'platform', # device: iphone, ipad, etc...
            'platformVersion', # ios 17, ios 16, etc...
            'pageType', # product page, store sheet, etc...
            'region', # region: europe, usa and canada, asia, etc...
            'storefront', # territory: united states, germany, etc...
            'appReferrer', # Google Chrome, Firefix, etc...
            'domainReferrer', # anytype.io, google.com, etc...
        ]
        groupsDefaultSettings = {
            'rank': 'DESCENDING',
            'limit': 10,
        }
        invalidMeasureDimensionCombination = {
            'updates': ['pageType'],
            'payingUsers': ['platform'],
            'sessions': ['platformVersion'],
            'rollingActiveDevices': [
                'appReferrer',
                'domainReferrer',
            ],
            'crashes': [
                'source',
                'platform',
                'pageType',
                'region',
                'storefront',
                'appReferrer',
                'domainReferrer',
            ],
        }


        for metric in metrics:
            settings = defaultSettings.copy()
            if not 'measures' in settings:
                settings['measures'] = metric
            # metrics grouping by date {{
            response = self.timeSeriesAnalytics(**settings)
            yield { 'settings': settings, 'response': response }
            # }}

            # metrics with grouping {{
            if groupsByMap:
                # if set, get groups by static maps
                for _metric,_group in groupsByMap.items():
                    if _metric != metric:
                        continue
                    if _metric not in metrics:
                        self.logger.warning(f"{defName}: invalid pair='{_metric}':'{_group}' in groupsByMap, metric not in available metrics list")
                        continue
                    if _group not in groups:
                        self.logger.warning(f"{defName}: invalid pair='{_metric}':'{_group}' in groupsByMap, group not in available groups list")
                        continue
                    if _metric in invalidMeasureDimensionCombination.keys() and _group in invalidMeasureDimensionCombination[_metric]:
                        self.logger.warning(f"{defName}: invalid pair='{_metric}':'{_group}' in groupsByMap, invalid measure-dimension combination")
                        # skip if we have invalid measure-dimension combination
                        continue
                    _groupSettings = groupsDefaultSettings.copy()
                    _groupSettings['metric'] = settings['measures']
                    _groupSettings['dimension'] = _group
                    settings['group'] = _groupSettings
                    response = self.timeSeriesAnalytics(**settings)
                    yield { 'settings': settings, 'response': response }

            else:
                # else, get all groups for all metrics
                # WARNING: most likely you will get rate limit
                for group in groups:
                    if metric in invalidMeasureDimensionCombination.keys() and group in invalidMeasureDimensionCombination[metric]:
                        self.logger.debug(f"{defName}: skipping invalid measure-dimension combination: metric={metric}, group={group}")
                        # skip if we have invalid measure-dimension combination
                        continue
                    _groupSettings = groupsDefaultSettings.copy()
                    _groupSettings['metric'] = settings['measures']
                    _groupSettings['dimension'] = group
                    settings['group'] = _groupSettings
                    response = self.timeSeriesAnalytics(**settings)
                    yield { 'settings': settings, 'response': response }
            # }}


    def benchmarks(self, appleId, days=182, startTime=None, endTime=None):
        """
        benchmarks
        default intervals: 4 weeks, 12 weeks, 26 weeks (182 days)
        """

        defName = inspect.stack()[0][3]
        # set default time interval
        if not startTime and not endTime:
            timeInterval = self.timeInterval(days)
            startTime = timeInterval['startTime']
            endTime = timeInterval['endTime']

        metrics = {
            # conversionRate {{
            'benchConversionRate': {
                'dimensionFilters': [
                    {
                        'dimensionKey': 'peerGroupId',
                        'optionKeys': ['14'],
                    }
                ],
            },
            'conversionRate': {},
            # }}
            # crashRate {{
            'benchCrashRate': {
                'dimensionFilters': [
                    {
                        'dimensionKey': 'peerGroupId',
                        'optionKeys': ['14'],
                    }
                ],
            },
            'crashRate': {},
            # }}
            # retentionD1 {{
            'benchRetentionD1': {
                'dimensionFilters': [
                    {
                        'dimensionKey': 'peerGroupId',
                        'optionKeys': ['14'],
                    }
                ],
            },
            'retentionD1': {},
            # }}
            # retentionD7 {{
            'benchRetentionD7': {
                'dimensionFilters': [
                    {
                        'dimensionKey': 'peerGroupId',
                        'optionKeys': ['14'],
                    }
                ],
            },
            'retentionD7': {},
            # }}
            # retentionD28 {{
            'benchRetentionD28': {
                'dimensionFilters': [
                    {
                        'dimensionKey': 'peerGroupId',
                        'optionKeys': ['14'],
                    }
                ],
            },
            'retentionD28': {},
            # }}
        }

        defaultSettings = {
            'appIds': appleId,
            'startTime': startTime,
            'endTime': endTime,
            'frequency': 'week',
            'group': None,
            'apiVersion': 'v2',
        }

        for metric,settings in metrics.items():
            args = defaultSettings.copy()
            args.update(settings)
            if not 'measures' in args:
                args['measures'] = metric
            response = self.timeSeriesAnalytics(**args)
            yield { 'settings': args, 'response': response }
