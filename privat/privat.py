import asyncio
import logging
import sys
from datetime import datetime, timedelta
import aiohttp


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
            result [date] [currency] = {
                'sale': exchange_rates.get(currency, {}).get('saleRate', 'N/A'),
                'purchase': exchange_rates.get(currency, {}).get('purchaseRate', 'N/A')
            }
        return result
    

async def main():
    if len(sys.argv) < 3:
        print("Usage: py privat.py <number_of_days> <currencies>")
        return
    
    try:
        days = int(sys.argv[1])
        if days < 1 or days > 10:
            print("Please enter a number between 1 and 10.")
            return
    except ValueError:
        print("Please provide a valid number.")
        return
    
    currencies = [currency.upper() for currency in sys.argv[2:]]
    client = ExchangeRateClient()
    rates = await client.get_exchange_for_days(days, currencies)
    print(rates)
    

if __name__ == "__main__":
    asyncio.run(main())
