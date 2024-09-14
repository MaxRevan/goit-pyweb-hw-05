import asyncio
import logging
import sys
from datetime import datetime, timedelta
import aiofile
from aiopath import AsyncPath
import aiohttp
import websockets
import names
from websockets import WebSocketServerProtocol
from websockets.exceptions import ConnectionClosedOK


logging.basicConfig(level=logging.INFO)


class ExchangeRateClient:
    BASE_URL = "https://api.privatbank.ua/p24api/exchange_rates?json&date="

    async def request(self, date: str) -> dict:
        
        async with aiohttp.ClientSession() as session:
            url = f"{self.BASE_URL}{date}"
            try:
                async with session.get(url) as response:
                    if response.status == 200:
                        return await response.json()
                    logging.error(f"Error status: {response.status} for {url}")
                    return {}
            except aiohttp.ClientConnectorError as err:
                logging.error(f"Connection error: {str(err)}")
                return {}

    async def get_exchange_for_days(self, days: int, currencies: list):
        
        results = []
        today = datetime.now()
        for i in range(days):
            date = (today - timedelta(days=i)).strftime("%d.%m.%Y")
            data = await self.request(date)
            if data:
                results.append(self.get_exchange(data, currencies))
        return results

    def get_exchange(self, data: dict, currencies: list) -> dict:
        
        date = data.get("date", "N/A")
        exchange_rates = {rate['currency']: rate for rate in data.get('exchangeRate', [])}
        result = {date: {}}
        for currency in currencies:
            result[date][currency] = {
                'sale': exchange_rates.get(currency, {}).get('saleRate', 'N/A'),
                'purchase': exchange_rates.get(currency, {}).get('purchaseRate', 'N/A')
            }
        return result


class Server:
    clients = set()
    exchange_client = ExchangeRateClient()

    async def register(self, ws: WebSocketServerProtocol):
        ws.name = names.get_full_name()
        self.clients.add(ws)
        logging.info(f'{ws.remote_address} connects')

    async def unregister(self, ws: WebSocketServerProtocol):
        self.clients.remove(ws)
        logging.info(f'{ws.remote_address} disconnects')

    async def send_to_clients(self, message: str):
        if self.clients:
            [await client.send(message) for client in self.clients]

    async def ws_handler(self, ws: WebSocketServerProtocol):
        await self.register(ws)
        try:
            await self.distribute(ws)
        except ConnectionClosedOK:
            pass
        finally:
            await self.unregister(ws)

    async def log_exchange_command(self, ws_name, message):
        log_file = AsyncPath("exchange_log.txt")
        async with aiofile.AIOFile(log_file, 'a') as afp:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_message = f"[{timestamp}] {ws_name}: {message}\n"
            writer = aiofile.Writer(afp)
            await writer(log_message)

    async def distribute(self, ws: WebSocketServerProtocol):
        async for message in ws:
            if message.startswith("exchange"):
                try:
                    parts = message.split()
                    days = 1
                    currencies = ["USD"]
                    if len(parts) > 1:
                        try:
                            days = int(parts[1])
                            if days < 1:
                                days = 1
                        except ValueError:
                            pass
                    if len(parts) > 2:
                        currencies = [currency.upper() for currency in parts[2:]] 
                    exchange_rates = await self.exchange_client.get_exchange_for_days(days, currencies)
                    formatted_rates = "\n\n".join(
                        f"{date}: \n" + "\n".join(
                            f"  {currency} - Sale: {info.get('sale', 'N/A')}, Purchase: {info.get('purchase', 'N/A')}"
                            for currency, info in rates.items()
                        )
                        for date_info in exchange_rates 
                        for date, rates in date_info.items() 
                    )
                    await self.send_to_clients(f"{ws.name}:\n{formatted_rates}\n")
                    await self.log_exchange_command(ws.name, message)
                except Exception as e:
                    await self.send_to_clients(f"Error: {str(e)}")
            else:
                await self.send_to_clients(f"{ws.name}: {message}")
    

async def main():

    server = Server()
    async with websockets.serve(server.ws_handler, 'localhost', 8081):
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
