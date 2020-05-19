# import json
# import websockets
# from websockets.http import Headers
# import pprint

import websocket

try:
    import thread
except ImportError:
    import _thread as thread
import time


API_HOST = "wss://api.3di.live/v3.0"


class WebsocketClient:
    def __init__(
        self,
        jwt_token: str,
        bearer='Bearer'
    ):

        self.websocket = None
        self.do_listen = True
        self.bearer = bearer
        self.jwt_token = jwt_token
#
#     async def listen(self):
#         uri = f'{API_HOST}/' +\
#               f'active-simulations'
#         print(f"Connecting to {uri}")
#         headers = Headers(authorization=f'{self.bearer} {self.jwt_token}')
#         async with websockets.connect(uri, extra_headers=headers) as websocket:
#             self.websocket = websocket
#             while self.do_listen:
#                 try:
#                     data = await websocket.recv()
#                     data = json.loads(data)
#                     content = data["data"]
#                     pp.pprint(content)
#                     # print(content)
#                 except websockets.exceptions.ConnectionClosedOK:
#                     self.do_listen = False
#
#     async def close(self):
#         self.do_listen = False
#         await self.websocket.close()



    def on_message(self, ws, message):
        print(message)

    def on_error(self, ws, error):
        print(error)

    def on_close(self, ws):
        print("### closed ###")

    def on_open(self, ws):
        def run(*args):
            for i in range(3):
                time.sleep(1)
                ws.send("Hello %d" % i)
            time.sleep(1)
            ws.close()
            print("thread terminating...")
        thread.start_new_thread(run, ())

    def connect(self):
        websocket.enableTrace(True)
        ws = websocket.WebSocketApp(API_HOST + "active-simulations",
                                on_message=self.on_message,
                                on_error=self.on_error,
                                on_close=self.on_close,
                                header={"authorization": f'{self.bearer} {self.jwt_token}'})
        ws.on_open = self.on_open
        ws.run_forever()


xx = WebsocketClient("deded")
xx.connect()
