import inspect
import json

class AcquisitionMixin:
    def sourcesList(self, adamId, measures, startTime, endTime, frequency, dimension, apiVersion='v1'):
        """
        https://appstoreconnect.apple.com/analytics/app/xx/yy/acquisition
        """

        defName = inspect.stack()[0][3]
        if not isinstance(adamId, list):
            adamId = [adamId]
        if not isinstance(measures, list):
            measures = [measures]

        payload = {
            "adamId": adamId,
            "measures": measures,
            "dimension": dimension,
            "frequency": frequency,
            "startTime": startTime,
            "endTime": endTime,
            "limit": 1,
        }
        headers = {
            "X-Requested-By": "appstoreconnect.apple.com",
        }
        url=f"https://appstoreconnect.apple.com/analytics/api/{apiVersion}/data/sources/list"
        self.logger.debug(f"{defName}: payload={json.dumps(payload)}")
        response = self.session.post(url, json=payload, headers=headers)

        # check status_code
        if response.status_code != 200:
            self.logger.error(f"{defName}: status_code={response.status_code}, payload={payload}, response.text={response.text}")
            return False

        # check json data
        try:
            data = response.json()
        except Exception as e:
            self.logger.error(f"{defName}: failed get response.json(), error={str(e)}")
            return None

        # check results
        if 'results' not in data:
            self.logger.error(f"{defName}: 'results' not found in response.json()={data}")
            return False

        return data

    def acquisition(self, appleId, days=7, startTime=None, endTime=None):
        """
        payload example
        {
            "adamId": [
                "6449487029"
            ],
            "measures": [
                "impressionsTotal",
                "totalDownloads",
                "proceeds",
                "sessions"
            ],
            "dimension": "campaignId",
            "frequency": "day",
            "startTime": "2024-10-01T00:00:00Z",
            "endTime": "2024-10-30T00:00:00Z",
            "limit": 1
        }
        """

        defName = inspect.stack()[0][3]
        # set default time interval
        if not startTime and not endTime:
            timeInterval = self.timeInterval(days)
            startTime = timeInterval['startTime']
            endTime = timeInterval['endTime']

        args = {
            'adamId': appleId,
            'startTime': startTime,
            'endTime': endTime,
            'frequency': 'day',
            'dimension': 'campaignId',
            'measures': ['impressionsTotal','totalDownloads','proceeds','sessions'],
        }
        self.logger.debug(f"{defName}: args='{args}'")
        response = self.sourcesList(**args)
        return { 'settings': args, 'response': response }
