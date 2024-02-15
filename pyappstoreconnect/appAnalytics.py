import inspect

class AppAnalytics:
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
            'adamId': appleId,
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
