import inspect
import json

class MetricsWithFilter:
    def getMetricsWithFilter(self, appleId, metrics=list(), filters=list(), days=7, startTime=None, endTime=None):
        """
        get metrics by filter
        """

        defName = inspect.stack()[0][3]

        if not isinstance(metrics, list):
            metrics = [metrics]
        if not isinstance(groups, list):
            groups = [groups]

        # set default time interval
        if not startTime and not endTime:
            timeInterval = self.timeInterval(days)
            startTime = timeInterval['startTime']
            endTime = timeInterval['endTime']

        # get available options for filters
        for metric in metrics:
            # get available dimensions id for metrics {{
            for measure in self.apiSettingsAll['measures']:
                if measure['key'] == metric or measure['title'] == metric:
                    availableDimensionsIds = measure['dimensions']
                    self.logger.debug(f"{defName}: metric={metric}, available dimensions={availableDimensionsIds}")
            # }}
            for _filter in filters:
                for dimension in self.apiSettingsAll['dimensions']:
                    if dimension['key'] == _filter or dimension['title'] == _filter:
                        if dimension['id'] in availableDimensionsIds:
                            self.logger.debug(f"{defName}: filter={_filter}, available option dimension['title']={dimension['title']}")
                        else:
                            self.logger.debug(f"{defName}: filter={_filter}, dimension['title']={dimension['title']}, dimension['id']={dimension['id']} not in availableDimensionsIds={availableDimensionsIds}")
                            continue
                        #self.logger.debug(f"dimension={json.dumps(dimension,indent=4)}")
                        for option in dimension['options']:
                            args = {
                                "adamId": appleId,
                                "measures": metric,
                                "dimensionFilters": [
                                    {
                                        "dimensionKey": dimension['key'],
                                        "optionKeys": [ option['id'] ],
                                    },
                                ],
                                "frequency":"day",
                                "startTime": startTime,
                                "endTime": endTime,
                            }
                            response = self.timeSeriesAnalytics(**args)
                            yield {
                                'settings': args,
                                'response': response,
                                'filters': {
                                    'dimension': {
                                        'id': dimension['id'],
                                        'key': dimension['key'],
                                    },
                                    'option': {
                                        'id': option['id'],
                                        'title': option['title'],
                                        'shortTitle': option['shortTitle'],
                                    },
                                }
                            }

