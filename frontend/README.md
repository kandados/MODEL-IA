# Model-IA Desktop

Interfaz local de Model-IA construida con React, TypeScript, Electron y
Three.js.

## Desarrollo

```bash
cd frontend
npm install
npm run dev
```

## Verificación

```bash
npm run typecheck
npm run build
```

## Empaquetado

```bash
npm run package
```

`package` genera la aplicación desempaquetada para el sistema actual.
`npm run dist` generará el instalador configurado para macOS, Windows o Linux.

## Persistencia local

Electron conserva automáticamente un espacio de trabajo independiente de los
archivos del repositorio. Cada proyecto recuerda:

- borrador de la petición;
- historial de conversación;
- referencias adjuntas;
- resultado, validaciones y exportaciones disponibles;
- etapa del pipeline y fecha de la última modificación.

Los adjuntos se seleccionan mediante el diálogo nativo del sistema y se copian
a la carpeta privada de datos de Model-IA. El proceso React nunca recibe rutas
absolutas del ordenador: únicamente identificadores y metadatos seguros a
través del `preload` de Electron. Al pulsar el nombre de un adjunto, Electron
abre la copia guardada con la aplicación predeterminada del sistema.

En macOS, la carpeta se encuentra bajo `~/Library/Application Support/`; en
Windows, bajo `%APPDATA%`; y en Linux, bajo `~/.config`. Electron elige el
subdirectorio exacto de Model-IA en cada plataforma.

## Frontera con el backend

React no importa código Python ni conoce CadQuery. Toda comunicación pasa por
la interfaz `ModelIAClient` situada en:

`src/renderer/src/model-ia-client.ts`

`AdaptiveModelIAClient` comprueba si FastAPI está disponible. Cuando responde,
usa el cliente HTTP/WebSocket real; cuando no responde, activa el simulador y
la interfaz lo indica como `Modo demostración`. La URL predeterminada es:

```text
http://127.0.0.1:8000/api/v1
```

Puede cambiarse en desarrollo mediante `VITE_MODEL_IA_API_URL`.

## Ejecutar la integración real

La API se inicia desde la raíz de Model-IA, con el entorno virtual activo:

```bash
cd ~/Model-IA
source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn src.api:app --reload
```

La comprobación directa del servicio debe devolver un JSON con `status: ok`:

```bash
curl http://127.0.0.1:8000/api/v1/health
```

En una segunda terminal se inicia Electron:

```bash
cd ~/Model-IA/frontend
npm run dev
```

Electron mostrará `Backend conectado`. Cada petición se ejecuta en segundo
plano y FastAPI transmite las fases por WebSocket. Los resultados se guardan
en una carpeta aislada por generación bajo `projects/generated/api/`; esta
carpeta es local y Git no la registra.

## Contrato API v1

### Estado

```http
GET /api/v1/health
```

Debe responder con HTTP 200. El contenido JSON puede incluir información
adicional; el frontend solo necesita el estado HTTP.

### Iniciar una generación

```http
POST /api/v1/generations
Content-Type: application/json
```

```json
{
  "project_id": "mac-mini-case",
  "message": "Diseña una carcasa funcional",
  "attachment_names": [],
  "requested_formats": ["STEP", "STL", "3MF"]
}
```

El backend acepta un trabajo asíncrono y devuelve:

```json
{
  "generation_id": "gen_123",
  "websocket_url": "/api/v1/generations/gen_123/events"
}
```

### Progreso WebSocket

Cada mensaje es JSON. Los eventos de progreso usan uno de los cuatro estados
visuales (`interpret`, `design`, `validate`, `export`):

```json
{
  "type": "progress",
  "stage": "design",
  "stage_index": 1,
  "progress": 0.45,
  "message": "Construyendo el diseño paramétrico"
}
```

También se reconocen estados internos del pipeline como `research`,
`knowledge`, `plan` y `cad`, que el cliente agrupa automáticamente en los
cuatro estados visuales.

El último evento contiene el resultado:

```json
{
  "type": "completed",
  "result": {
    "project_id": "mac-mini-case",
    "status": "completed",
    "specification": {
      "dimensions": {
        "width_mm": 210,
        "depth_mm": 210,
        "height_mm": 52
      },
      "material": "PETG",
      "tolerance_mm": 0.5
    },
    "validations": [
      {
        "id": "closed_geometry",
        "label": "Geometría correcta",
        "status": "passed"
      }
    ],
    "artifacts": [
      {
        "format": "STL",
        "file_name": "enclosure_base.stl + enclosure_lid.stl",
        "available": true,
        "files": [
          {
            "part_id": "base",
            "label": "Base",
            "file_name": "enclosure_base.stl",
            "download_url": "/api/v1/generations/gen_123/files/enclosure_base.stl"
          },
          {
            "part_id": "lid",
            "label": "Tapa",
            "file_name": "enclosure_lid.stl",
            "download_url": "/api/v1/generations/gen_123/files/enclosure_lid.stl"
          }
        ]
      }
    ],
    "preview": {
      "format": "STL",
      "parts": [
        {
          "id": "base",
          "label": "Base",
          "url": "/api/v1/generations/gen_123/files/enclosure_base.stl",
          "assembled_position_mm": [0, 0, 0],
          "exploded_position_mm": [-107.5, 0, 0]
        },
        {
          "id": "lid",
          "label": "Tapa",
          "url": "/api/v1/generations/gen_123/files/enclosure_lid.stl",
          "assembled_position_mm": [0, 0, 31.2],
          "exploded_position_mm": [107.5, 0, 0]
        }
      ]
    }
  }
}
```

El frontend carga los STL de base y tapa como piezas independientes. El botón
de vista explosionada alterna entre su disposición separada y el ensamblaje.
STEP contiene los componentes identificados, STL descarga un archivo por pieza
y 3MF coloca las piezas una al lado de la otra para laminar. FastAPI permite
CORS desde el servidor de desarrollo de Vite (`http://localhost:5173`) y desde
la aplicación Electron.

## Estado actual del frontend

- Ventana Electron con aislamiento de contexto.
- Pantalla principal basada en el mockup aprobado.
- Lista local de proyectos.
- Visor Three.js interactivo.
- Vista normal y explosionada.
- Controles de cámara, rotación y pantalla completa.
- Cliente adaptativo: FastAPI/WebSocket real con simulador de respaldo.
- Carga multipieza de base y tapa en el visor Three.js.
- Vista ensamblada y explosionada también para geometría real.
- STEP ensamblado, STL por pieza y 3MF preparado para impresión.
- Persistencia local de proyectos y borradores entre reinicios.
- Renombrado y eliminación segura de proyectos y sus adjuntos locales.
- Historial de conversación independiente por proyecto.
- Adjuntos locales reales con apertura y eliminación segura.
- Especificaciones, validaciones y formatos de salida.

La transferencia del contenido de los adjuntos a FastAPI sigue pendiente; el
contrato actual envía sus nombres. La API real, el WebSocket, la generación
CadQuery, la vista previa STL y las descargas STEP/STL/3MF ya están conectados.
