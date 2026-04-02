# 📈 Notion & Telegram Investment Dashboard

Un bot automatizado en Python que extrae el registro de inversiones desde una base de datos de Notion, cruza los datos con cotizaciones en tiempo real y **te envía un reporte gráfico actualizado directamente a tu Telegram**.

Ideal para automatizar el seguimiento de finanzas personales, calculando tanto rendimientos de interés simple (ej. cuentas remuneradas) como el valor en vivo de criptomonedas, todo unificado en Pesos Argentinos (ARS). Preparado para correr 24/7 en una Raspberry Pi o cualquier servidor usando Docker.

## ✨ Características

- **🤖 Bot de Telegram Integrado:**
  - Recibí un reporte diario automático todos los días a las 09:00 AM.
  - Pedile el gráfico en tiempo real al bot usando los comandos `/dashboard` o `/reporte`.
- **📊 Integración con Notion API:** Lee dinámicamente tu portafolio directamente desde tu workspace.
- **⏱️ Cotizaciones en Tiempo Real:**
  - Conexión a la API de Binance para extraer el precio de BTC/USDT.
   - Conexión a Yahoo Finance para tomar la referencia internacional de SPY/CEDEAR.
   - Conexión a TradingView como fuente local para CEDEARs argentinos cuando está disponible.
   - Conexión a DolarAPI como respaldo para obtener la cotización actual del Dólar Cripto en Argentina.
- **🧮 Cálculo de Rendimientos:** Computa automáticamente los intereses generados por días transcurridos según la TNA configurada.
- **🧾 Soporte CEDEAR / SPY:** Valúa posiciones de SP-500/CEDEAR usando precio internacional y tipo de cambio, con fallback seguro si falla alguna fuente.
- **🐳 Docker Ready:** Configurado para ejecutarse de forma continua y ligera en segundo plano (ideal para Raspberry Pi).

---

## 🚀 Instalación y Uso (Local)

1. **Cloná este repositorio:**
   ```bash
   git clone https://github.com/tingraffi/notion-investment-dashboard.git
   cd notion-investment-dashboard
   ```

2. **Instalá las dependencias necesarias:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configuración de Notion y Telegram:**
   - **Notion:** Creá una integración interna en [Notion Developers](https://developers.notion.com), obtené tu *Internal Integration Secret* y compartí tu base de datos de Inversiones con la integración.
   - **Telegram:** Hablá con `@BotFather` en Telegram para crear un bot y obtener el Token API. Luego, usá `@userinfobot` para obtener tu Chat ID.

4. **Configuración del Script:**
   Abrí `scriptInversiones.py` y reemplazá las variables con tus credenciales:
   ```python
   NOTION_TOKEN = 'tu_secreto_notion'
   DATABASE_ID = 'tu_id_de_base_de_datos'
   TELEGRAM_TOKEN = 'tu_token_de_telegram'
   CHAT_ID = 'tu_chat_id'
   ```

5. **Ejecutá el bot:**
   ```bash
   python scriptInversiones.py
   ```

---

## 🐳 Despliegue con Docker (Recomendado para Raspberry Pi)

Si querés que el bot quede corriendo 24/7 en un servidor o Raspberry Pi sin preocuparte por caídas:

1. **Construí la imagen de Docker:**
   ```bash
   docker build -t inversiones-notion .
   ```

2. **Ejecutá el contenedor en segundo plano:**
   ```bash
   docker run -d --restart unless-stopped --name bot_inversiones inversiones-notion
   ```

> El flag `--restart unless-stopped` asegura que el bot vuelva a encenderse solo si se reinicia la Raspberry Pi.

---

## 🛠️ Estructura de la Base de Datos en Notion

Para que el script funcione correctamente, la tabla en Notion debe contener las siguientes propiedades exactas:

| Propiedad | Tipo | Notas |
|---|---|---|
| Activo | Select | Nombre de la inversión (ej. `Bitcoin`, `Frasco NaranjaX`) |
| Fecha | Date | Fecha en la que se realizó la inversión |
| Inversion Inicial (ARS/USDT) | Number | Capital inicial invertido |
| Cantidad Obtenida | Number | Solo para criptomonedas (ej. cantidad de BTC) |
| TNA (%) | Number | Solo para cuentas remuneradas (ej. `45.5`) |

### Soporte SP-500 / CEDEAR SPY

El script permite valuar una posición de SP-500/CEDEAR usando Yahoo Finance como referencia internacional, TradingView como precio local cuando está disponible y DolarAPI como respaldo para el tipo de cambio.

Se adapta a tu tabla actual de Notion, sin agregar propiedades nuevas obligatorias. Usa estas columnas existentes:

| Propiedad | Tipo | Ejemplo | Nota |
|---|---|---|---|
| Activo | Select | `SP-500` o `SPY CEDEAR` | Si contiene `SP-500` o `SPY`, se activa esta lógica |
| Fecha | Date | `2026-04-01` | Fecha de compra |
| Inversion Inicial (ARS/USDT) | Number | `500000` | Monto invertido en pesos |
| Cantidad Obtenida | Number | `10` | Cantidad de CEDEARs comprados |
| TNA (%) | Number | `0` | No se usa para SP-500 |

Campos opcionales que el script también puede leer para mejorar la estimación:

- `Cotizacion de Compra`
- `SPY Compra (USDT)`
- `USDT/ARS Compra`
- `Ratio CEDEAR SPY`

Configuración en el script (sin tocar Notion):

- `SPY_YAHOO_TICKER = 'SPY'`
- `SPY_CEDEAR_RATIO = 1`
- `SPY_LOCAL_SYMBOLS = ['BCBA:SPY', 'BCBA:SPYD', 'BCBA:SPYC']`

Fórmula de valuación estimada en ARS:

- Precio CEDEAR ARS estimado = (Precio SPY en USD / Ratio CEDEAR) * USDTARS
- Valor actual ARS = Cantidad Obtenida * Precio CEDEAR ARS estimado
- % rendimiento = ((Valor actual - Inversion inicial) / Inversion inicial) * 100

Notas:

- Si existe una cotización local del CEDEAR en TradingView, el bot la usa primero.
- Si TradingView no responde, toma la referencia de Yahoo Finance y la convierte a ARS.
- Si falta información suficiente para estimar el rendimiento, el bot no se cae: toma temporalmente el valor actual igual al inicial para esa fila.
