from comptext_conductor_max.antigravity import parse_stream_json


def test_parse_stream_json_uses_terminal_result_usage_without_double_counting():
    stream = "\n".join(
        [
            '{"event":"init","conversation_id":"c1","init":{"cwd":"/repo","tools":[],"permission_mode":"request-review"}}',
            '{"event":"step_update","step_update":{"conversation_id":"c1","step_index":1,"state":"DONE","step_type":"agent_response","usage":{"input_tokens":100,"output_tokens":20,"thinking_tokens":10,"cache_read_tokens":50,"total_tokens":120}}}',
            '{"event":"result","result":{"conversation_id":"c1","status":"SUCCESS","duration_seconds":2.5,"num_turns":1,"usage":{"input_tokens":110,"output_tokens":22,"thinking_tokens":10,"cache_read_tokens":50,"total_tokens":132}}}',
        ]
    )
    parsed = parse_stream_json(stream)
    assert parsed.status == "SUCCESS"
    assert parsed.input_tokens == 110
    assert parsed.output_tokens == 22
    assert parsed.thinking_tokens == 10
    assert parsed.cache_read_tokens == 50
    assert parsed.total_tokens == 132
    assert parsed.conversation_id == "c1"


def test_parse_stream_json_rejects_missing_terminal_result():
    try:
        parse_stream_json('{"event":"init","conversation_id":"c1","init":{}}')
    except ValueError as exc:
        assert "terminal result" in str(exc)
    else:
        raise AssertionError("missing result event must be rejected")
