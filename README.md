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
  - Conexión a DolarAPI para obtener la cotización actual del Dólar Cripto en Argentina.
- **🧮 Cálculo de Rendimientos:** Computa automáticamente los intereses generados por días transcurridos según la TNA configurada.
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

### Soporte SP-500 (CEDEAR SPY) sin API de IOL

El script ahora permite valuar una posicion de SP-500/CEDEAR usando Binance como fuente de referencia y calcular ganancia/perdida en ARS.

Se adapta a tu tabla actual de Notion, sin agregar propiedades nuevas. Solo usa estas columnas existentes:

| Propiedad | Tipo | Ejemplo | Nota |
|---|---|---|---|
| Activo | Select | `SP-500` o `SPY CEDEAR` | Si contiene `SP-500` o `SPY`, se activa esta logica |
| Fecha | Date | `2026-04-01` | Fecha de compra |
| Inversion Inicial (ARS/USDT) | Number | `500000` | Monto invertido en pesos |
| Cantidad Obtenida | Number | `10` | Cantidad de CEDEARs comprados |
| TNA (%) | Number | `0` | No se usa para SP-500 |

Configuracion en el script (sin tocar Notion):

- `SPY_BINANCE_SYMBOL = 'SPYUSDT'`
- `SPY_CEDEAR_RATIO = 1`

Formula de valuacion estimada en ARS:

- Precio Cedear ARS estimado = (Precio Binance en USDT / Ratio CEDEAR) * USDTARS
- Valor actual ARS = Cantidad Obtenida * Precio Cedear ARS estimado
- % rendimiento = ((Valor actual - Inversion inicial) / Inversion inicial) * 100

Notas:

- El tipo de cambio se intenta obtener con `USDTARS` en Binance. Si no esta disponible en tu region, usa DolarAPI como respaldo.
- Si el simbolo configurado no existe en Binance, el bot no se cae: toma temporalmente el valor actual igual al inicial para esa fila.
