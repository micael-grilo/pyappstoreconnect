import inspect

class Benchmarks:
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
