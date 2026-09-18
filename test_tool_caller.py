from perception.tool_caller import ToolCaller

def get_time() -> str:
    from datetime import datetime
    return datetime.now().isoformat()

def add_numbers(a: int, b: int) -> int:
    return a + b

caller = ToolCaller()
caller.register_tool(
    "get_time", "Get current time",
    {"type": "object", "properties": {}},
    get_time
)
caller.register_tool(
    "add_numbers", "Add two numbers",
    {"type": "object", "properties": {
        "a": {"type": "integer"},
        "b": {"type": "integer"}
    }, "required": ["a", "b"]},
    add_numbers
)

print(caller.think("What time is it?"))
print(caller.think("What is 42 + 58?"))
