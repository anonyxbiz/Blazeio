from . import Session
from time import perf_counter
from asyncio import run, sleep, gather, create_task

p = print

class Test:
    async def test(app, url="http://example.com"):
        try:
            async with Session(url) as r:
                async for data in r.get_data():
                    #p(data)
                    p("\n\n")
                    
                return r.response_headers

        except Exception as e:
            p("Test Exception: " + str(e))
            
    async def main(app):
        urls = ["https://example.com", "https://www.google.com", "https://ipify.org", "https://youtube.com"]
        queue = []
        
        start = perf_counter()

        for url in urls:
            task = create_task(app.test(url))
            queue.append(task)
            await sleep(0)

        result = await gather(*queue)
        p(result)
        
        p(f"Duration: {perf_counter() - start:.4f} seconds")
        
     
if __name__ == "__main__":
    #run(Test().test())
    run(Test().main())
    