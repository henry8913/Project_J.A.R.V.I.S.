from __future__ import annotations

import asyncio
import logging
import mimetypes
from pathlib import Path
from uuid import uuid4

from aiogram import Bot, Dispatcher, F
from aiogram.types import FSInputFile, Message

from .agent import ArtifactQueue, JarvisAgentRunner
from .config import Settings
from .schemas import Attachment, AttachmentType, IncomingMessage, PendingArtifact

LOGGER = logging.getLogger(__name__)
TELEGRAM_MESSAGE_LIMIT = 4096


class JarvisTelegramService:
    def __init__(self, settings: Settings, agent_runner: JarvisAgentRunner | None = None) -> None:
        self.settings = settings
        self.agent_runner = agent_runner or JarvisAgentRunner(settings)
        self.bot = Bot(token=settings.telegram_bot_token)
        self.dispatcher = Dispatcher()
        self._register_handlers()

    def _register_handlers(self) -> None:
        self.dispatcher.message.register(self.handle_voice, F.voice)
        self.dispatcher.message.register(self.handle_audio, F.audio)
        self.dispatcher.message.register(self.handle_photo, F.photo)
        self.dispatcher.message.register(self.handle_document, F.document)
        self.dispatcher.message.register(self.handle_text, F.text)

    def is_allowed_user(self, user_id: int | None) -> bool:
        return bool(user_id and user_id == self.settings.telegram_allowed_user_id)

    async def run_polling(self) -> None:
        self.settings.ensure_directories()
        await self.dispatcher.start_polling(self.bot, allowed_updates=["message"])

    async def handle_text(self, message: Message) -> None:
        await self._process_message(message)

    async def handle_voice(self, message: Message) -> None:
        voice = message.voice
        if voice is None:
            return
        attachment = await self._download_attachment(
            file_id=voice.file_id,
            desired_name=f"voice-{message.message_id}.ogg",
            kind=AttachmentType.AUDIO,
            mime_type="audio/ogg",
        )
        await self._process_message(message, attachments=[attachment])

    async def handle_audio(self, message: Message) -> None:
        audio = message.audio
        if audio is None:
            return
        suffix = Path(audio.file_name or "audio.mp3").suffix or ".mp3"
        attachment = await self._download_attachment(
            file_id=audio.file_id,
            desired_name=f"audio-{message.message_id}{suffix}",
            kind=AttachmentType.AUDIO,
            mime_type=audio.mime_type,
            original_name=audio.file_name,
        )
        await self._process_message(message, attachments=[attachment])

    async def handle_photo(self, message: Message) -> None:
        if not message.photo:
            return
        photo = message.photo[-1]
        attachment = await self._download_attachment(
            file_id=photo.file_id,
            desired_name=f"photo-{message.message_id}.jpg",
            kind=AttachmentType.IMAGE,
            mime_type="image/jpeg",
        )
        await self._process_message(message, attachments=[attachment])

    async def handle_document(self, message: Message) -> None:
        document = message.document
        if document is None:
            return
        kind = self._document_kind(document.file_name or "", document.mime_type)
        suffix = Path(document.file_name or "document.bin").suffix or ".bin"
        attachment = await self._download_attachment(
            file_id=document.file_id,
            desired_name=f"document-{message.message_id}{suffix}",
            kind=kind,
            mime_type=document.mime_type,
            original_name=document.file_name,
        )
        await self._process_message(message, attachments=[attachment])

    async def _process_message(self, message: Message, attachments: list[Attachment] | None = None) -> None:
        user = message.from_user
        if not self.is_allowed_user(user.id if user else None):
            LOGGER.info("Rejected telegram user %s", getattr(user, "id", None))
            return

        incoming = IncomingMessage(
            chat_id=message.chat.id,
            user_id=user.id,
            text=self._extract_user_text(message),
            attachments=attachments or [],
        )

        for attachment in incoming.attachments:
            if attachment.kind is AttachmentType.AUDIO:
                transcript = await asyncio.to_thread(self.agent_runner.transcribe_audio, attachment.local_path)
                incoming.audio_transcript = transcript
                await self._reply_chunks(message, f"Trascrizione audio:\n\n{transcript}")
                break

        artifact_queue = ArtifactQueue(self.settings.output_path, self.settings.reports_path)
        reply_text = await asyncio.to_thread(self.agent_runner.run, incoming, artifact_queue)
        await self._reply_chunks(message, reply_text)
        await self._deliver_artifacts(message.chat.id, artifact_queue.items)

    def _extract_user_text(self, message: Message) -> str:
        return (message.text or message.caption or "").strip()

    def _document_kind(self, file_name: str, mime_type: str | None) -> AttachmentType:
        lowered = file_name.lower()
        mime = (mime_type or "").lower()
        if lowered.endswith(".pdf") or mime == "application/pdf":
            return AttachmentType.PDF
        if lowered.endswith(".csv") or mime == "text/csv":
            return AttachmentType.CSV
        guessed_mime, _ = mimetypes.guess_type(file_name)
        if (guessed_mime or mime).startswith("image/"):
            return AttachmentType.IMAGE
        return AttachmentType.DOCUMENT

    async def _download_attachment(
        self,
        file_id: str,
        desired_name: str,
        kind: AttachmentType,
        mime_type: str | None = None,
        original_name: str | None = None,
    ) -> Attachment:
        telegram_file = await self.bot.get_file(file_id)
        safe_name = f"{uuid4().hex}-{desired_name}"
        target_path = self.settings.incoming_path / safe_name
        await self.bot.download_file(telegram_file.file_path, destination=target_path)
        return Attachment(
            kind=kind,
            local_path=target_path,
            mime_type=mime_type,
            original_name=original_name,
        )

    async def _reply_chunks(self, message: Message, text: str) -> None:
        clean = text.strip() or "Operazione completata."
        for start in range(0, len(clean), TELEGRAM_MESSAGE_LIMIT):
            await message.answer(clean[start : start + TELEGRAM_MESSAGE_LIMIT])

    async def _deliver_artifacts(self, chat_id: int, artifacts: list[PendingArtifact]) -> None:
        for artifact in artifacts:
            suffix = artifact.local_path.suffix.lower()
            input_file = FSInputFile(str(artifact.local_path))
            caption = artifact.caption[:1024]
            if suffix in {".png", ".jpg", ".jpeg", ".webp"}:
                await self.bot.send_photo(chat_id=chat_id, photo=input_file, caption=caption)
            elif suffix in {".mp3", ".wav", ".ogg", ".m4a"}:
                await self.bot.send_audio(chat_id=chat_id, audio=input_file, caption=caption)
            else:
                await self.bot.send_document(chat_id=chat_id, document=input_file, caption=caption)
