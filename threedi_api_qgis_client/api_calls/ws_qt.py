from qgis.PyQt import QtNetwork
from qgis.PyQt.QtCore import QUrl, QCoreApplication, QTimer, QByteArray, QObject

from PyQt5 import QtWebSockets

API_HOST = "wss://api.3di.live/v3.0"


class ClientWS(QObject):
    def __init__(self, parent, receive_method, jwt_token: str, bearer='Bearer'):
        super().__init__(parent)

        self.bearer = bearer
        self.jwt_token = jwt_token

        req = QtNetwork.QNetworkRequest(QUrl(API_HOST + "/active-simulations/"))
        req.setRawHeader(QByteArray().append("Authorization"), QByteArray().append(f'{self.bearer} {self.jwt_token}'))
        self.client = QtWebSockets.QWebSocket("", QtWebSockets.QWebSocketProtocol.Version13, None)
        self.client.error.connect(self.error)

        self.client.open(req)
        self.client.pong.connect(self.onPong)
        self.client.textMessageReceived.connect(receive_method)

    def do_ping(self):
        print("client: do_ping")
        self.client.ping(b"foo")

    def send_message(self):
        print("client: send_message")
        self.client.sendTextMessage("asd")

    def onPong(self, elapsedTime, payload):
        print("onPong - time: {} ; payload: {}".format(elapsedTime, payload))

    def error(self, error_code):
        print("error code: {}".format(error_code))
        print(self.client.errorString())

    def close(self):
        self.client.close()

def quit_app():
    print("timer timeout - exiting")
    QCoreApplication.quit()

