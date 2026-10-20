"""Normalize complete calls, never streaming deltas. No provider credentials needed."""
import json
from .core import Action, Blocked, canonical


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON argument key')
        result[key] = value
    return result


def _arguments(value):
    if not isinstance(value, str):
        raise ValueError('Expected complete JSON argument string')
    result = json.loads(value, object_pairs_hook=_object)
    canonical(result)
    return result


def normalize(provider: str, call: dict, *, call_id=None) -> Action:
    """Input is one completed tool call, not the whole model response.

    Gemini callers supply a stable host-generated id for older calls without ids.
    """
    if not isinstance(call, dict):
        raise ValueError('Expected a tool-call object')
    try:
        if provider == 'openai_responses':
            if call.get('type') != 'function_call' or call.get('status', 'completed') != 'completed':
                raise ValueError('Expected a completed function_call')
            return Action(call['call_id'], call['name'], _arguments(call['arguments']))
        if provider == 'openai_chat':
            if call.get('type') != 'function':
                raise ValueError('Expected a function tool call')
            return Action(call['id'], call['function']['name'], _arguments(call['function']['arguments']))
        if provider == 'anthropic':
            if call.get('type') != 'tool_use':
                raise ValueError('Expected a tool_use content block')
            return Action(call['id'], call['name'], call['input'])
        if provider == 'gemini':
            function = call['functionCall']
            if not isinstance(function, dict):
                raise ValueError('Malformed tool call')
            return Action(function.get('id') or call_id, function['name'], function.get('args', {}))
        if provider == 'mcp':
            if call.get('method') != 'tools/call':
                raise ValueError('Expected MCP tools/call request')
            identity = call.get('id')
            if type(identity) not in (int, str) or identity == '':
                raise ValueError('MCP request id is required')
            return Action(str(identity), call['params']['name'], call['params'].get('arguments', {}))
    except (KeyError, TypeError) as exc:
        raise ValueError('Malformed tool call') from exc
    raise ValueError('Unsupported provider format')


def feedback(provider: str, action: Action, result):
    """Format tool feedback; preserve the provider's original surrounding transcript."""
    error = isinstance(result, Blocked)
    value = result.tool_result() if error else result
    text = canonical(value)
    if provider == 'openai_responses':
        return {'type': 'function_call_output', 'call_id': action.id, 'output': text}
    if provider == 'openai_chat':
        return {'role': 'tool', 'tool_call_id': action.id, 'content': text}
    if provider == 'anthropic':
        return {'type': 'tool_result', 'tool_use_id': action.id, 'content': text, 'is_error': error}
    if provider == 'gemini':
        return {'functionResponse': {'id': action.id, 'name': action.tool,
                                    'response': {'error' if error else 'result': value}}}
    if provider == 'mcp':
        # A CallToolResult, not a JSON-RPC envelope (host preserves original id type).
        return {'content': [{'type': 'text', 'text': text}], 'isError': error}
    raise ValueError('Unsupported provider format')
