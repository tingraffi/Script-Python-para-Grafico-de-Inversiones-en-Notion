import requests
import matplotlib.pyplot as plt
import numpy as np
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

ZONA_HORARIA = pytz.timezone('America/Argentina/Buenos_Aires')
HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

bot = telebot.TeleBot(TELEGRAM_TOKEN)

def obtener_hora_local():
    return datetime.now(ZONA_HORARIA)

def obtener_precio_btc():
    url = "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT"
    respuesta = requests.get(url)
    return float(respuesta.json()['price'])

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
            if activo == 'Bitcoin':
                datos_inv['cantidad'] = props.get('Cantidad Obtenida', {}).get('number') or 0
            elif 'Frasco NaranjaX' in activo:
                datos_inv['tna'] = props.get('TNA (%)', {}).get('number') or 0
            inversiones.append(datos_inv)
    return inversiones

def procesar_datos(inversiones):
    if not inversiones: return []
    precio_btc = obtener_precio_btc(); dolar_cripto = obtener_dolar_cripto()
    hoy = obtener_hora_local().replace(tzinfo=None)
    datos_agrupados = {}
    for inv in inversiones:
        valor_actual_ars = 0
        if inv['activo'] == 'Bitcoin':
            valor_actual_ars = (inv['cantidad'] * precio_btc) * dolar_cripto
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
    gs = fig.add_gridspec(2, 1, height_ratios=[0.7, 1.5], hspace=0.3)
    fig.suptitle(f"Dashboard de Inversiones | Actualizado: {obtener_hora_local().strftime('%d/%m/%Y %H:%M')}", fontsize=20, fontweight='bold')
    
    # 1. Rendimiento por Activo
    ax1 = fig.add_subplot(gs[0, 0])
    x = np.arange(len(nombres)); width = 0.35
    ax1.bar(x - width/2, iniciales, width, color='#ced4da', label='Inversión Inicial')
    bars = ax1.bar(x + width/2, actuales, width, color=['#2ecc71' if d['actual'] >= d['inicial'] else '#e74c3c' for d in datos], label='Valor Actual')
    ax1.set_ylim(0, 1000000); ax1.yaxis.set_major_formatter(formato_ars); ax1.set_xticks(x); ax1.set_xticklabels(nombres); ax1.legend()
    for i, bar in enumerate(bars):
        y = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2, y + 15000, f"${y:,.0f}\n({'+' if datos[i]['pct'] >= 0 else ''}{datos[i]['pct']:.1f}%)", ha='center', va='bottom', fontweight='bold')

    # Subgrids de abajo
    gs_bottom = gs[1, 0].subgridspec(1, 2, width_ratios=[0.8, 1.2], wspace=0.3)
    
    # 2. Composición
    ax2 = fig.add_subplot(gs_bottom[0, 0])
    ax2.pie([d['actual'] for d in datos if d['actual'] > 0], labels=[d['nombre_corto'] for d in datos if d['actual'] > 0], autopct='%1.1f%%', startangle=90, colors=['#F7931A', '#FF5A00', '#3498db', '#9b59b6'], wedgeprops=dict(width=0.4))
    ax2.set_title('Composición del Portafolio')

    # 3. Derecha (Variaciones + Cascada)
    gs_derecha = gs_bottom[0, 1].subgridspec(2, 1, height_ratios=[0.8, 1], hspace=0.5)
    
    # VARIACIONES POR ACTIVO
    ax_var = fig.add_subplot(gs_derecha[0])
    datos_ord = sorted(datos, key=lambda x: abs(x['ganancia']), reverse=True)
    y_pos = np.arange(len(datos_ord))
    ax_var.barh(y_pos, [d['ganancia']/1000 for d in datos_ord], color=['#2ecc71' if d['ganancia'] >= 0 else '#e74c3c' for d in datos_ord])
    ax_var.set_yticks(y_pos); ax_var.set_yticklabels([d['nombre_corto'] for d in datos_ord]); ax_var.axvline(0, color='grey', lw=1)
    
    # --- CAMBIO AQUÍ: Escala X de 0 a 100k ---
    ax_var.set_xlim(0, 100) # El eje está en miles (k), por lo que 100 = 100k
    
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
    ax3.set_ylim(0, 1000000); ax3.yaxis.set_major_formatter(formato_ars); ax3.set_title('Construcción del Capital')

    # Etiquetas sobre Inversión Inicial y Capital Total
    indices_destacados = [0, len(val_cascada) - 1]
    for idx in indices_destacados:
        bar = bars_cascada[idx]
        y_top = bottoms[idx] + val_cascada[idx]
        ax3.text(
            bar.get_x() + bar.get_width() / 2,
            y_top + 15000,
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
        resumen = (f"🚀 *Reporte de Inversiones*\n\n💰 *Invertido:* ${total_inv:,.0f} ARS\n📈 *Valor Actual:* ${total_act:,.0f} ARS\n"
                   f"💵 *Ganancia:* ${total_act-total_inv:,.0f} ARS\n\n📅 _Hora Local: {obtener_hora_local().strftime('%H:%M')}_")
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
    bot.infinity_polling()