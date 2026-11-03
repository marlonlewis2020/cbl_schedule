import os


api_key = os.environ.get("BAMBOOHR_API_KEY", "").strip()
if not api_key:
    raise RuntimeError("Set BAMBOOHR_API_KEY before posting schedules.")

KEY = f"{api_key}:x"