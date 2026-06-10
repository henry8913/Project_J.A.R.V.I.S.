from pathlib import Path

from jarvis_bot.attachments import prepare_agent_input
from jarvis_bot.schemas import Attachment, AttachmentType, IncomingMessage


def test_prepare_agent_input_for_csv_without_text(tmp_path: Path) -> None:
    csv_path = tmp_path / "sales.csv"
    csv_path.write_text("mese,valore\ngennaio,10\nfebbraio,20\nmarzo,15\n", encoding="utf-8")

    message = IncomingMessage(
        chat_id=1,
        user_id=123456789,
        attachments=[Attachment(kind=AttachmentType.CSV, local_path=csv_path)],
    )

    prepared = prepare_agent_input(message)

    assert "Analizza il CSV allegato" in prepared.prompt
    assert prepared.csv_paths == [csv_path]
    assert prepared.histogram_data
    assert prepared.infographic_descriptions
