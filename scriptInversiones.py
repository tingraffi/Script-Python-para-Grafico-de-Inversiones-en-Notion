import requests
import matplotlib.pyplot as plt
import numpy as np
import re
from datetime import datetime
from matplotlib.ticker import FuncFormatter
import telebot
import schedule
import time
import threading
import pytz

# --- CONFIGURACIÓN ---
NOTION_TOKEN = '' 
DATABASE_ID = '' 
TELEGRAM_TOKEN = ''
CHAT_ID = ''

# SP-500 (CEDEAR SPY): referencia internacional via Yahoo Finance
SPY_YAHOO_TICKER = 'SPY'
SPY_CEDEAR_RATIO = 1
SPY_LOCAL_SYMBOLS = ['BCBA:SPY', 'BCBA:SPYD', 'BCBA:SPYC']
TRADINGVIEW_SCANNER_URL = 'https://scanner.tradingview.com/argentina/scan'

ZONA_HORARIA = pytz.timezone('America/Argentina/Buenos_Aires')
HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

bot = telebot.TeleBot(TELEGRAM_TOKEN)

def es_activo_sp500(nombre_activo):
    normalizado = re.sub(r'[^A-Z0-9]', '', (nombre_activo or '').upper())
    return 'SP500' in normalizado or 'SPY' in normalizado

def obtener_hora_local():
    return datetime.now(ZONA_HORARIA)

def obtener_precio_btc():
    url = "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT"
    respuesta = requests.get(url)
    return float(respuesta.json()['price'])


def obtener_precio_simbolo_binance(simbolo):
    url = f"https://api.binance.com/api/v3/ticker/price?symbol={simbolo}"
    respuesta = requests.get(url, timeout=10)
    if respuesta.status_code != 200:
        raise ValueError(f"Binance no devolvio precio para {simbolo}. Status: {respuesta.status_code}")
    data = respuesta.json()
    if 'price' not in data:
        raise ValueError(f"Respuesta invalida de Binance para {simbolo}: {data}")
    return float(data['price'])


def obtener_precio_spy_yahoo(ticker=SPY_YAHOO_TICKER):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1m&range=1d"
    respuesta = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
    if respuesta.status_code != 200:
        raise ValueError(f"Yahoo no devolvio precio para {ticker}. Status: {respuesta.status_code}")

    data = respuesta.json()
    resultado = ((data.get('chart') or {}).get('result') or [])
    if not resultado:
        raise ValueError(f"Respuesta invalida de Yahoo para {ticker}: {data}")

    meta = resultado[0].get('meta', {})
    precio = meta.get('regularMarketPrice')
    if precio is None:
        cierres = (((resultado[0].get('indicators') or {}).get('quote') or [{}])[0]).get('close') or []
        cierres_validos = [c for c in cierres if c is not None]
        if not cierres_validos:
            raise ValueError(f"Yahoo no devolvio close valido para {ticker}")
        precio = cierres_validos[-1]

    return float(precio)


def obtener_precio_local_tradingview(symbols=None):
    symbols = symbols or SPY_LOCAL_SYMBOLS
    body = {
        'symbols': {'tickers': symbols, 'query': {'types': []}},
        'columns': ['close']
    }
    respuesta = requests.post(TRADINGVIEW_SCANNER_URL, json=body, timeout=10)
    if respuesta.status_code != 200:
        raise ValueError(f"TradingView no devolvio precio local. Status: {respuesta.status_code}")

    data = respuesta.json()
    resultados = data.get('data') or []
    for row in resultados:
        valores = row.get('d') or []
        if valores and valores[0] is not None:
            return float(valores[0]), row.get('s', '')

    raise ValueError('TradingView no devolvio close valido para CEDEAR SPY')


def obtener_usdt_ars_binance_o_fallback():
    """Intenta usar USDTARS de Binance; si no existe, usa DolarAPI como respaldo."""
    try:
        return obtener_precio_simbolo_binance('USDTARS')
    except Exception:
        return obtener_dolar_cripto()

def obtener_dolar_cripto():
    url = "https://dolarapi.com/v1/dolares/cripto"
    respuesta = requests.get(url)
    return float(respuesta.json()['venta'])

def leer_inversiones_notion():
    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
    respuesta = requests.post(url, headers=HEADERS)
    if respuesta.status_code != 200: return []
    resultados = respuesta.json().get('results', [])
    inversiones = []
    for item in resultados:
        props = item['properties']
        activo = props['Activo']['select']['name'] if props.get('Activo', {}).get('select') else 'Desconocido'
        if props.get('Fecha', {}).get('date'):
            fecha_str = props['Fecha']['date']['start']
            fecha_inv = datetime.strptime(fecha_str, "%Y-%m-%d")
            inv_inicial = props.get('Inversion Inicial (ARS/USDT)', {}).get('number') or 0
            datos_inv = {'activo': activo, 'fecha': fecha_inv, 'inicial': inv_inicial}
            datos_inv['cotizacion_compra'] = props.get('Cotizacion de Compra', {}).get('number') or 0
            if activo == 'Bitcoin':
                datos_inv['cantidad'] = props.get('Cantidad Obtenida', {}).get('number') or 0
            elif es_activo_sp500(activo):
                datos_inv['cantidad'] = props.get('Cantidad Obtenida', {}).get('number') or 0
                # Nuevas columnas sugeridas en Notion para no depender de cantidad manual:
                # - "SPY Compra (USDT)": precio de SPYUSDT al momento de compra
                # - "USDT/ARS Compra": tipo de cambio USDTARS al momento de compra
                # - "Ratio CEDEAR SPY" (opcional): ratio usado en la compra
                datos_inv['spy_compra_usdt'] = props.get('SPY Compra (USDT)', {}).get('number') or 0
                datos_inv['usdt_ars_compra'] = props.get('USDT/ARS Compra', {}).get('number') or 0
                ratio_compra = props.get('Ratio CEDEAR SPY', {}).get('number')
                datos_inv['ratio_cedear_compra'] = ratio_compra if ratio_compra and ratio_compra > 0 else (SPY_CEDEAR_RATIO if SPY_CEDEAR_RATIO else 1)
            elif 'Frasco NaranjaX' in activo:
                datos_inv['tna'] = props.get('TNA (%)', {}).get('number') or 0
            inversiones.append(datos_inv)
    return inversiones

def procesar_datos(inversiones):
    if not inversiones:
        return [], 0, 0
    precio_btc = obtener_precio_btc()
    dolar_cripto = obtener_usdt_ars_binance_o_fallback()
    hoy = obtener_hora_local().replace(tzinfo=None)
    datos_agrupados = {}
    cache_precios = {}
    for inv in inversiones:
        valor_actual_ars = 0
        if inv['activo'] == 'Bitcoin':
            valor_actual_ars = (inv['cantidad'] * precio_btc) * dolar_cripto
        elif es_activo_sp500(inv['activo']):
            try:
                cantidad_sp = inv.get('cantidad', 0) or 0

                precio_cedear_local_ars = None
                fuente_local = ''
                clave_local = 'LOCAL_SPY'
                try:
                    if clave_local not in cache_precios:
                        precio_local, simbolo_local = obtener_precio_local_tradingview(SPY_LOCAL_SYMBOLS)
                        cache_precios[clave_local] = (precio_local, simbolo_local)
                    precio_cedear_local_ars, fuente_local = cache_precios[clave_local]
                except Exception:
                    precio_cedear_local_ars = None

                if cantidad_sp > 0:
                    if precio_cedear_local_ars is not None:
                        valor_actual_ars = cantidad_sp * precio_cedear_local_ars
                    else:
                        clave_spy = f"YAHOO_{SPY_YAHOO_TICKER}"
                        if clave_spy not in cache_precios:
                            cache_precios[clave_spy] = obtener_precio_spy_yahoo(SPY_YAHOO_TICKER)
                        precio_spy_actual_usd = cache_precios[clave_spy]
                        ratio = inv.get('ratio_cedear_compra', 0) or (SPY_CEDEAR_RATIO if SPY_CEDEAR_RATIO else 1)
                        precio_estimado_cedear_ars = (precio_spy_actual_usd / ratio) * dolar_cripto
                        valor_actual_ars = cantidad_sp * precio_estimado_cedear_ars
                else:
                    cotizacion_compra = inv.get('cotizacion_compra', 0) or 0
                    spy_compra_usdt = inv.get('spy_compra_usdt', 0) or 0
                    usdt_ars_compra = inv.get('usdt_ars_compra', 0) or 0
                    ratio_compra = inv.get('ratio_cedear_compra', 0) or (SPY_CEDEAR_RATIO if SPY_CEDEAR_RATIO else 1)

                    if cotizacion_compra > 0 and precio_cedear_local_ars is not None:
                        cantidad_implicita = inv['inicial'] / cotizacion_compra
                        valor_actual_ars = cantidad_implicita * precio_cedear_local_ars
                    elif spy_compra_usdt > 0 and usdt_ars_compra > 0:
                        clave_spy = f"YAHOO_{SPY_YAHOO_TICKER}"
                        if clave_spy not in cache_precios:
                            cache_precios[clave_spy] = obtener_precio_spy_yahoo(SPY_YAHOO_TICKER)
                        precio_spy_actual_usd = cache_precios[clave_spy]
                        # Reconstruye cantidad implicita desde ARS inicial y datos de compra.
                        precio_compra_cedear_ars = (spy_compra_usdt / ratio_compra) * usdt_ars_compra
                        cantidad_implicita = inv['inicial'] / precio_compra_cedear_ars if precio_compra_cedear_ars > 0 else 0

                        precio_actual_cedear_ars = (precio_spy_actual_usd / ratio_compra) * dolar_cripto
                        valor_actual_ars = cantidad_implicita * precio_actual_cedear_ars
                    else:
                        # Sin cantidad ni precios de compra, no puede estimarse rendimiento real.
                        valor_actual_ars = inv['inicial']
            except Exception:
                # Si falla la cotizacion, no rompe el dashboard.
                valor_actual_ars = inv['inicial']
        elif 'Frasco NaranjaX' in inv['activo']:
            dias_pasados = max(0, (hoy - inv['fecha']).days)
            interes = inv['inicial'] * (inv['tna'] / 100) * (dias_pasados / 365)
            valor_actual_ars = inv['inicial'] + interes
        ganancia = valor_actual_ars - inv['inicial']
        activo = inv['activo']
        if activo not in datos_agrupados:
            datos_agrupados[activo] = {'nombre_corto': activo, 'inicial': 0, 'actual': 0, 'ganancia': 0, 'fecha_min': inv['fecha']}
        datos_agrupados[activo]['inicial'] += inv['inicial']
        datos_agrupados[activo]['actual'] += valor_actual_ars
        datos_agrupados[activo]['ganancia'] += ganancia
    
    datos_procesados = []
    for activo, data in datos_agrupados.items():
        pct = (data['ganancia'] / data['inicial'] * 100) if data['inicial'] > 0 else 0
        datos_procesados.append({
            'nombre': f"{activo}\n({data['fecha_min'].strftime('%m/%Y')})",
            'nombre_corto': activo,
            'fecha_min': data['fecha_min'],
            'inicial': data['inicial'],
            'actual': data['actual'],
            'ganancia': data['ganancia'],
            'pct': pct
        })
    return datos_procesados, precio_btc, dolar_cripto

def generar_dashboard(datos, precio_btc, dolar_cripto):
    plt.rcParams.update({'font.size': 12})
    formato_ars = FuncFormatter(lambda valor, _: f"${valor:,.0f}")
    def formato_miles(valor): return f"${valor:,.1f}k"
    
    nombres = []
    for d in datos:
        if d['nombre_corto'] == 'Bitcoin':
            nombres.append(
                f"Bitcoin\nBTC: US${precio_btc:,.0f} | ARS {dolar_cripto:,.0f}\n({d['fecha_min'].strftime('%m/%Y')})"
            )
        else:
            nombres.append(f"{d['nombre_corto']}\n({d['fecha_min'].strftime('%m/%Y')})")
    iniciales = [d['inicial'] for d in datos]; actuales = [d['actual'] for d in datos]
    total_inv = sum(iniciales); total_act = sum(actuales)
    
    fig = plt.figure(figsize=(16, 11))
    fig.subplots_adjust(left=0.06, right=0.98)
    gs = fig.add_gridspec(2, 1, height_ratios=[0.7, 1.5], hspace=0.3)
    fig.suptitle(f"Dashboard de Inversiones | Actualizado: {obtener_hora_local().strftime('%d/%m/%Y %H:%M')}", fontsize=20, fontweight='bold')
    
    # 1. Rendimiento por Activo
    ax1 = fig.add_subplot(gs[0, 0])
    x = np.arange(len(nombres)); width = 0.35
    bars_inicial = ax1.bar(x - width/2, iniciales, width, color='#ced4da', label='Inversión Inicial')
    bars = ax1.bar(x + width/2, actuales, width, color=['#2ecc71' if d['actual'] >= d['inicial'] else '#e74c3c' for d in datos], label='Valor Actual')
    offset_top = 15000
    ax1.set_ylim(0, 1000000)
    ax1.yaxis.set_major_formatter(formato_ars); ax1.set_xticks(x); ax1.set_xticklabels(nombres); ax1.legend()
    for bar in bars_inicial:
        y = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2, y + offset_top, f"${y:,.0f}", ha='center', va='bottom', fontweight='bold', color='#495057')
    for i, bar in enumerate(bars):
        y = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2, y + offset_top, f"${y:,.0f}\n({'+' if datos[i]['pct'] >= 0 else ''}{datos[i]['pct']:.2f}%)", ha='center', va='bottom', fontweight='bold')

    # Subgrids de abajo
    gs_bottom = gs[1, 0].subgridspec(1, 2, width_ratios=[0.95, 1.05], wspace=0.22)
    
    # 2. Composición
    ax2 = fig.add_subplot(gs_bottom[0, 0])
    valores_comp = [d['actual'] if d['actual'] > 0 else d['inicial'] for d in datos if (d['actual'] > 0 or d['inicial'] > 0)]
    etiquetas_comp = [d['nombre_corto'] for d in datos if (d['actual'] > 0 or d['inicial'] > 0)]
    ax2.pie(valores_comp, labels=etiquetas_comp, autopct='%1.1f%%', startangle=90, center=(-0.75, 0), colors=['#F7931A', '#FF5A00', '#3498db', '#9b59b6'], wedgeprops=dict(width=0.4))
    ax2.set_title('Composición del Portafolio')

    # 3. Derecha (Variaciones + Cascada)
    gs_derecha = gs_bottom[0, 1].subgridspec(2, 1, height_ratios=[0.8, 1], hspace=0.5)
    
    # VARIACIONES POR ACTIVO
    ax_var = fig.add_subplot(gs_derecha[0])
    datos_ord = sorted(datos, key=lambda x: abs(x['ganancia']), reverse=True)
    y_pos = np.arange(len(datos_ord))
    ax_var.barh(y_pos, [d['ganancia']/1000 for d in datos_ord], color=['#2ecc71' if d['ganancia'] >= 0 else '#e74c3c' for d in datos_ord])
    ax_var.set_yticks(y_pos); ax_var.set_yticklabels([d['nombre_corto'] for d in datos_ord]); ax_var.axvline(0, color='grey', lw=1)
    min_gain_k = min([d['ganancia']/1000 for d in datos_ord] + [0])
    max_gain_k = max([d['ganancia']/1000 for d in datos_ord] + [0])
    margen_k = max((max_gain_k - min_gain_k) * 0.12, 1)
    ax_var.set_xlim(min_gain_k - margen_k, max_gain_k + margen_k)
    
    ax_var.xaxis.set_major_formatter(FuncFormatter(lambda v, _: formato_miles(v))); ax_var.set_title('Variaciones por Activo')
    for i, d in enumerate(datos_ord):
        ax_var.text(d['ganancia']/1000, i, f" {'+' if d['ganancia'] >= 0 else ''}${d['ganancia']/1000:,.2f}k", va='center', fontweight='bold')

    # CONSTRUCCIÓN CAPITAL
    ax3 = fig.add_subplot(gs_derecha[1])
    cat_cascada = ['Inversión\nInicial'] + [d['nombre_corto'] for d in datos] + ['Capital\nTotal']
    val_cascada = [total_inv] + [d['ganancia'] for d in datos] + [total_act]
    bottoms = [0]; curr = total_inv
    for d in datos:
        bottoms.append(curr if d['ganancia'] >= 0 else curr + d['ganancia'])
        curr += d['ganancia']
    bottoms.append(0)
    bars_cascada = ax3.bar(cat_cascada, val_cascada, bottom=bottoms, color=['#34495e'] + ['#2ecc71' if d['ganancia'] >= 0 else '#e74c3c' for d in datos] + ['#3498db'])
    offset_cascada = 15000
    ax3.set_ylim(0, 1000000); ax3.yaxis.set_major_formatter(formato_ars); ax3.set_title('Construcción del Capital')

    # Etiquetas en todas las columnas para ver montos de BTC/NaranjaX/SP-500.
    for idx in range(len(val_cascada)):
        bar = bars_cascada[idx]
        y_top = bottoms[idx] + val_cascada[idx]
        y_label = y_top + offset_cascada if val_cascada[idx] >= 0 else bottoms[idx] + offset_cascada
        ax3.text(
            bar.get_x() + bar.get_width() / 2,
            y_label,
            f"${val_cascada[idx]:,.0f}",
            ha='center',
            va='bottom',
            fontweight='bold'
        )

    plt.savefig('dashboard_inversiones.png', dpi=300, bbox_inches='tight')
    plt.close()

def generar_y_enviar_reporte(destino_id):
    try:
        inv = leer_inversiones_notion()
        if not inv: return
        datos, btc, usdt = procesar_datos(inv)
        generar_dashboard(datos, btc, usdt)
        total_inv = sum(d['inicial'] for d in datos); total_act = sum(d['actual'] for d in datos)
        ratio_spy = SPY_CEDEAR_RATIO if SPY_CEDEAR_RATIO else 1
        resumen = (f"🚀 *Reporte de Inversiones*\n\n💰 *Invertido:* ${total_inv:,.0f} ARS\n📈 *Valor Actual:* ${total_act:,.0f} ARS\n"
                   f"💵 *Ganancia:* ${total_act-total_inv:,.0f} ARS\n"
                   f"📌 _SP-500: precio local CEDEAR (TradingView/BCBA) con fallback Yahoo {SPY_YAHOO_TICKER}. Ratio ref {ratio_spy}_\n\n"
                   f"📅 _Hora Local: {obtener_hora_local().strftime('%H:%M')}_")
        with open('dashboard_inversiones.png', 'rb') as f:
            bot.send_photo(destino_id, f, caption=resumen, parse_mode='Markdown')
    except Exception as e: print(f"Error: {e}")

@bot.message_handler(commands=['dashboard', 'reporte'])
def comando_dashboard(message):
    bot.reply_to(message, "⏳ Generando dashboard completo...")
    generar_y_enviar_reporte(message.chat.id)

def programador():
    schedule.every().day.at("09:00").do(lambda: generar_y_enviar_reporte(CHAT_ID))
    while True:
        schedule.run_pending(); time.sleep(1)

if __name__ == '__main__':
    threading.Thread(target=programador, daemon=True).start()
    print(f"🤖 Bot iniciado. Hora local: {obtener_hora_local().strftime('%H:%M')}")
    print("📤 Generando reporte inicial para validar que el bot responde desde la consola...")
    generar_y_enviar_reporte(CHAT_ID)
    bot.infinity_polling()