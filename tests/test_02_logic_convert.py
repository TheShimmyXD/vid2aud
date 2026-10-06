from __future__ import annotations

from modules.mod_02_convert.logic._02_logic_convert import ConvertLogic, ConvertState


def _ready() -> ConvertLogic:
    logic = ConvertLogic()
    logic.select_input()
    logic.finish_probe(ok=True, has_audio=True)
    return logic


def test_starts_empty_and_cannot_convert():
    logic = ConvertLogic()
    assert logic.state is ConvertState.EMPTY
    assert not logic.can_convert
    assert not logic.start_convert()["ok"]


def test_probe_with_audio_is_ready():
    logic = _ready()
    assert logic.state is ConvertState.READY
    assert logic.can_convert


def test_probe_without_audio_is_invalid_with_reason():
    logic = ConvertLogic()
    logic.select_input()
    payload = logic.finish_probe(ok=True, has_audio=False)
    assert logic.state is ConvertState.INVALID
    assert "audio" in payload["message"]


def test_failed_probe_keeps_service_message():
    logic = ConvertLogic()
    logic.select_input()
    payload = logic.finish_probe(ok=False, has_audio=False, message="El archivo no existe.")
    assert payload["message"] == "El archivo no existe."


def test_convert_cycle_done_then_again():
    logic = _ready()
    assert logic.start_convert()["ok"]
    assert logic.is_busy
    logic.finish_convert(ok=True, message="Listo.")
    assert logic.state is ConvertState.DONE
    assert logic.start_convert()["ok"]


def test_cancel_returns_to_ready():
    logic = _ready()
    logic.start_convert()
    payload = logic.finish_convert(ok=False, cancelled=True)
    assert logic.state is ConvertState.READY
    assert payload["ok"]


def test_error_allows_retry():
    logic = _ready()
    logic.start_convert()
    logic.finish_convert(ok=False, message="fallo")
    assert logic.state is ConvertState.ERROR
    assert logic.can_convert


def test_input_is_locked_while_converting():
    logic = _ready()
    logic.start_convert()
    assert not logic.select_input()["ok"]
    assert not logic.clear()["ok"]
    assert logic.state is ConvertState.CONVERTING


def test_late_results_are_ignored():
    logic = ConvertLogic()
    assert not logic.finish_probe(ok=True, has_audio=True)["ok"]
    assert not logic.finish_convert(ok=True)["ok"]
    assert logic.state is ConvertState.EMPTY
