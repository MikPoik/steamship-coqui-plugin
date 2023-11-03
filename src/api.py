"""Generator plugin for Stable Diffusion running on replicate.com."""
import logging
import time
import uuid
from typing import Iterator, Type

import requests
from pydantic import Field
from steamship import Block, File, MimeTypes, Steamship, SteamshipError
from steamship.data.workspace import SignedUrl
from steamship.invocable import Config, InvocableResponse
from steamship.plugin.inputs.raw_block_and_tag_plugin_input import RawBlockAndTagPluginInput
from steamship.plugin.inputs.raw_block_and_tag_plugin_input_with_preallocated_blocks import (
    RawBlockAndTagPluginInputWithPreallocatedBlocks, )
from steamship.plugin.outputs.block_type_plugin_output import BlockTypePluginOutput
from steamship.plugin.outputs.plugin_output import OperationType, OperationUnit
from steamship.plugin.outputs.stream_complete_plugin_output import StreamCompletePluginOutput
from steamship.plugin.request import PluginRequest
from steamship.plugin.streaming_generator import StreamingGenerator
from steamship.utils.signed_urls import upload_to_signed_url
from steamship.invocable import InvocationContext

# Example Voices


def save_audio(client: Steamship, plugin_instance_id: str,
               audio: bytes) -> str:

    # generate a UUID and convert it to a string
    uuid_str = str(uuid.uuid4())
    filename = f"{uuid_str}.mp4"

    if plugin_instance_id is None:
        raise SteamshipError(
            message=
            "Empty plugin_instance_id was provided; unable to save audio file."
        )

    filepath = f"{plugin_instance_id}/{filename}"

    logging.info(f"CoquiGenerator:save_audio - filename={filename}")

    if bytes is None:
        raise SteamshipError(message="Empty bytes returned.")

    workspace = client.get_workspace()

    signed_url_resp = workspace.create_signed_url(
        SignedUrl.Request(
            bucket=SignedUrl.Bucket.PLUGIN_DATA,
            filepath=filepath,
            operation=SignedUrl.Operation.WRITE,
        ))

    if not signed_url_resp:
        raise SteamshipError(
            message=
            "Empty result on Signed URL request while uploading model checkpoint"
        )
    if not signed_url_resp.signed_url:
        raise SteamshipError(
            message=
            "Empty signedUrl on Signed URL request while uploading model checkpoint"
        )

    upload_to_signed_url(signed_url_resp.signed_url, _bytes=audio)

    get_url_resp = workspace.create_signed_url(
        SignedUrl.Request(
            bucket=SignedUrl.Bucket.PLUGIN_DATA,
            filepath=filepath,
            operation=SignedUrl.Operation.READ,
        ))

    if not get_url_resp:
        raise SteamshipError(
            message=
            "Empty result on Download Signed URL request while uploading model checkpoint"
        )
    if not get_url_resp.signed_url:
        raise SteamshipError(
            message=
            "Empty signedUrl on Download Signed URL request while uploading model checkpoint"
        )

    return get_url_resp.signed_url


class CoquiPluginConfig(Config):

    coqui_api_key: str = Field(
        "",
        description="API key to use for Coqui. ")
    voice_id: str = Field("f05c5b91-7540-4b26-b534-e820d43065d1",
                          description="Voice ID to use. Defaults to Gracie")
    speed: float = Field(1.0, description="voice speed")
    language: str = Field("en", description="languages: en,de,fr,es,it,pt,pl")


def generate_audio_stream(input_text: str,
                          config: CoquiPluginConfig) -> Iterator[bytes]:
    data = {
        "voice_id": config.voice_id,
        "text": input_text,
        "language": config.language,
        "speed": config.speed
    }

    headers = {
        "Authorization": f"Bearer {config.coqui_api_key}",
        'accept': 'audio/wav',
    }

    url = f"https://app.coqui.ai/api/v2/samples/xtts"
    #logging.debug(f"Making request to {url}")

    response = requests.post(url, json=data, headers=headers, stream=True)

    if response.status_code == 200:
        return response.iter_content(chunk_size=1000)
    else:
        raise SteamshipError(
            f"Received status code {response.status_code} from Coqui. Reason: {response.reason}. Message: {response.text}"
        )


class CoquiPlugin(StreamingGenerator):

    config: CoquiPluginConfig

    @classmethod
    def config_cls(cls) -> Type[Config]:

        return CoquiPluginConfig

    def determine_output_block_types(
        self, request: PluginRequest[RawBlockAndTagPluginInput]
    ) -> InvocableResponse[BlockTypePluginOutput]:

        result = [MimeTypes.MP3.value]
        return InvocableResponse(data=BlockTypePluginOutput(
            block_types_to_create=result))

    def stream_into_block(self, text: str, block: Block):

        audit_url = f"{self.client.config.api_base}block/{block.id}/raw"

        # Begin Streaming

        start_time = time.time()
        _stream = generate_audio_stream(text, self.config)
        #logging.info(f"Streaming audio into {audit_url}")
        for chunk in _stream:
            try:
                block.append_stream(bytes=chunk)
            except Exception as e:
                logging.error(f"Exception: {e}")
                raise e

        block.finish_stream()
        logging.info(f"Called finish_stream on {audit_url}.")

        end_time = time.time()

        # Some light logging

        elapsed_time = end_time - start_time
        logging.info(
            f"Completed audio stream of {audit_url} in f{elapsed_time}")

    def run(
        self,
        request: PluginRequest[RawBlockAndTagPluginInputWithPreallocatedBlocks]
    ) -> InvocableResponse[StreamCompletePluginOutput]:

        if not self.config.voice_id:
            raise SteamshipError(message="Must provide an  voice_id")

        if not self.context.invocable_instance_handle:
            raise SteamshipError(
                message=
                "Empty invocable_instance_handle was provided; unable to save audio file."
            )

        if not request.data.output_blocks:
            raise SteamshipError(
                message=
                "Empty output blocks structure was provided. Need at least one to stream into."
            )

        if len(request.data.output_blocks) > 1:
            raise SteamshipError(
                message=
                "More than one output block provided. This plugin assumes only one output block."
            )

        input_blocks = request.data.blocks
        output_blocks = request.data.output_blocks

        input_text = " ".join(
            [block.text for block in input_blocks if block.text is not None])
        output_block = output_blocks[0]

        self.stream_into_block(input_text, output_block)

        return InvocableResponse(data=StreamCompletePluginOutput(), )


#if __name__ == "__main__":
#    client = Steamship(workspace="coqui-dev-ws")
#    plugin = CoquiPlugin(
#        client, None, InvocationContext(invocable_instance_handle="coquitest"))

#    text = "Hi there, how are you?"
#    f = File.create(client)
#    output_block = Block.create(client,
#                                file_id=f.id,
#                                streaming=True,
#                                public_data=True,
#                                mime_type=MimeTypes.WAV)

#   req = PluginRequest(data=RawBlockAndTagPluginInputWithPreallocatedBlocks(
#        blocks=[Block(text=text)], output_blocks=[output_block]))

#    resp = plugin.run(req)
#    print(str(resp))
#    print(f"{client.config.api_base}block/{output_block.id}/raw")
