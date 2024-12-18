# Blazeio/Modules/safeguards
from ..Dependencies import Err, p
from asyncio import sleep

class SafeGuards:
    @classmethod
    async def is_alive(app, r):
        #if r.response.get_write_buffer_size() > 1024: await sleep(0.01)
        
        print(r.__is_alive__)
        
        if not r.__is_alive__: raise Err("Client has disconnected. Skipping write.")
            
        #if not "read=polling" in str(r.response): raise Err("Client has disconnected. Skipping write.")
        
        return True


if __name__ == "__main__":
    pass
