import sys

from qgis.PyQt import QtCore, QtWebSockets, QtNetwork
from qgis.PyQt.QtCore import QUrl, QCoreApplication, QTimer
from qgis.PyQt.QtWidgets import QApplication

API_HOST = "wss://api.3di.live/v3.0"


class ClientWS(QtCore.QObject):
    def __init__(self, parent, jwt_token: str, bearer='Bearer'):
        super().__init__(parent)

        self.bearer = bearer
        self.jwt_token = jwt_token

        req = QtNetwork.QNetworkRequest(API_HOST + "/active-simulations")
        req.setRawHeader("authorization", f'{self.bearer} {self.jwt_token}')
        self.client =  QtWebSockets.QWebSocket("",QtWebSockets.QWebSocketProtocol.Version13,None)
        self.client.error.connect(self.error)

        self.client.open(req)
        # self.client.open(QUrl(API_HOST))
        self.client.pong.connect(self.onPong)

        # "/active-simulations"
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

# def ping():
#     client.do_ping()
#
# def send_message():
#     client.send_message()

# if __name__ == '__main__':
#     global client
#     app = QApplication(sys.argv)
#
#     QTimer.singleShot(2000, ping)
#     QTimer.singleShot(3000, send_message)
#     QTimer.singleShot(5000, quit_app)
#
#     client = Client(app)
#
#     app.exec_()
