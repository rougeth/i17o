import asyncio
import json
import os
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

import aiohttp
import requests
import schedule
from decouple import config
from loguru import logger


class Transifex:
    # https://docs.transifex.com/api/
    api_url = "https://www.transifex.com/api/2/project/python-newest/"
    # https://www.transifex.com/user/settings/api/
    api_token = config("TRANSIFEX_API_TOKEN")

    def __init__(self, session):
        self.session = session

    async def request(self, url):
        async with self.session.get(urljoin(self.api_url, url)) as response:
            logger.debug("transifex api request, url={}", url)
            return await response.json()

    async def resources(self):
        # Request all resources available on Transifex
        resources = await self.request("resources/")
        return [resource["slug"] for resource in resources]

    async def resource_stat(self, resource):
        response = await self.request(f"resource/{resource}/stats/pt_BR/")
        return resource, response

    async def stats(self, resources):
        fields = [
            "reviewed",
            "translated_entities",
            "translated_words",
            "untranslated_entities",
            "untranslated_words",
        ]

        response = await asyncio.gather(
            *[self.resource_stat(resource) for resource in resources]
        )

        stats = defaultdict(lambda: {field: 0 for field in fields})
        for resource, stat in response:
            # Group stats considering the first part of slug.
            # Transform "c-api--abstract" and "c-api--allocation" into "c-api".
            # resource = resource.split('--')[0]

            for field in fields:
                stats[resource][field] += stat[field]

        stats["glossary"] = stats.pop("glossary_")
        return {key: stats[key] for key in sorted(stats.keys(), reverse=True)}


async def daily_stats(output):
    logger.info("running daily stats")
    async with aiohttp.ClientSession(
        auth=aiohttp.BasicAuth("api", Transifex.api_token)
    ) as session:
        transifex = Transifex(session=session)
        resources = await transifex.resources()
        stats = await transifex.stats(resources)

    today = datetime.now().strftime("%Y-%m-%d")
    filename = output / f"{today}.json"

    with open(filename, mode="w") as file:
        logger.info("saving stats at {}", filename)
        file.write(json.dumps(stats))


def run_daily_stats():
    output = Path(config("OUTPUT_DATA"))
    loop = asyncio.get_event_loop()
    loop.run_until_complete(daily_stats(output))


def main():
    job = schedule.every().day.at("00:00").do(run_daily_stats)
    job.run()
    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    main()
