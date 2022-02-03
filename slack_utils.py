import requests
from SGDPyUtil.singleton_utils import SingletonInstance


class Slack(SingletonInstance):
    def __init__(self):
        self.token = "xoxb-2903637462119-2915398236053-2bcZWO053tM0Uhc7RCQzFZW7"

    def notify(self, channel, content):
        response = requests.post(
            "https://slack.com/api/chat.postMessage",
            headers={"Authorization": "Bearer " + self.token},
            data={"channel": channel, "text": content},
        )
        return
