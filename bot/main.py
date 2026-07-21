import os
import asyncio
import logging
import threading
from http.server import SimpleHTTPRequestHandler, HTTPServer
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from handlers import router

# Load environment variables
load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

BOT_TOKEN = os.environ.get("BOT_TOKEN") or os.environ.get("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN or TELEGRAM_BOT_TOKEN must be set in env")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("bot.log", encoding="utf-8")
    ]
)
logger = logging.getLogger(__name__)

def start_dummy_server():
    port = int(os.environ.get("PORT", 8080))
    server_address = ("", port)
    class HealthCheckHandler(SimpleHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(b"OK")
        def log_message(self, format, *args):
            pass # Suppress logging to keep console clean

    try:
        httpd = HTTPServer(server_address, HealthCheckHandler)
        logger.info(f"Starting dummy health check server on port {port}...")
        httpd.serve_forever()
    except Exception as e:
        logger.error(f"Failed to start health check server: {e}")

def fix_database_rls():
    import psycopg2
    supabase_url = os.environ.get("SUPABASE_URL", "")
    supabase_service_key = os.environ.get("SUPABASE_SERVICE_KEY", "")
    if not supabase_url or not supabase_service_key:
        return
    
    project_ref = supabase_url.replace("https://", "").split(".")[0]
    host = f"db.{project_ref}.supabase.co"
    port = 5432
    user = "postgres"
    password = supabase_service_key
    database = "postgres"
    
    try:
        conn = psycopg2.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            connect_timeout=10
        )
        cursor = conn.cursor()
        # Drop and create policies to allow public writes to settings table
        cursor.execute('DROP POLICY IF EXISTS "Allow public all settings" ON settings;')
        cursor.execute('DROP POLICY IF EXISTS "Allow public insert settings" ON settings;')
        cursor.execute('DROP POLICY IF EXISTS "Allow public update settings" ON settings;')
        cursor.execute('DROP POLICY IF EXISTS "Allow public delete settings" ON settings;')
        cursor.execute('CREATE POLICY "Allow public all settings" ON settings FOR ALL USING (true) WITH CHECK (true);')
        conn.commit()
        conn.close()
        logger.info("✅ Database RLS policies for settings table fixed successfully!")
    except Exception as e:
        logger.error(f"❌ Failed to fix database RLS policies: {e}")

async def main():
    # Initialize Bot and Dispatcher
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    
    # Register router
    dp.include_router(router)
    
    # Fix database RLS policies on startup
    await asyncio.to_thread(fix_database_rls)
    
    # Delete webhook if exists to use long polling
    try:
        await bot.delete_webhook(drop_pending_updates=True)
    except Exception as e:
        logger.warning(f"Could not delete webhook on startup: {e}")
    
    # Start the dummy port listener for Render
    threading.Thread(target=start_dummy_server, daemon=True).start()
    
    logger.info("Starting Telegram Contest Bot...")
    try:
        # Start polling
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped.")

