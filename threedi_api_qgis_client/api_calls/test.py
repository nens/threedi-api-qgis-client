import asyncio
import json
import websockets
from websockets.http import Headers
import pprint

API_HOST = "wss://api.3di.live/v3.0"
pp = pprint.PrettyPrinter(width=45, depth=1)


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

    async def listen(self):
        uri = f'wss://api.3di.live/v3.0/' +\
              f'active-simulations'
        print(f"Connecting to {uri}")
        headers = Headers(authorization=f'{self.bearer} {self.jwt_token}')
        async with websockets.connect(uri, extra_headers=headers) as websocket:
            self.websocket = websocket
            while self.do_listen:
                try:
                    data = await websocket.recv()
                    data = json.loads(data)
                    content = data["data"]
                    pp.pprint(content)
                    # print(content)
                except websockets.exceptions.ConnectionClosedOK:
                    self.do_listen = False

    async def close(self):
        self.do_listen = False
        await self.websocket.close()


ws = WebsocketClient("dewedwed")
# ws.
# asyncio.run(ws.listen())
# loop = asyncio.get_event_loop()
# result = loop.run_until_complete(ws.listen())

