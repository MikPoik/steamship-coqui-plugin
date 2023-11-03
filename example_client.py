from steamship import Block, File, MimeTypes, Steamship, Task
from time import sleep


def main():
    client = Steamship(workspace="coqui-dev-ws")

    generator = client.use_plugin("coqui-tts",
                                  config={
                                      "coqui_api_key": "",
                                      "voice_id":
                                      "c791b5b5-0558-42b8-bb0b-602ac5efc0b9",
                                      "speed": 1.2
                                  },
                                  version="0.0.4")

    text = "Here's a selfie of me! I hope you like it! "
    task = generator.generate(
        text=text,
        append_output_to_file=True,
        make_output_public=True,
    )

    task.wait()
    url = f"https://api.steamship.com/api/v1/block/{task.output.blocks[0].id}/raw"

    print(url)
    return task.output.blocks


if __name__ == "__main__":
    main()
