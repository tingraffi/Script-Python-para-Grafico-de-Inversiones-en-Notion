import requests
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime
from matplotlib.ticker import FuncFormatter

# --- CONFIGURACIÓN ---
NOTION_TOKEN = '' 
DATABASE_ID = '' 
TELEGRAM_TOKEN = ''
CHAT_ID = ''
HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

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
    
    if respuesta.status_code != 200:
        print(f"❌ ERROR DE CONEXIÓN: {respuesta.status_code}")
        return []
        
    resultados = respuesta.json().get('results', [])
    inversiones = []
    
    for item in resultados:
        props = item['properties']
        activo = props['Activo']['select']['name'] if props.get('Activo', {}).get('select') else 'Desconocido'
        
        if props.get('Fecha', {}).get('date'):
            fecha_str = props['Fecha']['date']['start']
            fecha_inv = datetime.strptime(fecha_str, "%Y-%m-%d")
        else:
            continue 
            
        inv_inicial = props.get('Inversion Inicial (ARS/USDT)', {}).get('number') or 0
        
        datos_inv = {
            'activo': activo,
            'fecha': fecha_inv,
            'inicial': inv_inicial,
        }
        
        if activo == 'Bitcoin':
            datos_inv['cantidad'] = props.get('Cantidad Obtenida', {}).get('number') or 0
        elif 'Frasco NaranjaX' in activo:
            datos_inv['tna'] = props.get('TNA (%)', {}).get('number') or 0
            
        inversiones.append(datos_inv)
        
    return inversiones

def procesar_datos(inversiones):
    if not inversiones:
        return []
        
    precio_btc = obtener_precio_btc()
    dolar_cripto = obtener_dolar_cripto()
    hoy = datetime.now()
    
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
            datos_agrupados[activo] = {
                'nombre_corto': activo,
                'inicial': 0,
                'actual': 0,
                'ganancia': 0,
                'fecha_min': inv['fecha'],
                'fecha_max': inv['fecha'],
                'cantidad_operaciones': 0
            }

        datos_agrupados[activo]['inicial'] += inv['inicial']
        datos_agrupados[activo]['actual'] += valor_actual_ars
        datos_agrupados[activo]['ganancia'] += ganancia
        datos_agrupados[activo]['fecha_min'] = min(datos_agrupados[activo]['fecha_min'], inv['fecha'])
        datos_agrupados[activo]['fecha_max'] = max(datos_agrupados[activo]['fecha_max'], inv['fecha'])
        datos_agrupados[activo]['cantidad_operaciones'] += 1

    datos_procesados = []
    for activo, data in datos_agrupados.items():
        pct = (data['ganancia'] / data['inicial'] * 100) if data['inicial'] > 0 else 0

        if data['cantidad_operaciones'] == 1:
            fecha_label = data['fecha_min'].strftime("%m/%Y")
        else:
            fecha_inicio = data['fecha_min'].strftime("%m/%Y")
            fecha_fin = data['fecha_max'].strftime("%m/%Y")
            fecha_label = f"{fecha_inicio}-{fecha_fin}" if fecha_inicio != fecha_fin else fecha_inicio

        nombre_etiqueta = f"{activo}\n({fecha_label})"

        datos_procesados.append({
            'nombre': nombre_etiqueta,
            'nombre_corto': activo,
            'fecha_label': fecha_label,
            'inicial': data['inicial'],
            'actual': data['actual'],
            'ganancia': data['ganancia'],
            'pct': pct
        })
        
    return datos_procesados, precio_btc, dolar_cripto

def generar_dashboard(datos, precio_btc, dolar_cripto):
    if not datos:
        return

    plt.rcParams.update({
        'font.size': 13,
        'axes.titlesize': 17,
        'axes.labelsize': 14,
        'xtick.labelsize': 13,
        'ytick.labelsize': 13,
        'legend.fontsize': 13
    })

    formato_ars = FuncFormatter(lambda valor, _: f"${valor:,.0f}")

    def formato_miles(valor):
        return f"${valor:,.0f}k" if abs(valor) >= 1 else f"${valor:,.2f}k"
        
    nombres = [d['nombre'] for d in datos]
    iniciales = [d['inicial'] for d in datos]
    actuales = [d['actual'] for d in datos]
    
    total_invertido = sum(iniciales)
    total_actual = sum(actuales)
    total_ganado = total_actual - total_invertido
    
    fig = plt.figure(figsize=(16, 10))
    gs = fig.add_gridspec(2, 1, height_ratios=[0.72, 1.48], hspace=0.26)
    fig.suptitle(f"Dashboard de Inversiones | Actualizado: {datetime.now().strftime('%d/%m/%Y %H:%M')}", fontsize=22, fontweight='bold')
    
    ax1 = fig.add_subplot(gs[0, 0])
    x = np.arange(len(nombres))
    width = 0.35
    
    ax1.bar(x - width/2, iniciales, width, color='#ced4da', label='Inversión Inicial')
    colores_actual = ['#2ecc71' if d['actual'] >= d['inicial'] else '#e74c3c' for d in datos]
    bars_actual = ax1.bar(x + width/2, actuales, width, color=colores_actual, label='Valor Actual')
    
    ax1.set_ylabel('Pesos Argentinos (ARS)')
    ax1.set_title('Rendimiento por Activo', pad=15)
    ax1.set_xticks(x)
    etiquetas_x = []
    for d in datos:
        if d['nombre_corto'] == 'Bitcoin':
            etiquetas_x.append(f"Bitcoin\nBTC: US${precio_btc:,.0f} | ARS ${dolar_cripto:,.0f}\n({d['fecha_label']})")
        else:
            etiquetas_x.append(d['nombre'])
    ax1.set_xticklabels(etiquetas_x)
    ax1.tick_params(axis='x', labelsize=13)
    ax1.yaxis.set_major_formatter(formato_ars)
    ax1.legend()
    ax1.set_ylim(0, max(actuales + iniciales) * 1.25)
    
    for i, bar in enumerate(bars_actual):
        yval = bar.get_height()
        pct = datos[i]['pct']
        signo = "+" if pct >= 0 else ""
        texto = f"${yval:,.0f}\n({signo}{pct:.1f}%)"
        ax1.text(bar.get_x() + bar.get_width()/2, yval + (max(actuales)*0.02), texto, ha='center', va='bottom', fontweight='bold', fontsize=13)

    gs_bottom = gs[1, 0].subgridspec(1, 2, width_ratios=[0.8, 1.2], wspace=0.30)
    ax2 = fig.add_subplot(gs_bottom[0, 0])
    act_validos = [d['actual'] for d in datos if d['actual'] > 0]
    nom_validos = [d['nombre_corto'] for d in datos if d['actual'] > 0]
    
    wedges, texts, autotexts = ax2.pie(act_validos, labels=nom_validos, autopct='%1.1f%%', startangle=90, 
                                       colors=['#F7931A', '#FF5A00', '#3498db', '#9b59b6'],
                                       wedgeprops=dict(width=0.4, edgecolor='w'))
    plt.setp(texts, fontsize=14)
    plt.setp(autotexts, fontsize=13, fontweight='bold')
    ax2.set_title('Composición del Portafolio')
    
    gs_derecha = gs_bottom[0, 1].subgridspec(2, 1, height_ratios=[0.72, 1], hspace=0.62)
    ax3_zoom = fig.add_subplot(gs_derecha[0])
    ax3 = fig.add_subplot(gs_derecha[1])
    
    cat_cascada = ['Inversión\nInicial'] + [d['nombre_corto'] for d in datos] + ['Capital\nTotal']
    val_cascada = [total_invertido] + [d['ganancia'] for d in datos] + [total_actual]
    
    bottoms = [0]
    current = total_invertido
    for d in datos:
        bottoms.append(current if d['ganancia'] >= 0 else current + d['ganancia'])
        current += d['ganancia']
    bottoms.append(0) 
    
    colores_cascada = ['#34495e'] + ['#2ecc71' if d['ganancia'] >= 0 else '#e74c3c' for d in datos] + ['#3498db']
    bars_cascada = ax3.bar(cat_cascada, val_cascada, bottom=bottoms, color=colores_cascada)
    ax3.set_title('Construcción del Capital (Ganancias/Pérdidas)')
    ax3.set_ylabel('Pesos Argentinos (ARS)')
    ax3.set_ylim(0, 1_000_000)
    ax3.yaxis.set_major_formatter(formato_ars)

    valores_acumulados = [total_invertido]
    capital_acumulado = total_invertido
    for d in datos:
        capital_acumulado += d['ganancia']
        valores_acumulados.append(capital_acumulado)
    valores_acumulados.append(total_actual)

    posiciones_cascada = np.arange(len(cat_cascada))
    ax3.plot(posiciones_cascada, valores_acumulados, color='#7f8c8d', marker='o', linewidth=1.0, markersize=4, zorder=4)
    
    for i, bar in enumerate(bars_cascada):
        if i == 0 or i == len(bars_cascada) - 1:
            yval = bar.get_height()
            ax3.text(bar.get_x() + bar.get_width()/2, yval + 22000, f"${yval:,.0f}", ha='center', va='bottom', fontweight='bold', fontsize=14)
        else: 
            yval = bar.get_height()
            ypos = bottoms[i] + yval/2 
            signo = "+" if yval >= 0 else ""
            ax3.text(bar.get_x() + bar.get_width()/2, ypos, f"{signo}${yval:,.0f}", ha='center', va='center', color='white', fontweight='bold', fontsize=12)

    ganancias = [d['ganancia'] for d in datos]
    if ganancias:
        datos_ordenados = sorted(datos, key=lambda item: abs(item['ganancia']), reverse=True)
        nombres_zoom = [d['nombre_corto'] for d in datos_ordenados]
        ganancias_zoom = [d['ganancia'] / 1000 for d in datos_ordenados] 
        colores_zoom = ['#2ecc71' if valor >= 0 else '#e74c3c' for valor in ganancias_zoom]
        y_pos = np.arange(len(nombres_zoom))
        barras_zoom = ax3_zoom.barh(y_pos, ganancias_zoom, color=colores_zoom)
        ax3_zoom.set_yticks(y_pos)
        ax3_zoom.set_yticklabels(nombres_zoom)
        ax3_zoom.axvline(0, color='#7f8c8d', linewidth=1)
        max_variacion = max(abs(valor) for valor in ganancias_zoom)
        margen_zoom = max(0.5, max_variacion * 0.30)
        ax3_zoom.set_xlim(min(ganancias_zoom) - margen_zoom, max(ganancias_zoom) + margen_zoom)
        ax3_zoom.set_title('Variaciones por Activo', fontsize=15)
        ax3_zoom.tick_params(axis='x', labelsize=12)
        ax3_zoom.tick_params(axis='y', labelsize=13)
        ax3_zoom.xaxis.set_major_formatter(FuncFormatter(lambda valor, _: formato_miles(valor)))
        ax3_zoom.grid(axis='x', linestyle='--', linewidth=0.6, alpha=0.35)
        ax3_zoom.set_xlabel('Miles de Pesos Argentinos (ARS)', fontsize=12)

        for barra, ganancia in zip(barras_zoom, ganancias_zoom):
            signo = "+" if ganancia >= 0 else ""
            offset = max(0.12, margen_zoom * 0.08)
            offset = offset if ganancia >= 0 else -offset
            ha = 'left' if ganancia >= 0 else 'right'
            ax3_zoom.text(
                ganancia + offset,
                barra.get_y() + barra.get_height()/2,
                f"{signo}{formato_miles(ganancia)}",
                ha=ha,
                va='center',
                fontsize=12,
                fontweight='bold'
            )
    else:
        ax3_zoom.axis('off')

    fig.subplots_adjust(top=0.91, bottom=0.13)
    plt.savefig('dashboard_inversiones.png', dpi=300, bbox_inches='tight')
    print("✅ ¡Dashboard generado con éxito!")

def enviar_a_telegram(archivo_path, texto):
    """Envía la imagen generada y un resumen por Telegram."""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    try:
        with open(archivo_path, 'rb') as photo:
            payload = {'chat_id': CHAT_ID, 'caption': texto, 'parse_mode': 'Markdown'}
            files = {'photo': photo}
            res = requests.post(url, data=payload, files=files)
            if res.status_code == 200:
                print("✅ Dashboard enviado a Telegram correctamente")
            else:
                print(f"❌ Error de Telegram: {res.text}")
    except Exception as e:
        print(f"❌ Error al enviar: {e}")

# =========================================================
# ÚNICO BLOQUE DE EJECUCIÓN PRINCIPAL
# =========================================================
if __name__ == '__main__':
    print("Conectando con Notion y APIs...")
    inversiones = leer_inversiones_notion()
    
    if inversiones:
        print("Procesando datos y calculando rendimientos...")
        datos_procesados, p_btc, p_usdt = procesar_datos(inversiones)
        print("Dibujando gráficos...")
        generar_dashboard(datos_procesados, p_btc, p_usdt)
        
        # Generar texto de resumen para el mensaje
        total_inv = sum(d['inicial'] for d in datos_procesados)
        total_act = sum(d['actual'] for d in datos_procesados)
        ganancia_total = total_act - total_inv
        pct_ganancia = (ganancia_total / total_inv * 100) if total_inv > 0 else 0
        
        resumen = (
            f"🚀 *Reporte Diario de Inversiones*\n\n"
            f"💰 *Invertido:* ${total_inv:,.0f} ARS\n"
            f"📈 *Valor Actual:* ${total_act:,.0f} ARS\n"
            f"💵 *Ganancia:* ${ganancia_total:,.0f} ARS "
            f"({pct_ganancia:.1f}%)\n\n"
            f"📅 _Actualizado: {datetime.now().strftime('%d/%m/%Y %H:%M')}_"
        )
        
        print("Enviando a Telegram...")
        enviar_a_telegram('dashboard_inversiones.png', resumen)
        print("Proceso finalizado con éxito.")