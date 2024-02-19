import inspect

class Benchmarks:
    """
    available optionKeys
        14  - "Productivity App" This peer set includes apps in the Productivity category on the App Store.
        2   - "All Categories" This peer set includes apps in all categories on the App Store.
    """

    def benchmarks(self, appleId, days=182, startTime=None, endTime=None, optionKeys=14):
        """
        benchmarks
        default intervals: 4 weeks, 12 weeks, 26 weeks (182 days)
        """

        defName = inspect.stack()[0][3]
        if not isinstance(optionKeys, list):
            optionKeys = [optionKeys]
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
                        'optionKeys': optionKeys,
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
                        'optionKeys': optionKeys,
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
                        'optionKeys': optionKeys,
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
                        'optionKeys': optionKeys,
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
                        'optionKeys': optionKeys,
                    }
                ],
            },
            'retentionD28': {},
            # }}
        }

        defaultSettings = {
            'adamId': appleId,
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
