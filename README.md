# 📈 Notion Investment Dashboard

Un script automatizado en Python que extrae el registro de inversiones desde una base de datos de Notion, cruza los datos con cotizaciones en tiempo real y genera un gráfico de rendimiento actualizado. Ideal para automatizar el seguimiento de finanzas personales, calculando tanto rendimientos de interés simple (ej. cuentas remuneradas) como el valor en vivo de criptomonedas, todo unificado en Pesos Argentinos (ARS).

## ✨ Características

* **Integración con Notion API:** Lee dinámicamente tu portafolio directamente desde tu workspace.
* **Cotizaciones en Tiempo Real:**
  * Conexión a la API de Binance para extraer el precio de BTC/USDT.
  * Conexión a DolarAPI para obtener la cotización actual del Dólar Cripto en Argentina.
* **Cálculo de Rendimientos:** Computa automáticamente los intereses generados por días transcurridos según la TNA configurada.
* **Generación de Gráficos:** Utiliza matplotlib para exportar una imagen (.png) con el estado actual del portafolio, total invertido y ganancias netas.

## 🚀 Instalación y Uso

1. **Cloná este repositorio:**

```bash
git clone https://github.com/tingraffi/notion-investment-dashboard.git
cd notion-investment-dashboard
```

2. **Instalá las dependencias necesarias:**

```bash
pip install requests matplotlib
```

3. **Configuración en Notion:**

   - Creá una integración interna en [Notion Developers](https://developers.notion.com/) y obtené tu **Internal Integration Secret**.
   - Compartí tu base de datos de **Inversiones** con la integración que acabás de crear.
   - Copiá el **ID de tu base de datos** (la cadena alfanumérica en la URL).

4. **Configuración del Script:**

   Abrí el archivo principal y reemplazá las variables de entorno con tus credenciales:

```python
NOTION_TOKEN = 'tu_secreto_aqui'
DATABASE_ID = 'tu_id_de_base_de_datos_aqui'
```

5. **Ejecutá el script:**

```bash
python scriptInversiones.py
```

## 🛠️ Estructura de la Base de Datos en Notion

Para que el script funcione correctamente, la tabla en Notion debe contener las siguientes propiedades exactas:

| Propiedad | Tipo |
|---|---|
| Activo | Select |
| Fecha | Date |
| Inversion Inicial (ARS/USDT) | Number |
| Cantidad Obtenida | Number — Para criptomonedas |
| TNA (%) | Number — Para cuentas remuneradas |

TNA (%) (Number) - Para cuentas remuneradas
