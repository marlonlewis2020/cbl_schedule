import os


api_key = "723b6f9d210e9a1009bfaf0fe6a6b8ef411798da"
if not api_key:
    raise RuntimeError("Set BAMBOOHR_API_KEY before posting schedules.")

KEY = f"{api_key}:x"