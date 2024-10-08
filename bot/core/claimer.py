import asyncio
from time import time
from dateutil import parser
from datetime import datetime, timezone
from urllib.parse import unquote

import aiohttp
from aiohttp_proxy import ProxyConnector
from better_proxy import Proxy
from pyrogram import Client
from pyrogram.errors import Unauthorized, UserDeactivated, AuthKeyUnregistered
from pyrogram.raw.functions.messages import RequestWebView

from bot.config import settings
from bot.utils import logger
from bot.exceptions import InvalidSession
from .headers import headers
import random

class Claimer:
	def __init__(self, tg_client: Client):
		self.session_name = tg_client.name
		self.tg_client = tg_client

	async def get_tg_web_data(self, proxy: str | None) -> str:
		proxy_dict = None
		self.tg_client.proxy = proxy_dict
		
		try:
			if not self.tg_client.is_connected:
				try:
					await self.tg_client.connect()
				except (Unauthorized, UserDeactivated, AuthKeyUnregistered):
					raise InvalidSession(self.session_name)
			web_view = await self.tg_client.invoke(RequestWebView(
				peer=await self.tg_client.resolve_peer('claytoncoinbot'),
				bot=await self.tg_client.resolve_peer('claytoncoinbot'),
				platform='android',
				from_bot_menu=False,
				url='https://tonclayton.fun/'
			))
			auth_url = web_view.url
			tg_web_data = unquote(
				string=auth_url.split('tgWebAppData=', maxsplit=1)[1].split('&tgWebAppVersion', maxsplit=1)[0])
			if self.tg_client.is_connected:
				await self.tg_client.disconnect()

			return tg_web_data

		except InvalidSession as error:
			raise error

		except Exception as error:
			logger.error(f"{self.session_name} | Unknown error during Authorization: {error}")
			await asyncio.sleep(delay=3)

	async def send_claim(self, http_client: aiohttp.ClientSession) -> bool:
		try:
			response = await http_client.post('https://tonclayton.fun/api/user/claim', json={})
			response.raise_for_status()
			return True
		except Exception as error:
			logger.error(f"{self.session_name} | Unknown error when Claiming: {error}")
			await asyncio.sleep(delay=3)

			return False

	async def start_farming(self, http_client: aiohttp.ClientSession) -> bool:
		await asyncio.sleep(delay=6)
		try:
			response = await http_client.post('https://tonclayton.fun/api/user/start', json={})
			response.raise_for_status()

			return True
		except Exception as error:
			logger.error(f"{self.session_name} | Unknown error when Start Farming: {error}")
			await asyncio.sleep(delay=3)

			return False

	async def check_proxy(self, http_client: aiohttp.ClientSession, proxy: Proxy) -> None:
		try:
			response = await http_client.get(url='https://httpbin.org/ip', timeout=aiohttp.ClientTimeout(5))
			ip = (await response.json()).get('origin')
			logger.info(f"{self.session_name} | Proxy IP: {ip}")
		except Exception as error:
			logger.error(f"{self.session_name} | Proxy: {proxy} | Error: {error}")

	async def get_mining_data(self, http_client: aiohttp.ClientSession) -> dict[str, str]:
		try:
			response = await http_client.post('https://tonclayton.fun/api/user/auth')
			response.raise_for_status()
			
			response_json = await response.json()
			mining_data = response_json

			return mining_data
		except Exception as error:
			logger.error(f"{self.session_name} | Unknown error when getting Profile Data: {error}")
			await asyncio.sleep(delay=3)
			return {}
	
	async def perform_game(self, http_client: aiohttp.ClientSession, multiplier: int) -> None:
		# Start a new '1024' game
		try:
			response = await http_client.post('https://tonclayton.fun/api/game/start')
			response.raise_for_status()
			logger.info(f"{self.session_name} | Game '1024' started")
		except aiohttp.ClientResponseError as e:
			logger.error(f"{self.session_name} | Error starting game: {e}")
			return
		except Exception as error:
			logger.error(f"{self.session_name} | Unknown error when starting game: {error}")
			return

		await asyncio.sleep(random.randint(2, 3))  # Sleep 2-3 seconds

		# Progress through tile values
		base_url = 'https://tonclayton.fun/api/game/save-tile'
		tile_values = [4, 8, 16, 32, 64, 128, 256, 512, 1024]
		tiles_count = len(tile_values)
		start_time = asyncio.get_event_loop().time()
		end_time = start_time + 150  # 2:30
		interval = (150 - 5) / tiles_count # сalculate interval leaving 5 seconds to the end
		try:
			i = 0
			while i < tiles_count and (asyncio.get_event_loop().time() < end_time - 5):
				payload = {"maxTile": tile_values[i]}
				response = await http_client.post(base_url, json=payload)
				response.raise_for_status()
				logger.info(f"{self.session_name} | Successfully saved tile: {tile_values[i]}")
				i += 1
				if i < tiles_count: await asyncio.sleep(interval)

			# End the game after reaching 1024
			payload = {"multiplier": multiplier}
			response = await http_client.post('https://tonclayton.fun/api/game/over', json=payload)
			response.raise_for_status()
			response_json = await response.json()
			earn = response_json.get('earn', 0)
			if earn > 0:
				logger.success(f"{self.session_name} | Game '1024' finished (+{earn} tokens)")
			else:
				logger.warning(f"{self.session_name} | Game '1024' failed")
		except aiohttp.ClientResponseError as e:
			logger.error(f"{self.session_name} | Error during game play: {e}")
			return
		except Exception as error:
			logger.error(f"{self.session_name} | Error during game play: {error}")
			return

	async def perform_stack(self, http_client: aiohttp.ClientSession, multiplier: int) -> None:
		# Start a new 'Stack' game
		try:
			response = await http_client.post('https://tonclayton.fun/api/stack/start-game')
			response.raise_for_status()
			logger.info(f"{self.session_name} | Game 'Stack' started")
		except aiohttp.ClientResponseError as e:
			logger.error(f"{self.session_name} | Error starting game: {e}")
			return
		except Exception as error:
			logger.error(f"{self.session_name} | Unknown error when starting game: {error}")
			return
		
		start_time = asyncio.get_event_loop().time()
		end_time = start_time + 120  # 2:00
		max_score = 90
		score = 0
		update_count = max_score / 10
		interval = (120 - 5) / update_count # сalculate interval leaving 5 seconds to the end
		try:
			while score < max_score and (asyncio.get_event_loop().time() < end_time - 5):
				score += 10
				payload = {"score": score}
				response = await http_client.post('https://tonclayton.fun/api/stack/update-game', json=payload)
				response.raise_for_status()
				logger.info(f"{self.session_name} | Successfully saved score: {score}")
				await asyncio.sleep(interval)
			
			score += random.randint(2, 8)
			payload = {"score": score, "multiplier": multiplier}
			response = await http_client.post('https://tonclayton.fun/api/stack/end-game', json=payload)
			response.raise_for_status()
			response_json = await response.json()
			earn = response_json.get('earn', 0)
			if earn > 0:
				logger.success(f"{self.session_name} | Game 'Stack' finished (+{earn} tokens)")
			else:
				logger.warning(f"{self.session_name} | Game 'Stack' failed")
		except aiohttp.ClientResponseError as e:
			logger.error(f"{self.session_name} | Error during game play: {e}")
			return
		except Exception as error:
			logger.error(f"{self.session_name} | Error during game play: {error}")
			return

	async def daily_reward(self, http_client: aiohttp.ClientSession) -> None:
		try:
			response = await http_client.post('https://tonclayton.fun/api/user/daily-claim')
			response.raise_for_status()
			
			response_json = await response.json()
			tokens = response_json['tokens']
			logger.success(f"{self.session_name} | Daily reward claimed (+{tokens} tokens)")
		except Exception as error:
			logger.error(f"{self.session_name} | Unknown error in daily reward: {error}")
			await asyncio.sleep(delay=3)
	
	async def perform_tasks(self, http_client: aiohttp.ClientSession) -> None:
		task_urls = ['https://tonclayton.fun/api/tasks/super-tasks', 'https://tonclayton.fun/api/tasks/partner-tasks', 'https://tonclayton.fun/api/user/okx/tickets', 'https://tonclayton.fun/api/tasks/daily-tasks', 'https://tonclayton.fun/api/tasks/default-tasks']
		url_check = 'https://tonclayton.fun/api/tasks/check'
		url_complete = 'https://tonclayton.fun/api/tasks/complete'
		url_claim = 'https://tonclayton.fun/api/tasks/claim'
		try:
			for url in task_urls:
				response = await http_client.get(url)
				response.raise_for_status()
				response_json = await response.json()
				if 'okx/tickets' in url: continue
				for task in response_json:
					if task['is_claimed']: continue
					logger.info(f"{self.session_name} | Processing task {task['task_id']}...")
					if task['task']['requires_check']:
						payload = {"task_id": task['task_id']}
						response2 = await http_client.post(url_check, json=payload)
						response2.raise_for_status()
						response2_json = await response2.json()
						if response2_json['is_completed']:
							payload = {"task_id": task['task_id']}
							response2 = await http_client.post(url_claim, json=payload)
							response2.raise_for_status()
							response2_json = await response2.json()
							if response2_json['reward_tokens']:
								logger.success(f"{self.session_name} | Task {task['task_id']} completed (+{response2_json['reward_tokens']} tokens)")
						else:
							payload = {"task_id": task['task_id']}
							response2 = await http_client.post(url_complete, json=payload)
							response2.raise_for_status()
							response2_json = await response2.json()
							if response2_json.get('message', False) and 'completed' in response2_json['message']:
								payload = {"task_id": task['task_id']}
								response2 = await http_client.post(url_claim, json=payload)
								response2.raise_for_status()
								response2_json = await response2.json()
								if response2_json['reward_tokens']:
									logger.success(f"{self.session_name} | Task {task['task_id']} completed (+{response2_json['reward_tokens']} tokens)")
						await asyncio.sleep(random.randint(12, 24))
				await asyncio.sleep(random.randint(24, 48))
		except Exception as error:
			logger.error(f"{self.session_name} | Unknown error in daily reward: {error}")
			await asyncio.sleep(delay=3)

	async def run(self, proxy: str | None) -> None:
		claim_time = 0

		proxy_conn = ProxyConnector().from_url(proxy) if proxy else None

		async with aiohttp.ClientSession(headers=headers, connector=proxy_conn) as http_client:
			while True:
				try:
					tg_web_data = await self.get_tg_web_data(proxy=proxy)
					http_client.headers["Init-Data"] = tg_web_data
					headers["Init-Data"] = tg_web_data
					mining_data = await self.get_mining_data(http_client=http_client)
					tokens = int(mining_data['user']['tokens'])
					multiplier = mining_data['user']['multiplier']
					daily_attempts = mining_data['user']['daily_attempts']
					need_daily_claim = mining_data['dailyReward']['can_claim_today']
					#active_farm = mining_data['active_farm']
					#start_time = parser.parse(mining_data['start_time'])
					#start_time = start_time.astimezone(timezone.utc)
					#current_time = datetime.now(timezone.utc)
					
					# Log current status
					logger.info(f"{self.session_name} | Balance: {tokens} | "
								f"Multiplier: {multiplier}")
					
					await asyncio.sleep(random.randint(2, 4))
					if need_daily_claim:
						logger.info(f"{self.session_name} | Daily reward available")
						await self.daily_reward(http_client=http_client)
					else:
						logger.info(f"{self.session_name} | Daily reward not available")
					
					await asyncio.sleep(random.randint(4, 8))
					await self.perform_tasks(http_client=http_client)

					await asyncio.sleep(random.randint(4, 8))
					if daily_attempts > 0:
						logger.info(f"{self.session_name} | Game attempts remaining: {daily_attempts}")
						games = ['1024', 'Stack']
						while daily_attempts > 0:
							game = random.choice(games)
							if game == '1024':
								await self.perform_game(http_client=http_client, multiplier=multiplier)
							else:
								await self.perform_stack(http_client=http_client, multiplier=multiplier)
							daily_attempts -= 1
							await asyncio.sleep(random.randint(10, 15))  # Sleep between games
						continue
					
					'''await asyncio.sleep(random.randint(2, 4))
					if not active_farm:
						logger.info(f"{self.session_name} | Farm not active. Claiming and starting farming.")
						if await self.send_claim(http_client=http_client):
							logger.success(f"{self.session_name} | Claim successful.")
						if await self.start_farming(http_client=http_client):
							logger.success(f"{self.session_name} | Farming started successfully.")
					else:
						time_elapsed = current_time - start_time
						time_to_wait = max(0, 6 * 3600 - time_elapsed.total_seconds())
						
						if time_to_wait > 0:
							hours = int(time_to_wait // 3600)
							minutes = int((time_to_wait % 3600) // 60)
							logger.info(f"{self.session_name} | Farming active. Waiting for {hours} hours and {minutes} minutes before claiming and restarting.")
							await asyncio.sleep(time_to_wait)
							continue
						
						logger.info(f"{self.session_name} | Time to claim and restart farming.")
						if await self.send_claim(http_client=http_client):
							logger.success(f"{self.session_name} | Claim successful.")
						if await self.start_farming(http_client=http_client):
							logger.success(f"{self.session_name} | Farming restarted successfully.")'''
				
				except InvalidSession as error:
					raise error
				except Exception as error:
					logger.error(f"{self.session_name} | Unknown error: {error}")
					await asyncio.sleep(delay=3)
				else:
					
					sleep_time = random.randint(3600, 10800)
					hours, minutes = divmod(sleep_time, 3600)
					minutes //= 60
					logger.info(f"{self.session_name} | Sleep {int(hours)} hours {int(minutes)} minutes")
					await asyncio.sleep(delay=sleep_time)

async def run_claimer(tg_client: Client, proxy: str | None):
	try:
		await Claimer(tg_client=tg_client).run(proxy=proxy)
	except InvalidSession:
		logger.error(f"{tg_client.name} | Invalid Session")
