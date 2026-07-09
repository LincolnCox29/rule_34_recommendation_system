import logging

class NetworkSpamFilter(logging.Filter):
    def filter(self, record):
        text = record.getMessage()

        spam = (
            "Failed to fetch updates",
            "Sleep for",
            "TelegramNetworkError",
        )

        return not any(s in text for s in spam)

def enable_log_filter():
    logging.getLogger("aiogram.dispatcher").addFilter(NetworkSpamFilter())