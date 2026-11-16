"""Source IDP Mode2 start command switches caption and dispatch."""
import pytest
from ..core.original_start_workbench import source_measure_button_caption


def test_source_connect_and_disconnect_caption_keys():
    assert source_measure_button_caption(False)==("Измерение","bTaskConnect")
    assert source_measure_button_caption(True)==("Отключить","bTaskConnectOff")


@pytest.mark.parametrize("invalid",(1,0,None,"true","false"))
def test_source_mode2_requires_boolean_input(invalid):
    with pytest.raises(ValueError):
        source_measure_button_caption(invalid)
