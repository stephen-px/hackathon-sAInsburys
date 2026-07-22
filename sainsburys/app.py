import os
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_surface import handlers

app = App(token=os.environ["SLACK_BOT_TOKEN"])
handlers.register(app)

if __name__ == "__main__":
    SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()
