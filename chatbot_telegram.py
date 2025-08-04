import os
import datetime
from pathlib import Path
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
import openai

# Carrega variáveis do arquivo .env
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not TELEGRAM_TOKEN or not OPENAI_API_KEY:
    print("ERRO: TELEGRAM_TOKEN ou OPENAI_API_KEY não encontrados no .env")
    exit(1)

openai.api_key = OPENAI_API_KEY

# Diretório para salvar conversas
conversations_dir = Path("conversations")
conversations_dir.mkdir(exist_ok=True)

def save_conversation(user_id, username, message, is_bot=False):
    try:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        safe_username = username if username else f"user_{user_id}"
        safe_username = "".join(c if c.isalnum() else "_" for c in safe_username)

        user_folder = conversations_dir / f"{user_id}_{safe_username}"
        user_folder.mkdir(parents=True, exist_ok=True)

        date_str = datetime.datetime.now().strftime("%Y-%m-%d")
        file_path = user_folder / f"conversa_{date_str}.txt"

        print(f"[DEBUG] Salvando conversa em: {file_path.resolve()}")

        sender = "BOT" if is_bot else f"USUARIO ({safe_username})"
        line = f"[{timestamp}] {sender}: {message}\n"

        with open(file_path, 'a', encoding='utf-8') as f:
            f.write(line)

        print(f"[✔] Mensagem salva em {file_path}")
    except Exception as e:
        print(f"[ERRO] Falha ao salvar conversa: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"Olá, {user.first_name}! Me envie uma pergunta e eu responderei com inteligência artificial. "
        "Se quiser uma imagem, use o comando /img seguido do que deseja."
    )
    save_conversation(user.id, user.username or user.first_name, "/start", is_bot=False)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text

    save_conversation(user.id, user.username or user.first_name, text, is_bot=False)

    response = generate_openai_response(text)

    save_conversation(user.id, user.username or user.first_name, response, is_bot=True)

    await update.message.reply_text(response)

async def generate_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    prompt = " ".join(context.args)
    if not prompt:
        await update.message.reply_text("Por favor, envie um texto para gerar a imagem após o comando /img")
        return

    save_conversation(user.id, user.username or user.first_name, f"/img {prompt}", is_bot=False)

    try:
        response = openai.Image.create(
            prompt=prompt,
            n=1,
            size="512x512"
        )
        image_url = response['data'][0]['url']
        save_conversation(user.id, user.username or user.first_name, f"Imagem gerada: {image_url}", is_bot=True)
        await update.message.reply_photo(image_url)
    except Exception as e:
        error_msg = f"Erro ao gerar imagem: {e}"
        save_conversation(user.id, user.username or user.first_name, error_msg, is_bot=True)
        await update.message.reply_text(error_msg)

def generate_openai_response(user_message):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",  # modelo disponível para todos
            messages=[
                {"role": "system", "content": "Você é um assistente útil."},
                {"role": "user", "content": user_message}
            ],
            max_tokens=1000,
            temperature=0.7
        )
        return response['choices'][0]['message']['content'].strip()
    except Exception as e:
        return f"Erro ao gerar resposta: {e}"

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("img", generate_image))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot do Telegram iniciado!")
    app.run_polling()

if __name__ == "__main__":
    main()
