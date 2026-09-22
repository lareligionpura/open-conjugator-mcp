# Open Conjugator MCP

MCP de solo lectura e independiente de Reverso para análisis y conjugación verbal. El árabe es la prioridad: usa **CAMeL Tools 1.6.0** como motor y la base abierta **CAMeL Morph MSA v1.0**. Español, inglés y francés se resuelven con instantáneas fijadas de **UniMorph**.

No consulta Reverso, no hace scraping y no necesita red durante una consulta. Los datos se descargan una sola vez durante la preparación o construcción del contenedor, se verifican por SHA-256 y quedan locales.

## Herramientas MCP

| Herramienta | Resultado |
|---|---|
| `conjugate_verb` | Lema, raíz/patrón árabe, voces, modos, tiempos, personas, formas vocalizadas, paradigmas y transliteración Buckwalter opcional. |
| `identify_verb_form` | Todos los análisis compatibles de una forma conjugada; conserva explícitamente la ambigüedad. |
| `search_verb` | Busca lemas, formas flexionadas, árabe vocalizado/sin vocalizar, Buckwalter y erratas pequeñas. |
| `get_verb_models` | Raíces y patrones reales de CAMeL Morph; en UniMorph, haces de rasgos paradigmáticos atestiguados. |
| `get_conjugation_help` | Explicación del esquema instalado y enlaces a la documentación oficial. |
| `get_supported_languages` | Inventario exacto de idiomas, motores y capacidades disponibles localmente. |

Todas las herramientas son idempotentes, no destructivas y devuelven JSON estructurado con `sources`, `sourceUrl`, `retrievedAt` y `provenance`.

## Cobertura

- `ar` / `ara`: árabe estándar moderno, análisis y generación con CAMeL Morph/CAMeL Tools; raíz, patrón, voz activa/pasiva, perfecto, imperfecto, imperativo, modos y Buckwalter.
- `es` / `spa`: español mediante UniMorph.
- `en` / `eng`: inglés mediante UniMorph.
- `fr` / `fra`: francés mediante UniMorph.

También acepta nombres como `árabe`, `Arabic`, `español`, `English` o `français`.

Ejemplo abreviado:

```json
{
  "query": {"original": "يَكْتُبُونَ", "resolved": "يَكْتُبُونَ"},
  "canonicalVerb": "كَتَب",
  "model": {
    "root": "ك.ت.ب",
    "pattern": "1َ2َ3",
    "patternAbstract": "1َ2َ3"
  },
  "candidateLemmas": ["كَتَب", "أَكْتَب"]
}
```

Las ḥarakāt, shadda, sukūn, hamza, alif maqṣūra, tāʾ marbūṭa y el orden RTL se conservan en toda salida. Solo la clave interna de búsqueda puede ignorar diacríticos; nunca se sustituye el texto devuelto.

## Arquitectura

```text
ChatGPT / Work / Codex
          │ Streamable HTTP o STDIO
          ▼
  seis herramientas MCP 2.x
          │
          ├── árabe → CAMeL Tools → CAMeL Morph MSA v1.0 (DB local)
          └── es/en/fr → índice SQLite de verbos UniMorph (local)
```

- El endpoint remoto usa Streamable HTTP sin estado.
- La base UniMorph se indexa por lema y forma; no se carga el corpus completo en memoria.
- El motor árabe se carga de forma perezosa y las consultas repetidas se almacenan en caché LRU.
- No hay cookies, cuentas, credenciales ni llamadas lingüísticas salientes en runtime.
- La concurrencia del analizador/generador se serializa para proteger las estructuras internas de CAMeL Tools.

## Instalación local

Requiere Python 3.11 o superior.

```bash
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -e '.[test]'
.venv/bin/pip install --no-deps -r requirements-morphology.txt
.venv/bin/python scripts/prepare_data.py
```

La instalación deliberadamente ligera evita descargar los modelos de IA de CAMeL Tools que no intervienen en morfología. Solo se instalan el paquete oficial y las dependencias que requieren el analizador, el generador y la transliteración.

### STDIO

```bash
PYTHONPATH=src .venv/bin/python -m open_conjugator_mcp --transport stdio
```

### Streamable HTTP local

```bash
PYTHONPATH=src PORT=3000 MCP_PATH=/api/open-conjugator-mcp \
  .venv/bin/python -m open_conjugator_mcp --transport http
```

- MCP: `http://127.0.0.1:3000/api/open-conjugator-mcp`
- Salud: `http://127.0.0.1:3000/health`

## Pruebas

```bash
PYTHONPATH=src .venv/bin/pytest
```

La batería cubre las siete entradas árabes solicitadas (`كتب`, `كَتَبَ`, `يَكْتُبُونَ`, `قال`, `رأى`, `استمر`, `kataba`), ambigüedad, Unicode, raíces y patrones; además de `hablar`, `write`, `parler`, las seis herramientas mediante un cliente MCP STDIO y una llamada real por Streamable HTTP.

## Contenedor y despliegue

```bash
docker build -t open-conjugator-mcp .
docker run --rm -p 3000:3000 open-conjugator-mcp
```

`render.yaml` describe un servicio Docker sin secretos. En Render puede crearse como Blueprint después de subir este repositorio. La ruta pública final será:

```text
https://SU-SERVICIO.onrender.com/api/open-conjugator-mcp
```

Producción necesita una URL HTTPS estable y accesible. Esta forma sigue la guía oficial de [servidores MCP de OpenAI](https://developers.openai.com/plugins/build/mcp-server), que recomienda Streamable HTTP y probar todas las herramientas con MCP Inspector.

## ChatGPT y ChatGPT Work

1. Abra **Settings → Plugins / Developer mode**; en Work, el administrador debe permitir plugins y herramientas MCP.
2. Pulse `+` en el directorio de plugins, cree una app MCP e introduzca la URL HTTPS completa.
3. Confirme las seis herramientas detectadas y pruebe `identify_verb_form` con `يَكْتُبُونَ`.

ChatGPT web y Work necesitan el endpoint HTTPS; no pueden abrir el proceso STDIO de este ordenador. La arquitectura de plugins compartida por ChatGPT y Codex se describe en la [documentación oficial](https://developers.openai.com/plugins/concepts/plugins).

## Codex

Instalación remota:

```bash
codex mcp add open-conjugator --url https://SU-SERVICIO.onrender.com/api/open-conjugator-mcp
```

Instalación local en este proyecto:

```bash
codex mcp add open-conjugator -- \
  /RUTA/AL/PROYECTO/.venv/bin/python \
  -m open_conjugator_mcp --transport stdio
```

Para STDIO, configure también `PYTHONPATH=/RUTA/AL/PROYECTO/src` si el paquete no se instaló con `pip install -e .`. Codex CLI, la app y la extensión comparten su configuración MCP.

## Procedencia y licencias

- [CAMeL Tools](https://github.com/CAMeL-Lab/camel_tools): MIT.
- [CAMeL Morph](https://github.com/CAMeL-Lab/camel_morph): código MIT; base MSA v1.0 bajo CC BY 4.0.
- [UniMorph](https://unimorph.github.io/): las instantáneas `eng`, `spa` y `fra` usadas aquí son CC BY-SA 3.0.

Los commits y hashes exactos están en `scripts/prepare_data.py`; consulte también `THIRD_PARTY_NOTICES.md`. El código del MCP es MIT. La base SQLite derivada de UniMorph conserva CC BY-SA 3.0.

## Limitaciones

- CAMeL Morph analiza fuera de contexto: una misma grafía puede tener varios lemas o lecturas. El MCP devuelve esa ambigüedad en vez de fingir una única certeza.
- La transliteración aceptada y devuelta para árabe es Buckwalter; `kataba` funciona, pero no se pretende reconocer cualquier convención latina informal.
- CAMeL Morph no etiqueta directamente cada lema con el número tradicional de wazn. Se devuelven raíz, patrón y patrón abstracto reales; no se inventa el número.
- Los participios árabes se modelan como entradas nominales separadas y no se atribuyen automáticamente a un verbo sin evidencia explícita.
- UniMorph ofrece tablas y rasgos, no explicaciones prescriptivas ni nombres de “modelos” como un conjugador pedagógico.
- Solo se empaquetan español, inglés y francés como cobertura secundaria para mantener una imagen remota razonable.

## Solución de problemas

- **Faltan bases de datos**: ejecute `.venv/bin/python scripts/prepare_data.py`.
- **El primer arranque árabe tarda**: la base CAMeL Morph se carga de forma perezosa una vez por proceso.
- **ChatGPT no conecta**: compruebe `/health`, HTTPS público y la ruta exacta `/api/open-conjugator-mcp`.
- **Codex no muestra herramientas**: ejecute `codex mcp list` y reinicie el cliente después de añadir el servidor.
- **Resultado árabe ambiguo**: use los campos `candidateLemmas`, `matches` y `rawFeatures`; es un resultado lingüístico válido, no un fallo.
