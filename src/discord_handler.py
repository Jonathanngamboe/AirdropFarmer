# discord_handler.py
from discord.ext import commands

class DiscordHandler:
    def __init__(self, connected_to_discord_event):
        self.client = commands.Bot(command_prefix=".", self_bot=True, help_command=None)
        self.connected_to_discord = connected_to_discord_event

        @self.client.event
        async def on_ready():
            self.connected_to_discord.set()
            print(f"Discord : Logged in as {self.client.user}")

    @property
    def is_connected(self):
        return self.connected_to_discord.is_set()

    async def perform_action(self, action):
        if action["action"] == "send_message":
            await self.send_message(action["channel_id"], action["message"])

    async def send_message(self, channel_id, message):
        channel = self.client.get_channel(channel_id)
        print(f"Trying to send a message to channel: {channel_id}")
        if channel:
            print(f"Found channel: {channel.name}")
            await channel.send(message)
            print("Discord message sent")
        else:
            print("Channel not found.")


