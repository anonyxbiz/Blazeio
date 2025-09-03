import Blazeio as io

class Asynctemplate:
    def __init__(app):
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
            instruction_maps = io.ddict(stream_file = app.stream_file),
            encoder_maps = io.ddict(strip_newlines = app.strip_newlines_encoder)
        )

    def strip_newlines_encoder(app, value: str):
        return value.replace('\n', ' ')

    def content_from_instruction(app, r: io.BlazeioProtocol, metadata: io.ddict, instruction: (None, str)):
        if not instruction or (idx := instruction.find(app.templatify_frames.instructions.content.start)) == -1 or (ide := instruction.find(app.templatify_frames.instructions.content.end)) == -1: return

        if (instruction_map := app.maps.instruction_maps.get(instruction[:idx])):
            return instruction_map(r, metadata, instruction[idx+len(app.templatify_frames.instructions.content.start):ide])

    def encoder_from_instruction(app, instruction: (None, str)):
        if not instruction or (idx := instruction.find(app.templatify_frames.instructions.encoder.start)) == -1 or (ide := instruction.find(app.templatify_frames.instructions.encoder.end)) == -1: return

        if (encoding_map := app.maps.encoder_maps.get(instruction[idx+len(app.templatify_frames.instructions.encoder.start):ide])):
            return encoding_map

    async def stream_file(app, r: io.BlazeioProtocol, metadata: io.ddict, file: str):
        if not io.path.exists(path := io.path.join(app.static_path, file)): return

        async with io.async_open(path, "rb") as f:
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