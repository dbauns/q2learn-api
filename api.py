from fastapi import FastAPI

app = FastAPI(
    title="Q2Learn API",
    version="1.0.0"
)

@app.get("/")
def root():
    return {
        "message": "Q2Learn API is running"
    }
