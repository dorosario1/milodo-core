SKILL_NAME = "example_skill"
SKILL_DESCRIPTION = "Minimal example skill for MILODO dynamic loading."


def run(input_data=None):
    print("Example skill executed")
    return {
        "success": True,
        "message": "Example skill executed",
        "input": input_data,
    }
