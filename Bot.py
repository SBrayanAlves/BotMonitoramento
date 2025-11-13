import os
import time
import requests
import sqlite3
import re
from datetime import datetime
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

# Traz as variaveis de ambiente
load_dotenv()

# Banco de Dados
connect = sqlite3.connect('GeladeiraCompraCerta.db')
cursor = connect.cursor()

cursor.execute(
    '''
    CREATE TABLE IF NOT EXISTS dados(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        quantidade INTEGER NOT NULL,
        data_registro TEXT
    )
    '''
)

cursor.execute(
    '''
    CREATE TABLE IF NOT EXISTS controle_limpeza(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ultima_limpeza TEXT
    )
    '''
)

connect.commit()

# Conexao com o Discord
WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL')

# Bot
class BotCompraCerta:

    # Inicia o driver e a espera
    def __init__(self):
        self.chrome_options = Options()
        self.chrome_options.add_argument("--headless=new")
        self.chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
        self.chrome_options.add_argument("--disable-gpu")
        self.chrome_options.add_argument("--no-sandbox")
        self.chrome_options.add_argument("--log-level=3")

        prefs = {"profile.managed_default_content_settings.images": 2}
        self.chrome_options.add_experimental_option("prefs", prefs)

        cursor.execute("SELECT * FROM controle_limpeza LIMIT 1")
        if not cursor.fetchone():
            agora = datetime.now().isoformat()
            cursor.execute("INSERT INTO controle_limpeza (ultima_limpeza) VALUES (?)", (agora,))
            connect.commit()

    def Limpeza(self):
        try:
            cursor.execute("SELECT ultima_limpeza FROM controle_limpeza LIMIT 1")
            resultado = cursor.fetchone()

            if resultado:
                ultima_data_str = resultado[0]
                ultima_data = datetime.fromisoformat(ultima_data_str)
                agora = datetime.now()

                diferenca = agora - ultima_data

                if diferenca.days >= 7:
                    cursor.execute("DELETE FROM dados")
                    
                    nova_data = agora.isoformat()
                    cursor.execute("UPDATE controle_limpeza SET ultima_limpeza = ?", (nova_data,))

                    cursor.execute("VACUUM")
                    connect.commit()

                    try:
                        requests.post(WEBHOOK_URL, json={"username": "Bot CompraCerta", "content": "🧹 **MANUTENÇÃO:** O banco de dados foi limpo automaticamente (Ciclo de 7 dias)."})
                    except:
                        pass
        except Exception as e:
            print(f"Erro ao verificar limpeza {e}")

    def Monitoramento(self):
        driver = None

        try:
            driver = webdriver.Chrome(options=self.chrome_options)
            wait = WebDriverWait(driver, 10)
            
            # Tenta abrir o navegador
            driver.get(os.getenv("URL"))
            # Espera 10 segundos pra carregar tudo
            time.sleep(10)

            # Tenta pegar o numero atual
            elemento = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div[class*='totalProducts']")))
            texto_bruto = elemento.get_attribute("textContent")
            match = re.search(r'(\d+)', texto_bruto)
            
            if match:
                valor = int(match.group(1))
                print(f"-->Quantidade de Produtos: {valor}")

                data_hoje = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                # Busca o ultimo registro do banco de dados
                cursor.execute('SELECT * FROM dados ORDER BY id DESC LIMIT 1;')
                consulta = cursor.fetchone()

                if consulta is None:
                    print("Sistema inicialmente pela primeira vez!")
                    cursor.execute('INSERT INTO dados (quantidade, data_registro) VALUES (?, ?)', (valor, data_hoje,))
                    connect.commit()
                    return 
                
                valor_anterior = consulta[1]

                # Faz a comparacao 
                if valor > valor_anterior:
                    data = {
                        "username": "Bot CompraCerta",
                        "content": f"🚨 **NOVOS PRODUTOS ENCONTRADOS!**\n\nAcabaram de cair: **{valor - valor_anterior}** no CompraCerta!"
                    }
                    try:
                        requests.post(WEBHOOK_URL, json=data)
                        print("Notificacao enviada")
                        cursor.execute('INSERT INTO dados (quantidade, data_registro) VALUES (?, ?)', (valor, data_hoje,))
                        connect.commit()
                    except Exception as e:
                        print(f"Ocorre um erro: {e}")

                elif valor < valor_anterior:
                    cursor.execute("INSERT INTO dados (quantidade, data_registro) VALUES (?, ?)", (valor, data_hoje,))
                    connect.commit()

        # Erro caso o navegador nao abra
        except Exception as e:
            print(f"Erro crítico: {e}")

        finally:
            if driver:
                driver.quit()

    def Looping(self):
        try:
            while True:
                self.Limpeza()
                self.Monitoramento()
                time.sleep(600)

        except KeyboardInterrupt:
            print("\nBot parado pelo usuário (Ctrl+C detectado).")

if __name__ == "__main__":
    bot = BotCompraCerta()
    bot.Looping()