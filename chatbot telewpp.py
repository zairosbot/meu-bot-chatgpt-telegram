import os
import datetime
import threading
from pathlib import Path
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
import openai
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import time

# Carrega as variáveis do .env
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not TELEGRAM_TOKEN or not OPENAI_API_KEY:
    print("ERRO: TELEGRAM_TOKEN ou OPENAI_API_KEY não encontrados no .env")
    exit(1)

openai.api_key = OPENAI_API_KEY

# Pastas de conversas
telegram_dir = Path("conversations/telegram")
whatsapp_dir = Path("conversations/whatsapp")
telegram_dir.mkdir(parents=True, exist_ok=True)
whatsapp_dir.mkdir(parents=True, exist_ok=True)

# ---------- Funções comuns ----------

def salvar_conversa(base_path, user_id, username, numero, mensagem, is_bot=False):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    nome_arquivo = f"{user_id}_{username or 'sem_nome'}_{numero or 'sem_numero'}"
    pasta = base_path / nome_arquivo
    pasta.mkdir(exist_ok=True)

    file_path = pasta / f"conversa_{datetime.date.today()}.txt"
    origem = "BOT" if is_bot else f"USUÁRIO ({username})"
    with open(file_path, 'a', encoding='utf-8') as f:
        f.write(f"[{timestamp}] {origem}: {mensagem}\n")

def gerar_resposta_openai(pergunta):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Você é um assistente útil."},
                {"role": "user", "content": pergunta}
            ]
        )
        return response['choices'][0]['message']['content'].strip()
    except Exception as e:
        return f"Erro ao gerar resposta: {e}"

# ---------- Bot Telegram ----------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(f"Olá {user.first_name}, envie uma pergunta.")
    salvar_conversa(telegram_dir, user.id, user.username or user.first_name, "telegram", "/start", is_bot=False)

async def tratar_mensagem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    mensagem = update.message.text
    salvar_conversa(telegram_dir, user.id, user.username or user.first_name, "telegram", mensagem, is_bot=False)

    resposta = gerar_resposta_openai(mensagem)
    salvar_conversa(telegram_dir, user.id, user.username or user.first_name, "telegram", resposta, is_bot=True)

    await update.message.reply_text(resposta)

def iniciar_telegram():
    import asyncio
    asyncio.set_event_loop(asyncio.new_event_loop())

    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, tratar_mensagem))

    print("[Telegram] Bot iniciado!")
    app.run_polling()

# ---------- Bot WhatsApp (via Selenium) ----------

def iniciar_whatsapp():
    print("[WhatsApp] Inicializando navegador...")

    options = Options()
    options.add_argument("--user-data-dir=whatsapp_profile")
    options.add_argument("--start-maximized")
    driver = webdriver.Chrome(options=options)
    driver.get("https://web.whatsapp.com")

    print("[WhatsApp] Escaneie o QR Code para login.")
    time.sleep(15)

    print("[WhatsApp] Bot em execução. Monitorando mensagens...")

    last_messages = {}

    while True:
        try:
            time.sleep(5)
            chats = driver.find_elements(By.XPATH, '//div[@role="row"]')

            for chat in chats[:5]:
                try:
                    nome = chat.find_element(By.XPATH, './/span[contains(@class,"ggj6brxn")]').text
                    chat.click()
                    time.sleep(2)

                    mensagens = driver.find_elements(By.XPATH, '//div[contains(@class,"message-in") or contains(@class,"message-out")]')
                    ultima = mensagens[-1]
                    texto = ultima.text.strip()

                    if nome not in last_messages or last_messages[nome] != texto:
                        last_messages[nome] = texto
                        print(f"[WhatsApp] Nova mensagem de {nome}: {texto}")

                        resposta = gerar_resposta_openai(texto)
                        salvar_conversa(whatsapp_dir, nome, nome, "whatsapp", texto, is_bot=False)
                        salvar_conversa(whatsapp_dir, nome, nome, "whatsapp", resposta, is_bot=True)

                        caixa_texto = driver.find_element(By.XPATH, '//div[@title="Digite uma mensagem"]')
                        caixa_texto.click()
                        caixa_texto.send_keys(resposta)
                        time.sleep(1)

                        botao_enviar = driver.find_element(By.XPATH, '//span[@data-icon="send"]')
                        botao_enviar.click()
                        print(f"[WhatsApp] Resposta enviada para {nome}.")

                        time.sleep(3)
                except Exception as e:
                    continue
        except Exception as erro:
            print(f"[WhatsApp] Erro geral: {erro}")
            continue

# ---------- Execução Paralela ----------

if __name__ == "__main__":
    t1 = threading.Thread(target=iniciar_telegram)
    t2 = threading.Thread(target=iniciar_whatsapp)

    t1.start()
    t2.start()

    t1.join()
    t2.join()
