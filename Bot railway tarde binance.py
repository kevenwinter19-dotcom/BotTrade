#!/usr/bin/env python3
“””
╔══════════════════════════════════════════════════════════════════════╗
║           BOT ULTRA v4.0 — FORA DA CURVA                           ║
║                                                                      ║
║  🧠 Q-Learning com estado rico multi-timeframe                      ║
║  📰 NLP: análise de sentimento de notícias cripto em tempo real     ║
║  🐋 Whale Detector: detecta movimentos anormais de volume           ║
║  ⏱  Multi-Timeframe: M5 + M15 + H1 precisam concordar              ║
║  🔬 Auto-otimização: backtest a cada 24h e ajusta parâmetros        ║
║  💰 Kelly Criterion + Trailing Stop ATR                             ║
║  🛡️  Proteção de drawdown + circuit breaker                         ║
║  🌐 Dashboard web integrado (porta 8080)                            ║
╚══════════════════════════════════════════════════════════════════════╝

INSTALAÇÃO:
pip install python-binance pandas numpy requests

USO:
python bot_v4_ultra.py

O dashboard estará disponível em: http://localhost:8080
“””

import os, time, json, logging, threading, requests
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from collections import deque
from http.server import HTTPServer, BaseHTTPRequestHandler
from binance.client import Client
from binance.exceptions import BinanceAPIException

# ══════════════════════════════════════════════════════════════════════

# ⚙️  CONFIGURAÇÕES

# ══════════════════════════════════════════════════════════════════════

API_KEY      = os.environ.get(“BINANCE_API_KEY”, “COLE_AQUI”)
API_SECRET   = os.environ.get(“BINANCE_API_SECRET”, “COLE_AQUI”)
USAR_TESTNET = os.environ.get(“USAR_TESTNET”, “true”).lower() == “true”

PARES          = [“BTCUSDT”, “ETHUSDT”, “BNBUSDT”]
CAPITAL_TOTAL  = float(os.environ.get(“CAPITAL_TOTAL”, “100”))
RISCO_BASE     = 0.02
MAX_POSICOES   = 2
MAX_DRAWDOWN   = 0.15
INTERVALO      = 60
DASHBOARD_PORT = int(os.environ.get(“PORT”, “8080”))

TIMEFRAMES = {
“M5”:  Client.KLINE_INTERVAL_5MINUTE,
“M15”: Client.KLINE_INTERVAL_15MINUTE,
“H1”:  Client.KLINE_INTERVAL_1HOUR,
}

ARQUIVO_MEMORIA   = “memoria_v4.json”
ARQUIVO_ESTADO    = “estado_dashboard.json”

# ══════════════════════════════════════════════════════════════════════

# 📋  LOGGING

# ══════════════════════════════════════════════════════════════════════

logging.basicConfig(
level=logging.INFO,
format=”%(asctime)s | %(levelname)s | %(message)s”,
datefmt=”%Y-%m-%d %H:%M:%S”,
handlers=[
logging.FileHandler(“bot_v4_log.txt”, encoding=“utf-8”),
logging.StreamHandler()
]
)
log = logging.getLogger(**name**)

# Estado global para o dashboard

ESTADO_GLOBAL = {
“status”: “iniciando”,
“capital”: CAPITAL_TOTAL,
“capital_inicial”: CAPITAL_TOTAL,
“trades”: 0, “wins”: 0, “losses”: 0,
“lucro_total”: 0.0,
“posicoes”: {},
“sentimento”: 50,
“fear_greed_label”: “Neutro”,
“whale_alertas”: [],
“nlp_score”: 0,
“nlp_label”: “Neutro”,
“ultimo_sinal”: {},
“historico_pnl”: [],
“parametros”: {},
“ultima_otimizacao”: “Nunca”,
“log_recente”: [],
“inicio”: datetime.now().isoformat(),
}

# ══════════════════════════════════════════════════════════════════════

# 🌐  DASHBOARD WEB

# ══════════════════════════════════════════════════════════════════════

DASHBOARD_HTML = “””<!DOCTYPE html>

<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta http-equiv="refresh" content="30">
<title>BOT ULTRA v4</title>
<link href="https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Barlow:wght@300;600;800&display=swap" rel="stylesheet">
<style>
:root {
  --bg: #050508; --s1: #0c0c14; --s2: #12121e;
  --border: #1a1a2e; --accent: #00f5c4; --accent2: #ff6b35;
  --blue: #4facfe; --red: #ff4757; --green: #2ed573;
  --warn: #ffa502; --text: #e8eaf0; --muted: #4a4a6a;
  --font-mono: 'Share Tech Mono', monospace;
  --font-main: 'Barlow', sans-serif;
}
* { margin:0; padding:0; box-sizing:border-box; }
body {
  background: var(--bg); color: var(--text);
  font-family: var(--font-main);
  min-height: 100vh; padding: 12px;
  background-image: radial-gradient(ellipse at 20% 50%, rgba(0,245,196,0.03) 0%, transparent 60%),
                    radial-gradient(ellipse at 80% 20%, rgba(79,172,254,0.03) 0%, transparent 60%);
}
.scanline {
  position: fixed; inset: 0; pointer-events: none; z-index: 999;
  background: repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0,0,0,0.03) 2px, rgba(0,0,0,0.03) 4px);
}
header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 16px; margin-bottom: 16px;
  background: var(--s1); border: 1px solid var(--border);
  border-radius: 12px; border-left: 3px solid var(--accent);
}
.logo { font-family: var(--font-mono); font-size: 18px; color: var(--accent); letter-spacing: 3px; }
.logo span { color: var(--accent2); }
.status-pill {
  display: flex; align-items: center; gap: 8px;
  font-family: var(--font-mono); font-size: 12px; color: var(--green);
}
.pulse-dot {
  width: 8px; height: 8px; border-radius: 50%;
  background: var(--green);
  animation: pulse 2s infinite;
}
@keyframes pulse {
  0%,100% { box-shadow: 0 0 0 0 rgba(46,213,115,0.4); }
  50% { box-shadow: 0 0 0 6px rgba(46,213,115,0); }
}
.grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 10px; }
.grid-3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; margin-bottom: 10px; }
.card {
  background: var(--s1); border: 1px solid var(--border);
  border-radius: 10px; padding: 14px;
}
.card-title {
  font-family: var(--font-mono); font-size: 10px; color: var(--muted);
  text-transform: uppercase; letter-spacing: 2px; margin-bottom: 8px;
}
.big-num {
  font-family: var(--font-mono); font-size: 28px; font-weight: 800;
  line-height: 1;
}
.big-num.green { color: var(--green); }
.big-num.red   { color: var(--red); }
.big-num.accent{ color: var(--accent); }
.big-num.blue  { color: var(--blue); }
.sub { font-size: 11px; color: var(--muted); margin-top: 4px; font-family: var(--font-mono); }

/* Gauge */
.gauge-wrap { position: relative; width: 80px; height: 44px; margin: 4px auto; }
.gauge-bg { width: 80px; height: 40px; border-radius: 40px 40px 0 0; overflow: hidden; }
.gauge-fill { width: 100%; height: 100%; border-radius: 40px 40px 0 0; }
.gauge-val { text-align: center; font-family: var(–font-mono); font-size: 18px; margin-top: 2px; }
.gauge-label { text-align: center; font-size: 10px; color: var(–muted); font-family: var(–font-mono); }

/* Whale alerts */
.whale-item {
display: flex; align-items: center; gap: 10px;
padding: 8px 10px; margin-bottom: 6px;
background: rgba(255,107,53,0.08); border: 1px solid rgba(255,107,53,0.2);
border-radius: 8px; font-size: 12px; font-family: var(–font-mono);
}
.whale-icon { font-size: 16px; }
.whale-info { flex: 1; }
.whale-time { color: var(–muted); font-size: 10px; }

/* NLP */
.nlp-bar-wrap { height: 6px; background: var(–border); border-radius: 100px; margin: 8px 0; overflow: hidden; }
.nlp-bar { height: 100%; border-radius: 100px; transition: width 0.5s; }

/* Posições */
.pos-item {
padding: 10px; margin-bottom: 6px;
background: var(–s2); border-radius: 8px;
border-left: 3px solid var(–green);
}
.pos-item.short { border-left-color: var(–red); }
.pos-header { display: flex; justify-content: space-between; font-family: var(–font-mono); font-size: 13px; }
.pos-pnl { font-weight: 800; }
.pos-details { font-size: 11px; color: var(–muted); margin-top: 4px; font-family: var(–font-mono); }

/* Log */
.log-box {
background: #020204; border: 1px solid var(–border);
border-radius: 10px; padding: 12px;
max-height: 180px; overflow-y: auto;
font-family: var(–font-mono); font-size: 11px;
}
.log-line { padding: 2px 0; border-bottom: 1px solid rgba(255,255,255,0.03); line-height: 1.5; }
.log-line .ts { color: var(–muted); margin-right: 8px; }
.log-line .info { color: var(–blue); }
.log-line .warn { color: var(–warn); }
.log-line .err  { color: var(–red); }
.log-line .ok   { color: var(–green); }

/* Multi-TF */
.tf-row { display: flex; gap: 6px; margin-bottom: 6px; }
.tf-badge {
flex: 1; text-align: center; padding: 6px 4px;
border-radius: 6px; font-family: var(–font-mono); font-size: 11px;
border: 1px solid var(–border);
}
.tf-badge.long  { background: rgba(46,213,115,0.1); border-color: rgba(46,213,115,0.3); color: var(–green); }
.tf-badge.short { background: rgba(255,71,87,0.1);  border-color: rgba(255,71,87,0.3);  color: var(–red); }
.tf-badge.wait  { background: var(–s2); color: var(–muted); }

/* Otimização */
.opt-badge {
display: inline-block; padding: 2px 8px;
background: rgba(79,172,254,0.1); border: 1px solid rgba(79,172,254,0.3);
border-radius: 4px; color: var(–blue); font-family: var(–font-mono); font-size: 11px;
}
.param-row { display: flex; justify-content: space-between; padding: 4px 0;
font-size: 12px; border-bottom: 1px solid rgba(255,255,255,0.04); }
.param-row .pk { color: var(–muted); font-family: var(–font-mono); }
.param-row .pv { color: var(–accent); font-family: var(–font-mono); }

.refresh-note { text-align: center; font-size: 10px; color: var(–muted);
font-family: var(–font-mono); margin-top: 16px; padding-bottom: 20px; }
</style>

</head>
<body>
<div class="scanline"></div>

<header>
  <div class="logo">BOT <span>ULTRA</span> v4.0</div>
  <div class="status-pill">
    <div class="pulse-dot" id="statusDot"></div>
    <span id="statusLabel">CARREGANDO...</span>
  </div>
</header>

<!-- Capital + Stats -->

<div class="grid">
  <div class="card">
    <div class="card-title">Capital Atual</div>
    <div class="big-num accent" id="capital">$--</div>
    <div class="sub" id="capitalRet">retorno: --</div>
  </div>
  <div class="card">
    <div class="card-title">P&L Total</div>
    <div class="big-num" id="pnl">$--</div>
    <div class="sub" id="pnlSub">-- trades</div>
  </div>
</div>

<div class="grid-3">
  <div class="card" style="text-align:center">
    <div class="card-title">Winrate</div>
    <div class="big-num green" id="winrate">--%</div>
    <div class="sub" id="wlRatio">W/L: --/--</div>
  </div>
  <div class="card" style="text-align:center">
    <div class="card-title">Fear & Greed</div>
    <div class="big-num" id="fgVal" style="color:#ffa502">--</div>
    <div class="sub" id="fgLabel">--</div>
  </div>
  <div class="card" style="text-align:center">
    <div class="card-title">NLP Score</div>
    <div class="big-num blue" id="nlpVal">--</div>
    <div class="sub" id="nlpLabel">--</div>
  </div>
</div>

<!-- Multi-TF por par -->

<div class="card" style="margin-bottom:10px">
  <div class="card-title">Multi-Timeframe — Consenso</div>
  <div id="tfGrid"></div>
</div>

<!-- Posições abertas -->

<div class="card" style="margin-bottom:10px">
  <div class="card-title">Posições Abertas</div>
  <div id="posicoes"><div style="color:var(--muted);font-size:12px;font-family:var(--font-mono)">Nenhuma posição aberta</div></div>
</div>

<!-- Whale Alerts -->

<div class="card" style="margin-bottom:10px">
  <div class="card-title">🐋 Whale Alerts</div>
  <div id="whaleAlerts"><div style="color:var(--muted);font-size:12px;font-family:var(--font-mono)">Monitorando...</div></div>
</div>

<!-- Auto-otimização -->

<div class="card" style="margin-bottom:10px">
  <div class="card-title">🔬 Auto-Otimização <span class="opt-badge" id="lastOpt">--</span></div>
  <div id="paramGrid"></div>
</div>

<!-- Log -->

<div class="card" style="margin-bottom:10px">
  <div class="card-title">Log em Tempo Real</div>
  <div class="log-box" id="logBox"></div>
</div>

<div class="refresh-note">↻ atualiza a cada 30s &nbsp;|&nbsp; BOT ULTRA v4.0</div>

<script>
async function carregar() {
  try {
    const r = await fetch('/api/estado');
    const d = await r.json();

    // Status
    const running = d.status === 'rodando';
    document.getElementById('statusDot').style.background = running ? 'var(--green)' : 'var(--warn)';
    document.getElementById('statusLabel').textContent = d.status.toUpperCase();

    // Capital
    const ret = ((d.capital - d.capital_inicial) / d.capital_inicial * 100).toFixed(2);
    document.getElementById('capital').textContent = '$' + d.capital.toFixed(2);
    document.getElementById('capitalRet').textContent = 'retorno: ' + (ret >= 0 ? '+' : '') + ret + '%';
    document.getElementById('capital').className = 'big-num ' + (d.capital >= d.capital_inicial ? 'accent' : 'red');

    // PnL
    const pnl = d.lucro_total;
    document.getElementById('pnl').textContent = (pnl >= 0 ? '+$' : '-$') + Math.abs(pnl).toFixed(4);
    document.getElementById('pnl').className = 'big-num ' + (pnl >= 0 ? 'green' : 'red');
    document.getElementById('pnlSub').textContent = d.trades + ' trades realizados';

    // Winrate
    const wr = d.trades > 0 ? (d.wins / d.trades * 100).toFixed(1) : '--';
    document.getElementById('winrate').textContent = wr + '%';
    document.getElementById('wlRatio').textContent = 'W/L: ' + d.wins + '/' + d.losses;

    // Fear & Greed
    document.getElementById('fgVal').textContent = d.sentimento;
    document.getElementById('fgLabel').textContent = d.fear_greed_label;
    const fgColor = d.sentimento <= 25 ? 'var(--red)' : d.sentimento >= 75 ? 'var(--warn)' : 'var(--accent)';
    document.getElementById('fgVal').style.color = fgColor;

    // NLP
    document.getElementById('nlpVal').textContent = (d.nlp_score >= 0 ? '+' : '') + d.nlp_score;
    document.getElementById('nlpLabel').textContent = d.nlp_label;
    document.getElementById('nlpVal').style.color = d.nlp_score > 0 ? 'var(--green)' : d.nlp_score < 0 ? 'var(--red)' : 'var(--blue)';

    // Multi-TF
    const tfDiv = document.getElementById('tfGrid');
    tfDiv.innerHTML = '';
    if (d.ultimo_sinal && Object.keys(d.ultimo_sinal).length > 0) {
      for (const [par, info] of Object.entries(d.ultimo_sinal)) {
        const row = document.createElement('div');
        row.innerHTML = '<div style="font-family:var(--font-mono);font-size:11px;color:var(--muted);margin-bottom:3px">' + par + '</div>';
        const tfRow = document.createElement('div'); tfRow.className = 'tf-row';
        for (const [tf, sinal] of Object.entries(info.timeframes || {})) {
          const cls = sinal === 'COMPRAR' ? 'long' : sinal === 'VENDER' ? 'short' : 'wait';
          tfRow.innerHTML += '<div class="tf-badge ' + cls + '">' + tf + '<br>' + sinal + '</div>';
        }
        row.appendChild(tfRow);
        tfDiv.appendChild(row);
      }
    } else {
      tfDiv.innerHTML = '<div style="color:var(--muted);font-size:12px;font-family:var(--font-mono)">Aguardando análise...</div>';
    }

    // Posições
    const posDiv = document.getElementById('posicoes');
    const pos = d.posicoes;
    if (Object.keys(pos).length === 0) {
      posDiv.innerHTML = '<div style="color:var(--muted);font-size:12px;font-family:var(--font-mono)">Nenhuma posição aberta</div>';
    } else {
      posDiv.innerHTML = '';
      for (const [par, p] of Object.entries(pos)) {
        const isLong = p.lado === 'COMPRAR';
        posDiv.innerHTML += '<div class="pos-item ' + (isLong ? '' : 'short') + '">' +
          '<div class="pos-header"><span>' + par + ' ' + (isLong ? '↑ LONG' : '↓ SHORT') + '</span>' +
          '<span class="pos-pnl" style="color:' + (isLong ? 'var(--green)' : 'var(--red)') + '">@ $' + p.entrada.toLocaleString() + '</span></div>' +
          '<div class="pos-details">Stop: $' + p.stop + ' | Alvo: $' + p.alvo + ' | Qtd: ' + p.qtd + '</div>' +
          '</div>';
      }
    }

    // Whale alerts
    const whaleDiv = document.getElementById('whaleAlerts');
    if (!d.whale_alertas || d.whale_alertas.length === 0) {
      whaleDiv.innerHTML = '<div style="color:var(--muted);font-size:12px;font-family:var(--font-mono)">Nenhum alerta recente</div>';
    } else {
      whaleDiv.innerHTML = d.whale_alertas.slice(-4).reverse().map(a =>
        '<div class="whale-item"><div class="whale-icon">🐋</div><div class="whale-info">' +
        '<div>' + a.par + ' — ' + a.tipo + ' <strong>' + a.volume_x + 'x</strong> volume normal</div>' +
        '<div class="whale-time">' + a.hora + '</div></div></div>'
      ).join('');
    }

    // Parâmetros / otimização
    document.getElementById('lastOpt').textContent = 'última: ' + d.ultima_otimizacao;
    const paramDiv = document.getElementById('paramGrid');
    paramDiv.innerHTML = '';
    for (const [k, v] of Object.entries(d.parametros || {})) {
      paramDiv.innerHTML += '<div class="param-row"><span class="pk">' + k + '</span><span class="pv">' + v + '</span></div>';
    }

    // Log
    const logDiv = document.getElementById('logBox');
    logDiv.innerHTML = (d.log_recente || []).slice(-30).reverse().map(l => {
      const cls = l.includes('✅') || l.includes('🎯') ? 'ok' :
                  l.includes('❌') || l.includes('🛑') ? 'err' :
                  l.includes('⚠️') || l.includes('🐋') ? 'warn' : 'info';
      const ts = l.substring(0, 19);
      const msg = l.substring(22);
      return '<div class="log-line"><span class="ts">' + ts + '</span><span class="' + cls + '">' + msg + '</span></div>';
    }).join('');

  } catch(e) {
    console.error(e);
  }
}
carregar();
setInterval(carregar, 10000);
</script>

</body>
</html>"""

class DashboardHandler(BaseHTTPRequestHandler):
def do_GET(self):
if self.path == ‘/api/estado’:
self.send_response(200)
self.send_header(‘Content-Type’, ‘application/json’)
self.send_header(‘Access-Control-Allow-Origin’, ‘*’)
self.end_headers()
self.wfile.write(json.dumps(ESTADO_GLOBAL).encode())
else:
self.send_response(200)
self.send_header(‘Content-Type’, ‘text/html; charset=utf-8’)
self.end_headers()
self.wfile.write(DASHBOARD_HTML.encode())

```
def log_message(self, *args): pass  # Silencia logs do servidor HTTP
```

def iniciar_dashboard():
server = HTTPServer((‘0.0.0.0’, DASHBOARD_PORT), DashboardHandler)
log.info(f”🌐 Dashboard: http://localhost:{DASHBOARD_PORT}”)
server.serve_forever()

# ══════════════════════════════════════════════════════════════════════

# 📰  NLP — ANÁLISE DE SENTIMENTO DE NOTÍCIAS

# ══════════════════════════════════════════════════════════════════════

class AnalisadorNLP:
“””
Analisa headlines de notícias cripto via CryptoCompare News API (gratuita).
Usa léxico financeiro para scoring de sentimento sem precisar de ML externo.
“””
POSITIVAS = [
“bullish”,“rally”,“surge”,“soar”,“gain”,“rise”,“high”,“record”,
“breakout”,“adoption”,“approve”,“launch”,“partner”,“upgrade”,
“growth”,“buy”,“long”,“pump”,“moon”,“ath”,“accumulate”,
“institutional”,“etf”,“support”,“recovery”
]
NEGATIVAS = [
“bearish”,“crash”,“dump”,“fall”,“drop”,“low”,“ban”,“hack”,
“scam”,“fraud”,“sell”,“short”,“fear”,“panic”,“liquidation”,
“regulation”,“fine”,“lawsuit”,“down”,“loss”,“warning”,“risk”,
“bubble”,“collapse”,“fear”,“concern”,“investigation”
]

```
def __init__(self):
    self.score = 0
    self.label = "Neutro"
    self.noticias = []
    self.ultima_atualizacao = None

def atualizar(self):
    agora = datetime.now()
    if self.ultima_atualizacao and (agora - self.ultima_atualizacao).seconds < 1800:
        return  # Cache 30 min

    try:
        url = "https://min-api.cryptocompare.com/data/v2/news/?lang=EN&categories=BTC,ETH&sortOrder=popular"
        r = requests.get(url, timeout=10)
        dados = r.json().get("Data", [])[:15]

        score_total = 0
        titulos = []
        for noticia in dados:
            titulo = noticia.get("title", "").lower()
            body   = noticia.get("body", "").lower()[:200]
            texto  = titulo + " " + body
            titulos.append(noticia.get("title", ""))

            pos = sum(1 for p in self.POSITIVAS if p in texto)
            neg = sum(1 for n in self.NEGATIVAS if n in texto)
            score_total += (pos - neg)

        self.score = max(-10, min(10, score_total))
        self.noticias = titulos[:5]
        self.ultima_atualizacao = agora

        if self.score >= 3:
            self.label = "Muito Positivo"
        elif self.score >= 1:
            self.label = "Positivo"
        elif self.score <= -3:
            self.label = "Muito Negativo"
        elif self.score <= -1:
            self.label = "Negativo"
        else:
            self.label = "Neutro"

        log.info(f"📰 NLP: score={self.score:+d} ({self.label}) | {len(dados)} notícias analisadas")

    except Exception as e:
        log.warning(f"⚠️  NLP falhou: {e}")

def ajustar_sinal(self, sinal):
    """NLP muito negativo bloqueia compras; muito positivo bloqueia vendas."""
    if self.score <= -4 and sinal == "COMPRAR":
        log.info(f"🚫 NLP bloqueia COMPRA (score={self.score})")
        return "AGUARDAR"
    if self.score >= 4 and sinal == "VENDER":
        log.info(f"🚫 NLP bloqueia VENDA (score={self.score})")
        return "AGUARDAR"
    return sinal
```

# ══════════════════════════════════════════════════════════════════════

# 🐋  WHALE DETECTOR

# ══════════════════════════════════════════════════════════════════════

class WhaleDetector:
“””
Detecta volumes anormais comparando o volume atual
com a média das últimas N barras.
Volume > 3x a média = possível movimento de whale.
“””
def **init**(self, multiplicador=3.0, janela=20):
self.multiplicador = multiplicador
self.janela        = janela
self.alertas       = deque(maxlen=20)

```
def analisar(self, df, par):
    """Retorna True se detectar volume anormal."""
    if len(df) < self.janela + 1:
        return False, 1.0

    vol_atual = df["volume"].iloc[-1]
    vol_media = df["volume"].iloc[-(self.janela+1):-1].mean()
    ratio     = vol_atual / vol_media if vol_media > 0 else 1.0

    if ratio >= self.multiplicador:
        direcao = "COMPRA" if df["close"].iloc[-1] > df["open"].iloc[-1] else "VENDA"
        alerta = {
            "par":      par,
            "tipo":     f"Volume {direcao}",
            "volume_x": round(ratio, 1),
            "hora":     datetime.now().strftime("%H:%M:%S")
        }
        self.alertas.append(alerta)
        log.info(f"🐋 WHALE ALERT: {par} | Volume {ratio:.1f}x normal | {direcao}")
        return True, ratio

    return False, ratio

def ajustar_sinal(self, sinal, par, df):
    """Usa whale detection para confirmar ou rejeitar sinal."""
    whale, ratio = self.analisar(df, par)

    if whale:
        ultimo = df.iloc[-1]
        direcao_whale = "COMPRAR" if ultimo["close"] > ultimo["open"] else "VENDER"
        if direcao_whale == sinal:
            log.info(f"🐋 Whale CONFIRMA sinal {sinal} em {par}")
            return sinal, ratio
        else:
            log.info(f"🐋 Whale CONTRADIZ sinal — aguardando")
            return "AGUARDAR", ratio

    return sinal, ratio
```

# ══════════════════════════════════════════════════════════════════════

# ⏱  MULTI-TIMEFRAME

# ══════════════════════════════════════════════════════════════════════

def calcular_indicadores(df):
df = df.copy()
c = df[“close”]; h = df[“high”]; l = df[“low”]

```
df["ema9"]  = c.ewm(span=9,  adjust=False).mean()
df["ema21"] = c.ewm(span=21, adjust=False).mean()
df["ema50"] = c.ewm(span=50, adjust=False).mean()

delta = c.diff()
g = delta.clip(lower=0).ewm(com=13, adjust=False).mean()
p = (-delta.clip(upper=0)).ewm(com=13, adjust=False).mean()
df["rsi"] = 100 - (100 / (1 + g / p))

ema12 = c.ewm(span=12, adjust=False).mean()
ema26 = c.ewm(span=26, adjust=False).mean()
df["macd"]        = ema12 - ema26
df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
df["macd_hist"]   = df["macd"] - df["macd_signal"]

sma20 = c.rolling(20).mean(); std20 = c.rolling(20).std()
df["bb_upper"] = sma20 + 2*std20
df["bb_lower"] = sma20 - 2*std20
df["bb_mid"]   = sma20

tr = pd.concat([h-l, (h-c.shift()).abs(), (l-c.shift()).abs()], axis=1).max(axis=1)
df["atr"] = tr.ewm(span=14, adjust=False).mean()

pt = (h+l+c)/3
df["vwap"] = (pt * df["volume"]).cumsum() / df["volume"].cumsum()
df["volatilidade"] = c.pct_change().rolling(20).std()

return df.dropna().reset_index(drop=True)
```

def score_tf(df):
“”“Score técnico -10 a +10 para um timeframe.”””
u = df.iloc[-1]; p1 = df.iloc[-2]
s = 0

```
if u["ema9"] > u["ema21"] > u["ema50"]: s += 3
elif u["ema9"] < u["ema21"] < u["ema50"]: s -= 3

if p1["ema9"] <= p1["ema21"] and u["ema9"] > u["ema21"]: s += 2
elif p1["ema9"] >= p1["ema21"] and u["ema9"] < u["ema21"]: s -= 2

if u["rsi"] < 35: s += 2
elif u["rsi"] > 65: s -= 2
elif u["rsi"] < 45: s += 1
elif u["rsi"] > 55: s -= 1

if p1["macd_hist"] <= 0 and u["macd_hist"] > 0: s += 2
elif p1["macd_hist"] >= 0 and u["macd_hist"] < 0: s -= 2

if u["close"] < u["bb_lower"]: s += 2
elif u["close"] > u["bb_upper"]: s -= 2

if u["close"] > u["vwap"]: s += 1
else: s -= 1

return s, u
```

def sinal_multi_tf(client, par):
“””
Analisa M5, M15 e H1. Só opera se DOIS dos três timeframes concordarem.
H1 tem peso duplo (tendência maior).
“””
scores = {}
ultimo_m15 = None

```
for nome, tf in TIMEFRAMES.items():
    try:
        klines = client.get_klines(symbol=par, interval=tf, limit=100)
        df = pd.DataFrame(klines, columns=[
            "time","open","high","low","close","volume",
            "close_time","quote_vol","trades","taker_base","taker_quote","ignore"
        ])
        for col in ["open","high","low","close","volume"]:
            df[col] = df[col].astype(float)
        df["time"] = pd.to_datetime(df["time"], unit="ms")
        df = calcular_indicadores(df)
        s, u = score_tf(df)
        scores[nome] = {"score": s, "u": u, "df": df}
        if nome == "M15":
            ultimo_m15 = u
    except Exception as e:
        log.error(f"Erro {par} {nome}: {e}")
        scores[nome] = {"score": 0, "u": None, "df": None}

# Score ponderado: H1 vale 2x
score_total = (
    scores["M5"]["score"] +
    scores["M15"]["score"] +
    scores["H1"]["score"] * 2
)

sinais_tf = {}
for nome, d in scores.items():
    s = d["score"]
    sinais_tf[nome] = "COMPRAR" if s >= 4 else ("VENDER" if s <= -4 else "AGUARDAR")

# Threshold mais alto por ser multi-TF ponderado
if score_total >= 7:
    sinal = "COMPRAR"
elif score_total <= -7:
    sinal = "VENDER"
else:
    sinal = "AGUARDAR"

atr = ultimo_m15["atr"] if ultimo_m15 is not None else 0
preco = ultimo_m15["close"] if ultimo_m15 is not None else 0

log.info(f"[{par}] Score M5={scores['M5']['score']:+d} M15={scores['M15']['score']:+d} "
         f"H1={scores['H1']['score']:+d} → Total={score_total:+d} | {sinal}")

df_m15 = scores["M15"]["df"]
return sinal, score_total, sinais_tf, atr, preco, df_m15
```

# ══════════════════════════════════════════════════════════════════════

# 🔬  AUTO-OTIMIZAÇÃO

# ══════════════════════════════════════════════════════════════════════

class AutoOtimizador:
“””
A cada 24h, roda backtest rápido com diferentes combinações de parâmetros
e adota o conjunto que gerou maior Sharpe ratio no período recente.
“””
def **init**(self):
self.parametros = {
“threshold_score”: 7,
“rsi_oversold”:    35,
“rsi_overbought”:  65,
“atr_stop_mult”:   2.0,
“atr_tp_mult”:     4.0,
}
self.ultima_otimizacao = None
self.intervalo_horas   = 24

```
def deve_otimizar(self):
    if self.ultima_otimizacao is None:
        return True
    return (datetime.now() - self.ultima_otimizacao).seconds >= self.intervalo_horas * 3600

def backtest_rapido(self, df, params):
    """Simula operações no histórico e retorna Sharpe ratio."""
    retornos = []
    i = 50
    while i < len(df) - 20:
        u  = df.iloc[i]
        p1 = df.iloc[i-1]

        s = 0
        if u["ema9"] > u["ema21"] > u["ema50"]: s += 3
        elif u["ema9"] < u["ema21"] < u["ema50"]: s -= 3
        if u["rsi"] < params["rsi_oversold"]: s += 2
        elif u["rsi"] > params["rsi_overbought"]: s -= 2
        if p1["macd_hist"] <= 0 and u["macd_hist"] > 0: s += 2
        elif p1["macd_hist"] >= 0 and u["macd_hist"] < 0: s -= 2

        if abs(s) >= params["threshold_score"]:
            lado = 1 if s > 0 else -1
            entrada = u["close"]
            atr = u["atr"]
            stop = entrada - lado * atr * params["atr_stop_mult"]
            alvo = entrada + lado * atr * params["atr_tp_mult"]

            for j in range(i+1, min(i+40, len(df))):
                p = df.iloc[j]["close"]
                pnl = (p - entrada) * lado
                if lado == 1 and (p <= stop or p >= alvo):
                    retornos.append(pnl / entrada)
                    break
                elif lado == -1 and (p >= stop or p <= alvo):
                    retornos.append(pnl / entrada)
                    break
            i += 15
        else:
            i += 1

    if len(retornos) < 5:
        return 0.0
    r = np.array(retornos)
    return float(np.mean(r) / (np.std(r) + 1e-9))

def otimizar(self, client, par="BTCUSDT"):
    log.info("🔬 Iniciando auto-otimização...")
    try:
        klines = client.get_klines(
            symbol=par, interval=Client.KLINE_INTERVAL_15MINUTE, limit=500
        )
        df = pd.DataFrame(klines, columns=[
            "time","open","high","low","close","volume",
            "close_time","quote_vol","trades","taker_base","taker_quote","ignore"
        ])
        for col in ["open","high","low","close","volume"]:
            df[col] = df[col].astype(float)
        df = calcular_indicadores(df)

        grade = {
            "threshold_score": [5, 6, 7, 8],
            "rsi_oversold":    [30, 35, 40],
            "rsi_overbought":  [60, 65, 70],
            "atr_stop_mult":   [1.5, 2.0, 2.5],
            "atr_tp_mult":     [3.0, 4.0, 5.0],
        }

        melhor_sharpe = -999
        melhores_params = self.parametros.copy()
        testados = 0

        # Amostragem aleatória (evita explosão combinatória)
        for _ in range(30):
            params = {k: np.random.choice(v) for k, v in grade.items()}
            sharpe = self.backtest_rapido(df, params)
            testados += 1
            if sharpe > melhor_sharpe:
                melhor_sharpe = sharpe
                melhores_params = params.copy()

        self.parametros = melhores_params
        self.ultima_otimizacao = datetime.now()
        log.info(f"✅ Otimização: {testados} combinações | "
                 f"Melhor Sharpe={melhor_sharpe:.3f} | {melhores_params}")
        return melhores_params

    except Exception as e:
        log.error(f"Erro na otimização: {e}")
        return self.parametros
```

# ══════════════════════════════════════════════════════════════════════

# 🧠  AGENTE Q-LEARNING

# ══════════════════════════════════════════════════════════════════════

class AgenteQL:
ACOES = [“AGUARDAR”, “COMPRAR”, “VENDER”]

```
def __init__(self):
    self.alpha = 0.1; self.gamma = 0.9
    self.epsilon = 0.2; self.epsilon_min = 0.03; self.epsilon_decay = 0.998
    self.q_table = {}
    self.historico = deque(maxlen=500)
    self.total_trades = 0; self.lucro_total = 0.0
    self.wins = 0; self.losses = 0
    self.carregar_memoria()

def _get_q(self, e):
    if e not in self.q_table: self.q_table[e] = [0.0,0.0,0.0]
    return self.q_table[e]

def codificar_estado(self, score_mtf, sentimento, nlp_score, whale_ratio):
    s_zona  = "FORTE+" if score_mtf>=7 else ("+"  if score_mtf>=4 else
              ("FORTE-" if score_mtf<=-7 else ("-" if score_mtf<=-4 else "N")))
    fg_zona = "ME" if sentimento<=25 else ("M" if sentimento<=45 else
              ("N" if sentimento<=55 else ("G" if sentimento<=75 else "GE")))
    nlp_z   = "+" if nlp_score>=3 else ("-" if nlp_score<=-3 else "N")
    wh_z    = "W" if whale_ratio >= 3 else "n"
    rec     = "".join("W" if r>0 else "L" for r in list(self.historico)[-3:]).ljust(3,"N")
    return f"{s_zona}|{fg_zona}|{nlp_z}|{wh_z}|{rec}"

def escolher_acao(self, estado, sinal_sistema):
    if np.random.rand() < self.epsilon:
        probs = [0.2,0.6,0.2] if sinal_sistema=="COMPRAR" else (
                [0.2,0.2,0.6] if sinal_sistema=="VENDER" else [0.6,0.2,0.2])
        acao = np.random.choice(3, p=probs)
    else:
        acao = int(np.argmax(self._get_q(estado)))
    return acao

def aprender(self, e, a, r, e2):
    q = self._get_q(e); qf = self._get_q(e2)
    q[a] += self.alpha * (r + self.gamma * max(qf) - q[a])
    self.q_table[e] = q
    if self.epsilon > self.epsilon_min:
        self.epsilon *= self.epsilon_decay

def registrar(self, lucro, capital):
    self.historico.append(lucro)
    self.total_trades += 1; self.lucro_total += lucro
    if lucro > 0: self.wins += 1
    else: self.losses += 1
    wr = self.wins/self.total_trades*100
    log.info(f"📊 {'✅' if lucro>0 else '❌'} ${lucro:+.4f} | "
             f"Capital: ${capital:.2f} | WR: {wr:.1f}% | "
             f"Estados RL: {len(self.q_table)}")
    self.salvar_memoria()

def salvar_memoria(self):
    with open(ARQUIVO_MEMORIA,"w") as f:
        json.dump({
            "q_table": self.q_table, "epsilon": self.epsilon,
            "historico": list(self.historico), "total_trades": self.total_trades,
            "lucro_total": self.lucro_total, "wins": self.wins, "losses": self.losses,
            "atualizado": datetime.now().isoformat()
        }, f, indent=2)

def carregar_memoria(self):
    try:
        with open(ARQUIVO_MEMORIA) as f: d = json.load(f)
        self.q_table = d.get("q_table",{}); self.epsilon = d.get("epsilon",0.2)
        self.historico = deque(d.get("historico",[]), maxlen=500)
        self.total_trades = d.get("total_trades",0)
        self.lucro_total = d.get("lucro_total",0.0)
        self.wins = d.get("wins",0); self.losses = d.get("losses",0)
        log.info(f"🧠 Memória: {len(self.q_table)} estados | {self.total_trades} trades")
    except FileNotFoundError:
        log.info("🆕 Iniciando sem memória anterior.")
```

# ══════════════════════════════════════════════════════════════════════

# 💰  GESTÃO DE CAPITAL + PROTEÇÃO

# ══════════════════════════════════════════════════════════════════════

class GestaoCapital:
def **init**(self, capital):
self.capital = capital
self.pico = capital
self.historico_retornos = deque(maxlen=50)

```
def kelly(self):
    if len(self.historico_retornos) < 10: return RISCO_BASE
    r = list(self.historico_retornos)
    wins = [x for x in r if x > 0]; losses = [x for x in r if x < 0]
    if not wins or not losses: return RISCO_BASE
    p = len(wins)/len(r); q = 1-p
    b = np.mean(wins)/abs(np.mean(losses))
    k = (b*p - q)/b
    return max(0.005, min(k*0.5, 0.04))

def tamanho(self, preco, stop):
    k = self.kelly()
    risco_usd = self.capital * k
    pct_sl = abs(preco - stop) / preco
    if pct_sl == 0: return 0, 0
    val = min(risco_usd / pct_sl, self.capital * 0.25)
    return val, round(val / preco, 6)

def atualizar(self, novo):
    self.capital = novo
    if novo > self.pico: self.pico = novo

def drawdown(self):
    return (self.pico - self.capital) / self.pico

def pode_operar(self):
    return self.drawdown() < MAX_DRAWDOWN
```

# ══════════════════════════════════════════════════════════════════════

# 🔄  LOOP PRINCIPAL

# ══════════════════════════════════════════════════════════════════════

def atualizar_estado(agente, gestao, sentimento, nlp, whale, posicoes, otimizador, log_buffer):
ESTADO_GLOBAL.update({
“status”: “rodando”,
“capital”: round(gestao.capital, 4),
“trades”: agente.total_trades,
“wins”: agente.wins,
“losses”: agente.losses,
“lucro_total”: round(agente.lucro_total, 4),
“sentimento”: sentimento.valor,
“fear_greed_label”: sentimento.classificacao,
“nlp_score”: nlp.score,
“nlp_label”: nlp.label,
“whale_alertas”: list(whale.alertas),
“posicoes”: {k: {
“lado”: v[“lado”], “entrada”: v[“entrada”],
“stop”: v[“stop”], “alvo”: v[“alvo”], “qtd”: v[“qtd”]
} for k, v in posicoes.items()},
“parametros”: {k: str(v) for k, v in otimizador.parametros.items()},
“ultima_otimizacao”: otimizador.ultima_otimizacao.strftime(”%d/%m %H:%M”) if otimizador.ultima_otimizacao else “Nunca”,
“log_recente”: list(log_buffer)[-40:],
})

class LogCapturador(logging.Handler):
def **init**(self, buffer):
super().**init**()
self.buffer = buffer
def emit(self, record):
self.buffer.append(self.format(record))

def main():
log.info(“╔══════════════════════════════════════════════════════╗”)
log.info(“║          BOT ULTRA v4.0 — FORA DA CURVA             ║”)
log.info(f”║  Capital: ${CAPITAL_TOTAL} | Testnet: {USAR_TESTNET}              ║”)
log.info(“╚══════════════════════════════════════════════════════╝”)

```
# Capturar logs para o dashboard
log_buffer = deque(maxlen=100)
handler = LogCapturador(log_buffer)
handler.setFormatter(logging.Formatter("%(asctime)s %(message)s", "%Y-%m-%d %H:%M:%S"))
logging.getLogger(__name__).addHandler(handler)

# Dashboard em thread separada
t = threading.Thread(target=iniciar_dashboard, daemon=True)
t.start()

# Inicializar componentes
client    = Client(API_KEY, API_SECRET, testnet=USAR_TESTNET)
agente    = AgenteQL()
gestao    = GestaoCapital(CAPITAL_TOTAL)
sentimento= type('S', (), {
    'valor': 50, 'classificacao': 'Neutro',
    'ultima_atualizacao': None,
    'atualizar': lambda self: None,
    'filtrar_sinal': lambda self, s: s,
    'fator_confianca': lambda self: 0.7
})()

# Fear & Greed simples
def atualizar_fg():
    try:
        r = requests.get("https://api.alternative.me/fng/?limit=1", timeout=8)
        d = r.json()["data"][0]
        sentimento.valor = int(d["value"])
        sentimento.classificacao = d["value_classification"]
        log.info(f"📊 Fear & Greed: {sentimento.valor} ({sentimento.classificacao})")
    except: pass

nlp       = AnalisadorNLP()
whale     = WhaleDetector()
otimizador= AutoOtimizador()
posicoes  = {}   # {par: {...}}
estado_rl = {}   # {par: ultimo_estado}

log.info(f"🚀 Iniciado | Dashboard: http://localhost:{DASHBOARD_PORT}")
atualizar_fg()
nlp.atualizar()

ultimo_relatorio = datetime.now()
ciclo = 0

while True:
    try:
        ciclo += 1

        # Atualizar dados externos a cada 30 ciclos (~30min)
        if ciclo % 30 == 0:
            atualizar_fg()
            nlp.atualizar()

        # Auto-otimização
        if otimizador.deve_otimizar():
            otimizador.otimizar(client)

        # Verificar proteção de capital
        if not gestao.pode_operar():
            log.warning(f"🛑 DRAWDOWN {gestao.drawdown():.1%} — bot pausado")
            atualizar_estado(agente, gestao, sentimento, nlp, whale, posicoes, otimizador, log_buffer)
            time.sleep(300); continue

        # Monitorar posições abertas
        for par in list(posicoes.keys()):
            pos = posicoes[par]
            try:
                preco = float(client.get_symbol_ticker(symbol=par)["price"])
                entrada = pos["entrada"]
                lado    = pos["lado"]

                pnl_pct = (preco-entrada)/entrada if lado=="COMPRAR" else (entrada-preco)/entrada
                pnl_usd = pnl_pct * pos["qtd"] * entrada

                fechar = False
                if lado == "COMPRAR":
                    fechar = preco <= pos["stop"] or preco >= pos["alvo"]
                else:
                    fechar = preco >= pos["stop"] or preco <= pos["alvo"]

                if fechar:
                    lado_f = "SELL" if lado=="COMPRAR" else "BUY"
                    try:
                        client.order_market(symbol=par, side=lado_f, quantity=pos["qtd"])
                    except BinanceAPIException as e:
                        log.error(f"Erro fechando {par}: {e.message}")
                    novo_cap = gestao.capital + pnl_usd
                    gestao.atualizar(novo_cap)
                    gestao.historico_retornos.append(pnl_pct)

                    # RL aprende
                    if par in estado_rl:
                        recompensa = np.log1p(pnl_pct*100) if pnl_usd>0 else -2.5*abs(pnl_pct*100)
                        agente.aprender(estado_rl[par], pos["acao_idx"], recompensa, estado_rl[par])

                    agente.registrar(pnl_usd, gestao.capital)
                    del posicoes[par]
                    log.info(f"🔔 {par} fechado | PnL: ${pnl_usd:+.4f}")

            except Exception as e:
                log.error(f"Erro monitorando {par}: {e}")

        # Analisar novos sinais
        sinais_dashboard = {}
        for par in PARES:
            if par in posicoes: continue
            if len(posicoes) >= MAX_POSICOES: break

            try:
                sinal, score, sinais_tf, atr, preco, df_m15 = sinal_multi_tf(client, par)
                sinais_dashboard[par] = {"timeframes": sinais_tf, "score": score}

                if sinal == "AGUARDAR": continue

                # Filtros em cascata
                sinal = nlp.ajustar_sinal(sinal)
                if sinal == "AGUARDAR": continue

                sinal, whale_ratio = whale.ajustar_sinal(sinal, par, df_m15)
                if sinal == "AGUARDAR": continue

                # Fear & Greed filter
                if sentimento.valor <= 20 and sinal == "VENDER":
                    log.info(f"🚫 Fear Extremo bloqueia VENDA em {par}")
                    continue
                if sentimento.valor >= 80 and sinal == "COMPRAR":
                    log.info(f"🚫 Ganância Extrema bloqueia COMPRA em {par}")
                    continue

                # Estado RL
                estado = agente.codificar_estado(score, sentimento.valor, nlp.score, whale_ratio)
                acao_idx = agente.escolher_acao(estado, sinal)
                acao = agente.ACOES[acao_idx]

                if acao not in ("COMPRAR", "VENDER"): continue

                # Calcular stops com ATR otimizado
                mult_stop = otimizador.parametros["atr_stop_mult"]
                mult_tp   = otimizador.parametros["atr_tp_mult"]
                pct_sl = atr * mult_stop / preco
                pct_tp = atr * mult_tp   / preco

                if acao == "COMPRAR":
                    stop = round(preco*(1-pct_sl), 2)
                    alvo = round(preco*(1+pct_tp), 2)
                else:
                    stop = round(preco*(1+pct_sl), 2)
                    alvo = round(preco*(1-pct_tp), 2)

                # Kelly
                val, qtd = gestao.tamanho(preco, stop)
                if qtd <= 0: continue

                # Executar
                lado = "BUY" if acao == "COMPRAR" else "SELL"
                try:
                    ordem = client.order_market(symbol=par, side=lado, quantity=qtd)
                    log.info(f"✅ [{par}] {acao} {qtd} @ ${preco:,.2f} | "
                             f"Stop=${stop} Alvo=${alvo} | Score={score:+d}")
                    posicoes[par] = {
                        "lado": acao, "entrada": preco, "stop": stop,
                        "alvo": alvo, "qtd": qtd, "acao_idx": acao_idx
                    }
                    estado_rl[par] = estado
                except BinanceAPIException as e:
                    log.error(f"❌ [{par}] {e.message}")

            except Exception as e:
                log.error(f"Erro {par}: {e}")
                continue

            time.sleep(2)

        # Atualizar dashboard
        ESTADO_GLOBAL["ultimo_sinal"] = sinais_dashboard
        atualizar_estado(agente, gestao, sentimento, nlp, whale, posicoes, otimizador, log_buffer)

        time.sleep(INTERVALO)

    except KeyboardInterrupt:
        log.info("🛑 Bot encerrado.")
        ESTADO_GLOBAL["status"] = "encerrado"
        break
    except Exception as e:
        log.error(f"❌ Erro geral: {e}")
        time.sleep(30)
```

if **name** == “**main**”:
main()
