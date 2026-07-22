import json
import anthropic

client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env


def run_agent(system, user_msg, tools, impls, model="claude-sonnet-4-6", max_turns=6):
    messages = [{"role": "user", "content": user_msg}]
    for _ in range(max_turns):
        resp = client.messages.create(
            model=model, max_tokens=2000,
            system=system, tools=tools, messages=messages,
        )
        if resp.stop_reason != "tool_use":
            return resp
        messages.append({"role": "assistant", "content": resp.content})
        results = []
        for block in resp.content:
            if block.type == "tool_use":
                out = impls[block.name](**block.input)
                results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(out),
                })
        messages.append({"role": "user", "content": results})
    raise RuntimeError("agent exceeded max_turns")
