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
from aiogram import Bot


STATS_FIELDS = [
    "reviewed",
    "translated_entities",
    "translated_words",
    "untranslated_entities",
    "untranslated_words",
]

STATS_MESSAGES = {
    "reviewed": "- Traduções revisadas: {:+}\n",
    "translated_words": "- Palavras traduzidas: {:+}\n",
}


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
        response = await asyncio.gather(
            *[self.resource_stat(resource) for resource in resources]
        )

        stats = defaultdict(lambda: {field: 0 for field in STATS_FIELDS})

        for resource, stat in response:
            stats[resource] = stat

        stats["glossary"] = stats.pop("glossary_")
        return {key: stats[key] for key in sorted(stats.keys(), reverse=True)}


async def download_current_stats(output):
    """
    Download statistics from every resource present at Transifex and
    save it as JSON files at `output`.
    """
    logger.info("Downloading current statistics")
    async with aiohttp.ClientSession(
        auth=aiohttp.BasicAuth("api", Transifex.api_token)
    ) as session:
        transifex = Transifex(session=session)
        resources = await transifex.resources()
        stats = await transifex.stats(resources)

    today = datetime.now().strftime("%Y-%m-%d")
    filename = output / f"{today}.json"

    with open(filename, mode="w") as file:
        logger.info("Saving stats at {}", filename)
        file.write(json.dumps(stats))


def run_daily_stats():
    output = Path(config("OUTPUT_DATA"))
    loop = asyncio.get_event_loop()
    loop.run_until_complete(download_current_stats(output))


def select_report_files(output):
    stats_files = sorted(os.listdir(output), reverse=True)
    latest_file = output / stats_files[0]

    if len(stats_files) > 7:
        previous_file = output / stats_files[6]
    else:
        previous_file = output / stats_files[-1]

    logger.debug(
        "Report files selected, latest_file={}, previous_file={}",
        latest_file,
        previous_file,
    )

    with latest_file.open() as latest_file, previous_file.open() as previous_file:
        return json.load(latest_file), json.load(previous_file)


def serialize_report(report, group_resources=False):
    updated_report = defaultdict(lambda: {field: 0 for field in STATS_FIELDS})

    for resource, stats in report.items():
        if group_resources:
            resource = resource.split("--")[0]

        for field in stats:
            updated_report[resource][field] += stats[field]

    if updated_report.get("glossary_"):
        updated_report["glossary"] = updated_report.pop("glossary_")

    return updated_report


def compare_reports():
    output = Path(config("OUTPUT_DATA"))
    reports = select_report_files(output)
    latest_report, previous_report = map(
        lambda r: serialize_report(r, group_resources=True), reports
    )

    report = defaultdict(dict)
    for resource, stats in latest_report.items():
        for stat, value in stats.items():
            previous_value = previous_report[resource][stat]
            if value != previous_value:
                report[resource][stat] = value - previous_value

    return report


async def report():
    bot = Bot(token=config("TELEGRAM_API_TOKEN"))
    report = compare_reports()

    # Consider only reviewed and words translated statistics
    for resource in report:
        report[resource] = {
            k: v
            for k, v in report[resource].items()
            if k in ["reviewed", "translated_words"]
        }

    if not report:
        logger.warning("Nothing to report!")
        return

    message = "📈 *Estastísticas da tradução*\nPeríodo: 7 dias\n\n"

    for resource, stats in sorted(report.items()):
        if not stats:
            continue

        message += f"*{resource}*\n"
        for stat, value in stats.items():
            stat_message = STATS_MESSAGES.get(stat)
            if not stat_message:
                continue
            message += stat_message.format(value)

    users = config(
        "BROADCAST_REPORT_TO", cast=lambda v: [s.strip() for s in v.split(",")]
    )

    await asyncio.gather(
        *[bot.send_message(user, message, parse_mode="Markdown") for user in users]
    )


def main():
    run_daily_stats()
    schedule.every().sunday.at("18:00").do(asyncio.run(report()))
    schedule.every().day.at("23:59").do(run_daily_stats).run()
    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    main()
