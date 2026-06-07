"""Start the Telegram bot with long-polling."""
from bot.bot import build_app

if __name__ == "__main__":
    app = build_app()
    print("[bot] Polling started. Send /start or /auto_start in Telegram.")
    app.run_polling(drop_pending_updates=True)
