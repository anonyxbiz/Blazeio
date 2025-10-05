import Blazeio as io

class Map(io.ddict):
    @property
    def __name__(app):
        return "Map"

    def __call__(app, fn, *args, **kwargs):
        app[fn.__name__] = fn
        return fn

    def attach_fns(app, parent, source):
        for name in source:
            parent.maps.instruction_maps[name] = getattr(parent, name)

@io.Scope
class Asynctemplate:
    def __init__(app):
        if not hasattr(app, "static_chunk_size"):
            app.static_chunk_size = io.ioConf.INBOUND_CHUNK_SIZE
        app.templatify_frames = io.ddict(
            start = b"<!--",
            end = b"-->",
            inline_logic = io.ddict(
                instructions = io.ddict(
                    start = "(",
                    end = ")"
                )
            ),
            instructions = io.ddict(
                encoder = io.ddict(
                    start = "(::",
                    end = "::)"
                ),
                content = io.ddict(
                    start = "(",
                    end = ")"
                )
            )
        )
        app.maps = io.ddict(
            instruction_maps = Map(stream_file = app.stream_file),
            encoder_maps = Map(strip_newlines = app.strip_newlines_encoder)
        )

    def strip_newlines_encoder(app, value: str):
        return value.replace('\n', ' ')

    def content_from_instruction(app, r: io.BlazeioProtocol, metadata: io.ddict, instruction: (None, str)):
        if not instruction or (idx := instruction.find(app.templatify_frames.instructions.content.start)) == -1 or (ide := instruction.find(app.templatify_frames.instructions.content.end)) == -1: return

        if (instruction_map := app.maps.instruction_maps.get(instruction[:idx])):
            return instruction_map(r, metadata) if not (arg := instruction[idx+len(app.templatify_frames.instructions.content.start):ide]) else instruction_map(r, metadata, arg)

    def encoder_from_instruction(app, instruction: (None, str)):
        if not instruction or (idx := instruction.find(app.templatify_frames.instructions.encoder.start)) == -1 or (ide := instruction.find(app.templatify_frames.instructions.encoder.end)) == -1: return

        if (encoding_map := app.maps.encoder_maps.get(instruction[idx+len(app.templatify_frames.instructions.encoder.start):ide])):
            return encoding_map
    
    def resolve_path(app, path):
        return path

    async def stream_file(app, r: io.BlazeioProtocol, metadata: io.ddict, file: str):
        if not io.path.exists(file := app.resolve_path(file)): return

        async with io.async_open(file, "rb") as f:
            while (chunk := await f.read(app.static_chunk_size)):
                async for chunk in app.templatify(r, metadata, chunk): yield chunk

    async def templatify(app, r: io.BlazeioProtocol, metadata: io.ddict, chunk: bytes):
        while (ida := chunk.find(app.templatify_frames.start)) != -1 and (idb := chunk.find(app.templatify_frames.end)) != -1:
            var = chunk[ida + len(app.templatify_frames.start):idb].decode()
            
            if (chunk_before := chunk[:ida]): yield chunk_before

            chunk = chunk[idb + len(app.templatify_frames.end):]

            if (idx := var.find(app.templatify_frames.inline_logic.instructions.start)) != -1 and (ide := var.rfind(app.templatify_frames.inline_logic.instructions.end)) != -1:
                instruction, var = var[idx+len(app.templatify_frames.inline_logic.instructions.start):ide], var[:idx]
            else:
                instruction = None

            if not (content := app.content_from_instruction(r, metadata, instruction)):
                for source in (metadata, r.store):
                    if isinstance(source, dict) and (value := source.get(var)) is not None: break

                if value is not None:
                    if isinstance(value, dict):
                        value = [i for i in value.values() if not isinstance(i, bool)][0]

                    if (encoder := app.encoder_from_instruction(instruction)):
                        value = encoder(value)

                    if value and (value := str(value).encode()): yield value

            else:
                async for value in content:
                    if value: yield value

        if chunk: yield chunk

if __name__ == "__main__": ...