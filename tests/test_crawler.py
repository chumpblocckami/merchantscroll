import os

from entrypoint import start_crawler

if __name__ == "__main__":
    os.environ["MERCHANT_SCROLL_DEBUG"] = "1"
    start_crawler()
