class NetworkStatus(object):
    def __init__(self):
        self._wifi = None
        self._ethernet = None

    @property
    def wifi(self):
        return self._wifi

    @wifi.setter
    def wifi(self, value):
        self._wifi = value

    @property
    def ethernet(self):
        return self._ethernet

    @ethernet.setter
    def ethernet(self, value):
        self._ethernet = value

    def is_connected(self):
        return self._wifi or self._ethernet
