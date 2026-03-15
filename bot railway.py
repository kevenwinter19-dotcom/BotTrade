#!/usr/bin/env python3
“””
╔══════════════════════════════════════════════════════════════╗
║     BOT INTELIGENTE BTC/USDT — RAILWAY EDITION              ║
║     Lê API Key via variáveis de ambiente (seguro!)           ║
╚══════════════════════════════════════════════════════════════╝
“””

import os
import time
import json
import logging
import numpy as np
import pandas as pd
from datetime import datetime
from collections import deque
from binance.client import Client
from binance.exceptions import BinanceAPIException

# ─────────────────────────────────────────────────────────

# ⚙️  CONFIGURAÇÕES — lidas das variáveis de ambiente

# (você define isso no painel do Railway, não no código)

# ─────────────────────────────────────────────────────────

API_KEY         = os.environ.get(“BINANCE_API_KEY”, “”)
API_SECRET      = os.environ.get(“BINANCE_API_SECRET”, “”)
USAR_TESTNET    = os.environ.get(“USAR_TESTNET”, “true”).lower() == “true”

PAR             = os.environ.get(“PAR”, “BTCUSDT”)
VALOR_TRADE     = float(os.environ.get(“VALOR_TRADE”, “10”))
STOP_LOSS_USD   = float(os.environ.get(“STOP_LOSS_USD”, “10”))
TAKE_PROFIT_USD = float(os.environ.get(“TAKE_PROFIT_USD”, “20”))
INTERVALO       = int(os.environ.get(“INTERVALO”, “60”))
TIMEFRAME       = Client.KLINE_INTERVAL_15MINUTE
ARQUIVO_MEMORIA = “memoria_bot.json”

# ─────────────────────────────────────────────────────────

# 📋  LOGGING

# ─────────────────────────────────────────────────────────

logging.basicConfig(
level=logging.INFO,
format=”%(asctime)s | %(levelname)s | %(message)s”,
datefmt=”%Y-%m-%d %H:%M:%S”,
handlers=[logging.StreamHandler()]  # Railway captura stdout
)
log = logging.getLogger(**name**)

# ─────────────────────────────────────────────────────────

# 🧠  AGENTE Q-LEARNING

# ─────────────────────────────────────────────────────────

class AgenteQL:
ACOES = [“AGUARDAR”, “COMPRAR”, “VENDER”]

```
def __init__(self, alpha=0.1, gamma=0.9, epsilon=0.3):
    self.alpha        = alpha
    self.gamma        = gamma
    self.epsilon      = epsilon
    self.epsilon_min  = 0.05
    self.epsilon_decay= 0.995
    self.q_table      = {}
    self.historico    = deque(maxlen=200)
    self.total_trades = 0
    self.lucro_total  = 0.0
    self.wins         = 0
    self.losses       = 0
    self.params = {
        "ema_rapida": 9, "ema_lenta": 21,
        "rsi_periodo": 14, "rsi_compra": 45, "rsi_venda": 55,
    }
    self.carregar_memoria()

def _get_q(self, estado):
    if estado not in self.q_table:
        self.q_table[estado] = [0.0, 0.0, 0.0]
    return self.q_table[estado]

def escolher_acao(self, estado):
    if np.random.rand() < self.epsilon:
        acao = np.random.randint(3)
        log.info(f"🎲 Explorando → {self.ACOES[acao]}")
    else:
        q = self._get_q(estado)
        acao = int(np.argmax(q))
        log.info(f"🧠 Decisão → {self.ACOES[acao]} (Q={[round(v,3) for v in q]})")
    return acao

def aprender(self, estado, acao, recompensa, proximo_estado):
    q_atual  = self._get_q(estado)
    q_futuro = self._get_q(proximo_estado)
    q_atual[acao] = q_atual[acao] + self.alpha * (
        recompensa + self.gamma * max(q_futuro) - q_atual[acao]
    )
    self.q_table[estado] = q_atual
    if self.epsilon > self.epsilon_min:
        self.epsilon *= self.epsilon_decay

def codificar_estado(self, ind):
    preco = ind["preco"]; vwap = ind["vwap"]
    rsi   = ind["rsi"];   ema_r = ind["ema_r"]; ema_l = ind["ema_l"]
    vol   = ind["volatilidade"]

    tendencia = "ALTA" if ema_r > ema_l*1.001 else ("BAIXA" if ema_r < ema_l*0.999 else "LATERAL")
    zona_rsi  = ("SOBREVEND" if rsi<35 else ("SOBRECOMP" if rsi>65 else
                 ("BAIXO" if rsi<45 else ("ALTO" if rsi>55 else "NEUTRO"))))
    pos_vwap  = "ACIMA" if preco>vwap*1.002 else ("ABAIXO" if preco<vwap*0.998 else "NO_VWAP")
    vol_zona  = "ALTA" if vol>0.015 else ("MEDIA" if vol>0.007 else "BAIXA")
    recentes  = list(self.historico)[-3:]
    ultimas   = "".join("W" if r>0 else "L" for r in recentes).ljust(3,"N")
    return f"{tendencia}|{zona_rsi}|{pos_vwap}|{vol_zona}|{ultimas}"

def calcular_recompensa(self, lucro):
    return np.log1p(lucro) if lucro > 0 else -2.0 * abs(lucro)

def registrar_resultado(self, lucro):
    self.historico.append(lucro)
    self.total_trades += 1
    self.lucro_total  += lucro
    if lucro > 0: self.wins += 1
    else: self.losses += 1
    wr = self.wins / self.total_trades * 100
    log.info(f"📊 {'✅' if lucro>0 else '❌'} ${lucro:+.2f} | "
             f"Total: ${self.lucro_total:.2f} | WR: {wr:.1f}% | "
             f"ε={self.epsilon:.3f} | Estados: {len(self.q_table)}")
    if self.total_trades % 10 == 0:
        self._adaptar_parametros()
    self.salvar_memoria()

def _adaptar_parametros(self):
    recentes = list(self.historico)[-10:]
    wr = sum(1 for r in recentes if r > 0) / len(recentes)
    lucro = sum(recentes)
    log.info(f"🔧 Revisão de parâmetros — WR recente: {wr*100:.0f}% | Lucro: ${lucro:.2f}")
    if wr < 0.4:
        self.params["rsi_compra"] = max(35, self.params["rsi_compra"] - 2)
        self.params["rsi_venda"]  = min(65, self.params["rsi_venda"]  + 2)
        log.info(f"⚠️  Modo conservador ativado")
    elif wr > 0.65:
        self.params["rsi_compra"] = min(50, self.params["rsi_compra"] + 1)
        self.params["rsi_venda"]  = max(50, self.params["rsi_venda"]  - 1)
        log.info(f"✅ Modo agressivo ativado")

def salvar_memoria(self):
    dados = {
        "q_table": self.q_table, "epsilon": self.epsilon,
        "historico": list(self.historico), "total_trades": self.total_trades,
        "lucro_total": self.lucro_total, "wins": self.wins,
        "losses": self.losses, "params": self.params,
        "atualizado": datetime.now().isoformat()
    }
    with open(ARQUIVO_MEMORIA, "w") as f:
        json.dump(dados, f, indent=2)

def carregar_memoria(self):
    try:
        with open(ARQUIVO_MEMORIA, "r") as f:
            d = json.load(f)
        self.q_table      = d.get("q_table", {})
        self.epsilon      = d.get("epsilon", 0.3)
        self.historico    = deque(d.get("historico", []), maxlen=200)
        self.total_trades = d.get("total_trades", 0)
        self.lucro_total  = d.get("lucro_total", 0.0)
        self.wins         = d.get("wins", 0)
        self.losses       = d.get("losses", 0)
        self.params       = d.get("params", self.params)
        log.info(f"🧠 Memória carregada: {len(self.q_table)} estados | "
                 f"{self.total_trades} trades | ${self.lucro_total:.2f}")
    except FileNotFoundError:
        log.info("🆕 Iniciando sem memória anterior.")
```

# ─────────────────────────────────────────────────────────

# 📊  INDICADORES

# ─────────────────────────────────────────────────────────

def buscar_candles(client):
klines = client.get_klines(symbol=PAR, interval=TIMEFRAME, limit=150)
df = pd.DataFrame(klines, columns=[
“time”,“open”,“high”,“low”,“close”,“volume”,
“close_time”,“quote_vol”,“trades”,“taker_base”,“taker_quote”,“ignore”
])
for col in [“open”,“high”,“low”,“close”,“volume”]:
df[col] = df[col].astype(float)
df[“time”] = pd.to_datetime(df[“time”], unit=“ms”)
return df

def calcular_indicadores(df, params):
df = df.copy()
er = params[“ema_rapida”]; el = params[“ema_lenta”]; rp = params[“rsi_periodo”]
df[“ema_r”] = df[“close”].ewm(span=er, adjust=False).mean()
df[“ema_l”] = df[“close”].ewm(span=el, adjust=False).mean()
delta = df[“close”].diff()
ganho = delta.clip(lower=0).ewm(com=rp-1, adjust=False).mean()
perda = (-delta.clip(upper=0)).ewm(com=rp-1, adjust=False).mean()
df[“rsi”]  = 100 - (100 / (1 + ganho / perda))
pt = (df[“high”] + df[“low”] + df[“close”]) / 3
df[“vwap”] = (pt * df[“volume”]).cumsum() / df[“volume”].cumsum()
df[“volatilidade”] = df[“close”].pct_change().rolling(20).std()
u = df.iloc[-1]
return {
“preco”: u[“close”], “ema_r”: u[“ema_r”], “ema_l”: u[“ema_l”],
“rsi”: u[“rsi”], “vwap”: u[“vwap”],
“volatilidade”: u[“volatilidade”] if not np.isnan(u[“volatilidade”]) else 0.01
}

# ─────────────────────────────────────────────────────────

# 💰  ORDENS

# ─────────────────────────────────────────────────────────

def calcular_stops(preco, lado):
pct_stop = STOP_LOSS_USD / VALOR_TRADE
pct_tp   = TAKE_PROFIT_USD / VALOR_TRADE
if lado == “COMPRAR”:
return round(preco*(1-pct_stop), 2), round(preco*(1+pct_tp), 2)
return round(preco*(1+pct_stop), 2), round(preco*(1-pct_tp), 2)

def executar_ordem(client, acao, preco):
qtd  = round(VALOR_TRADE / preco, 6)
stop, alvo = calcular_stops(preco, acao)
lado = “BUY” if acao == “COMPRAR” else “SELL”
log.info(f”🚀 {acao} | ${preco:,.2f} | Qtd: {qtd} | Stop: ${stop} | Alvo: ${alvo}”)
try:
ordem = client.order_market(symbol=PAR, side=lado, quantity=qtd)
log.info(f”✅ Ordem {ordem[‘orderId’]} executada!”)
return ordem, stop, alvo
except BinanceAPIException as e:
log.error(f”❌ Erro: {e.message}”)
return None, stop, alvo

def monitorar_posicao(client, entrada, stop, alvo, lado):
log.info(f”👁️  Monitorando… Entrada: ${entrada:,.2f} | Stop: ${stop} | Alvo: ${alvo}”)
while True:
try:
preco = float(client.get_symbol_ticker(symbol=PAR)[“price”])
if lado == “COMPRAR”:
lucro = (preco - entrada) / entrada * VALOR_TRADE
if preco <= stop: log.info(f”🛑 Stop! ${preco:,.2f}”); return lucro
if preco >= alvo: log.info(f”🎯 Alvo! ${preco:,.2f}”); return lucro
else:
lucro = (entrada - preco) / entrada * VALOR_TRADE
if preco >= stop: log.info(f”🛑 Stop! ${preco:,.2f}”); return lucro
if preco <= alvo: log.info(f”🎯 Alvo! ${preco:,.2f}”); return lucro
log.info(f”   BTC: ${preco:,.2f} | P&L: ${lucro:+.2f}”)
time.sleep(15)
except Exception as e:
log.error(f”Erro monitorando: {e}”)
time.sleep(15)

# ─────────────────────────────────────────────────────────

# 🔄  MAIN

# ─────────────────────────────────────────────────────────

def main():
if not API_KEY or not API_SECRET:
log.error(“❌ BINANCE_API_KEY e BINANCE_API_SECRET não configurados!”)
log.error(”   Configure as variáveis de ambiente no Railway.”)
return

```
log.info("╔══════════════════════════════════════════╗")
log.info("║   BOT INTELIGENTE — RAILWAY EDITION      ║")
log.info(f"║   Par: {PAR} | Trade: ${VALOR_TRADE} | Stop: ${STOP_LOSS_USD}  ║")
log.info(f"║   Testnet: {USAR_TESTNET}                         ║")
log.info("╚══════════════════════════════════════════╝")

client = Client(API_KEY, API_SECRET, testnet=USAR_TESTNET)
agente = AgenteQL()

while True:
    try:
        df  = buscar_candles(client)
        ind = calcular_indicadores(df, agente.params)
        estado = agente.codificar_estado(ind)

        log.info(f"📈 BTC: ${ind['preco']:,.2f} | RSI={ind['rsi']:.1f} | "
                 f"EMA={ind['ema_r']:.0f}/{ind['ema_l']:.0f} | "
                 f"VWAP={ind['vwap']:.0f} | Estado: {estado}")

        acao_idx  = agente.escolher_acao(estado)
        acao_nome = agente.ACOES[acao_idx]

        if acao_nome in ("COMPRAR", "VENDER"):
            ordem, stop, alvo = executar_ordem(client, acao_nome, ind["preco"])
            if ordem:
                lucro = monitorar_posicao(client, ind["preco"], stop, alvo, acao_nome)
                recompensa = agente.calcular_recompensa(lucro)
                df2  = buscar_candles(client)
                ind2 = calcular_indicadores(df2, agente.params)
                prox = agente.codificar_estado(ind2)
                agente.aprender(estado, acao_idx, recompensa, prox)
                agente.registrar_resultado(lucro)
        else:
            log.info("⏳ Aguardando sinal...")

        time.sleep(INTERVALO)

    except BinanceAPIException as e:
        log.error(f"❌ Binance: {e.message}")
        time.sleep(30)
    except Exception as e:
        log.error(f"❌ Erro: {e}")
        time.sleep(30)
```

if **name** == “**main**”:
main()
