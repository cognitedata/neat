import webbrowser
from pathlib import Path

import uvicorn
from fastapi import FastAPI

app = FastAPI()


def run():
    (Path.cwd() / "data").mkdir(parents=True, exist_ok=True)
    webbrowser.open("http://localhost:8000/")
    uvicorn.run("cognite.neat.app.api.explorer:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    run()
