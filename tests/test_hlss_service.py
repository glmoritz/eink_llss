from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from hlss_service import HLSSService


def test_callbacks_append_api_prefix_when_missing():
    service = HLSSService(
        llss_base_url="https://eink.tutu.eng.br",
        hlss_base_url="https://hlss.example/api",
    )

    callbacks = service._get_callbacks("inst_123")

    assert callbacks.frames == "https://eink.tutu.eng.br/api/instances/inst_123/frames"
    assert callbacks.inputs == "https://eink.tutu.eng.br/api/instances/inst_123/inputs"
    assert callbacks.notify == "https://eink.tutu.eng.br/api/instances/inst_123/notify"


def test_callbacks_do_not_duplicate_api_prefix():
    service = HLSSService(
        llss_base_url="https://eink.tutu.eng.br/api",
        hlss_base_url="https://hlss.example/api",
    )

    callbacks = service._get_callbacks("inst_123")

    assert callbacks.frames == "https://eink.tutu.eng.br/api/instances/inst_123/frames"
    assert callbacks.inputs == "https://eink.tutu.eng.br/api/instances/inst_123/inputs"
    assert callbacks.notify == "https://eink.tutu.eng.br/api/instances/inst_123/notify"
