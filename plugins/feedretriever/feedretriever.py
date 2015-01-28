import json
import sys
import feedparser

from twisted.python import log

import plugin
from utils import str_utils

FAIL_MESSAGE = ("Unable to download or parse feed.  Remove unused feeds using "
                "the !listfeed and !removefeed commands.")

HELP_MESSAGE = ("!addfeed url [fetch time [custom title]] where:\n"
                "url - is the url of the atom or rss feed\n"
                "fetch time - is the number of minutes between each request\n"
                "custom title - is the title used for this feed.\n"
                "If no title is given, the default title parsed from the "
                "feed will be used instead.")

DEFAULT_FETCH_TIME = 10*60

# The Feed class handles printing out new entries
class Feed():
    # Note that data could both be a url, or an already parsed feed
    def __init__(self, data, title):
        if isinstance(data, basestring):
            data = feedparser.parse(data)
        self.last_entry = 0
        self.set_last(data.entries)
        self.title = title
        self.update_title(data)

    def update(self, data, say):
        if isinstance(data, basestring):
            data = feedparser.parse(data)
        if data.bozo != 0:
            log.msg("Error updating feed " + self.title)
            return
        self.update_title(data)
        log.msg("Updating feed: " + self.title)
        for entry in data.entries:
            # TODO: Check id, title and link, etc
            # Maybe save the entire data.entries and remove all duplicate when
            # a new update happens?
            if entry.published_parsed <= self.last_entry:
                break
            say(u"{}: {} <{}>".format(self.title, entry.title, entry.link))
        self.set_last(data.entries)

    def update_title(self, parsed):
        if parsed.bozo == 0 and self.title == "":
            self.title = parsed.feed.title

    def set_last(self, entries):
        if len(entries) > 0:
            self.last_entry = entries[0].published_parsed


# Simple polling class, fetches the feed in a regular intervall and passes
# the information on to the Feed object
class Feedpoller():
    def __init__(self, say, url, update_freq=DEFAULT_FETCH_TIME, title=""):
        parsed = feedparser.parse(url)
        self.feed = Feed(parsed, title)
        if parsed.bozo == 0:
            self.modified = parsed.get("modified", None)
            self.etag = parsed.get("etag", None)
            say("Added feed: " + self.feed.title)
        else:
            self.modified = ""
            say(FAIL_MESSAGE)
        self.say = say
        self.url = url
        self.consecutive_fails = 0
        self.update_freq = update_freq
        self.update_count = 0

    def update(self):
        self.update_count += 1
        if self.update_count >= self.update_freq:
            self.update_count = 0
            parsed = feedparser.parse(self.url, modified=self.modified, etag=self.etag)
            if parsed.bozo == 1:
                self.consecutive_fails += 1
                if self.consecutive_fails % 10 == 0:
                    self.say(FAIL_MESSAGE)
            else:
                self.modified = parsed.get("modified", None)
                self.etag = parsed.get("etag", None)
                self.feed.update(parsed, self.say)
                self.consecutive_fails = 0

# Aggregator class for adding and handling feeds
class Feedretriever(plugin.Plugin):
    def __init__(self):
        plugin.Plugin.__init__(self, "Feedretriever")
        self.feeds = []

    def started(self, settings):
        log.msg("Feedretriever.started", settings)
        #self.settings = json.loads(settings)
        #TODO: Save feeds to file and recreate when the bot is restarted

    def privmsg(self, server_id, user, channel, message):
        say = lambda msg: self.say(server_id, channel, msg)
        if message.startswith("!feed") or message.startswith("!addfeed"):
            _, url, time, title = str_utils.split(message, " ", 4)
            try:
                time = int(time) * 60
            except:
                time = DEFAULT_FETCH_TIME
            if url == "":
                say(HELP_MESSAGE)
                return
            self.feeds.append(Feedpoller(say, url, time, title))
        elif message.startswith("!removefeed"):
            i = message[12:]
            i = int(i) if unicode(i).isdecimal() else -1
            if i >= 0 and i < len(self.feeds):
                say("Removing: #{} - {}".format(i, self.feeds[i].feed.title))
                self.feeds.remove(i)
        elif message.startswith("!listfeed"):
            if len(self.feeds) == 0:
                say("No feeds")
            for i, feed in enumerate(self.feeds):
                say("#{}: {}".format(i, feed.feed.title))

    def update(self):
        for feed in self.feeds:
            feed.update()

if __name__ == "__main__":
    sys.exit(Feedretriever.run())
