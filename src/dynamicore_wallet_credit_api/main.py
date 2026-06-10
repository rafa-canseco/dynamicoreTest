import uvicorn

from dynamicore_wallet_credit_api.app import create_app

app = create_app()


def run() -> None:
    uvicorn.run(
        "dynamicore_wallet_credit_api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
