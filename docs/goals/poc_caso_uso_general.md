# POC – Definición del caso de uso funcional general

## 1. Propósito general de la POC

Esta POC pretende validar, de extremo a extremo, una pequeña plataforma de datos y analítica territorial capaz de:

- **recibir datos desde varias fuentes**,
- **persistir el dato original en RAW**,
- **transformarlo por capas RAW → STG → MART**,
- **enriquecerlo con información geográfica**,
- **servirlo desde PostGIS para consultas espaciales**,
- **visualizarlo en dashboards**,
- y, en la parte final de la POC, **consultarlo mediante un agente con RAG, memoria relacional y trazabilidad**.

La idea no es construir un producto cerrado, sino una **POC de aprendizaje técnico** que permita practicar una arquitectura moderna, local y reproducible, usando un stack "boring tech" razonable para:

- lakehouse ligero,
- analítica geográfica,
- observabilidad,
- consulta asistida por IA,
- y auditoría de extremo a extremo.

---

## 2. Caso de uso inventado que cubriremos

### 2.1 Escenario funcional

Vamos a simular una plataforma de **monitorización territorial de tráfico urbano** para varias ciudades.

La plataforma recibirá datos de sensores de tráfico distribuidos por distintas zonas geográficas. A partir de ellos, deberá permitir:

- conocer el estado diario del tráfico por ciudad y por zona,
- visualizar sensores y métricas sobre un mapa,
- detectar áreas con mayor congestión,
- agregar indicadores por región,
- habilitar consultas analíticas y geográficas,
- y preparar una evolución hacia un modo conversacional capaz de responder preguntas del tipo:
  - “¿Qué regiones presentan peor congestión hoy?”
  - “¿Qué sensores están dentro de esta zona?”
  - “¿Qué ha ocurrido en Valladolid y cómo se relaciona con otras señales disponibles?”

### 2.2 Visión final del producto POC

El objetivo final no es solo cargar datos y consultarlos en SQL. Queremos llegar a una demo donde exista:

1. un **pipeline reproducible** de datos,
2. una **capa GIS** en PostGIS,
3. un **dashboard ejecutivo**,
4. un **dashboard analista**,
5. un **servicio de consulta** con RAG y tools,
6. una **capa de relaciones/memoria** basada en grafo,
7. y una **trazabilidad técnica completa** mediante auditoría y observabilidad.

---

## 3. Fuentes de datos que utilizaremos en la POC

## 3.1 Fichero de tráfico diario

Recibiremos un fichero con datos agregados de tráfico por sensor y por día.

Formato actual de entrada:

- **PARQUET**

Contenido esperado:

- fecha de tráfico,
- identificador de sensor,
- ciudad,
- número de lecturas,
- total de vehículos,
- velocidad media,
- ocupación media,
- nivel máximo de congestión,
- número de incidentes agregados.

Este fichero representa la base analítica principal de la POC.

---

## 3.2 Fichero de regiones geográficas

Recibiremos otro fichero con la definición de las zonas geográficas sobre las que queremos analizar el tráfico.

Formato propuesto para la POC:

- **CSV** con geometría en **WKT**

Contenido esperado:

- identificador de región,
- nombre de región,
- ciudad,
- tipo de región,
- SRID,
- geometría de polígono.

> En esta POC, este fichero es **sintético/inventado** para poder practicar el flujo geoespacial sin depender todavía de cartografía oficial externa.

---

## 3.3 Fichero de localización de sensores

Recibiremos además un fichero con la localización geográfica de cada sensor.

Formato propuesto para la POC:

- **CSV** con coordenadas y geometría en **WKT**

Contenido esperado:

- identificador de sensor,
- ciudad,
- región asociada,
- longitud,
- latitud,
- SRID,
- geometría de punto.

> Este fichero también es **sintético/inventado** dentro de la POC, porque el dataset de tráfico no trae coordenadas y necesitamos esta pieza para hacer joins espaciales reales.

---

## 3.4 Fuentes adicionales para la parte final de la POC

Para cubrir los días finales, la POC podrá incorporar además datos complementarios, también simulados o simplificados, como por ejemplo:

- resúmenes curados por región y día,
- pequeños documentos descriptivos de indicadores o datasets,
- eventos o posts simulados con texto y localización,
- episodios derivados para poblar el grafo.

Estas fuentes no cambian el caso de uso principal; simplemente amplían la demo para cubrir RAG, agente conversacional y grafo temporal.

---

## 4. Problema funcional que queremos resolver

Con el fichero de tráfico por sí solo podemos calcular métricas tabulares, pero **no** podemos resolver correctamente preguntas geográficas o analíticas más avanzadas porque faltan varias piezas:

- la geometría de las regiones,
- la posición exacta de los sensores,
- una capa curada orientada a consumo,
- una capa servible GIS,
- y una forma amigable de consumo: dashboard y consulta asistida.

Por tanto, el objetivo de la POC es transformar un conjunto de datos inicialmente tabular en un pequeño producto analítico que permita:

1. ubicar cada sensor en el mapa,
2. asociarlo a una región,
3. agregar métricas por región,
4. construir paneles funcionales,
5. consultar la información desde SQL, GIS y chat,
6. y dejar trazabilidad del proceso de principio a fin.

---

## 5. Objetivos de aprendizaje de la POC

La POC está pensada para practicar, de forma incremental, los siguientes objetivos de aprendizaje:

### 5.1 Ingeniería de datos

- diseñar una ingesta por capas,
- conservar la zona RAW como fuente inmutable,
- transformar el dato hacia STG y MART,
- rehacer la capa curada de forma reproducible.

### 5.2 Analítica geoespacial

- trabajar con geometrías en WKT,
- cargar datos en PostGIS,
- realizar joins espaciales,
- preparar datasets aptos para mapas y KPIs.

### 5.3 Visualización y consumo

- exponer un dashboard ejecutivo,
- exponer un dashboard analista,
- diseñar salidas orientadas a consumo y no solo a almacenamiento.

### 5.4 IA aplicada a datos

- construir una pequeña base de conocimiento consultable,
- indexar contenido para RAG,
- combinar SQL, PostGIS y recuperación documental dentro de un agente.

### 5.5 Observabilidad y trazabilidad

- seguir una petición extremo a extremo,
- auditar las respuestas del agente,
- exponer métricas, logs y trazas.

---

## 6. Resultado funcional esperado al final de la POC

Al finalizar la POC, deberíamos poder hacer una demo donde:

1. se cargan ficheros de tráfico y geografía,
2. los ficheros quedan almacenados en RAW,
3. dbt construye una capa STG y MART,
4. PostGIS permite consultas espaciales,
5. Grafana muestra KPIs y mapas,
6. una API consulta el dato curado,
7. el chat responde preguntas usando SQL, RAG y grafo,
8. cada interacción queda auditada y trazada.

En términos de negocio de demo, deberíamos ser capaces de enseñar algo parecido a esto:

- “Aquí recibimos el dato crudo.”
- “Aquí lo transformamos.”
- “Aquí lo vemos en un dashboard.”
- “Aquí hacemos consultas espaciales.”
- “Y aquí preguntamos en lenguaje natural qué está pasando en una región concreta y de dónde sale la respuesta.”

---

## 7. Flujo funcional de extremo a extremo

El comportamiento esperado del sistema, una vez completada la POC, será el siguiente:

1. **Recibir** un fichero PARQUET con datos diarios de tráfico.
2. **Recibir** un CSV con regiones geográficas.
3. **Recibir** un CSV con localización de sensores.
4. **Persistir** todos los originales en la zona **RAW**.
5. **Transformar** y validar la información en una capa **STG**.
6. **Enriquecer** el tráfico con la localización de sensores y con las regiones.
7. **Construir** una capa **MART** orientada a consumo analítico.
8. **Cargar** geometrías en PostGIS.
9. **Publicar** dashboards ejecutivos y analíticos.
10. **Preparar** documentos/resúmenes curados para recuperación semántica.
11. **Poblar** un grafo con entidades, regiones, sensores, eventos o episodios.
12. **Exponer** un agente que combine SQL, GIS, RAG y grafo.
13. **Registrar** auditoría y observabilidad de cada paso y de cada consulta.

---

## 8. Modelo funcional por capas

## 8.1 RAW

La capa RAW almacenará los ficheros originales tal y como llegan.

Ejemplos de activos RAW:

- tráfico diario en PARQUET,
- regiones geográficas en CSV,
- localización de sensores en CSV,
- documentos complementarios o eventos simulados para la parte de IA.

Objetivo de aprendizaje:

- trabajar con una zona **inmutable**,
- conservar la traza de origen,
- permitir reprocesado completo desde la fuente original.

---

## 8.2 STG

La capa STG servirá para limpiar, tipar y validar los datos.

Ejemplos:

- normalización de tipos,
- validación de coordenadas,
- detección de duplicados,
- control del grain,
- validación del SRID y del WKT,
- armonización de campos para consumo posterior.

Objetivo de aprendizaje:

- separar dato crudo de dato confiable,
- introducir controles de calidad mínimos,
- preparar joins y agregaciones de forma reproducible.

---

## 8.3 MART

La capa MART contendrá datasets listos para explotación funcional.

Ejemplos de salidas esperadas:

- tráfico enriquecido con región y geometría de sensor,
- KPIs diarios por región,
- tablas listas para PostGIS,
- resúmenes curados reutilizables para dashboards y RAG.

Objetivo de aprendizaje:

- modelar salidas orientadas a negocio,
- desacoplar la ingesta de la explotación,
- preparar el salto a la capa servible y a la API.

---

## 8.4 Serving / consumo

La capa de serving incluirá:

- **PostGIS** para consultas geográficas,
- **Grafana** para dashboards,
- **API/Agent** para consulta programática y conversacional,
- **Graph store** para relaciones y memoria temporal.

Objetivo de aprendizaje:

- exponer el dato en formatos útiles,
- resolver preguntas reales desde distintos canales,
- no dejar la POC encerrada en tablas técnicas.

---

## 9. Consultas funcionales que queremos habilitar

Con la POC completa queremos ser capaces de responder, como mínimo, a preguntas como estas:

### 9.1 GIS / analítica

- ¿Qué sensores pertenecen a una determinada región?
- ¿Cuál es el total de vehículos por región en una fecha concreta?
- ¿Qué regiones presentan mayor congestión?
- ¿Qué sensores muestran menor velocidad media?
- ¿Cómo se distribuyen espacialmente las métricas de tráfico?

### 9.2 Dashboard / explotación

- ¿Qué ciudades o regiones concentran peor situación de tráfico hoy?
- ¿Cuál es la evolución temporal de la congestión?
- ¿Qué zonas conviene vigilar primero?

### 9.3 Agente / RAG / grafo

- ¿Qué está pasando en esta región?
- ¿Qué datos respaldan esa respuesta?
- ¿Qué entidades o episodios se relacionan con esta zona o este evento?
- ¿De qué tablas, documentos o relaciones sale esta conclusión?