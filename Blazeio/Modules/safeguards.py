# Blazeio/Modules/safeguards
from ..Dependencies import Err, p

class SafeGuards:
    @classmethod
    async def is_alive(app, r):
        if r.exploited:
            raise Err("Client has disconnected. Skipping write.")
            
        #if not "read=polling" in str(r.response):
            #raise Err("Client has disconnected. Skipping write.")
        else:
            return True


if __name__ == "__main__":
    pass
