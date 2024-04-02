import inspect

class Settings:
    def getSettingsAll(self):
        """
        get all settings for page
        """

        defName = inspect.stack()[0][3]
        url=f"https://appstoreconnect.apple.com/analytics/api/v1/settings/all"
        response = self.session.get(url)

        # check status_code
        if response.status_code != 200:
            self.logger.error(f"{defName}: status_code = {response.status_code}, response.text={response.text}")
            return False

        # check json data
        try:
            data = response.json()
        except Exception as e:
            self.logger.error(f"{defName}: failed get response.json(), error={str(e)}, response.text={response.text}")
            return None

        return data
