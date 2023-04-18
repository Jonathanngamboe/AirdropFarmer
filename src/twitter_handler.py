# twitter_handler.py
import tweepy
import config.settings as settings

class TwitterHandler:
    def __init__(self):
        auth = tweepy.OAuthHandler(settings.TWITTER_API_KEY, settings.TWITTER_API_SECRET)
        auth.set_access_token(settings.TWITTER_ACCESS_TOKEN, settings.TWITTER_ACCESS_TOKEN_SECRET)
        self.api = tweepy.API(auth)

    def perform_action(self, action):
        if action["action"] == "follow":
            self.follow_user(action["user"])
        elif action["action"] == "retweet":
            self.retweet(action["tweet_id"])
        elif action["action"] == "tweet":
            self.tweet(action["text"])

    def follow_user(self, user):
        self.api.create_friendship(screen_name=user)

    def retweet(self, tweet_id):
        self.api.retweet(tweet_id)

    def tweet(self, text):
        self.api.update_status(status=text)

