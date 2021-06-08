#!/usr/bin/python

import aiohttp
import asyncio
import pickle

from bs4 import BeautifulSoup
from dataclasses import dataclass
from typing import Optional

# Discord webhook URL
WEBHOOK_URLS = [""]
PIZZA = [
    "http://ispizzahalfprice.com/baltimore",
    "http://ispizzahalfprice.com/chicago",
    "http://ispizzahalfprice.com/dfw",
    "http://ispizzahalfprice.com/miami",
    "http://ispizzahalfprice.com/nyc",
    "http://ispizzahalfprice.com/philly",
    "http://ispizzahalfprice.com/dc",
]


class Persist:
    def __init__(self, filename: str):
        self._filename = filename
        try:
            open(filename, "xb")
        except FileExistsError:
            pass

    def read(self):
        with open(self._filename, "rb") as file:
            try:
                obj = pickle.load(file)
            except EOFError:
                obj = None
        return obj

    def write(self, obj):
        with open(self._filename, "wb") as file:
            pickle.dump(obj, file)


@dataclass(frozen=True)
class Pizza:
    state: str
    sale: bool
    url: str
    coupon_code: Optional[str]


async def fetch(session: aiohttp.ClientSession, url: str) -> Optional[str]:
    async with session.get(url) as response:
        if response.status == 200:
            return await response.text()
        else:
            raise RuntimeError(f"{response.status}: no pizza")


def pizza_parse(html: str, url: str) -> Pizza:
    soup = BeautifulSoup(html, "html.parser")
    state = soup.find(class_="btn").text.strip()
    verdict = soup.find(class_="verdict").find("p")
    sale = "yes" in verdict.text.lower()
    if sale:
        coupon_code = verdict.find("strong").text
    else:
        coupon_code = None
    return Pizza(state=state, sale=sale, url=url, coupon_code=coupon_code)


async def get_pizza(session: aiohttp.ClientSession, url: str) -> Pizza:
    html = None
    retry_count = 0
    while not html:
        try:
            html = await fetch(session, url)
        except RuntimeError as e:
            if retry_count >= 20:
                raise e
            await asyncio.sleep(60)
    return pizza_parse(html, url)


async def send_pizzas(session: aiohttp.ClientSession, pizzas: [Pizza]) -> None:
    embeds = []
    for pizza in pizzas:
        if pizza.sale:
            title = f"Pizza is on sale in {pizza.state.title()}"
            description = f"Coupon Code: {pizza.coupon_code}"
            color = "3468084"
        else:
            title = f"Pizza is no longer on sale in {pizza.state.title()}"
            description = ""
            color = "15414324"
        e = {
            "title": title,
            "description": description,
            "color": color,
            "url": pizza.url,
        }
        embeds.append(e)
    content = {
        "content": "",
        "embeds": embeds,
    }
    for url in WEBHOOK_URLS:
        await session.post(url, json=content)
        await asyncio.sleep(1)


async def main():
    persist = Persist("pizzas.dat")
    old_pizzas = persist.read()
    if not old_pizzas:
        old_pizzas = []
    async with aiohttp.ClientSession() as session:
        coros = [get_pizza(session, url) for url in PIZZA]
        new_pizzas = await asyncio.gather(*coros)
        changed_pizzas = list(set(old_pizzas) ^ set(new_pizzas))
        if changed_pizzas:
            await send_pizzas(session, changed_pizzas)
            persist.write(new_pizzas)


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
