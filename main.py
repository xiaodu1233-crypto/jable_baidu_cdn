import asyncio
# from redis.asyncio import Redis
import subprocess

async def main():
    # url = 'rediss://default:ASLRAAImcDFlZDM0YzQ3NTUxNTI0MjliYmVjNGFiYjBmZTExNzA2MXAxODkxMw@balanced-hagfish-8913.upstash.io:6379'
    # redis = Redis.from_url(url, decode_responses=True)
    # urls = await redis.srandmember('m3u8_urls', 1)
    res = subprocess.run(['N_m3u8DL-RE', 'https://gmas-clena.mushroomtrack.com/hls/Lu2ofmnUsErNx6I8yzdGug/1767970860/35000/35390/35390.m3u8'], encoding='utf-8')
    print(res)
    pass

if __name__ == "__main__":


    asyncio.run(main())