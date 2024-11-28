# Blazeio/Modules/safeguards
from ..Dependencies import Err, p

class SafeGuards:
    @classmethod
    async def is_alive(app, r):
        if not "read=polling" in str(r.response.transport):
            raise Err("Client has disconnected. Skipping write.")
        else:
            return True


if __name__ == "__main__":
    pass
