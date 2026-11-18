# ECU Recovery Witness — investigación profunda para QNX 8.0, IA y ML

## Hallazgo central

La investigación cambia bastante el proyecto: **ECU Recovery Witness tiene un nicho defendible y no parece ser una copia directa de ningún proyecto abierto que encontré**, pero sí existe un conjunto muy útil de piezas parciales que conviene reutilizar conceptualmente o como referencia. Lo más cercano en automoción es un trabajo de 2025 sobre *transactional logging* para diagnóstico de fallos durante reprogramación OTA: registra la intención antes de una operación riesgosa para poder identificar, tras un reinicio o corte de energía, dónde quedó incompleta. Ese trabajo valida precisamente que el problema de reconstruir qué ocurrió después de una interrupción es real y específicamente automotriz. citeturn388459search0

Sin embargo, ese trabajo no combina, hasta donde pude verificar, **trazas de RTOS + fault injection reproducible + reconstrucción forense + hipótesis abductivas de un LLM + evaluación opcional de ML sobre mecanismos no vistos**. Allí está el espacio propio de Recovery Witness. El proyecto tampoco debería presentarse como un updater OTA: Uptane, MCUboot, RAUC, SWUpdate y Mender ya resuelven diferentes partes del problema de actualización robusta. La diferenciación más sólida sería: **Recovery Witness no instala firmware; investiga y prueba qué estado quedó después de una instalación/configuración interrumpida y qué evidencia permite —o no permite— concluir que la recuperación fue correcta.** citeturn176953search3turn176953search4turn688847search0turn688847search2turn688847search5

AUTOSAR reconoce explícitamente que las actualizaciones pueden ser interrumpibles, que el software anterior debe conservarse durante activación y que, ante errores, puede ser necesario efectuar rollback; también advierte que una actualización distribuida puede obligar a revertir ECUs dependientes. NHTSA, por su parte, señala que la pérdida de energía durante programación es un problema de robustez real y que las actualizaciones remotas exigen que el vehículo quede en un estado recuperable. Esto da una justificación industrial mucho más fuerte que “simulamos una ECU porque QNX se usa en autos”. citeturn388459search9turn388459search10

La tesis técnica que propondría para el hackathon sería:

> **Después de una interrupción, un reinicio exitoso no demuestra una recuperación correcta. Recovery Witness reconstruye qué ocurrió, prueba invariantes del estado persistido y permite a un LLM formular y falsar explicaciones alternativas mediante experimentos reproducibles.**

El LLM puede ser realmente central sin entrar en la decisión de seguridad. Tus propias skills establecen justamente esa separación: abducción antes de deducción, hipótesis falsables, `ABSTAIN` como resultado legítimo, una frontera determinista a partir del artefacto ML congelado y disciplina específica contra leakage, evaluación ilusoria y divergencia training-serving. fileciteturn0file0 El repositorio público describe la misma “machine-learning seam”: entrenamiento potencialmente no determinista → artefacto congelado → inferencia reproducible → decisión determinista. citeturn260870search0

## Ecosistema reutilizable y antecedentes

La siguiente matriz separa deliberadamente **automoción real** de **análogos transferibles**. Esa distinción importa porque un crash-consistency tester de un filesystem puede enseñarnos muchísimo sobre experimentación, pero no constituye evidencia de comportamiento de una ECU.

| Recurso | Dominio real | Qué aporta | Reutilización para Recovery Witness | Limitación principal |
|---|---|---|---|---|
| [Transactional Logging for Failure Diagnostics in Automotive Reprogramming](https://doi.org/10.1109/ICCE-Asia67487.2025.11263639) | Automotriz OTA | Logging transaccional previo a operaciones y reconstrucción post-fallo | **Muy alta como antecedente científico** | No es nuestro sistema QNX/LLM/ML y el acceso al artículo completo puede ser restringido. citeturn388459search0 |
| [Uptane Standard](https://uptane.org/docs/latest/standard/uptane-standard) | Automotriz OTA | Threat model, rollback, freeze, partial bundle, mix-and-match | **Alta para invariantes y casos de falla** | Seguridad de distribución, no diagnóstico forense post-crash. citeturn176953search4 |
| [Aktualizr / Uptane](https://github.com/uptane/aktualizr) | Automotriz OTA | Cliente Uptane real; C++; MPL-2.0 | Referencia de estados/update lifecycle | No QNX; no convertirlo en dependencia sin validar portabilidad. citeturn171520view3 |
| [MCUboot](https://github.com/mcu-tools/mcuboot) | Embedded firmware | Test swap, confirmación, revert, rollback protection | **Excelente modelo de máquina de estados** | Microcontroladores, no ECU/QNX genérica. citeturn176953search3 |
| [RAUC](https://github.com/rauc/rauc) | Embedded Linux | Update atómico/fail-safe, slots, interrupción segura | Casos e invariantes de recuperación | Linux; LGPL, no QNX. citeturn688847search0 |
| [SWUpdate](https://github.com/sbabic/swupdate) | Embedded Linux | Estado `progress/failed`, power-failure, single/double copy | **Muy buen catálogo de fallas** | Linux; GPL-2.0; integración con bootloaders Linux. citeturn688847search2turn688847search4 |
| [Mender](https://github.com/mendersoftware/mender) | Embedded Linux | A/B, rollback tras fallos/reboots espontáneos | Referencia de estados/rollback | Linux; no evidencia de QNX. citeturn688847search5turn688847search6 |
| [CrashMonkey/Ace](https://github.com/utsaslab/crashmonkey) | Filesystems | Exploración exhaustiva acotada de puntos de crash | **Muy alta metodológicamente** | Linux/POSIX FS; no representa flash de ECU. citeturn171520view2turn176953search8 |
| [wal-crash](https://github.com/ahmed-hashim-pro/wal-crash) | Aplicaciones/storage | Materializa estados posibles tras pérdida de energía y usa checker | **Excelente inspiración para el fault injector** | Modelo Linux `strace`/filesystem, no QNX. citeturn695108search5 |
| [Pathfinder](https://github.com/efeslab/Pathfinder) | POSIX/MMIO | Reducción del espacio de crash states, checker externo | Interesante para escalar campañas | Investigación de crash consistency, no automoción. citeturn176953search1 |
| [outagefs](https://github.com/quark-zju/outagefs) | Filesystems | Simulación explícita de power-loss | Conceptos de persistencia y torn writes | FUSE/Linux. citeturn695108search6 |

Un detalle especialmente aprovechable de CrashMonkey es su idea de **bounded black-box crash testing**: no intentar probar infinitas secuencias posibles, sino definir un espacio acotado y explorar sistemáticamente los crash points. En el artículo OSDI, ese enfoque reprodujo 24 de 26 bugs históricos estudiados y encontró otros nuevos en filesystems Linux. No debemos trasladar esas cifras a ECUs, pero el diseño experimental es extraordinariamente pertinente. citeturn176953search8

`wal-crash` es incluso más cercano a lo que imagino para nuestro harness: registra operaciones, genera estados que un corte podría dejar, ejecuta la recuperación sobre cada estado y selecciona una violación mínima. Tiene además un principio muy compatible con `discriminating-proof`: el checker es el oráculo; si el checker es débil, la campaña también lo es. citeturn695108search5

Para la ECU virtual hay varios proyectos, aunque ninguno me convence como base única. [godocan](https://github.com/adpego/godocan) ofrece una ECU UDS configurable con ISO-TP y SocketCAN; [ecu-simulator](https://github.com/lbenthins/ecu-simulator) simula servicios de diagnóstico UDS/ISO-TP; [Xaloqi TestLab](https://github.com/Xaloqi/xaloqi-testlab-core) tiene cliente, simulador y campañas UDS con ISO-TP; [Virtual-ECU-Lab](https://github.com/radhikapatil17/Virtual-ECU-Lab) está escrito en C99 e incluye CAN virtual, fault injection, DTCs y logging. Todos son referencias útiles, pero sus READMEs describen Linux o simulación propia, no QNX 8.0; por tanto no prometo que ninguno compile allí sin trabajo de porting. citeturn270139search4turn270139search5turn270139search6turn270139search7

También encontré [Hardened Diagnostic Gateway](https://github.com/Bennmane27/hardened-diagnostic-gateway), una implementación C con ISO-TP, UDS, ECU virtual y fault injector, y [ecu-test-bench](https://github.com/Oussamabzkr/ecu-test-bench), que incluye pruebas de timing y fallas sobre una ECU virtual. Son buenos repositorios para estudiar cómo otros codifican adversarios y estados UDS, pero conviene evitar que Recovery Witness termine siendo “otro simulador UDS”. citeturn695108search1turn695108search2

## Datos disponibles para ML

La conclusión importante es que **sí existen datos automotrices suficientemente buenos para experimentar con ML, pero prácticamente ninguno etiqueta exactamente “estado de recuperación de firmware después de un power-loss”**. Por eso no recomendaría entrenar un único modelo con datasets públicos y luego afirmar que detecta recuperaciones defectuosas. Los datasets públicos servirían para pre-entrenar/evaluar propiedades más estrechas —anomalías temporales, cambios de estado, fallas intermitentes, generalización entre vehículos— y los datos específicos de recuperación tendrían que salir de nuestras campañas QNX.

Mi shortlist es ésta:

| Dataset | Real / simulado | Etiquetas / formato | Uso de ML razonable | Riesgo |
|---|---|---|---|---|
| [ORNL Multivariate Time Series Intermittent Fault Detection](https://zenodo.org/records/12807317) | Automóvil, fallas introducidas controladamente | CSV; señales a 0,1 s; `Fault_status`; fallas de cable de alimentación y bujía | **Supervisado**, semi-supervisado, detección temporal | Solo dos familias principales; no es firmware recovery. citeturn171520view1 |
| [PATH](https://github.com/lcs-crr/PATH) / [Zenodo](https://doi.org/10.5281/zenodo.13255120) | Powertrain automotriz simulado en Simulink | `.mat`, `pickle`, metadata; train/test limpio o contaminado | **No supervisado, semi-supervisado y auto-supervisado** | Simulador; riesgo de aprender artefactos del modelo. citeturn171520view0 |
| [ROAD](https://zenodo.org/records/10462796) | Vehículo real | Raw CAN + señales traducidas; 556,7 MB; ataques etiquetados | Anomaly detection y robustness | Ataques de seguridad, no fallas de recuperación; un solo vehículo. citeturn555657search1turn555657search2 |
| [CAN-MIRGU](https://github.com/sampathrajapaksha/CAN-MIRGU) | Vehículo real en movimiento | Logs benignos y ataques, metadata | Generalización de anomalías CAN | Seguridad CAN, no recuperación. citeturn555657search4 |
| can-train-and-test | Cuatro vehículos reales | `.log`, CSV etiquetado y sin etiquetar; nueve tipos de ataque | **Muy bueno para cross-vehicle generalization** | Nuevamente IDS, no recovery. citeturn555657search7 |
| [TSB-UAD](https://github.com/TheDatumOrg/TSB-UAD) | Multidominio | 12.686 series en versión original; anomalías etiquetadas | Benchmarks y baselines TSAD | No automotriz; útil sólo como control metodológico. citeturn493678search0 |
| [TSB-AD](https://github.com/TheDatumOrg/TSB-AD) | Multidominio | Colección curada de series y múltiples detectores | Comparación de métricas/modelos | No evidencia de comportamiento ECU. citeturn493678search3 |

El dataset ORNL de fallas intermitentes es probablemente **el mejor primer dataset externo para nuestro propósito**. Tiene señales automotrices multivariadas, timestamps, estados de falla explícitos y fallas físicas introducidas durante adquisición. Una de las campañas desconecta un cable común de alimentación y otra desconecta alimentación de una bujía; las ventanas están anotadas con inicio y fin. Eso se parece bastante más a “un sistema cambia abruptamente por un fallo físico” que un dataset de ataques CAN. citeturn171520view1

PATH es probablemente **el mejor dataset para desarrollar la metodología ML**, no para reclamar realismo físico. Está generado con un modelo de powertrain en Simulink, ofrece secuencias normales, anómalas y controles, además de folds predefinidos, versiones limpias/contaminadas y código reproducible de entrenamiento/evaluación. El repositorio es MIT y el dataset se distribuye también por Zenodo; la generación original requiere MATLAB/Simulink y varios toolboxes, pero los datos ya generados están disponibles. citeturn171520view0

ROAD merece mucha cautela. Es de gran calidad para IDS: más de 3,5 horas de un vehículo real, ataques físicamente verificados, tráfico benigno variado y versiones raw/signal-translated. Pero precisamente por ser un corpus de ataques, sería metodológicamente incorrecto convertir “ataque CAN” en sinónimo de “recuperación inconsistente”. Lo usaría como **prueba de transferencia fuera de distribución**, no como verdad de terreno de Recovery Witness. citeturn555657search1turn555657search2

Para evaluar algoritmos, TSB-UAD y el TSB-AD actualizado son valiosos porque la literatura reciente está señalando que muchos benchmarks de anomalías tienen problemas de trivialidad, etiquetas, densidades irreales y métricas sesgadas. TSB-AD incluso informa que métodos estadísticos o arquitecturas sencillas pueden superar a propuestas más sofisticadas en bastantes configuraciones. Eso refuerza la necesidad de que nuestro baseline no sea “otro neural network”, sino heurísticas y modelos simples capaces de ganarle limpiamente al ML si el ML no aporta. citeturn493678search0turn493678search3

### Qué entrenamiento permitiría cada fuente

**Supervisado:** ORNL intermittent faults, ROAD, CAN-MIRGU y can-train-and-test tienen etiquetas explícitas, aunque sus etiquetas describen fenómenos distintos de recuperación de firmware. Por eso son apropiados para tareas auxiliares bien definidas, no para entrenar directamente un veredicto `RECOVERY_SAFE`. citeturn171520view1turn555657search1turn555657search4turn555657search7

**Auto-supervisado/no supervisado:** PATH ofrece conjuntos nominales limpios y experimentos pensados para anomaly detection; nuestros propios *golden runs* de QNX serían todavía mejores para aprender comportamiento normal específico de Recovery Witness. citeturn171520view0

**Simulación etiquetada:** nuestro fault injector puede producir labels mucho más precisos que “anomalía”: por ejemplo `power_loss_between_write_and_commit`, `torn_payload`, `commit_before_verify`, `stale_confirmation`, `timeout_before_ack`, `reboot_after_persist_before_log`. Ésos deben derivarse de la posición real de la inyección y de invariantes deterministas, no de lo que prediga el modelo. Esta es una propuesta de diseño basada en la metodología de crash testing, no una propiedad de un dataset existente. citeturn176953search8turn695108search5

## QNX 8.0 como parte esencial, no decorativa

QNX nos ofrece una oportunidad muy buena: **el dataset principal puede ser producido por el propio sistema QNX**.

`TraceEvent()` permite iniciar/detener captura, configurar filtros e insertar eventos generados por la aplicación. `tracelogger` captura la instrumentación del kernel y puede funcionar en modo controlado por la aplicación. QNX también proporciona `traceprinter`, que puede convertir el archivo de trazas a una representación que incluya cycle count, CPU, event ID, timestamp, clase y subtipo. citeturn270139search0turn270139search1turn959016search7

Más importante todavía: QNX tiene una **clase de eventos de usuario**. Podemos insertar, por ejemplo:

```text
UPDATE_BEGIN
BLOCK_ERASE_BEGIN
BLOCK_ERASE_END
WRITE_BEGIN(block=17)
WRITE_END(block=17)
VERIFY_BEGIN
VERIFY_OK
COMMIT_BEGIN
COMMIT_PERSISTED
REBOOT_REQUESTED
BOOT_RECOVERY_BEGIN
STATE_RECONSTRUCTED
```

y correlacionarlos con scheduler activity, message passing, thread transitions e interrupts del kernel. QNX documenta precisamente que el kernel trace contiene eventos de procesos/hilos, context switches, message passing, señales e interrupciones, y permite insertar eventos propios mediante `TraceEvent()`. citeturn959016search5turn959016search6turn959016search8

Esto convierte las trazas QNX en algo mucho más interesante que un log textual: podemos tener **dos planos de evidencia independientes**:

```text
ECU application evidence
    ↕ correlation ID
QNX kernel trace evidence
```

Eso casa directamente con `incident-timeline-reconstruction`: cada fuente debe conservar su dominio de reloj, distinguir evento observado de evento inferido y no convertir mera adyacencia en causalidad. La skill insiste además en tratar un log que desaparece como un evento potencialmente informativo, no como “no ocurrió nada”. citeturn260870search2

QNX también dispone de su filesystem Power-Safe, basado en copy-on-write y snapshots consistentes; `fsync()` puede provocar snapshots y, tras power failure, se restaura el último snapshot. QNX advierte además que el filesystem no conoce automáticamente la atomicidad semántica de una operación de aplicación de alto nivel. Eso es perfecto para mostrar una idea crucial: **consistencia del filesystem ≠ consistencia de la operación ECU**. citeturn959016search10turn959016search11

De hecho, eso podría convertirse en uno de los experimentos estrella:

```text
Filesystem: consistente
Firmware file: íntegro
Log: dice "write finished"
ECU transaction invariant: VIOLATED
```

El storage puede haber sobrevivido perfectamente y, aun así, la transición lógica ser incorrecta.

Para comunicación entre componentes, QNX ofrece `MsgSend/MsgReceive/MsgReply` y pulses no bloqueantes. Esto permitiría separar simulador ECU, injector, witness y trace controller en procesos independientes sin inventar un bus de mensajes casero. citeturn959016search0turn959016search1

## El LLM como investigador abductivo

Aquí sí veo una aplicación del LLM que no es ornamental.

La OpenAI Responses API soporta function calling y salidas estructuradas con JSON Schema. Eso permite que el modelo no “hable libremente” con el entorno, sino que emita objetos tipados como hipótesis y solicitudes de experimento. La documentación oficial deja claro que las herramientas se conectan mediante function calling y que Structured Outputs obliga a respetar un esquema, aunque la aplicación todavía debe validar reglas semánticas propias. citeturn576278search0turn576278search2turn576278search3

Yo modelaría el ciclo así:

```text
OBSERVACIÓN
      ↓
LLM genera hipótesis rivales
      ↓
cada hipótesis incluye predicción falsable
      ↓
LLM selecciona una prueba permitida
      ↓
harness determinista ejecuta la prueba
      ↓
evidencia nueva + invariantes
      ↓
hipótesis REFUTADA / SOPORTADA / INDETERMINADA
      ↓
LLM revisa el conjunto de hipótesis
```

Las herramientas del modelo serían de **investigación**, no de autoridad: `get_trace_window`, `get_persistent_state`, `compare_snapshots`, `list_invariants`, `run_fault_scenario`, `replay_scenario`, `query_ml_anomaly_score`, `request_control_run`. La aplicación define qué parámetros son válidos y ejecuta cada operación. La API soporta este patrón explícitamente mediante function calling. citeturn576278search1turn576278search3

Hay trabajos recientes que respaldan esa dirección. **DoVer** critica el debugging basado sólo en logs y agrega intervenciones dirigidas para verificar activamente las hipótesis; reporta que puede validar o refutar entre 30% y 60% de sus hipótesis en sus benchmarks. **AgentDebugX** estructura debugging como Detect → Attribute → Recover → Rerun y muestra que la localización de causa en trayectorias largas sigue siendo difícil: incluso su mejor resultado citado en el benchmark Who-and-When es 28,8% de atribución estricta exacta para agente+paso. Eso es una advertencia útil: un LLM puede investigar, pero no debemos tratar su explicación como evidencia. citeturn576278academia7turn576278academia8

Un preprint de noviembre de 2026 sobre agentes depurando incidentes de bases de datos llega a una observación particularmente pertinente: en incidentes de concurrencia, las hipótesis erróneas frecuentemente eran compatibles con la evidencia visible porque al agente le faltaba acceso a datos runtime discriminantes. Es un solo estudio de campo y no deberíamos generalizarlo demasiado, pero refuerza exactamente nuestro diseño: **la calidad del razonamiento depende de darle al agente observaciones que puedan matar hipótesis, no de pedirle que “razone mejor” sobre logs incompletos.** citeturn576278academia10

La contribución científica del LLM podría medirse. No preguntaría “¿diagnosticó bien?”. Mediría:

- fracción de hipótesis refutables que formula;
- número de experimentos hasta discriminar la causa;
- información ganada por experimento;
- tasa de conclusiones prematuras;
- tasa de abstención correcta;
- capacidad para reconsiderar una hipótesis tras evidencia contraria;
- desempeño ante una causa que no aparece en ejemplos o prompt.

Eso convertiría a la IA en objeto de evaluación, no en truco de demo.

## Diseño del ML y cómo evitar engañarnos

Mi recomendación después de revisar los datasets es **sí construir la vía ML, pero hacer que pueda perder**. No la convertiría en requisito para que Recovery Witness sea exitoso.

La pregunta experimental correcta sería:

> **¿Un detector aprendido descubre estados o secuencias de recuperación anómalas que un conjunto razonable de invariantes y heurísticas no detecta, especialmente cuando el mecanismo de falla no apareció durante entrenamiento?**

Si la respuesta es no, el resultado sigue siendo útil: ML no agrega valor para esa frontera.

Tu set de skills es especialmente apropiado aquí. `data-leakage-hunting` advierte que la fuga puede aparecer por tiempo, grupos, duplicados o preprocessing; `training-run-provenance` exige preservar artefacto y manifest; `model-evaluation-discipline` exige baseline, intervalos, worst slice y controles negativos; `training-serving-parity` obliga a demostrar que la representación usada durante entrenamiento es realmente la servida en inferencia. fileciteturn0file0

### Splits que usaría

**Nunca un split aleatorio por ventanas.** Si tomamos una misma ejecución larga, la cortamos en ventanas y distribuimos ventanas al azar entre train y test, las ventanas vecinas pueden ser casi duplicados temporales. El modelo “generalizaría” sólo porque vio el mismo episodio. Este problema es especialmente relevante en time series y el trabajo ORNL de Hespeler et al. está dedicado precisamente al impacto de la validación temporal en detección de anomalías CAN. citeturn555657search0

Propondría cuatro niveles de evaluación:

| Split | Qué prueba |
|---|---|
| **por ejecución** | misma familia de falla, nueva corrida |
| **por semilla/configuración** | nueva realización y parámetros |
| **por dispositivo/ECU virtual** | cambios estructurales del sistema |
| **por mecanismo de falla** | la prueba fuerte: mecanismo totalmente no visto |

La cuarta debe ser el resultado principal. Por ejemplo, entrenar con reboot-before-commit, write truncation y timeout, pero reservar completamente `ack-before-persist` para test.

### Baselines obligatorios

No compararía un Transformer sólo contra otro Transformer. Usaría:

**Baseline determinista:** violaciones de invariantes explícitos.

**Baseline estadístico:** z-score robusto/EWMA sobre latencia, duración y conteos.

**Isolation Forest u OCSVM:** modelo tradicional.

**Matrix Profile o detector subsecuencial:** baseline temporal.

**Autoencoder/TCN pequeño:** primer modelo neural.

Sólo después probaría algo más complejo. TSB-UAD incluye baselines estadísticos, Isolation Forest, LOF, OCSVM, Matrix Profile, PCA, autoencoders, LSTM, CNN y otros, por lo que tenemos implementaciones y metodología externa para comparar familias sin inventar una carrera neural. citeturn493678search0

### Métricas

No usaría accuracy como métrica principal. Con anomalías raras puede ser magnífica aunque el modelo no encuentre ninguna.

Reportaría:

```text
precision
recall
F1 / Fβ según coste definido
PR-AUC
false positives por hora / por recovery
false negatives por mecanismo de falla
detection latency
abstention rate
coverage conditional on abstention
worst-mechanism recall
```

Para detección temporal también evaluaría métricas sensibles al rango, y usaría TSB-AD como referencia metodológica porque el benchmark fue creado en parte por problemas conocidos de métricas TSAD y usa VUS-PR en su leaderboard actual. citeturn493678search3

### Abstención

El ML no produciría `SAFE/UNSAFE`.

Produciría algo como:

```json
{
  "score": 0.91,
  "threshold_version": "v3",
  "calibration_group": "ecu_B",
  "decision": "ANOMALOUS",
  "coverage": "in_distribution"
}
```

o:

```json
{
  "decision": "ABSTAIN",
  "reason": "OUT_OF_DISTRIBUTION"
}
```

El veredicto forense seguiría dependiendo de evidencia e invariantes.

### Procedencia

Cada entrenamiento debería sellar al menos:

```text
dataset hashes
source URLs / DOI
license
capture IDs
split manifest
feature extractor version/hash
normalization parameters
model code commit
environment lockfile
seed(s)
known nondeterminism
model artifact hash
threshold-calibration data
evaluation manifest
```

Eso implementa directamente `training-run-provenance`; el claim de reproducibilidad debe corresponder a lo efectivamente reproducido, no a que “pusimos seed=42”. fileciteturn0file0

### Training-serving parity

Ésta puede ser una trampa concreta en nuestro proyecto.

Si entrenamos a partir de:

```text
traceprinter → parser Python → resample → normalize
```

pero durante la demo servimos:

```text
QNX trace → parser C distinto → normalize diferente
```

tenemos dos implementaciones de la misma feature y ninguna garantía de equivalencia. La solución es serializar un formato canónico intermedio o usar exactamente el mismo transformador en entrenamiento e inferencia y mantener fixtures byte-a-byte. La necesidad metodológica está expresamente contemplada en `training-serving-parity`. fileciteturn0file0

## Arquitectura y plan experimental recomendado

La arquitectura que emerge de la investigación es bastante clara:

```text
                    QNX 8.0 / QEMU
┌──────────────────────────────────────────────────────┐
│                                                      │
│   Virtual ECU        Fault Injector                  │
│       │                   │                          │
│       ├──── state machine ┤                          │
│       │                   ↓                          │
│       │             crash / reboot / torn write      │
│       │                                              │
│       ├── application evidence                       │
│       └── TraceEvent user markers                    │
│                        │                             │
│                QNX kernel tracing                    │
│                        │                             │
│                 Recovery Witness                     │
│           deterministic reconstruction               │
│           + invariant evaluation                     │
└────────────────────────┬─────────────────────────────┘
                         │
                  evidence bundle
                         │
              ┌──────────┴──────────┐
              │                     │
         ML detector          OpenAI LLM
        anomaly score      hypotheses/tests
              │                     │
              └────── evidence ─────┘
                         │
                 Experiment Harness
```

QNX no es incidental en este diseño: aporta scheduler/kernel traces, user trace events, IPC real-time, filesystem semantics concretas y el entorno donde ocurren las interrupciones. citeturn959016search0turn959016search5turn959016search8turn959016search10

El **estado de verdad** lo diseñaría como máquina de estados explícita:

```text
IDLE
PREPARED
ERASING
WRITING
VERIFYING
COMMITTING
COMMITTED
RECOVERING
RECOVERED
INDETERMINATE
```

Y ejemplos iniciales de invariantes:

```text
I1: COMMITTED ⇒ payload_hash == expected_hash
I2: COMMITTED ⇒ verification_completed_before_commit
I3: ACK_SUCCESS ⇒ durable_commit_evidence exists
I4: recovery may never manufacture COMMITTED from PREPARED
I5: active_image ∈ {old_verified, new_verified}
I6: generation counter never decreases except explicit authorized rollback
I7: after reboot, state reconstruction must be derivable from persisted evidence
```

Esos invariantes no son “la especificación automotriz universal”; serían la especificación de **nuestra ECU simulada**. Esa honestidad es importante.

La campaña de faults debería incluir, al menos: reboot antes/después de cada transición, corte entre persistencia de payload y metadata, escritura parcial, confirmation antes de durability, trace/log ausente, timeout, reorder de mensajes, replay de confirmación antigua, estado válido pero evidencia insuficiente y corrupción de evidencia. El diseño está inspirado en los mecanismos documentados por Uptane, MCUboot, SWUpdate y la literatura de crash consistency, pero la implementación y los labels serían propios. citeturn176953search3turn176953search4turn688847search4turn176953search8

`discriminating-proof` encaja literalmente con el harness: predicción previa, experimento mínimo que pueda matar la hipótesis, control negativo en la misma corrida y un oráculo binario fuerte. citeturn260870search3 `invariant-hunting` aporta la pregunta correcta —qué propiedad establecida antes de la transición debe seguir siendo cierta después— y `incident-timeline-reconstruction` impide que mezclemos timestamps QNX, timestamps del simulador y tiempos derivados como si fueran una única verdad cronológica. fileciteturn0file0

### Experimento ML decisivo

Yo fijaría desde el principio este experimento como condición para que ML “se gane” un lugar:

```text
TRAIN
normal
+ reboot-before-write
+ torn-write
+ verify-failure
+ timeout

VALIDATE
nuevas ejecuciones de esas familias

TEST-A
nueva ECU/configuración

TEST-B (sealed)
ack-before-durable-commit
stale-confirmation-after-reboot
out-of-order persistence
```

El set `TEST-B` no se mira durante model selection. Si después de iterar sobre él cambiamos el modelo, deja de ser test y se convierte en desarrollo; necesitamos un nuevo holdout. Eso es exactamente el tipo de “spent test set” que `data-leakage-hunting` pretende hacer visible. fileciteturn0file0

Además pondría **negativos difíciles**: reinicios perfectamente sanos, latencias altas pero permitidas, pérdida de logs donde otra evidencia sí alcanza, rollback legítimo y cargas CPU intensas sin corrupción. El modelo debe demostrar que no confunde “inusual” con “incorrecto”.

### Qué haría con datasets externos

No mezclaría todos los datasets en un monstruo de entrenamiento.

**ORNL intermittent faults:** dataset auxiliar para estudiar detección de cambios multivariados físicos y temporal validation. citeturn171520view1

**PATH:** sandbox metodológico para comparar modelos y practicar contamination/clean splits antes de tener suficientes datos QNX. citeturn171520view0

**ROAD / CAN-MIRGU / can-train-and-test:** pruebas de transferencia y falsos positivos sobre anomalías automotrices que **no** son recovery faults. Un buen modelo de Recovery Witness debería poder decir “esto es raro, pero no tengo evidencia de una recuperación inconsistente”. citeturn555657search1turn555657search4turn555657search7

**TSB-UAD/TSB-AD:** baselines y auditoría de metodología, no entrenamiento del modelo final. citeturn493678search0turn493678search3

## Recomendación final y gap de investigación

Mi recomendación es **construir ML, pero no diseñar Recovery Witness alrededor de que el ML necesariamente funcione**.

El proyecto ya tiene una contribución fuerte sin ML: QNX produce evidencia real de runtime; una ECU simulada atraviesa transiciones de firmware/configuración; el harness inyecta fallas reproducibles; el witness reconstruye estados y verifica invariantes; y el LLM actúa como investigador abductivo que propone explicaciones rivales y experimentos discriminantes. Todo eso está sólidamente conectado con problemas documentados de OTA automotriz y con capacidades específicas de QNX. citeturn388459search9turn388459search10turn959016search5turn959016search8

ML puede convertirse en **la pregunta experimental adicional**:

> ¿Puede un detector aprendido señalar una recuperación problemática antes de que una regla explícita la reconozca, y conservar esa ventaja ante mecanismos de falla no vistos?

La literatura actual no me permite afirmar de antemano que sí. De hecho, los benchmarks modernos de anomaly detection contienen suficientes advertencias sobre splits, datasets y métricas como para considerar perfectamente posible que una buena heurística gane. citeturn493678search0turn493678search3

Eso, paradójicamente, haría el proyecto más serio. Si Isolation Forest o una regla de transición gana, lo publicamos. Si un autoencoder o modelo temporal encuentra señales nuevas, demostramos cuáles y bajo qué split. Si ninguno generaliza a mecanismos no vistos, también lo mostramos. El proyecto no necesita que una red neuronal “quede linda” para tener IA: **el LLM ya tiene un papel central, evaluable y no cosmético.**

El gap que encontré puede expresarse con bastante precisión: hay trabajos sobre **actualización robusta y rollback automotriz**, trabajos sobre **diagnóstico transaccional de reprogramación**, herramientas de **crash-consistency/fault injection**, datasets de **anomalías y fallas CAN**, y trabajos recientes sobre **LLMs que depuran mediante hipótesis e intervenciones**; lo que no encontré es una plataforma abierta que una esas líneas en un entorno RTOS automotriz y trate la recuperación como un problema forense basado en evidencia, con un agente abductivo y una evaluación explícita de ML bajo fallas no vistas. citeturn388459search0turn176953search8turn171520view1turn576278academia7

Para un hackathon, además, tiene una demo extraordinariamente comprimible: ejecución sana → corte en punto crítico → reboot → evidencia contradictoria → LLM formula dos hipótesis → selecciona un experimento → una se refuta → witness conserva `INDETERMINATE` o emite un resultado respaldado por invariantes. **La IA hace algo visible, QNX hace algo visible y la ingeniería de recuperación hace algo visible en menos de tres minutos.**

Y, a diferencia de meter un chatbot en una ECU porque “el track pide innovación”, acá el LLM realmente tiene un trabajo que los mecanismos deterministas no hacen: **decidir qué pregunta conviene hacer a continuación cuando todavía no sabemos qué ocurrió.**